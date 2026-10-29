"""Rekruting yadrosi (F48): lavozim kompetensiya kartochkasi, telefon egaligi, takroriy nomzod, birlashgan profil,
moslik bali, suhbat taklifi (vaqt tanlash, eslatma), vakansiya SLA, rekruter kunlik ekrani va voronka."""

import re
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import error
from app.models.recruit import (
    Application,
    ApplicationEvent,
    Candidate,
    CandidateFile,
    CandidatePhone,
    InterviewInvite,
    PositionRequirement,
    RecruitCall,
    Vacancy,
    VacancyChannel,
)
from app.services import growth
from app.services import recruit as rsvc
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template
from app.timeutil import local_date, tz

REJECT_CODES = ("no_answer", "not_suitable", "declined", "salary", "schedule", "no_show", "failed_test", "failed_background", "hired_elsewhere", "other")
RANK = {"new": 0, "screening": 1, "interview": 2, "offer": 3, "hired": 4}
SLOT_MAX = 5

register_template("recruit.sla_warn", {"uz": "Vakansiya muddati yaqin", "ru": "Срок вакансии близок"}, {"uz": "{vacancy}: muddat {deadline} (qoldi {days} kun)", "ru": "{vacancy}: срок {deadline} (осталось {days} дн.)"}, "warning")
register_template("recruit.sla_overdue", {"uz": "Vakansiya muddati o'tdi", "ru": "Срок вакансии истёк"}, {"uz": "{vacancy}: muddat {deadline} edi", "ru": "{vacancy}: срок был {deadline}"}, "danger")
register_template("recruit.close_ads", {"uz": "E'lonlarni o'chiring", "ru": "Снимите объявления"}, {"uz": "«{vacancy}» yopildi: {count} ta kanalda e'lon turibdi", "ru": "«{vacancy}» закрыта: объявлений в каналах — {count}"}, "warning")
register_template("recruit.match_ok", {"uz": "Nomzod mos keldi", "ru": "Кандидат подходит"}, {"uz": "{candidate}: moslik {score}% («{vacancy}»). Suhbatga taklif qiling.", "ru": "{candidate}: соответствие {score}% («{vacancy}»). Пригласите на собеседование."}, "success")
register_template("recruit.invite_chosen", {"uz": "Nomzod suhbat vaqtini tanladi", "ru": "Кандидат выбрал время собеседования"}, {"uz": "{candidate}: {when}", "ru": "{candidate}: {when}"}, "info")
register_template("recruit.invite_reply", {"uz": "Nomzod suhbatga javob berdi", "ru": "Кандидат ответил по собеседованию"}, {"uz": "{candidate}: {answer}", "ru": "{candidate}: {answer}"}, "info")


# --- Kompetensiya kartochkasi ----------------------------------------------------------


def clean_card(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}

    def lst(key: str, cap: int = 30) -> list[str]:
        return list(dict.fromkeys(str(x).strip()[:80] for x in (raw.get(key) or []) if str(x).strip()))[:cap]

    exp = raw.get("min_experience")
    qs = list(dict.fromkeys(str(x).strip()[:300] for x in (raw.get("questions") or []) if str(x).strip()))[:30]
    return {
        "questions": qs,
        "duties": (str(raw.get("duties") or "").strip()[:3000]) or None, "hard_skills": lst("hard_skills"), "soft_skills": lst("soft_skills"), "languages": lst("languages", 10),
        "education": (str(raw.get("education") or "").strip()[:200]) or None, "min_experience": int(exp) if isinstance(exp, int | float) and 0 <= exp <= 50 else None, "exclusions": lst("exclusions"),
    }  # fmt: skip


def card_text(card: dict[str, Any]) -> str:
    """Tuzilgan kartochkadan vakansiya «Talablar» matni (vakansiya ochilganda avtomatik to'ldiriladi)."""
    lines: list[str] = []
    if card.get("education"):
        lines.append(f"Ma'lumot: {card['education']}")
    if card.get("min_experience"):
        lines.append(f"Tajriba: kamida {card['min_experience']} yil")
    if card.get("hard_skills"):
        lines.append("Kasbiy ko'nikmalar: " + ", ".join(card["hard_skills"]))
    if card.get("soft_skills"):
        lines.append("Shaxsiy sifatlar: " + ", ".join(card["soft_skills"]))
    if card.get("languages"):
        lines.append("Tillar: " + ", ".join(card["languages"]))
    return "\n".join(lines)


def snapshot(r: PositionRequirement) -> dict[str, Any]:
    return {"requirements": r.requirements, "competencies": r.competencies or [], "ad_template": r.ad_template, "profile": r.profile or {}}


# --- Telefon egaligi va takroriy nomzod ------------------------------------------------


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^\w']+", name.lower().replace("’", "'").replace("`", "'")) if len(t) >= 3}


def same_person(a: str, b: str) -> bool:
    """Ismlar mos kelsa (kamida bitta umumiy so'z, masalan familiya) — bir shaxs deb hisoblanadi."""
    ta, tb = _tokens(a), _tokens(b)
    return not ta or not tb or bool(ta & tb)


async def phone_owner(db: AsyncSession, phone: str, exclude_id: int | None = None) -> Candidate | None:
    stmt = select(Candidate).where(Candidate.phone == phone)
    if exclude_id:
        stmt = stmt.where(Candidate.id != exclude_id)
    return await db.scalar(stmt.limit(1))


async def assign_phone(db: AsyncSession, cand: Candidate, phone: str | None, moment: datetime) -> None:
    """Raqamni nomzodga biriktiradi. Boshqa shaxs egalik qilgan bo'lsa, eski egasining egaligi tarixda yopiladi."""
    if not phone or cand.phone == phone and await db.scalar(select(CandidatePhone.id).where(CandidatePhone.candidate_id == cand.id, CandidatePhone.phone == phone, CandidatePhone.ended_at.is_(None))):
        return
    for old in (await db.scalars(select(Candidate).where(Candidate.phone == phone, Candidate.id != cand.id))).all():
        for h in (await db.scalars(select(CandidatePhone).where(CandidatePhone.candidate_id == old.id, CandidatePhone.phone == phone, CandidatePhone.ended_at.is_(None)))).all():
            h.ended_at = moment
        old.phone = None
    if cand.phone and cand.phone != phone:
        for h in (await db.scalars(select(CandidatePhone).where(CandidatePhone.candidate_id == cand.id, CandidatePhone.phone == cand.phone, CandidatePhone.ended_at.is_(None)))).all():
            h.ended_at = moment
    cand.phone = phone
    db.add(CandidatePhone(candidate_id=cand.id, phone=phone, started_at=moment))


async def phone_history(db: AsyncSession, phone: str) -> list[dict[str, Any]]:
    rows = (await db.execute(select(CandidatePhone, Candidate).join(Candidate, Candidate.id == CandidatePhone.candidate_id).where(CandidatePhone.phone == phone).order_by(CandidatePhone.started_at.desc()))).all()
    return [{"candidate": {"id": c.id, "full_name": c.full_name}, "started_at": h.started_at, "ended_at": h.ended_at, "current": h.ended_at is None} for h, c in rows]


async def merge_candidates(db: AsyncSession, primary: Candidate, secondary_ids: list[int], moment: datetime) -> dict[str, int]:
    """Takroriy kartochkalarni birlashtiradi: ariza, fayl, qo'ng'iroq va telefon tarixi asosiy kartochkaga ko'chadi."""
    moved = {"applications": 0, "files": 0, "calls": 0, "skipped_applications": 0}
    for sid in dict.fromkeys(secondary_ids):
        if sid == primary.id:
            raise error(400, "merge_self")
        sec = await db.get(Candidate, sid)
        if not sec:
            raise error(404, "not_found")
        have = set((await db.scalars(select(Application.vacancy_id).where(Application.candidate_id == primary.id))).all())
        for a in (await db.scalars(select(Application).where(Application.candidate_id == sid))).all():
            if a.vacancy_id in have:
                moved["skipped_applications"] += 1
                await db.delete(a)  # bir vakansiyaga ikki marta: asosiy kartochkadagisi qoladi
            else:
                a.candidate_id = primary.id
                have.add(a.vacancy_id)
                moved["applications"] += 1
        for f in (await db.scalars(select(CandidateFile).where(CandidateFile.candidate_id == sid))).all():
            f.candidate_id = primary.id
            moved["files"] += 1
        for c in (await db.scalars(select(RecruitCall).where(RecruitCall.candidate_id == sid))).all():
            c.candidate_id = primary.id
            moved["calls"] += 1
        for h in (await db.scalars(select(CandidatePhone).where(CandidatePhone.candidate_id == sid))).all():
            h.candidate_id = primary.id
        if sec.phone and not primary.phone:
            primary.phone = sec.phone
        for fld in ("email", "birth_date", "address", "pinfl", "source", "telegram_chat_id"):
            if not getattr(primary, fld) and getattr(sec, fld):
                if fld == "telegram_chat_id":
                    chat, sec.telegram_chat_id = sec.telegram_chat_id, None
                    await db.flush()
                    primary.telegram_chat_id = chat
                else:
                    setattr(primary, fld, getattr(sec, fld))
        primary.skills = list(dict.fromkeys([*(primary.skills or []), *(sec.skills or [])]))[:30]
        if sec.resume_text and not primary.resume_text:
            primary.resume_text = sec.resume_text
        primary.profile = {**(sec.profile or {}), **(primary.profile or {})}
        sec.phone = None
        await db.flush()
        await db.delete(sec)
    return moved


# --- Birlashgan profil va moslik bali --------------------------------------------------

PROFILE_FIELDS = ("full_name", "phone", "birth_date", "address", "email", "region", "experience", "expected_salary", "languages", "skills", "about")


async def build_profile(db: AsyncSession, c: Candidate) -> dict[str, Any]:
    """Nomzod ma'lumotlari manbalardan birlashtiriladi: anketa > kartochka > rezyume matni > qo'ng'iroq izohlari. Har maydon manbasi ko'rsatiladi."""
    fields: dict[str, Any] = {}
    sources: dict[str, str] = {}

    def put(key: str, value: Any, src: str) -> None:
        if value in (None, "", [], {}) or key in fields:
            return
        fields[key], sources[key] = value, src

    anketa = c.profile or {}
    for k in PROFILE_FIELDS:
        put(k, anketa.get(k), "anketa")
    cols = {"full_name": c.full_name, "phone": c.phone, "birth_date": c.birth_date.isoformat() if c.birth_date else None, "address": c.address, "email": c.email, "skills": c.skills}
    for k, v in cols.items():
        put(k, v, "kartochka")
    if c.resume_text:
        for k, v in rsvc.parse_resume(c.resume_text).items():
            put(k, v, "rezyume")
    notes = [n for (n,) in (await db.execute(select(RecruitCall.note).where(RecruitCall.candidate_id == c.id, RecruitCall.note.is_not(None)).order_by(RecruitCall.id.desc()).limit(5))).all()]
    if notes:
        blob = " ".join(notes)
        for k, v in rsvc.parse_resume(blob).items():
            put(k, v, "qo'ng'iroq")
        m = re.search(r"(\d{1,2})\s*(?:yil|год|года|лет)", blob.lower())
        if m:
            put("experience", f"{m.group(1)} yil", "qo'ng'iroq")
        m = re.search(r"(\d[\d\s]{4,})\s*(?:so'm|sum|сум)", blob.lower())
        if m:
            put("expected_salary", int(re.sub(r"\s+", "", m.group(1))), "qo'ng'iroq")
    return {"fields": fields, "sources": sources, "confirmed_at": c.profile_confirmed_at}


def _years(text: Any) -> int | None:
    if isinstance(text, int | float):
        return int(text)
    m = re.search(r"(\d{1,2})", str(text or ""))
    return int(m.group(1)) if m else None


def score_match(fields: dict[str, Any], resume_text: str | None, card: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    """Kartochkaga moslik (0-100). Jins/yosh/millat/din hisobga olinmaydi. Istisno mezoni topilsa ball 0 va `excluded`."""
    if not card or not any(card.get(k) for k in ("hard_skills", "languages", "min_experience", "exclusions")):
        return None, {}
    blob = " ".join([str(resume_text or ""), " ".join(fields.get("skills") or []), str(fields.get("experience") or ""), str(fields.get("about") or "")]).lower()
    parts: list[dict[str, Any]] = []
    excluded = [x for x in card.get("exclusions") or [] if x.lower() in blob]
    if card.get("hard_skills"):
        hit = [s for s in card["hard_skills"] if s.lower() in blob]
        parts.append({"key": "hard_skills", "weight": 50, "ratio": len(hit) / len(card["hard_skills"]), "hit": hit, "miss": [s for s in card["hard_skills"] if s not in hit]})
    if card.get("languages"):
        langs = " ".join(fields.get("languages") or []).lower() + " " + blob
        hit = [x for x in card["languages"] if x.lower() in langs]
        parts.append({"key": "languages", "weight": 15, "ratio": len(hit) / len(card["languages"]), "hit": hit, "miss": [x for x in card["languages"] if x not in hit]})
    if card.get("min_experience"):
        yrs = _years(fields.get("experience"))
        parts.append({"key": "experience", "weight": 25, "ratio": 0.0 if yrs is None else min(1.0, yrs / card["min_experience"]), "have": yrs, "need": card["min_experience"]})
    filled = sum(1 for k in ("phone", "address", "experience", "skills", "expected_salary") if fields.get(k))
    parts.append({"key": "profile", "weight": 10, "ratio": filled / 5})
    total = sum(p["weight"] for p in parts)
    score = 0 if excluded else round(sum(p["weight"] * p["ratio"] for p in parts) / total * 100)
    return score, {"parts": [{k: v for k, v in p.items() if k != "weight"} | {"weight": p["weight"]} for p in parts], "excluded": excluded}


async def rescore(db: AsyncSession, a: Application) -> int | None:
    v = await db.get(Vacancy, a.vacancy_id)
    c = await db.get(Candidate, a.candidate_id)
    req = await db.scalar(select(PositionRequirement).where(PositionRequirement.position_id == v.position_id)) if v and v.position_id else None
    if not c or not req:
        a.match_score, a.match_detail = None, None
        return None
    prof = await build_profile(db, c)
    a.match_score, a.match_detail = score_match(prof["fields"], c.resume_text, req.profile or {})
    return a.match_score


# --- Suhbat taklifi --------------------------------------------------------------------


def new_token() -> str:
    return secrets.token_urlsafe(14)[:20]


def clean_slots(slots: list[datetime], moment: datetime) -> list[str]:
    out = []
    for s in sorted({(x if x.tzinfo else x.replace(tzinfo=tz())).isoformat() for x in slots}):
        if datetime.fromisoformat(s) <= moment:
            raise error(400, "slot_in_past")
        out.append(s)
    if not out or len(out) > SLOT_MAX:
        raise error(400, "slots_invalid", max=SLOT_MAX)
    return out


def invite_out(i: InterviewInvite, url: str | None = None) -> dict[str, Any]:
    return {
        "id": i.id, "status": i.status, "mode": i.mode, "slots": i.slots or [], "place": i.place, "map_url": i.map_url, "contact_phone": i.contact_phone, "meeting_url": i.meeting_url,
        "chosen_at": i.chosen_at, "reply": i.reply, "replied_at": i.replied_at, "created_at": i.created_at, "url": url,
    }  # fmt: skip


def when_text(dt: datetime) -> str:
    return dt.astimezone(tz()).strftime("%d.%m.%Y %H:%M")


async def reminder_scan(db: AsyncSession, moment: datetime) -> list[tuple[int, str]]:
    """Belgilangan suhbatlar uchun 1 kun va 2 soat oldin nomzodga eslatma (Telegram) — [(chat_id, matn)]."""
    out: list[tuple[int, str]] = []
    rows = (await db.scalars(select(InterviewInvite).where(InterviewInvite.status == "scheduled", InterviewInvite.chosen_at.is_not(None), InterviewInvite.chosen_at > moment, InterviewInvite.reply.is_distinct_from("not_coming")))).all()
    for i in rows:
        left = i.chosen_at - moment  # type: ignore[operator]
        due_day = left <= timedelta(hours=24) and not i.reminded_day
        due_2h = left <= timedelta(hours=2) and not i.reminded_2h
        if not (due_day or due_2h):
            continue
        a = await db.get(Application, i.application_id)
        c = await db.get(Candidate, a.candidate_id) if a else None
        v = await db.get(Vacancy, a.vacancy_id) if a else None
        if due_day:
            i.reminded_day = True
        if due_2h:
            i.reminded_day = i.reminded_2h = True
        if c and c.telegram_chat_id and v:
            where = i.meeting_url if i.mode == "online" and i.meeting_url else (i.place or "")
            kind = "2 soatdan keyin" if due_2h else "ertaga"
            out.append((c.telegram_chat_id, f"⏰ Suhbat {kind}: «{v.title}», {when_text(i.chosen_at)}. {where}".strip()))  # type: ignore[arg-type]
    return out


# --- SLA --------------------------------------------------------------------------------


async def sla_scan(db: AsyncSession, moment: datetime) -> list:
    cfg = await growth.get_setting(db, "recruit")
    today = local_date(moment)
    notes: list = []
    managers = await users_with_permission(db, "recruit.manage")
    for v in (await db.scalars(select(Vacancy).where(Vacancy.status == "open", Vacancy.deadline.is_not(None)))).all():
        targets = list(dict.fromkeys([u for u in (v.recruiter_id, *managers) if u]))
        left = (v.deadline - today).days  # type: ignore[operator]
        params = {"vacancy": v.title, "deadline": f"{v.deadline:%d.%m.%Y}", "days": left}
        if left < 0 and v.sla_overdue_at is None:
            v.sla_overdue_at = moment
            notes += await notify(db, targets, "recruit.sla_overdue", params=params, link=f"/recruit/vacancies/{v.id}")
        elif 0 <= left <= cfg["warn_days"] and v.sla_warned_at is None:
            v.sla_warned_at = moment
            notes += await notify(db, targets, "recruit.sla_warn", params=params, link=f"/recruit/vacancies/{v.id}")
    return notes


async def close_ads_notice(db: AsyncSession, v: Vacancy) -> list:
    n = await db.scalar(select(func.count()).select_from(VacancyChannel).where(VacancyChannel.vacancy_id == v.id, VacancyChannel.closed_at.is_(None))) or 0
    if n and v.recruiter_id:
        return await notify(db, [v.recruiter_id], "recruit.close_ads", params={"vacancy": v.title, "count": n}, link=f"/recruit/vacancies/{v.id}/promo")
    return []


# --- Rekruter kunlik ekrani va voronka -------------------------------------------------


async def my_day(db: AsyncSession, recruiter_id: int, moment: datetime) -> dict[str, Any]:
    today = local_date(moment)
    start = datetime.combine(today, datetime.min.time(), tzinfo=tz())
    end = start + timedelta(days=1)
    vacs = list((await db.scalars(select(Vacancy).where(Vacancy.status == "open", Vacancy.recruiter_id == recruiter_id).order_by(Vacancy.deadline.asc().nulls_last()))).all())
    ch = dict((await db.execute(select(VacancyChannel.vacancy_id, func.count()).where(VacancyChannel.vacancy_id.in_([v.id for v in vacs]), VacancyChannel.closed_at.is_(None)).group_by(VacancyChannel.vacancy_id))).all()) if vacs else {}
    cnt = dict((await db.execute(select(Application.vacancy_id, func.count()).where(Application.vacancy_id.in_([v.id for v in vacs]), Application.stage.in_(rsvc.OPEN_STAGES)).group_by(Application.vacancy_id))).all()) if vacs else {}
    vrows = [{"id": v.id, "title": v.title, "deadline": v.deadline, "days_left": (v.deadline - today).days if v.deadline else None, "channels": ch.get(v.id, 0), "open_applications": cnt.get(v.id, 0)} for v in vacs]
    calls_today = await db.scalar(select(func.count()).select_from(RecruitCall).where(RecruitCall.recruiter_id == recruiter_id, RecruitCall.called_at >= start, RecruitCall.called_at < end)) or 0
    cb = (await db.execute(select(RecruitCall, Candidate).outerjoin(Candidate, Candidate.id == RecruitCall.candidate_id).where(RecruitCall.recruiter_id == recruiter_id, RecruitCall.outcome == "callback", RecruitCall.callback_date <= today).order_by(RecruitCall.callback_date).limit(30))).all()
    ivs = (await db.execute(select(Application, Candidate, Vacancy).join(Candidate, Candidate.id == Application.candidate_id).join(Vacancy, Vacancy.id == Application.vacancy_id).where(Application.recruiter_id == recruiter_id, Application.stage == "interview", Application.interview_at >= start, Application.interview_at < end + timedelta(days=1)).order_by(Application.interview_at))).all()
    offers = (await db.execute(select(Application, Candidate, Vacancy).join(Candidate, Candidate.id == Application.candidate_id).join(Vacancy, Vacancy.id == Application.vacancy_id).where(Application.recruiter_id == recruiter_id, Application.offer_status == "approved", Application.offer_sent_at.is_not(None), Application.stage == "offer"))).all()
    new_apps = (await db.execute(select(Application, Candidate, Vacancy).join(Candidate, Candidate.id == Application.candidate_id).join(Vacancy, Vacancy.id == Application.vacancy_id).where(Application.recruiter_id == recruiter_id, Application.stage == "new").order_by(Application.applied_at.desc()).limit(20))).all()
    return {
        "date": today, "calls_today": calls_today,
        "vacancies": vrows, "without_ads": [v for v in vrows if v["channels"] == 0], "expiring": [v for v in vrows if v["days_left"] is not None and v["days_left"] <= 3],
        "callbacks": [{"call_id": c.id, "candidate": {"id": cand.id, "name": cand.full_name} if cand else None, "phone": c.phone, "date": c.callback_date, "overdue": bool(c.callback_date and c.callback_date < today)} for c, cand in cb],
        "interviews": [{"application_id": a.id, "candidate": cand.full_name, "vacancy": v.title, "at": a.interview_at, "today": a.interview_at is not None and a.interview_at < end} for a, cand, v in ivs],
        "offers_waiting": [{"application_id": a.id, "candidate": cand.full_name, "vacancy": v.title, "sent_at": a.offer_sent_at} for a, cand, v in offers],
        "new_applications": [{"application_id": a.id, "candidate": cand.full_name, "vacancy": v.title, "match": a.match_score, "applied_at": a.applied_at} for a, cand, v in new_apps],
    }  # fmt: skip


async def funnel(db: AsyncSession, *, vacancy_id: int | None, start: date | None, end: date | None) -> dict[str, Any]:
    """Voronka: har bosqichga yetgan arizalar soni va o'tish foizi; rad etish sabablari toifalar bo'yicha."""
    stmt = select(Application)
    if vacancy_id:
        stmt = stmt.where(Application.vacancy_id == vacancy_id)
    if start:
        stmt = stmt.where(Application.applied_at >= datetime.combine(start, datetime.min.time(), tzinfo=tz()))
    if end:
        stmt = stmt.where(Application.applied_at < datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz()))
    apps = list((await db.scalars(stmt.limit(5000))).all())
    ids = [a.id for a in apps]
    best: dict[int, int] = {a.id: RANK.get(a.stage, 0) for a in apps}
    if ids:
        for aid, frm, to in (await db.execute(select(ApplicationEvent.application_id, ApplicationEvent.from_stage, ApplicationEvent.to_stage).where(ApplicationEvent.application_id.in_(ids), ApplicationEvent.action.in_(("stage", "rejected", "hired"))))).all():
            for s in (frm, to):
                if s in RANK:
                    best[aid] = max(best[aid], RANK[s])
    labels = ("new", "screening", "interview", "offer", "hired")
    counts = [sum(1 for a in apps if best[a.id] >= RANK[s]) for s in labels]
    steps = [{"stage": s, "count": counts[i], "rate": round(counts[i] / counts[i - 1] * 100) if i and counts[i - 1] else None} for i, s in enumerate(labels)]
    reasons: dict[str, int] = defaultdict(int)
    for a in apps:
        if a.stage == "rejected":
            reasons[a.reject_code or "other"] += 1
    return {"total": len(apps), "steps": steps, "rejected": sum(reasons.values()), "reasons": [{"code": k, "count": v} for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])]}
