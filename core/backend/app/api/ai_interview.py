"""AI suhbat (hard/soft skill): HR yaratadi -> nomzod ochiq havoladan yozma yoki ovozli javob beradi (Whisper) ->
AI baholaydi (yoki HR qo'lda). Xodim uchun ham (masalan stajyor attestatsiyasidan oldin)."""

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.recruit_sources import _rate
from app.db import get_session
from app.deps import AuthContext, error, require_any
from app.models.employees import Employee
from app.models.recruit import Application, Candidate, Vacancy
from app.models.smart import AiInterview
from app.services import ai, speech
from app.services import interview as svc
from app.services.answers import users_with_permission
from app.services.notifications import deliver, notify, register_template
from app.services.preboarding import audio_mime
from app.timeutil import now

router = APIRouter(prefix="/v1/ai-interviews", tags=["ai-interview"])
public_router = APIRouter(prefix="/v1/public/interview", tags=["public"])
Manage = require_any("recruit.manage", "internship.manage")
Read = require_any("recruit.read", "recruit.manage", "internship.read", "internship.manage")

register_template("ai_interview.submitted", {"uz": "AI suhbat topshirildi", "ru": "AI-интервью пройдено"},
                  {"uz": "{name}: {title}. Hard {hard}%, soft {soft}%", "ru": "{name}: {title}. Hard {hard}%, soft {soft}%"}, "info")  # fmt: skip


class CreateIn(BaseModel):
    application_id: int | None = None
    employee_id: int | None = None
    position_id: int | None = None
    lang: str = Field(default="uz", pattern="^(uz|ru)$")


@router.get("/meta")
async def meta(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    return {"ai": ai.feature_on(await ai.get_cfg(db), "interview"), "speech": speech.configured()}


@router.post("", status_code=201)
async def create(body: CreateIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    if bool(body.application_id) == bool(body.employee_id):
        raise error(400, "target_required")
    position_id = body.position_id
    if body.application_id:
        a = await db.get(Application, body.application_id)
        if not a:
            raise error(404, "not_found")
        v = await db.get(Vacancy, a.vacancy_id)
        position_id = position_id or (v.position_id if v else None)
    else:
        e = await db.get(Employee, body.employee_id)
        if not e:
            raise error(404, "not_found")
        position_id = position_id or e.position_id
    title, questions = await svc.build_questions(db, auth.user.id, position_id, body.lang)
    iv = AiInterview(token=svc.new_token(), application_id=body.application_id, employee_id=body.employee_id, position_id=position_id,
                     title=title, questions=questions, lang=body.lang, created_by=auth.user.id)  # fmt: skip
    db.add(iv)
    await db.commit()
    return svc.out(iv)


@router.get("")
async def list_(application_id: int | None = Query(default=None), employee_id: int | None = Query(default=None), db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    stmt = select(AiInterview).order_by(AiInterview.id.desc()).limit(100)
    if application_id:
        stmt = stmt.where(AiInterview.application_id == application_id)
    if employee_id:
        stmt = stmt.where(AiInterview.employee_id == employee_id)
    return {"items": [svc.out(x) for x in (await db.scalars(stmt)).all()]}


async def _get(db: AsyncSession, iid: int) -> AiInterview:
    iv = await db.get(AiInterview, iid)
    if not iv:
        raise error(404, "not_found")
    return iv


@router.get("/{iid}")
async def get_one(iid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    return svc.out(await _get(db, iid))


class ManualGradeIn(BaseModel):
    hard_pct: int = Field(ge=0, le=100)
    soft_pct: int = Field(ge=0, le=100)
    summary: str | None = Field(default=None, max_length=1500)


@router.post("/{iid}/grade")
async def grade(iid: int, body: ManualGradeIn | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Body bo'lmasa AI baholaydi; body bilan HR qo'lda baholaydi."""
    iv = await _get(db, iid)
    if iv.status not in ("submitted", "graded"):
        raise error(409, "not_submitted")
    if body is None:
        if not await svc.grade(db, iv, auth.user.id):
            raise error(503, "ai_disabled")
    else:
        iv.hard_pct, iv.soft_pct, iv.summary, iv.status, iv.graded_at = body.hard_pct, body.soft_pct, body.summary, "graded", now()
    await db.commit()
    return svc.out(iv)


# --- Ochiq (nomzod) ---------------------------------------------------------------------------


async def _by_token(db: AsyncSession, token: str, *, lock: bool = False) -> AiInterview:
    stmt = select(AiInterview).where(AiInterview.token == token[:24])
    iv = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not iv:
        raise error(404, "not_found")
    return iv


def _open(iv: AiInterview) -> None:
    if iv.status not in ("sent", "answering"):
        raise error(409, "already_submitted")


def _qid(iv: AiInterview, qid: str) -> str:
    if qid not in {q["id"] for q in iv.questions}:
        raise error(400, "unknown_question")
    return qid


@public_router.get("/{token}")
async def public_get(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "interview_view", 120, 60)
    iv = await _by_token(db, token)
    return {**svc.out(iv, public=True), "speech": speech.configured(), "submitted": iv.status in ("submitted", "graded")}


class AnswerIn(BaseModel):
    qid: str = Field(max_length=10)
    text: str = Field(max_length=4000)


@public_router.post("/{token}/answer")
async def public_answer(token: str, body: AnswerIn, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "interview_write", 60, 60)
    iv = await _by_token(db, token, lock=True)
    _open(iv)
    qid = _qid(iv, body.qid)
    iv.answers = {**(iv.answers or {}), qid: {**(iv.answers or {}).get(qid, {}), "text": body.text.strip(), "at": now().isoformat()}}
    iv.status = "answering"
    await db.commit()
    return svc.out(iv, public=True)


@public_router.post("/{token}/voice")
async def public_voice(token: str, request: Request, qid: str = Form(max_length=10), file: UploadFile = File(), db: AsyncSession = Depends(get_session)):
    """Ovozli javob: Whisper matnga aylantiradi, matn javob maydoniga yoziladi (nomzod tahrirlashi mumkin)."""
    await _rate(request, "interview_voice", 20, 600)
    iv = await _by_token(db, token, lock=True)
    _open(iv)
    qid = _qid(iv, qid)
    data = await file.read(speech.MAX_AUDIO_BYTES + 1)
    mime = audio_mime(data) if data else None
    if not mime:
        raise error(415, "unsupported_type")
    text = await speech.transcribe(data, mime, iv.lang)
    prev = (iv.answers or {}).get(qid, {})
    iv.answers = {**(iv.answers or {}), qid: {**prev, "transcript": text, "text": (prev.get("text") + "\n" if prev.get("text") else "") + text, "at": now().isoformat()}}
    iv.status = "answering"
    await db.commit()
    return {"transcript": text, **svc.out(iv, public=True)}


@public_router.post("/{token}/submit")
async def public_submit(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "interview_submit", 10, 600)
    iv = await _by_token(db, token, lock=True)
    _open(iv)
    if not any(((iv.answers or {}).get(q["id"]) or {}).get("text") for q in iv.questions):
        raise error(400, "no_answers")
    iv.status, iv.submitted_at = "submitted", now()
    await db.commit()
    graded = bool(iv.created_by) and await svc.grade(db, iv, iv.created_by)
    name = "Xodim"
    if iv.application_id:
        a = await db.get(Application, iv.application_id)
        c = await db.get(Candidate, a.candidate_id) if a else None
        name = c.full_name if c else name
    elif iv.employee_id:
        e = await db.get(Employee, iv.employee_id)
        name = e.full_name if e else name
    targets: set[int] = {iv.created_by} if iv.created_by else set(await users_with_permission(db, "recruit.manage"))
    link = f"/recruit/applications/{iv.application_id}" if iv.application_id else f"/employees/{iv.employee_id}"
    notes: list[Any] = await notify(db, sorted(targets), "ai_interview.submitted", link=link,
                                    params={"name": name, "title": iv.title, "hard": iv.hard_pct if graded else "—", "soft": iv.soft_pct if graded else "—"})  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    return {"ok": True, "submitted": True}
