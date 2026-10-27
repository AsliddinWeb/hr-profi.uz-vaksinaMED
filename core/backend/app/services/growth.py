"""Attestatsiya, yig'ma baho (online kuzatuv) va o'sish: sozlamalar, davrni ochish, ball hisobi, avtomatik o'sish taklifi."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employees import Employee
from app.models.growth import Attestation, CareerLevel, HrSetting, Promotion
from app.models.internship import InternshipEnrollment, InternshipProgress
from app.models.org import Branch
from app.models.penalties import Penalty
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template

DEFAULTS: dict[str, dict[str, Any]] = {
    "attestation": {"pass_score": 70, "test_weight": 50, "practical_weight": 50, "promote_after": 2},
    "score_weights": {"attendance": 30, "learning": 20, "attestation": 30, "discipline": 20},
    "retention": {"interview_days": 3, "decision_days": 7, "meeting_gap_days": 7, "low_score": 50, "notice_days_default": 15, "notice_days_senior": 30},
}
DECISIONS = "passed|retake|extra_lessons"
RESULT_UZ = {"passed": "o'tdi", "retake": "qayta topshiradi", "extra_lessons": "qo'shimcha dars"}

register_template("attestation.opened", {"uz": "Oylik attestatsiya boshlandi", "ru": "Началась ежемесячная аттестация"}, {"uz": "{month}: {level}", "ru": "{month}: {level}"}, "info")
register_template("attestation.decided", {"uz": "Attestatsiya natijasi", "ru": "Результат аттестации"}, {"uz": "{employee}: {result}. {note}", "ru": "{employee}: {result}. {note}"}, "info")
register_template("attestation.summary", {"uz": "Attestatsiya ochildi", "ru": "Аттестация открыта"}, {"uz": "{month}: {count} xodim", "ru": "{month}: {count} сотрудников"}, "info")
register_template("career.proposed", {"uz": "O'sish taklifi", "ru": "Предложение о повышении"}, {"uz": "{employee}: {from_level} → {to_level}", "ru": "{employee}: {from_level} → {to_level}"}, "info")
register_template("career.decided", {"uz": "O'sish bo'yicha qaror", "ru": "Решение о повышении"}, {"uz": "{employee}: {result}. {note}", "ru": "{employee}: {result}. {note}"}, "info")


async def get_setting(db: AsyncSession, key: str) -> dict[str, Any]:
    row = await db.get(HrSetting, key)
    return {**DEFAULTS[key], **((row.value or {}) if row else {})}


def month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def total_score(test: float | None, practical: float | None, cfg: dict[str, Any]) -> float | None:
    parts = [(test, cfg["test_weight"]), (practical, cfg["practical_weight"])]
    have = [(v, w) for v, w in parts if v is not None and w > 0]
    if not have:
        return None
    return round(sum(v * w for v, w in have) / sum(w for _, w in have), 1)


async def levels(db: AsyncSession, *, active_only: bool = True) -> list[CareerLevel]:
    stmt = select(CareerLevel).order_by(CareerLevel.sort_order, CareerLevel.id)
    if active_only:
        stmt = stmt.where(CareerLevel.is_active.is_(True))
    return list((await db.scalars(stmt)).all())


def level_of(emp: Employee, lvls: list[CareerLevel]) -> CareerLevel | None:
    return next((lv for lv in lvls if lv.position_id and lv.position_id == emp.position_id), None)


async def open_cycle(db: AsyncSession, month: str, moment: datetime) -> tuple[int, list]:
    """Oy uchun attestatsiyalarni ochadi: zinapoyadagi lavozimlarda ishlayotgan faol xodimlar. Takrorlanmaydi."""
    lvls = await levels(db)
    pos = {lv.position_id: lv for lv in lvls if lv.position_id}
    if not pos:
        return 0, []
    emps = list((await db.scalars(select(Employee).where(Employee.status == "active", Employee.position_id.in_(pos)))).all())
    have = set((await db.scalars(select(Attestation.employee_id).where(Attestation.month == month))).all())
    created, notes = 0, []
    branches = {b.id: b for b in (await db.scalars(select(Branch))).all()}
    per_branch: dict[int, int] = {}
    for e in emps:
        if e.id in have:
            continue
        lv = pos[e.position_id]  # type: ignore[index]
        db.add(Attestation(employee_id=e.id, month=month, level_id=lv.id, status="open", feedbacks=[], opened_at=moment))
        created += 1
        if e.branch_id:
            per_branch[e.branch_id] = per_branch.get(e.branch_id, 0) + 1
        if e.user_id:
            notes += await notify(db, [e.user_id], "attestation.opened", params={"month": month, "level": lv.name}, link="/attestation")
    await db.flush()
    for bid, n in per_branch.items():
        b = branches.get(bid)
        targets = [u for u in (b.manager_user_id if b else None, b.coordinator_user_id if b else None) if u]
        if targets:
            notes += await notify(db, targets, "attestation.summary", params={"month": month, "count": n}, link="/attestation")
    hr = await users_with_permission(db, "attestation.manage")
    if hr and created:
        notes += await notify(db, hr, "attestation.summary", params={"month": month, "count": created}, link="/attestation")
    return created, notes


async def maybe_propose(db: AsyncSession, emp: Employee, moment: datetime) -> tuple[Promotion | None, list]:
    """Ketma-ket N ta «o'tdi» attestatsiyadan keyin keyingi darajaga avtomatik taklif (HRD tasdiqlaydi)."""
    lvls = await levels(db)
    cur = level_of(emp, lvls)
    if cur is None:
        return None, []
    idx = lvls.index(cur)
    if idx + 1 >= len(lvls):
        return None, []
    cfg = await get_setting(db, "attestation")
    rows = (await db.scalars(select(Attestation).where(Attestation.employee_id == emp.id, Attestation.status == "decided").order_by(Attestation.month.desc()))).all()
    streak = 0
    for a in rows:
        if a.decision == "passed" and a.level_id == cur.id:
            streak += 1
        else:
            break
    if streak < int(cfg["promote_after"]):
        return None, []
    nxt = lvls[idx + 1]
    if await db.scalar(select(Promotion.id).where(Promotion.employee_id == emp.id, Promotion.status == "proposed")):
        return None, []
    p = Promotion(employee_id=emp.id, from_level_id=cur.id, to_level_id=nxt.id, status="proposed", source="auto", basis=f"Ketma-ket {streak} ta attestatsiyadan o'tdi ({cur.name})")
    db.add(p)
    await db.flush()
    targets = set(await users_with_permission(db, "career.manage")) | set(await users_with_permission(db, "attestation.manage"))
    return p, await notify(db, list(targets), "career.proposed", params={"employee": emp.full_name, "from_level": cur.name, "to_level": nxt.name}, link="/career")


# --- Yig'ma ball (online kuzatuv) ---------------------------------------------------------

ATTENDED = {"present", "late", "early", "late_early", "working", "no_checkout", "incomplete", "unscheduled"}


async def attendance_component(db: AsyncSession, emp: Employee, today: date) -> float | None:
    from app.api.attendance import _rows  # noqa: PLC0415  (api -> service sikli oldini olish)

    start, end = today - timedelta(days=30), today - timedelta(days=1)
    days = (await _rows(db, [emp], start, end))[emp.id]
    days = [d for d in days if not emp.hire_date or d["date"] >= emp.hire_date]
    attended = sum(1 for d in days if d["status"] in ATTENDED)
    absent = sum(1 for d in days if d["status"] == "absent")
    late = sum(1 for d in days if d["status"] in ("late", "late_early"))
    if attended + absent == 0:
        return None
    return round(max(0.0, attended / (attended + absent) * 100 - 2 * late), 1)


async def learning_component(db: AsyncSession, emp: Employee) -> float | None:
    done = await db.scalar(select(InternshipEnrollment.final_score).where(InternshipEnrollment.employee_id == emp.id, InternshipEnrollment.final_score.is_not(None)).order_by(InternshipEnrollment.id.desc()).limit(1))
    if done is not None:
        return round(float(done), 1)
    ids = (await db.scalars(select(InternshipEnrollment.id).where(InternshipEnrollment.employee_id == emp.id))).all()
    if not ids:
        return None
    scores = (await db.scalars(select(InternshipProgress.score).where(InternshipProgress.enrollment_id.in_(ids), InternshipProgress.score.is_not(None)))).all()
    return round(sum(scores) / len(scores), 1) if scores else None


async def attestation_component(db: AsyncSession, emp: Employee) -> float | None:
    v = await db.scalar(select(Attestation.total).where(Attestation.employee_id == emp.id, Attestation.status == "decided", Attestation.total.is_not(None)).order_by(Attestation.month.desc()).limit(1))
    return round(float(v), 1) if v is not None else None


async def discipline_component(db: AsyncSession, emp: Employee, today: date) -> float | None:
    if emp.hire_date and (today - emp.hire_date).days < 14:
        return None  # yangi xodim: hali baholab bo'lmaydi
    n = len((await db.scalars(select(Penalty.id).where(Penalty.employee_id == emp.id, Penalty.status == "approved", Penalty.incident_date >= today - timedelta(days=90)))).all())
    return float(max(0, 100 - 20 * n))


async def employee_score(db: AsyncSession, emp: Employee, today: date, weights: dict[str, Any] | None = None) -> dict[str, Any]:
    """Yig'ma ball 0..100: mavjud komponentlar og'irliklar bo'yicha qayta me'yorlanadi."""
    w = weights or await get_setting(db, "score_weights")
    values = {
        "attendance": await attendance_component(db, emp, today), "learning": await learning_component(db, emp),
        "attestation": await attestation_component(db, emp), "discipline": await discipline_component(db, emp, today),
    }  # fmt: skip
    comps = [{"key": k, "value": v, "weight": w.get(k, 0), "available": v is not None} for k, v in values.items()]
    have = [c for c in comps if c["available"] and c["weight"] > 0]
    total = round(sum(c["value"] * c["weight"] for c in have) / sum(c["weight"] for c in have), 1) if have else None
    return {"score": total, "components": comps}
