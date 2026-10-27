"""Nomzodlar va ish o'rinlari: pipeline holatlari, matndan to'ldirish, voronka, xodimga aylantirish."""

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.auth import User
from app.models.recruit import Application, ApplicationEvent, Candidate, Vacancy
from app.rbac import matches
from app.services.notifications import notify, register_template
from app.timeutil import tz

STAGES = ("new", "screening", "interview", "offer", "hired", "rejected")
OPEN_STAGES = ("new", "screening", "interview", "offer")
MOVABLE = ("new", "screening", "interview", "offer")
SOURCES = ("walk_in", "referral", "telegram", "olx", "hh", "social", "other")

register_template("recruit.new_application", {"uz": "Yangi nomzod arizasi", "ru": "Новый отклик кандидата"}, {"uz": "{candidate} → {vacancy}", "ru": "{candidate} → {vacancy}"}, "info")
register_template("recruit.hired", {"uz": "Nomzod ishga olindi", "ru": "Кандидат принят на работу"}, {"uz": "{candidate}: {vacancy}", "ru": "{candidate}: {vacancy}"}, "success")
register_template("recruit.assigned", {"uz": "Sizga vakansiya biriktirildi", "ru": "Вам назначена вакансия"}, {"uz": "{vacancy}", "ru": "{vacancy}"}, "info")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


# --- Matndan to'ldirish (qoidaga asoslangan; LLM keyingi fazada ulanadi) -------------------

PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\(?\d{2}\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
LABEL = {
    "name": r"(?:f\.?\s?i\.?\s?sh\.?|ФИО|full\s*name|name|ism|имя)",
    "address": r"(?:manzil|address|адрес)",
    "skills": r"(?:ko[’'`]?nikmalar|skills|навыки|malaka)",
    "birth": r"(?:tug[’'`]?ilgan|birth|born|дата рождения|рожд)",
}
KNOWN_SKILLS = ("excel", "word", "1c", "1с", "farmatsevt", "kassir", "savdo", "ingliz", "rus", "ofitsiant", "haydovchi", "kompyuter", "mijozlar", "ombor", "buxgalter")


def _label_value(text: str, key: str) -> str | None:
    m = re.search(rf"(?im)^\s*[•\-*]?\s*{LABEL[key]}\s*[:\-–]\s*(.+)$", text)
    return m.group(1).strip() if m else None


def parse_resume(text: str) -> dict[str, Any]:
    """Rezyume matnidan ism, telefon, email, tug'ilgan sana, manzil, ko'nikmalarni ajratadi."""
    from app.services.employees import normalize_phone

    out: dict[str, Any] = {}
    name = _label_value(text, "name")
    if not name:
        for line in text.splitlines():
            line = line.strip(" \t•-*")
            words = line.split()
            if 2 <= len(words) <= 4 and all(w.replace("'", "").replace("’", "").replace(".", "").isalpha() for w in words) and len(line) <= 60:
                name = line
                break
    if name:
        out["full_name"] = " ".join(w.capitalize() if w.islower() else w for w in name.split())[:250]
    for m in PHONE_RE.finditer(text):
        try:
            phone = normalize_phone(m.group(0))
        except ValueError:
            continue
        if phone:
            out["phone"] = phone
            break
    if m := EMAIL_RE.search(text):
        out["email"] = m.group(0).lower()
    birth_src = _label_value(text, "birth") or text
    for m in DATE_RE.finditer(birth_src):
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m.group(1) else date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
        except ValueError:
            continue
        if 1940 <= d.year <= date.today().year - 14:
            out["birth_date"] = d.isoformat()
            break
    if addr := _label_value(text, "address"):
        out["address"] = addr[:300]
    skills: list[str] = []
    if line := _label_value(text, "skills"):
        skills += [s.strip() for s in re.split(r"[,;•]", line) if s.strip()]
    low = text.lower()
    skills += [k for k in KNOWN_SKILLS if k in low and not any(k in s.lower() for s in skills)]
    if skills:
        out["skills"] = list(dict.fromkeys(s[:40] for s in skills))[:20]
    return out


# --- Natija ------------------------------------------------------------------------------


async def names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    if not ids2:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()}


def candidate_out(c: Candidate) -> dict[str, Any]:
    return {"id": c.id, "full_name": c.full_name, "phone": c.phone, "email": c.email, "birth_date": c.birth_date, "address": c.address, "source": c.source, "skills": c.skills or [], "note": c.note}


def log(db: AsyncSession, a: Application, actor_id: int | None, action: str, *, frm: str | None = None, to: str | None = None, note: str | None = None, data: dict | None = None) -> None:
    db.add(ApplicationEvent(application_id=a.id, actor_id=actor_id, action=action, from_stage=frm, to_stage=to, note=note, data=data))


async def funnel(db: AsyncSession, vacancy_id: int | None = None) -> dict[str, int]:
    stmt = select(Application.stage, func.count()).group_by(Application.stage)
    if vacancy_id:
        stmt = stmt.where(Application.vacancy_id == vacancy_id)
    got = dict((await db.execute(stmt)).all())
    return {s: got.get(s, 0) for s in STAGES}


async def move(db: AsyncSession, a: Application, auth: AuthContext, stage: str, note: str | None, moment: datetime, *, interview_at: datetime | None = None, rating: int | None = None) -> None:
    if a.stage in ("hired", "rejected"):
        raise error(409, "invalid_transition")
    if stage not in MOVABLE:
        raise error(400, "stage_invalid")
    if stage == "interview" and not (interview_at or a.interview_at):
        raise error(400, "interview_time_required")
    if stage != a.stage:
        log(db, a, auth.user.id, "stage", frm=a.stage, to=stage, note=(note or "").strip() or None)
        a.stage, a.stage_changed_at = stage, moment
    if interview_at is not None:
        a.interview_at = interview_at
    if rating is not None and rating != a.rating:
        log(db, a, auth.user.id, "rating", data={"from": a.rating, "to": rating})
        a.rating = rating


async def reject(db: AsyncSession, a: Application, auth: AuthContext, reason: str, moment: datetime) -> None:
    if a.stage in ("hired", "rejected"):
        raise error(409, "invalid_transition")
    log(db, a, auth.user.id, "rejected", frm=a.stage, to="rejected", note=reason.strip())
    a.stage, a.reject_reason, a.stage_changed_at = "rejected", reason.strip(), moment


async def reopen(db: AsyncSession, a: Application, auth: AuthContext, moment: datetime) -> None:
    if a.stage != "rejected":
        raise error(409, "invalid_transition")
    log(db, a, auth.user.id, "reopened", frm="rejected", to="screening")
    a.stage, a.reject_reason, a.stage_changed_at = "screening", None, moment


def split_name(full: str) -> tuple[str, str, str | None]:
    """"Familiya Ism Otasining ismi" -> (familiya, ism, otasi). Bitta so'z bo'lsa ism bo'sh qoladi."""
    parts = full.split()
    if len(parts) == 1:
        return parts[0], "", None
    return parts[0], parts[1], " ".join(parts[2:]) or None


async def notify_new(db: AsyncSession, v: Vacancy, c: Candidate, exclude: int | None):
    targets = [u for u in {v.recruiter_id} if u and u != exclude]
    return await notify(db, targets, "recruit.new_application", link=f"/recruit/vacancies/{v.id}", params={"candidate": c.full_name, "vacancy": v.title})


def local_dt(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=tz())
