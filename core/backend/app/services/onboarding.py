"""Preboarding/onboarding: filial paketi, 7-kun qarori va onboardingni avtomatik ochish, darslar, kadrovik xabarlari."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.employees import Employee
from app.models.internship import InternshipEnrollment, InternshipProgram
from app.models.org import Branch
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template

DAYS = 7

register_template(
    "internship.package",
    {"uz": "Filial haqida ma'lumot", "ru": "Информация о филиале"},
    {"uz": "{text}", "ru": "{text}"},
    "info",
)
register_template(
    "internship.decision",
    {"uz": "7 kunlik sinov qarori", "ru": "Решение по 7-дневному испытанию"},
    {"uz": "{intern}: {result}. {note}", "ru": "{intern}: {result}. {note}"},
    "info",
)
register_template(
    "internship.onboarding",
    {"uz": "Onboarding boshlandi", "ru": "Начался онбординг"},
    {"uz": "{program} ({days} kun)", "ru": "{program} ({days} дн.)"},
    "success",
)
register_template(
    "class.invite",
    {"uz": "Dars/amaliyot: {title}", "ru": "Занятие: {title}"},
    {"uz": "{when}, {place}", "ru": "{when}, {place}"},
    "info",
)
register_template(
    "class.absent",
    {"uz": "Darsga kelmadi", "ru": "Не пришёл на занятие"},
    {"uz": "{intern}: {title} ({when})", "ru": "{intern}: {title} ({when})"},
    "warning",
)
register_template(
    "kadr.arrived",
    {"uz": "Yangi xodim keldi: hujjatlarni oling", "ru": "Пришёл новый сотрудник: примите документы"},
    {"uz": "{employee}", "ru": "{employee}"},
    "info",
)
register_template(
    "kadr.docs",
    {"uz": "Hujjatlar qabul qilindi", "ru": "Документы приняты"},
    {"uz": "{employee}", "ru": "{employee}"},
    "success",
)
register_template(
    "kadr.order",
    {"uz": "Kadr buyrug'i tayyor", "ru": "Кадровый приказ готов"},
    {"uz": "{employee} {order}", "ru": "{employee} {order}"},
    "success",
)


def day_no(start: datetime, moment: datetime) -> int:
    """Preboardingning nechanchi kuni (1..)."""
    return max(1, (moment.date() - start.date()).days + 1)


async def branch_of(db: AsyncSession, emp: Employee | None) -> Branch | None:
    return await db.get(Branch, emp.branch_id) if emp and emp.branch_id else None


async def package_text(db: AsyncSession, e: InternshipEnrollment, emp: Employee, branch: Branch | None) -> str:
    """Filial paketi: manzil, ish vaqti, ustozlar (trener, HR, mudir), hamkasblar."""
    names = {}
    ids = {x for x in (e.mentor_id, e.created_by, branch.manager_user_id if branch else None) if x}
    if ids:
        names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()}
    lines = [f"📍 Filial: {branch.name if branch else '—'}"]
    if branch:
        if branch.address:
            lines.append(f"Manzil: {branch.address}")
        if branch.is_24h:
            lines.append("Ish vaqti: 24 soat")
        elif branch.open_time and branch.close_time:
            lines.append(f"Ish vaqti: {branch.open_time:%H:%M}–{branch.close_time:%H:%M}")
        if branch.phone:
            lines.append(f"Telefon: {branch.phone}")
    lines.append(f"Trener: {names.get(e.mentor_id or 0, '—')}")
    lines.append(f"HR: {names.get(e.created_by or 0, '—')}")
    lines.append(f"Filial mudiri: {names.get(branch.manager_user_id or 0, '—') if branch else '—'}")
    if branch:
        mates = (await db.scalars(select(Employee.full_name).where(Employee.branch_id == branch.id, Employee.status == "active", Employee.id != emp.id).order_by(Employee.full_name).limit(8))).all()
        if mates:
            lines.append("Hamkasblar: " + ", ".join(mates))
    return "\n".join(lines)


async def send_package(db: AsyncSession, e: InternshipEnrollment) -> list:
    """Filial paketi: xodimga to'liq matn; mudir, koordinator va trenerga «xodim keladi» xabari."""
    emp = await db.get(Employee, e.employee_id)
    if emp is None:
        return []
    branch = await branch_of(db, emp)
    text = await package_text(db, e, emp, branch)
    notes: list = []
    if emp.user_id:
        notes += await notify(db, [emp.user_id], "internship.package", params={"text": text}, link=f"/internship/enrollments/{e.id}")
    others = {u for u in (e.mentor_id, branch.manager_user_id if branch else None, branch.coordinator_user_id if branch else None) if u}
    if others:
        notes += await notify(db, list(others), "internship.package", params={"text": f"{emp.full_name} keladi.\n{text}"}, link=f"/internship/enrollments/{e.id}")
    return notes


async def program_for_position(db: AsyncSession, position_id: int | None) -> InternshipProgram | None:
    if not position_id:
        return None
    return await db.scalar(select(InternshipProgram).where(InternshipProgram.phase == "onboarding", InternshipProgram.is_active.is_(True), InternshipProgram.position_id == position_id).order_by(InternshipProgram.id))


async def start_onboarding(db: AsyncSession, e: InternshipEnrollment, emp: Employee, actor_id: int, moment: datetime, program: InternshipProgram | None = None) -> tuple[InternshipEnrollment | None, list]:
    """7-kun qarori «mos»: lavozim bo'yicha onboarding dasturiga yozadi (muddat — dastur davomiyligi, standart 90 kun)."""
    p = program or await program_for_position(db, emp.position_id)
    if p is None:
        return None, []
    nxt = InternshipEnrollment(
        program_id=p.id, employee_id=emp.id, mentor_id=e.mentor_id, status="active", started_at=moment, phase="onboarding",
        due_date=moment.date() + timedelta(days=p.duration_days or 90), created_by=actor_id,
    )  # fmt: skip
    db.add(nxt)
    await db.flush()
    e.next_enrollment_id = nxt.id
    targets = [u for u in {emp.user_id, e.mentor_id} if u]
    notes = await notify(db, targets, "internship.onboarding", params={"program": p.name, "days": p.duration_days or 90}, link=f"/internship/enrollments/{nxt.id}") if targets else []
    return nxt, notes


async def hr_targets(db: AsyncSession) -> list[int]:
    return await users_with_permission(db, "internship.manage")


def kadr_status(d: Any) -> str:
    if d is None or d.docs_received_at is None:
        return "waiting_docs"
    return "order_ready" if d.order_ready_at else "waiting_order"
