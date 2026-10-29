"""Rekruting oqimi: suhbat natijasi, fon tekshiruv, AI skaner, job offer (HRD tasdig'i), taklif va qo'ng'iroqlar hisoboti."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.recruit import Manage, Read, _application, _out_many
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.recruit import Application, Candidate, RecruitCall, Vacancy
from app.services import ai as ai_svc
from app.services import employees as emp_svc
from app.services import recruit as rsvc
from app.services import recruit_pipeline as psvc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_dt_fmt, now, tz

router = APIRouter(prefix="/v1/recruit", tags=["recruit-pipeline"])


async def _tell_candidate(request: Request, c: Candidate | None, text: str) -> bool:
    """Nomzod botga yozgan bo'lsa (chat_id bor), unga Telegram xabari navbatga qo'yiladi."""
    if not psvc.can_message(c):
        return False
    await request.app.state.queue.enqueue("deliver_candidate_telegram", c.telegram_chat_id, text)  # type: ignore[union-attr]
    return True


class InterviewIn(BaseModel):
    experience_level: str = Field(pattern="^(high|mid|none)$")
    hard_skill: int = Field(ge=1, le=5)
    soft_skill: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=3000)


@router.post("/applications/{aid}/interview")
async def save_interview(aid: int, body: InterviewIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Suhbat natijasi: tajriba darajasi (ochiladigan bosqichlarni belgilaydi), hard va soft skill."""
    a = await _application(db, aid, lock=True)
    if a.stage in ("hired", "rejected"):
        raise error(409, "invalid_transition")
    a.experience_level, a.hard_skill, a.soft_skill = body.experience_level, body.hard_skill, body.soft_skill
    a.interview_notes, a.interviewed_by, a.interviewed_at = (body.notes or "").strip() or None, auth.user.id, now()
    rsvc.log(db, a, auth.user.id, "comment", note=f"Suhbat: tajriba={body.experience_level}, hard={body.hard_skill}, soft={body.soft_skill}", data={"interview": True})
    await audit(db, request, "recruit.interview", actor=auth.user, entity="application", entity_id=a.id, data={"level": body.experience_level})
    await db.commit()
    return (await _out_many(db, [a]))[0]


class InviteIn(BaseModel):
    interview_at: datetime
    place: str | None = Field(default=None, max_length=200)


@router.post("/applications/{aid}/invite")
async def invite(aid: int, body: InviteIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Suhbatga chaqirish: bosqich 'suhbat' ga o'tadi, joy va vaqt nomzodga Telegram orqali yuboriladi (bot orqali kelgan bo'lsa)."""
    a = await _application(db, aid, lock=True)
    when = body.interview_at if body.interview_at.tzinfo else body.interview_at.replace(tzinfo=tz())
    await rsvc.move(db, a, auth, "interview", (body.place or "").strip() or None, now(), interview_at=when)
    c, v = await db.get(Candidate, a.candidate_id), await db.get(Vacancy, a.vacancy_id)
    sent = await _tell_candidate(request, c, psvc.invite_text(v, local_dt_fmt(when), body.place))  # type: ignore[arg-type]
    await audit(db, request, "recruit.invite", actor=auth.user, entity="application", entity_id=a.id, data={"telegram": sent})
    await db.commit()
    return {**(await _out_many(db, [a]))[0], "telegram_sent": sent}


class BackgroundIn(BaseModel):
    status: str = Field(pattern="^(pending|passed|failed)$")
    note: str | None = Field(default=None, max_length=2000)


@router.post("/applications/{aid}/background")
async def background(aid: int, body: BackgroundIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid, lock=True)
    note = (body.note or "").strip() or None
    if body.status == "failed" and not note:
        raise error(400, "note_required")
    a.bg_status, a.bg_note, a.bg_by, a.bg_at = body.status, note, auth.user.id, now()
    rsvc.log(db, a, auth.user.id, "comment", note=f"Fon tekshiruv: {body.status}" + (f" — {note}" if note else ""), data={"background": body.status})
    await audit(db, request, "recruit.background", actor=auth.user, entity="application", entity_id=a.id, data={"status": body.status})
    await db.commit()
    return (await _out_many(db, [a]))[0]


@router.post("/applications/{aid}/ai-scan")
async def ai_scan(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """AI skaner: tavsiya beradi, qaror HR da qoladi (natija arizada saqlanadi)."""
    a = await _application(db, aid)
    result = await ai_svc.scan_application(db, auth, a)
    a = await _application(db, aid, lock=True)
    a.ai_scan, a.ai_scan_at = result, now()
    await audit(db, request, "recruit.ai_scan", actor=auth.user, entity="application", entity_id=a.id, data={"score": result["score"], "rec": result["recommendation"]})
    await db.commit()
    return (await _out_many(db, [a]))[0]


class OfferIn(BaseModel):
    level: str = Field(pattern="^(intern|pharmacist|senior)$")
    salary: int = Field(ge=0, le=200_000_000)
    start_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


@router.post("/applications/{aid}/offer")
async def make_offer(aid: int, body: OfferIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """HR job offer tayyorlaydi (lavozim darajasi suhbatdagi tajribaga mos bo'lishi shart). HRD tasdiqlaydi."""
    a = await _application(db, aid, lock=True)
    if a.stage in ("hired", "rejected"):
        raise error(409, "invalid_transition")
    psvc.check_level(a, body.level)
    a.offer_level, a.offer_salary, a.offer_start, a.offer_note, a.offer_by = body.level, body.salary, body.start_date, (body.note or "").strip() or None, auth.user.id
    a.offer_decision_note, a.offer_decided_by, a.offer_decided_at, a.offer_sent_at = None, None, None, None
    c = await db.get(Candidate, a.candidate_id)
    notes: list = []
    if rsvc.has(auth, "recruit.approve"):  # HRD o'zi tayyorlasa tasdiq kerak emas
        a.offer_status, a.offer_decided_by, a.offer_decided_at = "approved", auth.user.id, now()
        await rsvc.move(db, a, auth, "offer", None, now())
    else:
        a.offer_status = "pending_hrd"
        hrd = [u for u in await users_with_permission(db, "recruit.approve") if u != auth.user.id]
        notes = await notify(db, hrd, "recruit.offer_review", link=f"/recruit/applications/{a.id}", params={"candidate": c.full_name if c else "", "level": psvc.LEVEL_UZ[body.level], "salary": psvc.money(body.salary)})
    rsvc.log(db, a, auth.user.id, "comment", note=f"Job offer: {psvc.LEVEL_UZ[body.level]}, {psvc.money(body.salary)} so'm", data={"offer": a.offer_status})
    await audit(db, request, "recruit.offer", actor=auth.user, entity="application", entity_id=a.id, data={"level": body.level, "salary": body.salary, "status": a.offer_status})
    await db.commit()
    await deliver(request.app, notes)
    return (await _out_many(db, [a]))[0]


class DecideIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)


@router.post("/applications/{aid}/offer/decide")
async def decide_offer(aid: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not rsvc.has(auth, "recruit.approve"):
        raise error(403, "forbidden")
    a = await _application(db, aid, lock=True)
    if a.offer_status != "pending_hrd":
        raise error(409, "already_decided")
    note = (body.note or "").strip() or None
    if body.action == "reject" and not note:
        raise error(400, "note_required")
    moment = now()
    a.offer_status = "approved" if body.action == "approve" else "rejected"
    a.offer_decided_by, a.offer_decided_at, a.offer_decision_note = auth.user.id, moment, note
    if body.action == "approve" and a.stage != "offer":
        await rsvc.move(db, a, auth, "offer", None, moment)
    c = await db.get(Candidate, a.candidate_id)
    notes = await notify(
        db, [u for u in {a.offer_by, a.recruiter_id} if u and u != auth.user.id], "recruit.offer_decided", link=f"/recruit/applications/{a.id}",
        params={"candidate": c.full_name if c else "", "result": "tasdiqlandi" if body.action == "approve" else "rad etildi", "note": note or ""},
    )  # fmt: skip
    rsvc.log(db, a, auth.user.id, "comment", note=f"Job offer {a.offer_status}" + (f": {note}" if note else ""), data={"offer": a.offer_status})
    await audit(db, request, f"recruit.offer_{body.action}", actor=auth.user, entity="application", entity_id=a.id, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return (await _out_many(db, [a]))[0]


@router.post("/applications/{aid}/offer/send")
async def send_offer(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Tasdiqlangan offerni nomzodga Telegram orqali yuboradi (parol yuborilmaydi: login xodim kartasida yaratiladi)."""
    a = await _application(db, aid, lock=True)
    if a.offer_status != "approved":
        raise error(409, "offer_not_approved")
    c, v = await db.get(Candidate, a.candidate_id), await db.get(Vacancy, a.vacancy_id)
    if not await _tell_candidate(request, c, psvc.offer_text(a, v)):
        raise error(409, "candidate_no_telegram")
    a.offer_sent_at = now()
    await audit(db, request, "recruit.offer_send", actor=auth.user, entity="application", entity_id=a.id)
    await db.commit()
    return (await _out_many(db, [a]))[0]


# --- Qo'ng'iroqlar va rekruter paneli -----------------------------------------------------


class CallIn(BaseModel):
    outcome: str = Field(pattern="^(suitable|unsuitable|no_answer|callback)$")
    phone: str | None = Field(default=None, max_length=20)
    vacancy_id: int | None = None
    note: str | None = Field(default=None, max_length=300)
    callback_date: date | None = None


@router.post("/calls", status_code=201)
async def log_call(body: CallIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    phone = None
    if body.phone:
        try:
            phone = emp_svc.normalize_phone(body.phone)
        except ValueError:
            raise error(400, "phone_invalid") from None
    cand = await db.scalar(select(Candidate).where(Candidate.phone == phone)) if phone else None
    call = RecruitCall(recruiter_id=auth.user.id, phone=phone, candidate_id=cand.id if cand else None, vacancy_id=body.vacancy_id, outcome=body.outcome, note=(body.note or "").strip() or None, callback_date=body.callback_date)
    db.add(call)
    await db.commit()
    return {"id": call.id}


@router.get("/recruiter-report")
async def recruiter_report(start: date, end: date, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    """Rekruter paneli (deck 23-slayd): qo'ng'iroq, mos/mos emas, rezyume, suhbat, fon tekshiruv, offer, ishga olingan."""
    if end < start or (end - start).days > 400:
        raise error(400, "range_invalid", max_days=400)
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz())
    A = Application
    rows: dict[int | None, dict[str, int]] = {}

    def bucket(uid: int | None) -> dict[str, int]:
        return rows.setdefault(uid, {"calls": 0, "suitable": 0, "unsuitable": 0, "no_answer": 0, "applications": 0, "interviews": 0, "bg_passed": 0, "offers": 0, "hired": 0})

    for uid, outcome, n in (await db.execute(select(RecruitCall.recruiter_id, RecruitCall.outcome, func.count()).where(RecruitCall.called_at >= s_dt, RecruitCall.called_at < e_dt).group_by(RecruitCall.recruiter_id, RecruitCall.outcome))).all():
        b = bucket(uid)
        b["calls"] += n
        if outcome in b:
            b[outcome] += n
    for uid, applied, interviews, bg, offers, hired in (
        await db.execute(
            select(
                A.recruiter_id, func.count(), func.count().filter(A.interviewed_at.is_not(None)), func.count().filter(A.bg_status == "passed"),
                func.count().filter(A.offer_status.in_(("approved", "pending_hrd"))), func.count().filter(A.stage == "hired"),
            ).where(A.applied_at >= s_dt, A.applied_at < e_dt).group_by(A.recruiter_id)
        )
    ).all():
        b = bucket(uid)
        b["applications"], b["interviews"], b["bg_passed"], b["offers"], b["hired"] = applied, interviews, bg, offers, hired
    names = await rsvc.names(db, {k for k in rows if k})
    return {"start": start, "end": end, "items": sorted([{"recruiter": names.get(k) if k else None, **v} for k, v in rows.items()], key=lambda x: -x["calls"])}


__all__: list[Any] = []
