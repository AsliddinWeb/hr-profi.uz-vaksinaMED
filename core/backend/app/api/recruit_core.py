"""Rekruting yadrosi (F48): telefon qidiruvi, takroriy nomzod, anketa (nomzod havolasi), moslik, suhbat taklifi,
kanal yopish, rekruter kunlik ekrani va voronka."""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _base_url
from app.api.recruit import Manage, Read, _application, _candidate
from app.db import get_session
from app.deps import AuthContext, error
from app.models.recruit import (
    Application,
    Candidate,
    CandidateFile,
    InterviewInvite,
    Vacancy,
    VacancyChannel,
)
from app.rbac import matches
from app.services import employees as emp_svc
from app.services import growth
from app.services import recruit as rsvc
from app.services import recruit_core as core
from app.services.audit import audit, client_ip
from app.services.notifications import deliver, notify
from app.services.uploads import read_upload, storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/recruit", tags=["recruit-core"])
public_router = APIRouter(prefix="/v1/public", tags=["public"])
MAX_PUBLIC_FILES = 5


async def _rate(request: Request, kind: str, limit: int, window: int) -> None:
    redis = request.app.state.redis
    key = f"rl:{kind}:{client_ip(request)}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, window)
    if n > limit:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(key), 1))


async def _tell(request: Request, c: Candidate | None, text: str) -> bool:
    if c and c.telegram_chat_id:
        await request.app.state.queue.enqueue("deliver_candidate_telegram", c.telegram_chat_id, text)  # type: ignore[union-attr]
        return True
    return False


# --- Telefon qidiruvi, birlashtirish ------------------------------------------------------


@router.get("/candidates/by-phone")
async def by_phone(phone: str = Query(min_length=5, max_length=32), db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    """Kiruvchi qo'ng'iroq: raqam bo'yicha hozirgi egasi (kartochka, arizalari) va raqam tarixi."""
    try:
        p = emp_svc.normalize_phone(phone)
    except ValueError:
        raise error(400, "phone_invalid") from None
    owner = await core.phone_owner(db, p) if p else None
    current = None
    if owner:
        apps = (await db.scalars(select(Application).where(Application.candidate_id == owner.id).order_by(Application.applied_at.desc()))).all()
        titles = {v.id: v.title for v in (await db.scalars(select(Vacancy).where(Vacancy.id.in_([a.vacancy_id for a in apps])))).all()} if apps else {}
        current = {**rsvc.candidate_out(owner), "applications": [{"id": a.id, "vacancy": titles.get(a.vacancy_id), "stage": a.stage, "applied_at": a.applied_at, "match_score": a.match_score} for a in apps]}
    return {"phone": p, "current": current, "history": await core.phone_history(db, p) if p else []}


class MergeIn(BaseModel):
    secondary_ids: list[int] = Field(min_length=1, max_length=10)


@router.post("/candidates/{cid}/merge")
async def merge(cid: int, body: MergeIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    primary = await _candidate(db, cid)
    moved = await core.merge_candidates(db, primary, body.secondary_ids, now())
    await audit(db, request, "recruit.candidate_merge", actor=auth.user, entity="candidate", entity_id=primary.id, data={"secondary": body.secondary_ids, **moved})
    await db.commit()
    return {"id": primary.id, **moved}


# --- Birlashgan profil va anketa ----------------------------------------------------------


@router.get("/candidates/{cid}/profile")
async def profile(cid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    c = await _candidate(db, cid)
    prof = await core.build_profile(db, c)
    apps = (await db.scalars(select(Application).where(Application.candidate_id == c.id))).all()
    return {**prof, "applications": [{"id": a.id, "vacancy_id": a.vacancy_id, "stage": a.stage, "match_score": a.match_score, "match_detail": a.match_detail} for a in apps]}


@router.post("/candidates/{cid}/profile-link")
async def profile_link(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Nomzodga shaxsiy anketa havolasi: rezyume/obyektivka yuklaydi va birlashgan profilni tasdiqlaydi. Telegrami bo'lsa o'sha yerga yuboriladi."""
    c = await _candidate(db, cid)
    if not c.profile_token:
        c.profile_token = core.new_token()
    url = f"{_base_url(request)}/profile/{c.profile_token}"
    sent = await _tell(request, c, f"📝 Anketani to'ldiring va rezyumeingizni yuklang: {url}")
    await audit(db, request, "recruit.profile_link", actor=auth.user, entity="candidate", entity_id=c.id, data={"telegram": sent})
    await db.commit()
    return {"url": url, "telegram_sent": sent}


@router.post("/applications/{aid}/rescore")
async def rescore(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid, lock=True)
    score = await core.rescore(db, a)
    await db.commit()
    return {"match_score": score, "match_detail": a.match_detail}


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=250)
    birth_date: date | None = None
    address: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=100)
    experience: str | None = Field(default=None, max_length=300)
    expected_salary: int | None = Field(default=None, ge=0, le=1_000_000_000)
    languages: list[str] = Field(default_factory=list, max_length=10)
    skills: list[str] = Field(default_factory=list, max_length=30)
    about: str | None = Field(default=None, max_length=2000)


async def _by_token(db: AsyncSession, token: str, *, lock: bool = False) -> Candidate:
    stmt = select(Candidate).where(Candidate.profile_token == token[:24])
    c = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not c:
        raise error(404, "not_found")
    return c


async def _public_profile(db: AsyncSession, c: Candidate) -> dict[str, Any]:
    prof = await core.build_profile(db, c)
    files = (await db.scalars(select(CandidateFile).where(CandidateFile.candidate_id == c.id, CandidateFile.uploaded_by.is_(None)).order_by(CandidateFile.id))).all()
    return {"full_name": c.full_name, "fields": prof["fields"], "sources": prof["sources"], "confirmed_at": c.profile_confirmed_at, "files": [{"id": f.id, "filename": f.filename, "size": f.size} for f in files], "max_files": MAX_PUBLIC_FILES}


@public_router.get("/profile/{token}")
async def public_profile(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "profile_view", 120, 60)
    return await _public_profile(db, await _by_token(db, token))


@public_router.put("/profile/{token}")
async def public_profile_update(token: str, body: ProfileIn, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "profile_write", 30, 60)
    c = await _by_token(db, token, lock=True)
    c.full_name = " ".join(body.full_name.split())
    c.birth_date, c.address, c.email = body.birth_date, (body.address or "").strip() or None, (body.email or "").strip().lower() or None
    c.skills = list(dict.fromkeys(s.strip()[:40] for s in body.skills if s.strip()))
    c.profile = {"region": body.region, "experience": body.experience, "expected_salary": body.expected_salary, "languages": [x.strip()[:40] for x in body.languages if x.strip()], "about": body.about}
    c.profile_confirmed_at = None  # o'zgartirilgan profil qayta tasdiqlanadi
    await db.commit()
    return await _public_profile(db, c)


@public_router.post("/profile/{token}/file", status_code=201)
async def public_profile_file(token: str, request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_session)):
    """Nomzod rezyume/obyektivkani yuklaydi (PDF, DOCX, rasm)."""
    await _rate(request, "profile_file", 20, 600)
    c = await _by_token(db, token, lock=True)
    n = await db.scalar(select(func.count()).select_from(CandidateFile).where(CandidateFile.candidate_id == c.id, CandidateFile.uploaded_by.is_(None))) or 0
    if n >= MAX_PUBLIC_FILES:
        raise error(409, "too_many_files", max=MAX_PUBLIC_FILES)
    up = await read_upload(file, 8 * 1024 * 1024)
    key = storage_key(f"candidates/{c.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    db.add(CandidateFile(candidate_id=c.id, uploaded_by=None, key=key, filename=up.filename, mime=up.mime, size=len(up.data)))
    c.profile_confirmed_at = None
    await db.commit()
    return await _public_profile(db, c)


@public_router.post("/profile/{token}/confirm")
async def public_profile_confirm(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    """Nomzod birlashgan profilini tasdiqlaydi: ariza(lar)ning moslik bali hisoblanadi, mos bo'lsa rekruterga taklif tavsiyasi boradi."""
    await _rate(request, "profile_confirm", 20, 600)
    c = await _by_token(db, token, lock=True)
    c.profile_confirmed_at = now()
    cfg = await growth.get_setting(db, "recruit")
    notes: list = []
    for a in (await db.scalars(select(Application).where(Application.candidate_id == c.id, Application.stage.in_(("new", "screening"))))).all():
        score = await core.rescore(db, a)
        v = await db.get(Vacancy, a.vacancy_id)
        if score is not None and score >= cfg["invite_threshold"] and a.recruiter_id and v:
            notes += await notify(db, [a.recruiter_id], "recruit.match_ok", params={"candidate": c.full_name, "score": score, "vacancy": v.title}, link=f"/recruit/applications/{a.id}")
    await db.commit()
    await deliver(request.app, notes)
    return await _public_profile(db, c)


# --- Suhbat taklifi -----------------------------------------------------------------------


class InvitationIn(BaseModel):
    slots: list[datetime] = Field(min_length=1, max_length=core.SLOT_MAX)
    mode: str = Field(default="offline", pattern="^(offline|online)$")
    place: str | None = Field(default=None, max_length=200)
    map_url: str | None = Field(default=None, max_length=300)
    contact_phone: str | None = Field(default=None, max_length=20)
    meeting_url: str | None = Field(default=None, max_length=300)


def _url_ok(u: str | None) -> str | None:
    u = (u or "").strip() or None
    if u and not u.lower().startswith(("http://", "https://")):
        raise error(400, "url_invalid")
    return u


@router.post("/applications/{aid}/invitation", status_code=201)
async def create_invitation(aid: int, body: InvitationIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Suhbatga taklif: nomzod havola orqali bo'sh vaqtni tanlaydi. Bitta vaqt berilsa suhbat darhol belgilanadi."""
    a = await _application(db, aid, lock=True)
    if a.stage in ("hired", "rejected"):
        raise error(409, "invalid_transition")
    moment = now()
    slots = core.clean_slots(body.slots, moment)
    for old in (await db.scalars(select(InterviewInvite).where(InterviewInvite.application_id == a.id, InterviewInvite.status.in_(("sent", "scheduled"))))).all():
        old.status = "cancelled"
    token = core.new_token()
    meeting = _url_ok(body.meeting_url) or (f"https://meet.jit.si/hrprofi-{token[:12]}" if body.mode == "online" else None)  # onlayn: havola avtomatik yaratiladi
    inv = InterviewInvite(application_id=a.id, token=token, slots=slots, mode=body.mode, place=(body.place or "").strip() or None, map_url=_url_ok(body.map_url), contact_phone=(body.contact_phone or "").strip() or None, meeting_url=meeting, created_by=auth.user.id)
    db.add(inv)
    first = datetime.fromisoformat(slots[0])
    if len(slots) == 1:
        inv.status, inv.chosen_at = "scheduled", first
        await rsvc.move(db, a, auth, "interview", inv.place, moment, interview_at=first)
    elif a.stage != "interview":
        a.stage_changed_at = moment
        rsvc.log(db, a, auth.user.id, "stage", frm=a.stage, to="interview", note="Suhbatga taklif yuborildi")
        a.stage = "interview"
    await db.flush()
    c, v = await db.get(Candidate, a.candidate_id), await db.get(Vacancy, a.vacancy_id)
    url = f"{_base_url(request)}/invite/{token}"
    text = f"📅 Suhbatga taklif: «{v.title if v else ''}». Vaqtni tanlang va javob bering: {url}"
    sent = await _tell(request, c, text)
    await audit(db, request, "recruit.invitation", actor=auth.user, entity="application", entity_id=a.id, data={"slots": len(slots), "telegram": sent})
    await db.commit()
    return {**core.invite_out(inv, url), "telegram_sent": sent}


@router.get("/applications/{aid}/invitation")
async def get_invitation(aid: int, request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    await _application(db, aid)
    inv = await db.scalar(select(InterviewInvite).where(InterviewInvite.application_id == aid).order_by(InterviewInvite.id.desc()).limit(1))
    return core.invite_out(inv, f"{_base_url(request)}/invite/{inv.token}") if inv else None


@router.post("/applications/{aid}/invitation/cancel")
async def cancel_invitation(aid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    await _application(db, aid, lock=True)
    n = 0
    for inv in (await db.scalars(select(InterviewInvite).where(InterviewInvite.application_id == aid, InterviewInvite.status.in_(("sent", "scheduled"))))).all():
        inv.status = "cancelled"
        n += 1
    await db.commit()
    return {"cancelled": n}


async def _invite_ctx(db: AsyncSession, token: str, *, lock: bool = False) -> tuple[InterviewInvite, Application, Candidate | None, Vacancy | None]:
    stmt = select(InterviewInvite).where(InterviewInvite.token == token[:24])
    inv = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not inv:
        raise error(404, "not_found")
    a = await db.get(Application, inv.application_id)
    return inv, a, await db.get(Candidate, a.candidate_id), await db.get(Vacancy, a.vacancy_id)  # type: ignore[union-attr, arg-type]


def _public_invite(inv: InterviewInvite, v: Vacancy | None, moment: datetime) -> dict[str, Any]:
    scheduled = inv.status == "scheduled"
    return {
        "status": inv.status, "vacancy": v.title if v else None, "salary_from": v.salary_from if v else None, "salary_to": v.salary_to if v else None, "mode": inv.mode, "place": inv.place, "map_url": inv.map_url,
        "contact_phone": inv.contact_phone, "meeting_url": inv.meeting_url if scheduled and inv.mode == "online" else None, "chosen_at": inv.chosen_at, "reply": inv.reply,
        "slots": [s for s in inv.slots or [] if datetime.fromisoformat(s) > moment] if inv.status in ("sent", "scheduled") else [],
    }  # fmt: skip


@public_router.get("/invite/{token}")
async def public_invite(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "invite_view", 120, 60)
    inv, _, _, v = await _invite_ctx(db, token)
    return _public_invite(inv, v, now())


class ChooseIn(BaseModel):
    slot: datetime


@public_router.post("/invite/{token}/choose")
async def public_invite_choose(token: str, body: ChooseIn, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "invite_write", 30, 60)
    inv, a, c, v = await _invite_ctx(db, token, lock=True)
    moment = now()
    if inv.status not in ("sent", "scheduled"):
        raise error(409, "invite_closed")
    slot = (body.slot if body.slot.tzinfo else body.slot.replace(tzinfo=core.tz())).isoformat()
    if slot not in (datetime.fromisoformat(s).isoformat() for s in inv.slots or []) or datetime.fromisoformat(slot) <= moment:
        raise error(400, "slot_invalid")
    inv.chosen_at, inv.status, inv.reply = datetime.fromisoformat(slot), "scheduled", None
    inv.reminded_day = inv.reminded_2h = False
    a.interview_at = inv.chosen_at  # type: ignore[union-attr]
    notes = await notify(db, [a.recruiter_id] if a.recruiter_id else [], "recruit.invite_chosen", params={"candidate": c.full_name if c else "", "when": core.when_text(inv.chosen_at)}, link=f"/recruit/applications/{a.id}")  # type: ignore[union-attr]
    await db.commit()
    await deliver(request.app, notes)
    return _public_invite(inv, v, moment)


class ReplyIn(BaseModel):
    answer: str = Field(pattern="^(coming|not_coming)$")


@public_router.post("/invite/{token}/reply")
async def public_invite_reply(token: str, body: ReplyIn, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "invite_write", 30, 60)
    inv, a, c, v = await _invite_ctx(db, token, lock=True)
    if inv.status not in ("sent", "scheduled"):
        raise error(409, "invite_closed")
    inv.reply, inv.replied_at = body.answer, now()
    if body.answer == "not_coming":
        inv.status = "declined"
    notes = await notify(db, [a.recruiter_id] if a.recruiter_id else [], "recruit.invite_reply", params={"candidate": c.full_name if c else "", "answer": "kelaman" if body.answer == "coming" else "kela olmayman"}, link=f"/recruit/applications/{a.id}")  # type: ignore[union-attr]
    await db.commit()
    await deliver(request.app, notes)
    return _public_invite(inv, v, now())


# --- Kanal yopish ------------------------------------------------------------------------


@router.post("/vacancies/{vid}/channels/{cid}/close")
async def close_channel(vid: int, cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    ch = await db.get(VacancyChannel, cid)
    if not ch or ch.vacancy_id != vid:
        raise error(404, "not_found")
    ch.closed_at = ch.closed_at or now()
    await db.commit()
    return {"id": ch.id, "closed_at": ch.closed_at}


# --- Rekruter kunlik ekrani va voronka -----------------------------------------------------


@router.get("/my-day")
async def my_day(recruiter_id: int | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    """Rekruter tizimga kirganda birinchi ko'radigan chek-list: vakansiyalar, e'lon qo'yilmaganlari, qayta qo'ng'iroqlar, suhbatlar, muddat."""
    uid = auth.user.id
    if recruiter_id and recruiter_id != uid:
        if not matches(auth.permissions, "recruit.manage"):
            raise error(403, "forbidden")
        uid = recruiter_id
    return await core.my_day(db, uid, now())


@router.get("/funnel")
async def funnel(vacancy_id: int | None = None, start: date | None = None, end: date | None = None, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    if start and end and (end < start or (end - start).days > 800):
        raise error(400, "range_invalid", max_days=800)
    return await core.funnel(db, vacancy_id=vacancy_id, start=start, end=end)
