"""Ushlab qolish, offboarding va nazorat: ruxsatlar, hodisalar tarixi, avtomatik xavf skaneri, nazorat paneli."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.models.employees import Employee
from app.models.growth import Attestation
from app.models.internship import InternshipEnrollment
from app.models.org import Branch
from app.models.recruit import Vacancy
from app.models.retention import Offboarding, RetentionCase, RetentionMeeting
from app.models.tasks import Task
from app.rbac import matches
from app.services import growth
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template
from app.timeutil import local_date

RISKS = ("shortage", "access", "understaff", "others_leaving", "competitor")
REASONS = ("salary", "manager", "workload", "team", "growth", "personal", "offer", "fired", "other")

register_template("retention.new", {"uz": "Ketish xavfi aniqlandi", "ru": "Выявлен риск ухода"}, {"uz": "{employee} ({branch}): {risk}", "ru": "{employee} ({branch}): {risk}"}, "warning")
register_template("retention.step", {"uz": "Ushlab qolish: yangilik", "ru": "Удержание: обновление"}, {"uz": "{employee}: {text}", "ru": "{employee}: {text}"}, "info")
register_template("retention.decided", {"uz": "Ushlab qolish qarori", "ru": "Решение по удержанию"}, {"uz": "{employee}: {result}", "ru": "{employee}: {result}"}, "info")
register_template("retention.meeting", {"uz": "Haftalik uchrashuv xulosasi", "ru": "Итоги еженедельной встречи"}, {"uz": "{summary}", "ru": "{summary}"}, "info")
register_template("offboarding.opened", {"uz": "Offboarding boshlandi", "ru": "Начат оффбординг"}, {"uz": "{employee}", "ru": "{employee}"}, "warning")
register_template("offboarding.reasons", {"uz": "Ketish sabablari va xavflar yozildi", "ru": "Причины ухода и риски записаны"}, {"uz": "{employee}: {text}", "ru": "{employee}: {text}"}, "info")
register_template("offboarding.done", {"uz": "Xodim ketdi: rasmiylashtiring", "ru": "Сотрудник ушёл: оформите"}, {"uz": "{employee}. Dostup yopildi.", "ru": "{employee}. Доступ закрыт."}, "info")
register_template("control.digest", {"uz": "Nazorat: kechikkan jarayonlar", "ru": "Контроль: просроченные процессы"}, {"uz": "{text}", "ru": "{text}"}, "warning")
register_template("retention.auto", {"uz": "Past yig'ma ball: ketish xavfi", "ru": "Низкий сводный балл: риск ухода"}, {"uz": "{employee}: ball {score}", "ru": "{employee}: балл {score}"}, "warning")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "retention.read") or has(auth, "retention.manage") or has(auth, "retention.audit")


def is_branch_lead(auth: AuthContext, branch: Branch | None) -> bool:
    return bool(branch and auth.user.id in (branch.manager_user_id, branch.coordinator_user_id))


def add_event(case: RetentionCase, actor: str | None, action: str, text: str | None, moment: datetime) -> None:
    case.events = [*(case.events or []), {"action": action, "actor": actor, "text": text, "at": moment.isoformat()}]


async def mentor_ids(db: AsyncSession, employee_id: int) -> set[int]:
    return {m for m in (await db.scalars(select(InternshipEnrollment.mentor_id).where(InternshipEnrollment.employee_id == employee_id))).all() if m}


async def lead_ids(db: AsyncSession, emp: Employee) -> list[int]:
    b = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    return [u for u in (b.manager_user_id if b else None, b.coordinator_user_id if b else None) if u]


async def auto_scan(db: AsyncSession, moment: datetime, limit: int = 600) -> tuple[int, list]:
    """Haftalik: yig'ma ball past (kamida 2 ta ko'rsatkich bilan) xodimlar uchun avtomatik xavf holati ochadi."""
    cfg = await growth.get_setting(db, "retention")
    today = local_date(moment)
    emps = list((await db.scalars(select(Employee).where(Employee.status == "active", Employee.hire_date <= today - timedelta(days=30)).order_by(Employee.id).limit(limit))).all())
    open_ids = set((await db.scalars(select(RetentionCase.employee_id).where((RetentionCase.status == "open") | (RetentionCase.created_at >= moment - timedelta(days=30))))).all())
    hr = await users_with_permission(db, "retention.manage")
    created, notes = 0, []
    for e in emps:
        if e.id in open_ids:
            continue
        r = await growth.employee_score(db, e, today)
        if r["score"] is None or r["score"] >= cfg["low_score"] or sum(1 for c in r["components"] if c["available"]) < 2:
            continue
        case = RetentionCase(employee_id=e.id, status="open", risk_level="medium", source="auto", note=f"Yig'ma ball past: {r['score']}", events=[])
        add_event(case, None, "created", case.note, moment)
        db.add(case)
        created += 1
        targets = {*hr, *await lead_ids(db, e)}
        notes += await notify(db, list(targets), "retention.auto", params={"employee": e.full_name, "score": r["score"]}, link="/retention")
    await db.flush()
    return created, notes


async def control_overview(db: AsyncSession, moment: datetime) -> dict[str, Any]:
    """Nazorat paneli: HRD va HR auditor uchun kechikkan jarayonlar ro'yxati."""
    cfg = await growth.get_setting(db, "retention")
    today = local_date(moment)
    names = {e.id: e.full_name for e in (await db.scalars(select(Employee))).all()}
    items: dict[str, list[dict[str, Any]]] = {}

    cases = list((await db.scalars(select(RetentionCase).where(RetentionCase.status == "open"))).all())
    items["interview_overdue"] = [
        {"id": c.id, "employee": names.get(c.employee_id), "days": (today - local_date(c.created_at)).days}
        for c in cases if c.hr_at is None and (today - local_date(c.created_at)).days >= cfg["interview_days"]
    ]  # fmt: skip
    items["decision_overdue"] = [
        {"id": c.id, "employee": names.get(c.employee_id), "days": (today - local_date(c.created_at)).days}
        for c in cases if (today - local_date(c.created_at)).days >= cfg["decision_days"]
    ]  # fmt: skip
    items["no_meeting"] = [
        {"id": c.id, "employee": names.get(c.employee_id), "days": (today - (c.last_discussed_on or local_date(c.created_at))).days}
        for c in cases if (today - (c.last_discussed_on or local_date(c.created_at))).days >= cfg["meeting_gap_days"]
    ]  # fmt: skip

    offs = list((await db.scalars(select(Offboarding).where(Offboarding.status == "open"))).all())
    items["exit_missing"] = [{"id": o.id, "employee": names.get(o.employee_id), "leave_date": o.leave_date} for o in offs if o.exit_at is None and o.leave_date and o.leave_date <= today]
    tasks = list((await db.scalars(select(Task).where(Task.status != "done", Task.due_at.is_not(None), Task.due_at < moment, Task.labels.contains(["nazorat"])))).all())
    items["tasks_overdue"] = [{"id": t.id, "title": t.title, "due_at": t.due_at} for t in tasks]

    enr = list((await db.scalars(select(InternshipEnrollment).where(InternshipEnrollment.phase == "preboarding", InternshipEnrollment.status != "cancelled", InternshipEnrollment.day7_decision.is_(None)))).all())
    items["day7_pending"] = [{"id": e.id, "employee": names.get(e.employee_id), "days": (today - local_date(e.started_at)).days} for e in enr if (today - local_date(e.started_at)).days >= 7]
    vac = list((await db.scalars(select(Vacancy).where(Vacancy.status == "open", Vacancy.deadline.is_not(None), Vacancy.deadline < today))).all())
    items["vacancies_overdue"] = [{"id": v.id, "title": v.title, "deadline": v.deadline} for v in vac]
    month_start = today.replace(day=1)
    att = list((await db.scalars(select(Attestation).where(Attestation.status != "decided", Attestation.opened_at.is_not(None), Attestation.opened_at < moment - timedelta(days=10)))).all())
    items["attestation_stale"] = [{"id": a.id, "employee": names.get(a.employee_id), "month": a.month} for a in att if a.month <= f"{month_start.year:04d}-{month_start.month:02d}"]
    return {"counts": {k: len(v) for k, v in items.items()}, "total": sum(len(v) for v in items.values()), "items": items}


async def meetings_recent(db: AsyncSession, limit: int = 10) -> list[RetentionMeeting]:
    return list((await db.scalars(select(RetentionMeeting).order_by(RetentionMeeting.held_on.desc(), RetentionMeeting.id.desc()).limit(limit))).all())


def meeting_due(last: date | None, today: date, gap: int) -> bool:
    return last is None or (today - last).days >= gap
