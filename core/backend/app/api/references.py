"""Xodim ish joyi ma'lumotnomalari: PDF, vazifalar va ochiq QR tekshiruvi."""

import secrets
from datetime import UTC

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _base_url
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch, Department, Position
from app.models.references import EmploymentReference
from app.services import references as svc
from app.services.audit import audit, client_ip
from app.timeutil import now

router = APIRouter(prefix="/v1/references", tags=["references"])
public_router = APIRouter(prefix="/v1/public", tags=["public"])


class IssueIn(BaseModel):
    employee_id: int


def _need_manage(auth: AuthContext) -> None:
    if not svc.has_permission(auth, "staffdocs.manage"):
        raise error(403, "forbidden")


def _out(doc: EmploymentReference) -> dict:
    return {"id": doc.id, "number": doc.number, "employee": doc.snapshot.get("employee_name"),
            "position": doc.snapshot.get("position"), "department": doc.snapshot.get("department"),
            "status": doc.status, "issued_at": doc.issued_at, "has_pdf": True}


@router.get("")
async def list_references(q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    stmt = select(EmploymentReference).order_by(EmploymentReference.issued_at.desc()).limit(200)
    if q and q.strip():
        needle = q.strip().casefold()
        rows = (await db.scalars(stmt)).all()
        docs = [d for d in rows if needle in str(d.snapshot.get("employee_name", "")).casefold() or needle in d.number.casefold()]
    else:
        docs = (await db.scalars(stmt)).all()
    return {"items": [_out(d) for d in docs]}


@router.post("", status_code=201)
async def issue_reference(body: IssueIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    emp = await db.get(Employee, body.employee_id)
    if not emp or emp.status != "active":
        raise error(404, "employee_not_found")
    position = await db.get(Position, emp.position_id) if emp.position_id else None
    department = await db.get(Department, emp.department_id) if emp.department_id else None
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    issuer = await db.get(User, auth.user.id)
    cfg = getattr(request.app.state, "client_config", None)
    brand = getattr(cfg, "brand", {}) or {}
    issued_at = now()
    snapshot = {
        "company": brand.get("name") or "HR-Profi",
        "company_subtitle": brand.get("tagline") or brand.get("subtitle") or brand.get("legal_name") or "",
        "employee_name": emp.full_name,
        "position": position.name if position else None,
        "department": department.name if department else None,
        "branch": branch.name if branch else None,
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
        "duties": list(position.duties or []) if position else [],
        "issued_by": issuer.full_name if issuer else None,
        "issued_at": issued_at.astimezone(UTC).isoformat(),
    }
    doc = EmploymentReference(
        number=f"MR-{issued_at.astimezone(UTC).year}-{secrets.token_hex(3).upper()}",
        code=secrets.token_urlsafe(18), employee_id=emp.id, snapshot=snapshot,
        content_hash=svc.digest(snapshot), status="issued", issued_by=auth.user.id, issued_at=issued_at,
    )
    db.add(doc)
    await db.flush()
    await audit(db, request, "reference.issue", actor=auth.user, entity="employment_reference", entity_id=doc.id,
                data={"employee_id": emp.id, "number": doc.number})
    await db.commit()
    return {**_out(doc), "verify_url": f"{_base_url(request)}/verify/reference/{doc.code}"}


@router.get("/{doc_id}")
async def get_reference(doc_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await db.get(EmploymentReference, doc_id)
    if not doc:
        raise error(404, "not_found")
    return {**_out(doc), "duties": doc.snapshot.get("duties", []), "verify_code": doc.code}


@router.get("/{doc_id}/pdf")
async def reference_pdf(doc_id: int, request: Request, lang: str = Query(default="uz", pattern="^(uz|ru)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await db.get(EmploymentReference, doc_id)
    if not doc:
        raise error(404, "not_found")
    url = f"{_base_url(request)}/verify/reference/{doc.code}"
    pdf = svc.build_pdf(doc, url, lang)
    await audit(db, request, "reference.pdf", actor=auth.user, entity="employment_reference", entity_id=doc.id)
    await db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{doc.number}.pdf"'})


@router.post("/{doc_id}/cancel")
async def cancel_reference(doc_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await db.get(EmploymentReference, doc_id)
    if not doc:
        raise error(404, "not_found")
    if doc.status != "cancelled":
        doc.status = "cancelled"
        await audit(db, request, "reference.cancel", actor=auth.user, entity="employment_reference", entity_id=doc.id)
        await db.commit()
    return _out(doc)


@public_router.get("/reference/{code}")
async def verify_reference(code: str, request: Request, hash: str | None = Query(default=None, max_length=64), db: AsyncSession = Depends(get_session)):
    redis = request.app.state.redis
    key = f"rl:verify-reference:{client_ip(request)}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, 60)
    if n > 60:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(key), 1))
    doc = await db.scalar(select(EmploymentReference).where(EmploymentReference.code == code[:40]))
    if not doc:
        raise error(404, "not_found")
    return svc.public_view(doc, hash)
