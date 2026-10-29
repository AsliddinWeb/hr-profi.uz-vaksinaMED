"""Xodim elektron hujjatlari: ariza va buyruq (raqam, QR, PDF, ochiq tekshiruv) hamda xodim kartochkasi uchun yig'ma lenta."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _base_url
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.hrdocs import StaffDocument
from app.models.letters import ExplanationLetter
from app.models.penalties import Penalty
from app.security import verify_password
from app.services import staffdocs as svc
from app.services.answers import users_with_permission
from app.services.audit import audit, client_ip
from app.services.notifications import deliver, notify
from app.timeutil import now

router = APIRouter(prefix="/v1/staffdocs", tags=["staffdocs"])
public_router = APIRouter(prefix="/v1/public", tags=["public"])
PW_FAILS, PW_WINDOW = 5, 600


class ApplicationIn(BaseModel):
    subtype: str = Field(pattern=f"^({'|'.join(svc.APP_TYPES)})$")
    body: str = Field(min_length=3, max_length=5000)
    start_date: date | None = None
    end_date: date | None = None


class OrderIn(BaseModel):
    employee_id: int
    subtype: str = Field(pattern=f"^({'|'.join(svc.ORDER_TYPES)})$")
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=8000)
    start_date: date | None = None
    end_date: date | None = None
    related_id: int | None = None


class OrderUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=8000)
    start_date: date | None = None
    end_date: date | None = None


class DecideIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)


class SignIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


def _sees_all(auth: AuthContext) -> bool:
    return svc.has(auth, "staffdocs.read") or svc.has(auth, "staffdocs.manage")


async def _emp(db: AsyncSession, emp_id: int) -> Employee:
    e = await db.get(Employee, emp_id)
    if not e:
        raise error(404, "not_found")
    return e


async def _my_emp(db: AsyncSession, auth: AuthContext) -> Employee | None:
    return await db.scalar(select(Employee).where(Employee.user_id == auth.user.id, Employee.status == "active"))


async def _load(db: AsyncSession, did: int, auth: AuthContext, *, lock: bool = False) -> tuple[StaffDocument, Employee]:
    stmt = select(StaffDocument).where(StaffDocument.id == did)
    doc = await db.scalar(stmt.with_for_update() if lock else stmt)
    emp = await db.get(Employee, doc.employee_id) if doc else None
    if not doc or not emp or not (_sees_all(auth) or emp.user_id == auth.user.id):
        raise error(404, "not_found")
    if doc.kind == "order" and doc.status == "draft" and not _sees_all(auth):
        raise error(404, "not_found")  # qoralama buyruqni xodim ko'rmaydi
    return doc, emp


def _out(doc: StaffDocument, emp: Employee, names: dict[int, str], auth: AuthContext) -> dict[str, Any]:
    mine = emp.user_id == auth.user.id
    manage = svc.has(auth, "staffdocs.manage")
    return {
        "id": doc.id, "kind": doc.kind, "subtype": doc.subtype, "number": doc.number, "title": doc.title, "body": doc.body, "status": doc.status,
        "employee": {"id": emp.id, "name": emp.full_name}, "start_date": doc.start_date, "end_date": doc.end_date, "related_id": doc.related_id,
        "created_by": names.get(doc.created_by or 0), "decided_by": names.get(doc.decided_by or 0), "decided_at": doc.decided_at, "decision_note": doc.decision_note,
        "signed_by": names.get(doc.signed_by or 0), "signed_at": doc.signed_at, "acknowledged_at": doc.acknowledged_at, "created_at": doc.created_at, "has_pdf": bool(doc.number),
        "can": {
            "decide": manage and doc.kind == "application" and doc.status == "submitted", "edit": manage and doc.kind == "order" and doc.status == "draft",
            "sign": svc.has(auth, "staffdocs.sign") and doc.kind == "order" and doc.status == "draft", "ack": mine and doc.kind == "order" and doc.status == "issued" and doc.acknowledged_at is None,
            "cancel": (doc.kind == "application" and doc.status == "submitted" and (mine or manage)) or (manage and doc.kind == "order" and doc.status in ("draft", "issued")),
            "make_order": manage and doc.kind == "application" and doc.status == "approved",
        },
    }  # fmt: skip


async def _names(db: AsyncSession, docs: list[StaffDocument]) -> dict[int, str]:
    ids = {u for d in docs for u in (d.created_by, d.decided_by, d.signed_by) if u}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}


@router.get("")
async def list_docs(
    kind: str | None = Query(default=None, pattern="^(application|order)$"),
    status: str | None = None,
    employee_id: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    stmt = select(StaffDocument, Employee).join(Employee, Employee.id == StaffDocument.employee_id)
    if not _sees_all(auth):
        if not svc.has(auth, "staffdocs.apply"):
            raise error(403, "forbidden")
        stmt = stmt.where(Employee.user_id == auth.user.id, or_(StaffDocument.kind == "application", StaffDocument.status != "draft"))
    if kind:
        stmt = stmt.where(StaffDocument.kind == kind)
    if status:
        stmt = stmt.where(StaffDocument.status == status)
    if employee_id:
        stmt = stmt.where(StaffDocument.employee_id == employee_id)
    if q and q.strip():
        stmt = stmt.where(or_(Employee.full_name.ilike(f"%{q.strip()}%"), StaffDocument.number.ilike(f"%{q.strip()}%"), StaffDocument.title.ilike(f"%{q.strip()}%")))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.order_by(StaffDocument.id.desc()).offset((page - 1) * size).limit(size))).all()
    names = await _names(db, [d for d, _ in rows])
    pending = 0
    if svc.has(auth, "staffdocs.manage"):
        pending = await db.scalar(select(func.count()).select_from(StaffDocument).where(StaffDocument.kind == "application", StaffDocument.status == "submitted")) or 0
    return {"total": total or 0, "page": page, "size": size, "pending_applications": pending, "items": [_out(d, e, names, auth) for d, e in rows]}


@router.get("/employee/{employee_id}/feed")
async def employee_feed(employee_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Xodim kartochkasi uchun yig'ma lenta: tushuntirish xatlari, jarimalar, arizalar va buyruqlar."""
    if not (_sees_all(auth) or svc.has(auth, "employees.documents") or svc.has(auth, "letters.read") or svc.has(auth, "penalties.read")):
        raise error(403, "forbidden")
    emp = await _emp(db, employee_id)
    out: list[dict[str, Any]] = []
    if _sees_all(auth) or svc.has(auth, "employees.documents"):
        for d in (await db.scalars(select(StaffDocument).where(StaffDocument.employee_id == employee_id))).all():
            out.append({"type": d.kind, "id": d.id, "number": d.number, "title": d.title, "date": d.created_at, "status": d.status, "link": f"/hr/documents/{d.id}"})
    if svc.has(auth, "letters.read") or svc.has(auth, "employees.documents") or _sees_all(auth):
        for lt in (await db.scalars(select(ExplanationLetter).where(ExplanationLetter.employee_id == employee_id))).all():
            out.append({"type": "letter", "id": lt.id, "number": lt.number, "title": f"Tushuntirish xati ({lt.incident_type})", "date": lt.created_at, "status": lt.status, "link": f"/letters/{lt.id}"})
    if svc.has(auth, "penalties.read") or _sees_all(auth) or svc.has(auth, "employees.documents"):
        for pn in (await db.scalars(select(Penalty).where(Penalty.employee_id == employee_id))).all():
            out.append({"type": "penalty", "id": pn.id, "number": None, "title": pn.label, "date": pn.created_at, "status": pn.status, "link": "/penalties"})
    out.sort(key=lambda x: x["date"], reverse=True)
    return {"employee": {"id": emp.id, "name": emp.full_name}, "items": out}


@router.post("/applications", status_code=201)
async def create_application(body: ApplicationIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.has(auth, "staffdocs.apply"):
        raise error(403, "forbidden")
    emp = await _my_emp(db, auth)
    if not emp:
        raise error(400, "no_employee")
    if body.subtype in svc.NEEDS_DATES and not body.start_date:
        raise error(400, "dates_required")
    if body.start_date and body.end_date and body.end_date < body.start_date:
        raise error(400, "date_range_invalid")
    moment = now()
    doc = StaffDocument(kind="application", subtype=body.subtype, employee_id=emp.id, title=svc.title_for(body.subtype), body=body.body.strip(), start_date=body.start_date, end_date=body.end_date, status="submitted", created_by=auth.user.id)
    db.add(doc)
    await db.flush()
    await svc.assign_number(db, doc, moment)
    doc.content_hash = svc.content_hash(doc, emp)
    hr = await users_with_permission(db, "staffdocs.manage")
    notes = await notify(db, hr, "staff.application_new", params={"employee": emp.full_name, "title": doc.title, "number": doc.number}, link=f"/hr/documents/{doc.id}")
    await audit(db, request, "staffdoc.apply", actor=auth.user, entity="staff_document", entity_id=doc.id, data={"number": doc.number, "subtype": doc.subtype})
    await db.commit()
    await deliver(request.app, notes)
    return _out(doc, emp, {auth.user.id: auth.user.full_name}, auth)


@router.post("/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.has(auth, "staffdocs.manage"):
        raise error(403, "forbidden")
    emp = await _emp(db, body.employee_id)
    if body.start_date and body.end_date and body.end_date < body.start_date:
        raise error(400, "date_range_invalid")
    if body.related_id:
        rel = await db.get(StaffDocument, body.related_id)
        if not rel or rel.kind != "application" or rel.employee_id != emp.id:
            raise error(400, "unknown_reference")
    text_body = (body.body or "").strip() or await svc.default_order_body(db, emp, body.subtype, body.start_date, body.end_date)
    doc = StaffDocument(kind="order", subtype=body.subtype, employee_id=emp.id, title=(body.title or "").strip() or svc.title_for(body.subtype), body=text_body, start_date=body.start_date, end_date=body.end_date, status="draft", related_id=body.related_id, created_by=auth.user.id)
    db.add(doc)
    await db.flush()
    await audit(db, request, "staffdoc.order_create", actor=auth.user, entity="staff_document", entity_id=doc.id)
    await db.commit()
    return _out(doc, emp, {auth.user.id: auth.user.full_name}, auth)


@router.get("/{did}")
async def get_doc(did: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    doc, emp = await _load(db, did, auth)
    return _out(doc, emp, await _names(db, [doc]), auth)


@router.put("/{did}")
async def update_order(did: int, body: OrderUpdate, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.has(auth, "staffdocs.manage"):
        raise error(403, "forbidden")
    doc, emp = await _load(db, did, auth, lock=True)
    if doc.kind != "order" or doc.status != "draft":
        raise error(409, "not_editable")
    doc.title, doc.body, doc.start_date, doc.end_date = body.title.strip(), body.body.strip(), body.start_date, body.end_date
    await audit(db, request, "staffdoc.order_update", actor=auth.user, entity="staff_document", entity_id=doc.id)
    await db.commit()
    return _out(doc, emp, await _names(db, [doc]), auth)


@router.post("/{did}/decide")
async def decide(did: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not svc.has(auth, "staffdocs.manage"):
        raise error(403, "forbidden")
    doc, emp = await _load(db, did, auth, lock=True)
    if doc.kind != "application" or doc.status != "submitted":
        raise error(409, "already_decided")
    note = (body.note or "").strip() or None
    if body.action == "reject" and not note:
        raise error(400, "note_required")
    doc.status = "approved" if body.action == "approve" else "rejected"
    doc.decided_by, doc.decided_at, doc.decision_note = auth.user.id, now(), note
    notes = await notify(db, [emp.user_id] if emp.user_id else [], "staff.application_decided", params={"title": doc.title, "number": doc.number, "result": "qabul qilindi" if doc.status == "approved" else "rad etildi" + (f": {note}" if note else "")}, link=f"/hr/documents/{doc.id}")
    await audit(db, request, f"staffdoc.{doc.status}", actor=auth.user, entity="staff_document", entity_id=doc.id)
    await db.commit()
    await deliver(request.app, notes)
    return _out(doc, emp, await _names(db, [doc]), auth)


@router.post("/{did}/cancel")
async def cancel(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    doc, emp = await _load(db, did, auth, lock=True)
    manage = svc.has(auth, "staffdocs.manage")
    own_app = doc.kind == "application" and doc.status == "submitted" and emp.user_id == auth.user.id
    if not (own_app or (manage and (doc.status == "submitted" or (doc.kind == "order" and doc.status in ("draft", "issued"))))):
        raise error(403 if not manage else 409, "cannot_cancel")
    doc.status = "cancelled"
    await audit(db, request, "staffdoc.cancel", actor=auth.user, entity="staff_document", entity_id=doc.id)
    await db.commit()
    return _out(doc, emp, await _names(db, [doc]), auth)


@router.post("/{did}/sign")
async def sign(did: int, body: SignIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Buyruqni elektron imzolaydi (parol bilan tasdiqlanadi): raqam, QR kod va xesh beriladi, xodimga xabar boradi."""
    if not svc.has(auth, "staffdocs.sign"):
        raise error(403, "forbidden")
    doc, emp = await _load(db, did, auth, lock=True)
    if doc.kind != "order" or doc.status != "draft":
        raise error(409, "not_signable")
    redis = request.app.state.redis
    key = f"rl:staffdocs:pw:{auth.user.id}"
    if int(await redis.get(key) or 0) >= PW_FAILS:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(key), 1))
    if not verify_password(body.password, auth.user.password_hash):
        n = await redis.incr(key)
        if n == 1:
            await redis.expire(key, PW_WINDOW)
        raise error(403, "wrong_password")
    await redis.delete(key)
    moment = now()
    await svc.assign_number(db, doc, moment)
    doc.status, doc.signed_by, doc.signed_at = "issued", auth.user.id, moment
    doc.content_hash = svc.content_hash(doc, emp)
    notes = await notify(db, [emp.user_id] if emp.user_id else [], "staff.order_issued", params={"title": doc.title, "number": doc.number}, link=f"/hr/documents/{doc.id}")
    await audit(db, request, "staffdoc.sign", actor=auth.user, entity="staff_document", entity_id=doc.id, data={"number": doc.number, "hash": doc.content_hash, "ip": client_ip(request)})
    await db.commit()
    await deliver(request.app, notes)
    return _out(doc, emp, await _names(db, [doc]), auth)


@router.post("/{did}/ack")
async def acknowledge(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    doc, emp = await _load(db, did, auth, lock=True)
    if emp.user_id != auth.user.id:
        raise error(403, "forbidden")
    if doc.kind != "order" or doc.status != "issued":
        raise error(409, "not_acknowledgeable")
    if doc.acknowledged_at is None:
        doc.acknowledged_at = now()
        await audit(db, request, "staffdoc.ack", actor=auth.user, entity="staff_document", entity_id=doc.id)
        await db.commit()
    return _out(doc, emp, await _names(db, [doc]), auth)


@router.get("/{did}/pdf")
async def pdf(did: int, request: Request, lang: str = Query(default="uz", pattern="^(uz|ru)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    doc, emp = await _load(db, did, auth)
    if not doc.number:
        raise error(409, "not_issued")
    cfg = getattr(request.app.state, "client_config", None)
    company = (cfg.brand.get("name") if cfg else None) or "HR-Profi"
    content = await svc.build_pdf(db, doc, emp, f"{_base_url(request)}/verify/doc/{doc.code}", company, lang)
    await audit(db, request, "staffdoc.pdf", actor=auth.user, entity="staff_document", entity_id=doc.id)
    await db.commit()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{doc.number}.pdf"'})


@public_router.get("/staffdoc/{code}")
async def verify(code: str, request: Request, hash: str | None = Query(default=None, max_length=64), db: AsyncSession = Depends(get_session)):
    redis = request.app.state.redis
    rk = f"rl:verify:{client_ip(request)}"
    n = await redis.incr(rk)
    if n == 1:
        await redis.expire(rk, 60)
    if n > 60:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(rk), 1))
    doc = await db.scalar(select(StaffDocument).where(StaffDocument.code == code[:40]))
    if not doc:
        raise error(404, "not_found")
    return svc.public_view(doc, await _emp(db, doc.employee_id), hash)
