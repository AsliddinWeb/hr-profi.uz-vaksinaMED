"""Zayafka -> vakansiya, lavozim talablari, e'lon matni, kanal va shaxsiy manba linklari."""

import secrets
import string
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.org import Branch
from app.models.pharmacy import StaffNeed
from app.models.recruit import Application, Candidate, PositionRequirement, SourceLink, Vacancy
from app.services import recruit as rsvc
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template

CHANNELS = ("hh_uz", "olx", "telegram", "site", "instagram", "billboard", "target", "referral", "other")
CHANNEL_RE = "^(" + "|".join(CHANNELS) + ")$"
ROLE_UZ = {"manager": "Filial mudiri", "pharmacist": "Farmasevt", "intern": "Stajyor", "other": "Xodim"}
REASONS = "departure|new_branch|workload|other"

DEFAULT_AD = (
    "📢 Vakansiya: {title}\n"
    "📍 Filial: {branch}\n"
    "{salary}"
    "\n✅ Talablar:\n{requirements}\n"
    "\n📝 Ariza qoldirish: {link}"
)

register_template(
    "need.review",
    {"uz": "Zayafka HRD tasdig'ini kutmoqda", "ru": "Заявка ждёт утверждения HRD"},
    {"uz": "{branch}: {role} × {count}", "ru": "{branch}: {role} × {count}"},
    "info",
)
register_template(
    "need.decided",
    {"uz": "Zayafka bo'yicha qaror", "ru": "Решение по заявке"},
    {"uz": "{branch}: {role} × {count} — {result}. {note}", "ru": "{branch}: {role} × {count} — {result}. {note}"},
    "info",
)
register_template(
    "need.vacancy",
    {"uz": "Yangi vakansiya ochildi", "ru": "Открыта новая вакансия"},
    {"uz": "{title}", "ru": "{title}"},
    "success",
)


def branch_label(b: Branch | None) -> str:
    return (f"№{b.number} {b.name}" if b.number else b.name) if b else "—"


def new_code() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def apply_url(code: str) -> str:
    base = (get_settings().public_url or "").rstrip("/")
    return f"{base}/apply/{code}"


def ad_text(v: Vacancy, branch: Branch | None, requirement: PositionRequirement | None, link: str) -> str:
    salary = ""
    if v.salary_from or v.salary_to:
        lo, hi = (f"{v.salary_from:,}".replace(",", " ") if v.salary_from else None), (f"{v.salary_to:,}".replace(",", " ") if v.salary_to else None)
        salary = "💰 Maosh: " + (f"{lo} – {hi}" if lo and hi else f"{lo or hi}") + " so'm\n"
    reqs = (v.requirements or (requirement.requirements if requirement else None) or "—").strip()
    template = (requirement.ad_template if requirement and requirement.ad_template else DEFAULT_AD)
    values = {"title": v.title, "branch": branch_label(branch), "salary": salary, "requirements": reqs, "link": link}
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return DEFAULT_AD.format(**values)


async def requirement_for(db: AsyncSession, position_id: int | None) -> PositionRequirement | None:
    if not position_id:
        return None
    return await db.scalar(select(PositionRequirement).where(PositionRequirement.position_id == position_id))


async def vacancy_from_need(db: AsyncSession, need: StaffNeed, branch: Branch, actor_id: int, moment: datetime, recruiter_id: int | None = None) -> tuple[Vacancy, list]:
    """HRD tasdiqlagan zayafkadan ochiq vakansiya yaratadi, rekruterlarga xabar beradi."""
    req = await requirement_for(db, need.position_id)
    v = Vacancy(
        title=f"{ROLE_UZ.get(need.role, 'Xodim')} — {branch_label(branch)}", branch_id=branch.id, position_id=need.position_id,
        requirements=req.requirements if req else None, openings=need.count, status="open", recruiter_id=recruiter_id,
        deadline=need.needed_from, opened_at=moment, created_by=actor_id,
    )  # fmt: skip
    db.add(v)
    await db.flush()
    need.vacancy_id = v.id
    targets = [recruiter_id] if recruiter_id else await users_with_permission(db, "recruit.manage")
    notes = await notify(db, [t for t in targets if t], "need.vacancy", params={"title": v.title}, link=f"/recruit/vacancies/{v.id}/promo")
    return v, notes


async def unique_code(db: AsyncSession) -> str:
    for _ in range(10):
        code = new_code()
        if not await db.scalar(select(SourceLink.id).where(SourceLink.code == code)):
            return code
    raise RuntimeError("code_collision")  # amalda bo'lmaydi: 36^8 ta variant


def link_out(link: SourceLink, owner: str | None, apps: int = 0, hired: int = 0) -> dict[str, Any]:
    return {
        "id": link.id, "code": link.code, "url": apply_url(link.code), "channel": link.channel, "label": link.label,
        "owner": {"id": link.owner_user_id, "name": owner} if link.owner_user_id else None,
        "clicks": link.clicks, "applications": apps, "hired": hired, "is_active": link.is_active,
    }  # fmt: skip


async def submit_application(db: AsyncSession, lk: SourceLink, v: Vacancy, *, full_name: str, phone: str | None, note: str | None, chat_id: int | None, moment: datetime) -> tuple[str, Candidate | None, list]:
    """Havola orqali ariza (sayt yoki Telegram bot): nomzod (telefon bo'yicha takrorlanmaydi) + ariza + rekruterga xabar.
    ('ok' | 'duplicate', nomzod, bildirishnomalar) qaytaradi."""
    from sqlalchemy.exc import IntegrityError  # noqa: PLC0415

    cand = await db.scalar(select(Candidate).where(Candidate.phone == phone)) if phone else None
    if cand is None:
        cand = Candidate(full_name=full_name.strip(), phone=phone, source=lk.channel, note=(note or "").strip() or None, skills=[])
        db.add(cand)
        await db.flush()
    if chat_id and cand.telegram_chat_id is None and not await db.scalar(select(Candidate.id).where(Candidate.telegram_chat_id == chat_id)):
        cand.telegram_chat_id = chat_id
    if await db.scalar(select(Application.id).where(Application.vacancy_id == v.id, Application.candidate_id == cand.id)):
        return "duplicate", cand, []
    a = Application(vacancy_id=v.id, candidate_id=cand.id, stage="new", recruiter_id=v.recruiter_id or lk.owner_user_id, applied_at=moment, stage_changed_at=moment, source_link_id=lk.id)
    db.add(a)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return "duplicate", cand, []
    rsvc.log(db, a, None, "applied", to="new", note=note, data={"source": lk.channel, "link": lk.code})
    targets = {t for t in (v.recruiter_id, lk.owner_user_id) if t} or set(await users_with_permission(db, "recruit.manage"))
    notes = await notify(db, targets, "recruit.new_application", link=f"/recruit/vacancies/{v.id}", params={"candidate": cand.full_name, "vacancy": v.title})
    return "ok", cand, notes
