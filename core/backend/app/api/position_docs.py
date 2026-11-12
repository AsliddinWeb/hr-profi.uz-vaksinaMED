"""Lavozim hujjatlari: HR lavozimga hujjat biriktiradi va xodimdan shaxsiy hujjatlarni so'raydi; xodim o'z panelida imzolaydi va yuklaydi.

- Lavozim yo'riqnomasi lavozim profili va vazifalaridan avtomatik tuziladi (HR hujjatlar kutubxonasida e'lon qilinadi).
- Imzo: chizilgan imzo rasmi + vaqt + IP + qurilma; hujjatning aniq versiyasiga bog'lanadi.
- Xodim yuklagan shaxsiy hujjat `pending` holatda, HR tasdiqlaydi yoki sabab bilan qaytaradi.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee, EmployeeDocument
from app.models.hrdocs import HrDocument, HrDocumentVersion
from app.models.org import Department, Position
from app.models.position_docs import DocumentSignature, PositionDocLink, PositionRequiredDoc
from app.rbac import matches
from app.services.audit import audit
from app.services.notifications import deliver, notify, register_template
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/position-docs", tags=["position-docs"])

REQUIRED_KINDS = ("photo", "passport", "diploma", "medical", "certificate", "contract", "other")
MAX_SIGNATURE = 300_000  # data URL uzunligi

register_template("posdocs.sign", {"uz": "Imzolash uchun hujjat", "ru": "Документ на подпись"}, {"uz": "{title}", "ru": "{title}"}, "info")
register_template("posdocs.upload", {"uz": "Xodim hujjat yukladi", "ru": "Сотрудник загрузил документ"}, {"uz": "{employee}: {title}", "ru": "{employee}: {title}"}, "info")
register_template("posdocs.review", {"uz": "Hujjatingiz ko'rib chiqildi", "ru": "Ваш документ рассмотрен"}, {"uz": "{title}: {result}", "ru": "{title}: {result}"}, "info")


def _has(auth: AuthContext, *perms: str) -> bool:
    return any(matches(auth.permissions, p) for p in perms)


def _manager(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not _has(auth, "org.manage", "hrdocs.manage", "employees.documents"):
        raise error(403, "forbidden")
    return auth


async def _position(db: AsyncSession, pid: int) -> Position:
    pos = await db.get(Position, pid)
    if not pos:
        raise error(404, "not_found")
    return pos


async def _signed(db: AsyncSession, doc_ids: list[int], user_ids: list[int]) -> set[tuple[int, int]]:
    """(document_id, user_id) — joriy versiyaga imzo qo'yilganlar."""
    if not doc_ids or not user_ids:
        return set()
    rows = (await db.execute(
        select(DocumentSignature.document_id, DocumentSignature.user_id).join(HrDocument, HrDocument.id == DocumentSignature.document_id)
        .where(DocumentSignature.document_id.in_(doc_ids), DocumentSignature.user_id.in_(user_ids), DocumentSignature.version == HrDocument.version)
    )).all()  # fmt: skip
    return {(d, u) for d, u in rows}


# --- HR: lavozim bo'yicha ------------------------------------------------------------------


@router.get("/positions/{pid}")
async def position_docs(pid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_manager)):
    pos = await _position(db, pid)
    docs = (await db.scalars(select(HrDocument).join(PositionDocLink, PositionDocLink.document_id == HrDocument.id).where(PositionDocLink.position_id == pid).order_by(HrDocument.title))).all()
    req = (await db.scalars(select(PositionRequiredDoc).where(PositionRequiredDoc.position_id == pid).order_by(PositionRequiredDoc.id))).all()
    emps = (await db.scalars(select(Employee).where(Employee.position_id == pid, Employee.status == "active").order_by(Employee.full_name))).all()
    signed = await _signed(db, [d.id for d in docs], [e.user_id for e in emps if e.user_id])
    uploads: dict[tuple[int, str], EmployeeDocument] = {}
    if emps:
        for d in (await db.scalars(select(EmployeeDocument).where(EmployeeDocument.employee_id.in_([e.id for e in emps])).order_by(EmployeeDocument.id))).all():
            uploads[(d.employee_id, d.kind)] = d
    library = (await db.scalars(select(HrDocument).where(HrDocument.status == "published").order_by(HrDocument.title))).all()
    return {
        "position": {"id": pos.id, "name": pos.name, "duties": pos.duties or []},
        "documents": [{"id": d.id, "title": d.title, "version": d.version, "signed": sum(1 for e in emps if e.user_id and (d.id, e.user_id) in signed)} for d in docs],
        "required": [{"id": r.id, "kind": r.kind, "title": r.title} for r in req],
        "employees": [
            {"id": e.id, "name": e.full_name, "has_account": bool(e.user_id),
             "signed": [d.id for d in docs if e.user_id and (d.id, e.user_id) in signed],
             "uploads": {r.kind: _upload_out(uploads.get((e.id, r.kind))) for r in req}}
            for e in emps
        ],  # fmt: skip
        "library": [{"id": d.id, "title": d.title} for d in library],
        "kinds": REQUIRED_KINDS,
    }


def _upload_out(d: EmployeeDocument | None) -> dict[str, Any] | None:
    return {"id": d.id, "status": d.status, "filename": d.filename, "note": d.review_note, "employee_id": d.employee_id} if d else None


class LinkIn(BaseModel):
    document_id: int


@router.post("/positions/{pid}/documents", status_code=201)
async def link_document(pid: int, body: LinkIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_manager)):
    await _position(db, pid)
    doc = await db.get(HrDocument, body.document_id)
    if not doc:
        raise error(404, "not_found")
    if not await db.scalar(select(PositionDocLink.id).where(PositionDocLink.position_id == pid, PositionDocLink.document_id == doc.id)):
        db.add(PositionDocLink(position_id=pid, document_id=doc.id))
        await db.flush()
        notes = await _notify_sign(db, pid, doc)
        await audit(db, request, "posdocs.link", actor=auth.user, entity="position", entity_id=pid, data={"document": doc.title})
        await db.commit()
        await deliver(request.app, notes)
    return {"ok": True}


@router.delete("/positions/{pid}/documents/{doc_id}", status_code=204)
async def unlink_document(pid: int, doc_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_manager)):
    await db.execute(delete(PositionDocLink).where(PositionDocLink.position_id == pid, PositionDocLink.document_id == doc_id))
    await db.commit()


async def _notify_sign(db: AsyncSession, pid: int, doc: HrDocument) -> list:
    users = [u for u in (await db.scalars(select(Employee.user_id).where(Employee.position_id == pid, Employee.status == "active", Employee.user_id.is_not(None)))).all() if u]
    return await notify(db, users, "posdocs.sign", params={"title": doc.title}, link="/my-documents") if users else []


def _instruction_text(pos: Position, dept: Department | None, profile: Any) -> str:
    data = (profile.data if profile else None) or {}
    lines = [f"LAVOZIM YO'RIQNOMASI: {pos.name.upper()}", ""]
    if dept:
        lines.append(f"Bo'lim: {dept.name}")
    gen = data.get("general") or {}
    if gen.get("reports_to"):
        lines.append(f"Bo'ysunadi: {gen['reports_to']}")
    if gen.get("work_mode"):
        lines.append(f"Ish rejimi: {gen['work_mode']}")
    if data.get("goal"):
        lines += ["", "1. LAVOZIM MAQSADI", data["goal"]]
    duties = [d for d in (data.get("functions") or []) if d] or [d.get("title") if isinstance(d, dict) else d for d in (pos.duties or [])]
    duties = [d for d in duties if d]
    if duties:
        lines += ["", "2. VAZIFALARI"] + [f"2.{i}. {d}" for i, d in enumerate(duties, 1)]
    daily = data.get("daily") or {}
    if daily.get("routine"):
        lines += ["", "3. ISH KUNI TARTIBI"] + [f"{r.get('time', '')} — {r.get('task', '')}" for r in daily["routine"] if r.get("task")]
    if daily.get("tools"):
        lines += ["", "4. ISHLATILADIGAN DASTURLAR", ", ".join(daily["tools"])]
    edu = data.get("education") or {}
    req = [v for v in (edu.get("level"), edu.get("field"), edu.get("experience"), edu.get("languages")) if v]
    if req:
        lines += ["", "5. MALAKA TALABLARI"] + [f"- {x}" for x in req]
    kpi = [k for k in (data.get("kpi") or []) if k.get("name")]
    if kpi:
        lines += ["", "6. SAMARADORLIK KO'RSATKICHLARI (KPI)"] + [f"- {k['name']}: {k.get('target', '')}" for k in kpi]
    lines += ["", "7. JAVOBGARLIK", "Xodim ushbu yo'riqnomada belgilangan vazifalarni o'z vaqtida va sifatli bajarmagani uchun ichki tartib qoidalari va mehnat qonunchiligiga muvofiq javob beradi.",
              "", "Men ushbu yo'riqnoma bilan tanishdim va unga amal qilishga roziman."]  # fmt: skip
    return "\n".join(lines)


@router.post("/positions/{pid}/instruction")
async def generate_instruction(pid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_manager)):
    """Lavozim yo'riqnomasini profil va vazifalardan tuzadi (bor bo'lsa yangi versiya), e'lon qiladi va lavozimga biriktiradi."""
    from app.models.competency import PositionProfile

    pos = await _position(db, pid)
    dept = await db.get(Department, pos.department_id) if pos.department_id else None
    prof = await db.scalar(select(PositionProfile).where(PositionProfile.position_id == pid, PositionProfile.status != "archived").order_by(PositionProfile.status != "approved", PositionProfile.version.desc()).limit(1))
    body = _instruction_text(pos, dept, prof)
    key = f"instr-{pid}"
    doc = await db.scalar(select(HrDocument).where(HrDocument.key == key))
    moment = now()
    if doc is None:
        doc = HrDocument(key=key, category="process", title=f"Lavozim yo'riqnomasi: {pos.name}"[:200], summary=f"{pos.name} lavozimi uchun yo'riqnoma", body=body,
                         version=1, status="published", requires_ack=True, roles=[], published_at=moment, updated_by=auth.user.id)  # fmt: skip
        db.add(doc)
        await db.flush()
    elif doc.body != body:
        doc.body, doc.version, doc.published_at, doc.updated_by, doc.status = body, doc.version + 1, moment, auth.user.id, "published"
    db.add(HrDocumentVersion(document_id=doc.id, version=doc.version, title=doc.title, body=body, changed_by=auth.user.id))
    notes: list = []
    if not await db.scalar(select(PositionDocLink.id).where(PositionDocLink.position_id == pid, PositionDocLink.document_id == doc.id)):
        db.add(PositionDocLink(position_id=pid, document_id=doc.id))
    await db.flush()
    notes = await _notify_sign(db, pid, doc)
    await audit(db, request, "posdocs.instruction", actor=auth.user, entity="position", entity_id=pid, data={"version": doc.version})
    await db.commit()
    await deliver(request.app, notes)
    return {"document_id": doc.id, "version": doc.version}


class RequiredIn(BaseModel):
    items: list[dict[str, str]] = Field(default_factory=list, max_length=30)


@router.put("/positions/{pid}/required")
async def set_required(pid: int, body: RequiredIn, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_manager)):
    await _position(db, pid)
    await db.execute(delete(PositionRequiredDoc).where(PositionRequiredDoc.position_id == pid))
    seen: set[tuple[str, str]] = set()
    for it in body.items:
        kind, title = it.get("kind", ""), (it.get("title") or "").strip()[:160]
        if kind not in REQUIRED_KINDS or not title or (kind, title) in seen:
            continue
        seen.add((kind, title))
        db.add(PositionRequiredDoc(position_id=pid, kind=kind, title=title))
    await db.commit()
    return {"count": len(seen)}


class ReviewIn(BaseModel):
    action: str = Field(pattern="^(approve|return)$")
    note: str | None = Field(default=None, max_length=1000)


@router.post("/uploads/{doc_id}/review")
async def review_upload(doc_id: int, body: ReviewIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_manager)):
    d = await db.get(EmployeeDocument, doc_id)
    if not d:
        raise error(404, "not_found")
    if body.action == "return" and not (body.note or "").strip():
        raise error(400, "note_required")
    d.status, d.review_note = ("approved", None) if body.action == "approve" else ("returned", body.note.strip())  # type: ignore[union-attr]
    emp = await db.get(Employee, d.employee_id)
    notes = await notify(db, [emp.user_id], "posdocs.review", params={"title": d.title, "result": "tasdiqlandi" if body.action == "approve" else f"qaytarildi: {d.review_note}"}, link="/my-documents") if emp and emp.user_id else []
    await audit(db, request, f"posdocs.upload_{body.action}", actor=auth.user, entity="employee", entity_id=d.employee_id, data={"doc_id": d.id})
    await db.commit()
    await deliver(request.app, notes)
    return _upload_out(d)


# --- Xodimning o'zi -------------------------------------------------------------------------


async def _me(db: AsyncSession, auth: AuthContext) -> Employee:
    emp = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id).limit(1))
    if not emp:
        raise error(404, "no_employee")
    return emp


@router.get("/my")
async def my_documents(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    emp = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id).limit(1))
    if not emp or not emp.position_id:
        return {"position": None, "documents": [], "required": [], "todo": 0}
    pos = await db.get(Position, emp.position_id)
    docs = (await db.scalars(select(HrDocument).join(PositionDocLink, PositionDocLink.document_id == HrDocument.id).where(PositionDocLink.position_id == emp.position_id, HrDocument.status == "published").order_by(HrDocument.title))).all()
    sigs = {s.document_id: s for s in (await db.scalars(select(DocumentSignature).where(DocumentSignature.user_id == auth.user.id, DocumentSignature.document_id.in_([d.id for d in docs])))).all() if s.version == next(x.version for x in docs if x.id == s.document_id)} if docs else {}
    req = (await db.scalars(select(PositionRequiredDoc).where(PositionRequiredDoc.position_id == emp.position_id).order_by(PositionRequiredDoc.id))).all()
    ups: dict[str, EmployeeDocument] = {}
    for d in (await db.scalars(select(EmployeeDocument).where(EmployeeDocument.employee_id == emp.id).order_by(EmployeeDocument.id))).all():
        ups[d.kind] = d
    documents = [{"id": d.id, "title": d.title, "version": d.version, "body": d.body, "has_file": bool(d.file_key), "signed_at": sigs[d.id].signed_at if d.id in sigs else None} for d in docs]
    required = [{"id": r.id, "kind": r.kind, "title": r.title, "upload": _upload_out(ups.get(r.kind))} for r in req]
    todo = sum(1 for d in documents if not d["signed_at"]) + sum(1 for r in required if not r["upload"] or r["upload"]["status"] == "returned")
    return {"position": {"id": pos.id, "name": pos.name} if pos else None, "documents": documents, "required": required, "todo": todo}


class SignIn(BaseModel):
    signature: str = Field(min_length=100, max_length=MAX_SIGNATURE)


@router.post("/my/sign/{doc_id}")
async def sign(doc_id: int, body: SignIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    emp = await _me(db, auth)
    if not body.signature.startswith("data:image/png;base64,"):
        raise error(400, "bad_signature")
    doc = await db.get(HrDocument, doc_id)
    if not doc or doc.status != "published" or not await db.scalar(select(PositionDocLink.id).where(PositionDocLink.position_id == emp.position_id, PositionDocLink.document_id == doc_id)):
        raise error(404, "not_found")
    if await db.scalar(select(DocumentSignature.id).where(DocumentSignature.document_id == doc_id, DocumentSignature.version == doc.version, DocumentSignature.user_id == auth.user.id)):
        raise error(409, "already_signed")
    moment = now()
    db.add(DocumentSignature(document_id=doc_id, version=doc.version, user_id=auth.user.id, signature=body.signature, signed_at=moment,
                             ip=(request.client.host if request.client else None), user_agent=(request.headers.get("user-agent") or "")[:300]))  # fmt: skip
    await audit(db, request, "posdocs.sign", actor=auth.user, entity="hr_document", entity_id=doc_id, data={"version": doc.version})
    await db.commit()
    return {"signed_at": moment}


@router.post("/my/upload", status_code=201)
async def upload_mine(request: Request, file: UploadFile = File(...), kind: str = Form(...), title: str = Form(..., min_length=1, max_length=160),
                      db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):  # fmt: skip
    emp = await _me(db, auth)
    if kind not in REQUIRED_KINDS:
        raise error(400, "unknown_doc_kind")
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"employees/{emp.id}/docs", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    d = EmployeeDocument(employee_id=emp.id, kind=kind, title=title.strip(), file_key=key, filename=up.filename, mime=up.mime, size=len(up.data),
                         issued_at=date.today(), uploaded_by=auth.user.id, status="pending")  # fmt: skip
    db.add(d)
    await db.flush()
    from app.services.answers import users_with_permission

    hr = [u for u in await users_with_permission(db, "employees.documents") if u != auth.user.id]
    notes = await notify(db, hr, "posdocs.upload", params={"employee": emp.full_name, "title": d.title}, link=f"/employees/{emp.id}") if hr else []
    await audit(db, request, "posdocs.upload", actor=auth.user, entity="employee", entity_id=emp.id, data={"doc_id": d.id, "kind": kind})
    await db.commit()
    await deliver(request.app, notes)
    return _upload_out(d)


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_manager)):
    """Tuzilma hisobotlari uchun: tekshirilishi kerak bo'lgan yuklangan hujjatlar soni."""
    return {"pending_uploads": await db.scalar(select(func.count()).select_from(EmployeeDocument).where(EmployeeDocument.status == "pending")) or 0}
