"""Tushuntirish xatlari: shablonlar, so'rash, yozish + imzo, ko'rib chiqish, PDF, skaner, ochiq tekshiruv."""

import asyncio
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _base_url
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.letters import ExplanationLetter, LetterEvent, LetterTemplate
from app.security import verify_password
from app.services import letters as svc
from app.services.audit import audit, client_ip
from app.services.letters_pdf import build_letter_pdf
from app.services.notifications import deliver
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/letters", tags=["letters"])
public_router = APIRouter(prefix="/v1/public", tags=["public"])

SCAN_MIMES = {"application/pdf", "image/jpeg", "image/png"}
PW_FAILS = 5
PW_WINDOW = 600


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


def _company(request: Request) -> str:
    cfg = getattr(request.app.state, "client_config", None)
    return (cfg.brand.get("name") if cfg else None) or "HR-Profi"


# --- Shablonlar -------------------------------------------------------------------------


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    recipient_line: str = Field(default="", max_length=300)
    body_template: str = Field(min_length=10, max_length=5000)
    instructions: str | None = Field(default=None, max_length=2000)
    is_default: bool = False
    is_active: bool = True


def template_out(t: LetterTemplate, used: int = 0) -> dict[str, Any]:
    return {
        "id": t.id, "name": t.name, "title": t.title, "recipient_line": t.recipient_line, "body_template": t.body_template,
        "instructions": t.instructions, "is_default": t.is_default, "is_active": t.is_active, "used": used,
    }  # fmt: skip


def _check_template(body: TemplateIn) -> None:
    bad = svc.unknown_placeholders(body.title, body.recipient_line, body.body_template)
    if bad:
        raise error(400, "unknown_placeholder", names=bad)
    if "{explanation}" not in body.body_template:
        raise error(400, "explanation_placeholder_missing")


async def _make_default(db: AsyncSession, keep: LetterTemplate) -> None:
    for t in (await db.scalars(select(LetterTemplate).where(LetterTemplate.is_default.is_(True), LetterTemplate.id != keep.id))).all():
        t.is_default = False
    await db.flush()


@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("letters.manage", "letters.issue", "letters.read"))
):
    used = dict((await db.execute(select(ExplanationLetter.template_id, func.count()).group_by(ExplanationLetter.template_id))).all())
    rows = (await db.scalars(select(LetterTemplate).order_by(LetterTemplate.name))).all()
    return [template_out(t, used.get(t.id, 0)) for t in rows]


@router.get("/templates/placeholders")
async def placeholders(_: AuthContext = Depends(require_any("letters.manage"))):
    return {"items": list(svc.PLACEHOLDERS)}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("letters.manage", "letters.issue", "letters.read"))
):
    t = await db.get(LetterTemplate, template_id)
    if not t:
        raise error(404, "not_found")
    n = await db.scalar(select(func.count()).select_from(ExplanationLetter).where(ExplanationLetter.template_id == t.id))
    return template_out(t, n or 0)


@router.post("/templates", status_code=201)
async def create_template(
    body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require_any("letters.manage"))
):
    _check_template(body)
    t = LetterTemplate(**body.model_dump(exclude={"is_default"}), is_default=False)
    db.add(t)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "template_name_taken") from exc
    if body.is_default and body.is_active:
        await _make_default(db, t)
        t.is_default = True
    await audit(db, request, "letters.template_create", actor=auth.user, entity="letter_template", entity_id=t.id, data={"name": t.name})
    await db.commit()
    return template_out(t)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int, body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require_any("letters.manage"))
):
    t = await db.get(LetterTemplate, template_id)
    if not t:
        raise error(404, "not_found")
    _check_template(body)
    if t.is_default and (not body.is_default or not body.is_active):
        raise error(409, "default_template_required")
    for k, v in body.model_dump(exclude={"is_default"}).items():
        setattr(t, k, v)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "template_name_taken") from exc
    if body.is_default and body.is_active and not t.is_default:
        await _make_default(db, t)
        t.is_default = True
    await audit(db, request, "letters.template_update", actor=auth.user, entity="letter_template", entity_id=t.id)
    await db.commit()
    return template_out(t)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require_any("letters.manage"))
):
    t = await db.get(LetterTemplate, template_id)
    if not t:
        raise error(404, "not_found")
    if t.is_default:
        raise error(409, "default_template_required")
    if await db.scalar(select(func.count()).select_from(ExplanationLetter).where(ExplanationLetter.template_id == t.id)):
        raise error(409, "template_in_use")
    await audit(db, request, "letters.template_delete", actor=auth.user, entity="letter_template", entity_id=t.id, data={"name": t.name})
    await db.delete(t)
    await db.commit()


# --- Xatlar -----------------------------------------------------------------------------


class IssueIn(BaseModel):
    employee_id: int
    template_id: int | None = None
    incident_type: str = Field(pattern="^(late|absent|early_leave|no_checkout|discipline|other)$")
    incident_date: date
    incident_note: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None


async def _emp(db: AsyncSession, emp_id: int) -> Employee:
    e = await db.get(Employee, emp_id)
    if not e:
        raise error(404, "not_found")
    return e


async def _load(db: AsyncSession, letter_id: int, auth: AuthContext, *, lock: bool = False) -> tuple[ExplanationLetter, Employee]:
    stmt = select(ExplanationLetter).where(ExplanationLetter.id == letter_id)
    letter = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not letter:
        raise error(404, "not_found")
    emp = await _emp(db, letter.employee_id)
    if not svc.can_view(auth, letter, emp):
        raise error(404, "not_found")
    return letter, emp


async def _requester_names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    if not ids2:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()}


@router.post("", status_code=201)
async def issue(body: IssueIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require_any("letters.issue", "letters.manage"))):
    emp = await _emp(db, body.employee_id)
    if not await svc.can_issue_to(db, auth, emp):
        raise error(403, "forbidden")
    moment = now()
    today = local_date(moment)
    if body.incident_date > today:
        raise error(400, "date_in_future")
    due = body.due_date or today + timedelta(days=3)
    if due < today:
        raise error(400, "due_in_past")
    template = await svc.get_template(db, body.template_id)
    letter, notes = await svc.issue(db, auth, emp, template, incident_type=body.incident_type, incident_date=body.incident_date, incident_note=body.incident_note, due_date=due, moment=moment)
    await audit(db, request, "letters.request", actor=auth.user, entity="letter", entity_id=letter.id,
                data={"number": letter.number, "employee_id": emp.id, "incident": letter.incident_type})  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    return svc.letter_out(letter, emp, today=today, auth=auth, requester=auth.user.full_name)


@router.get("")
async def list_letters(
    scope: str = Query(default="mine", pattern="^(mine|issued|all)$"),
    status: str | None = Query(default=None, pattern="^(open|overdue|requested|submitted|accepted|returned|cancelled)$"),
    q: str | None = None,
    employee_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    """mine: menga yozilgan; issued: men so'ragan; all: hammasi (letters.read)."""
    today = local_date(now())
    stmt = select(ExplanationLetter, Employee).join(Employee, Employee.id == ExplanationLetter.employee_id)
    if scope == "mine":
        stmt = stmt.where(Employee.user_id == auth.user.id)
    elif scope == "issued":
        stmt = stmt.where(ExplanationLetter.requested_by == auth.user.id)
    else:
        if not svc.has(auth, "letters.read"):
            raise error(403, "forbidden")
    if status == "open":
        stmt = stmt.where(ExplanationLetter.status.in_(svc.OPEN))
    elif status == "overdue":
        stmt = stmt.where(ExplanationLetter.status.in_(svc.OPEN), ExplanationLetter.due_date < today)
    elif status:
        stmt = stmt.where(ExplanationLetter.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Employee.full_name.ilike(like), ExplanationLetter.number.ilike(like)))
    if employee_id:
        stmt = stmt.where(ExplanationLetter.employee_id == employee_id)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.order_by(ExplanationLetter.id.desc()).offset((page - 1) * size).limit(size))).all()
    names = await _requester_names(db, {r.requested_by for r, _ in rows})
    return {
        "total": total or 0, "page": page, "size": size,
        "items": [svc.letter_out(r, e, today=today, auth=auth, requester=names.get(r.requested_by or 0)) for r, e in rows],
    }  # fmt: skip


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)) -> dict[str, int]:
    """Menyu belgisi: menga yozish kerak bo'lganlar va ko'rib chiqishni kutayotganlar."""
    to_write = await db.scalar(
        select(func.count()).select_from(ExplanationLetter).join(Employee, Employee.id == ExplanationLetter.employee_id)
        .where(Employee.user_id == auth.user.id, ExplanationLetter.status.in_(svc.OPEN))
    ) or 0  # fmt: skip
    to_review = 0
    if svc.has(auth, "letters.review") or svc.has(auth, "letters.issue"):
        stmt = select(func.count()).select_from(ExplanationLetter).join(Employee, Employee.id == ExplanationLetter.employee_id).where(
            ExplanationLetter.status == "submitted", Employee.user_id.is_distinct_from(auth.user.id)
        )
        if not svc.has(auth, "letters.review"):
            stmt = stmt.where(ExplanationLetter.requested_by == auth.user.id)
        to_review = await db.scalar(stmt) or 0
    return {"to_write": to_write, "to_review": to_review}


@router.get("/{letter_id}")
async def detail(letter_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    letter, emp = await _load(db, letter_id, auth)
    events = (await db.scalars(select(LetterEvent).where(LetterEvent.letter_id == letter.id).order_by(LetterEvent.id))).all()
    names = await _requester_names(db, {letter.requested_by, *(e.actor_id for e in events)})
    out = svc.letter_out(letter, emp, today=local_date(now()), auth=auth, requester=names.get(letter.requested_by or 0))
    tpl = await db.get(LetterTemplate, letter.template_id) if letter.template_id else None
    out["instructions"] = tpl.instructions if tpl else None
    out["explanation"] = letter.explanation
    out["snapshot"] = letter.snapshot
    out["signature"] = letter.signature and {"name": letter.signature.get("name"), "at": letter.signature.get("at")}
    out["events"] = [
        {"id": e.id, "action": e.action, "note": e.note, "actor": names.get(e.actor_id or 0), "created_at": e.created_at} for e in events
    ]  # fmt: skip
    return out


class SubmitIn(BaseModel):
    explanation: str = Field(min_length=1, max_length=svc.MAX_TEXT)
    password: str = Field(min_length=1, max_length=200)


@router.post("/{letter_id}/submit")
async def submit(
    letter_id: int,
    body: SubmitIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require_any("letters.own")),
):
    """Xodim matnni yozib, parolini tasdiqlab (elektron imzo) topshiradi."""
    letter, emp = await _load(db, letter_id, auth, lock=True)
    redis = request.app.state.redis
    key = f"rl:letters:pw:{auth.user.id}"
    if int(await redis.get(key) or 0) >= PW_FAILS:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(key), 1))
    if emp.user_id != auth.user.id:
        raise error(403, "forbidden")
    if not verify_password(body.password, auth.user.password_hash):
        n = await redis.incr(key)
        if n == 1:
            await redis.expire(key, PW_WINDOW)
        raise error(403, "wrong_password")
    await redis.delete(key)
    tpl = await db.get(LetterTemplate, letter.template_id) if letter.template_id else None
    notes = await svc.submit(db, letter, emp, auth, tpl, body.explanation, _company(request), client_ip(request), now())
    await audit(db, request, "letters.submit", actor=auth.user, entity="letter", entity_id=letter.id, data={"number": letter.number, "hash": letter.content_hash})
    await db.commit()
    await deliver(request.app, notes)
    return svc.letter_out(letter, emp, today=local_date(now()), auth=auth)


class ReviewIn(BaseModel):
    action: str = Field(pattern="^(accept|return)$")
    note: str | None = Field(default=None, max_length=1000)


@router.post("/{letter_id}/review")
async def review(
    letter_id: int,
    body: ReviewIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require_any("letters.review", "letters.issue")),
):
    letter, emp = await _load(db, letter_id, auth, lock=True)
    notes = await svc.review(db, letter, emp, auth, body.action, body.note, now())
    await audit(db, request, f"letters.{letter.status}", actor=auth.user, entity="letter", entity_id=letter.id, data={"number": letter.number}, note=letter.review_note)
    await db.commit()
    await deliver(request.app, notes)
    return svc.letter_out(letter, emp, today=local_date(now()), auth=auth)


@router.post("/{letter_id}/cancel")
async def cancel(letter_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    letter, emp = await _load(db, letter_id, auth, lock=True)
    if not svc.can_cancel(auth, letter):
        raise error(409 if letter.status not in svc.OPEN else 403, "cannot_cancel" if letter.status not in svc.OPEN else "forbidden")
    letter.status = "cancelled"
    svc.add_event(db, letter, "cancelled", auth.user.id)
    await audit(db, request, "letters.cancel", actor=auth.user, entity="letter", entity_id=letter.id, data={"number": letter.number})
    await db.commit()
    return svc.letter_out(letter, emp, today=local_date(now()), auth=auth)


# --- Skaner (qog'ozdagi imzolangan nusxa) -----------------------------------------------


@router.post("/{letter_id}/scan", status_code=204)
async def upload_scan(
    letter_id: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)
):
    letter, emp = await _load(db, letter_id, auth, lock=True)
    if letter.status not in ("submitted", "accepted") or not (emp.user_id == auth.user.id or svc.has(auth, "letters.review")):
        raise error(403, "forbidden")
    up = await read_upload(file, MAX_DOC_BYTES)
    if up.mime not in SCAN_MIMES:
        raise error(415, "file_type_not_allowed")
    storage = request.app.state.storage
    key = storage_key(f"letters/{letter.id}", "scan")
    await storage.put(key, up.data, up.mime)
    old = letter.scan_key
    letter.scan_key, letter.scan_mime, letter.scan_filename = key, up.mime, up.filename
    letter.scan_size, letter.scan_uploaded_at = len(up.data), now()
    svc.add_event(db, letter, "scanned", auth.user.id, up.filename)
    await audit(db, request, "letters.scan", actor=auth.user, entity="letter", entity_id=letter.id, data={"size": len(up.data)})
    await db.commit()
    if old:
        await storage.delete(old)


@router.get("/{letter_id}/scan")
async def download_scan(letter_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    letter, _ = await _load(db, letter_id, auth)
    if not letter.scan_key:
        raise error(404, "not_found")
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
               "Content-Disposition": f"inline; filename*=UTF-8''{quote(letter.scan_filename or 'scan')}"}  # fmt: skip
    return StreamingResponse(request.app.state.storage.stream(letter.scan_key), media_type=letter.scan_mime or "application/octet-stream", headers=headers)


@router.get("/{letter_id}/pdf")
async def pdf(letter_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    letter, _ = await _load(db, letter_id, auth)
    if not letter.signature or letter.status not in ("submitted", "accepted", "returned"):
        raise error(409, "letter_not_signed")
    url = f"{_base_url(request)}/verify/{letter.code}"
    content = await asyncio.to_thread(build_letter_pdf, letter, url)
    await audit(db, request, "letters.pdf", actor=auth.user, entity="letter", entity_id=letter.id)
    await db.commit()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{letter.number}.pdf"'})


# --- Ochiq tekshiruv (autentifikatsiyasiz) ----------------------------------------------


@public_router.get("/letters/{code}")
async def verify(code: str, request: Request, hash: str | None = Query(default=None, max_length=64), db: AsyncSession = Depends(get_session)):
    """QR orqali hujjatni tekshirish: matn ko'rsatilmaydi, faqat mavjudligi, holati va yaxlitligi."""
    redis = request.app.state.redis
    rk = f"rl:verify:{client_ip(request)}"
    n = await redis.incr(rk)
    if n == 1:
        await redis.expire(rk, 60)
    if n > 60:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(rk), 1))
    letter = await db.scalar(select(ExplanationLetter).where(ExplanationLetter.code == code[:40]))
    if not letter or not letter.signature:
        raise error(404, "not_found")
    emp = await _emp(db, letter.employee_id)
    return svc.public_view(letter, emp, hash)

