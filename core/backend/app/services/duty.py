"""Ish chek-listlari (bo'lim/lavozim): qo'llanish, davr, baholash, nazorat va kechikish bildirishnomalari."""

import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.duty import DutyChecklist, DutyRun
from app.models.employees import Employee
from app.models.org import Branch, Department, Position
from app.rbac import matches
from app.services import answers as leave_svc
from app.services.notifications import notify, register_template
from app.timeutil import local_date, tz

MAX_ITEMS = 60
register_template("duty.overdue", {"uz": "Chek-list bajarilmadi", "ru": "Чек-лист не выполнен"}, {"uz": "«{name}» muddatida to'ldirilmadi. Iltimos, hoziroq to'ldiring.", "ru": "«{name}» не заполнен в срок. Пожалуйста, заполните сейчас."}, "warning")
register_template("duty.overdue_lead", {"uz": "Xodimlar chek-listni bajarmadi", "ru": "Сотрудники не выполнили чек-лист"}, {"uz": "{text}", "ru": "{text}"}, "warning")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "duty.read") or has(auth, "duty.manage")


def period_start(freq: str, day: date) -> date:
    return day if freq == "daily" else day - timedelta(days=day.weekday())


def due_at(cl: DutyChecklist, start: date) -> datetime:
    end = start if cl.frequency == "daily" else start + timedelta(days=6)
    return datetime.combine(end, cl.deadline_time, tzinfo=tz())


def clean_items(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw or len(raw) > MAX_ITEMS:
        raise error(400, "items_invalid")
    out, seen = [], set()
    for it in raw:
        text = str(it.get("text") or "").strip()
        kind = it.get("kind", "yesno")
        if not text or kind not in ("yesno", "score"):
            raise error(400, "items_invalid")
        iid = str(it.get("id") or "") or secrets.token_hex(4)
        if iid in seen:
            raise error(400, "items_invalid")
        seen.add(iid)
        out.append({"id": iid, "text": text[:300], "kind": kind, "required": bool(it.get("required", True))})
    return out


def check_answers(items: list[dict[str, Any]], answers: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Javoblarni tekshiradi va (tozalangan javoblar, ball %) qaytaradi. Majburiy punkt javobsiz bo'lsa xato."""
    clean: dict[str, Any] = {}
    got = total = 0.0
    for it in items:
        v = answers.get(it["id"])
        if v is None:
            if it["required"]:
                raise error(400, "answers_incomplete")
            continue
        if it["kind"] == "yesno":
            if not isinstance(v, bool):
                raise error(400, "answer_invalid")
            clean[it["id"]] = v
            got += 1 if v else 0
        else:
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
                raise error(400, "answer_invalid")
            clean[it["id"]] = v
            got += v / 5
        total += 1
    return clean, round(got / total * 100) if total else 100


async def applicable(db: AsyncSession, emp: Employee) -> list[DutyChecklist]:
    conds = []
    if emp.position_id:
        conds.append((DutyChecklist.scope == "position") & (DutyChecklist.position_id == emp.position_id))
    if emp.department_id:
        conds.append((DutyChecklist.scope == "department") & (DutyChecklist.department_id == emp.department_id))
    if not conds:
        return []
    return list((await db.scalars(select(DutyChecklist).where(DutyChecklist.is_active.is_(True), or_(*conds)).order_by(DutyChecklist.frequency, DutyChecklist.name))).all())


def run_status(cl: DutyChecklist, run: DutyRun | None, start: date, moment: datetime) -> str:
    if run and run.completed_at:
        return "done"
    return "overdue" if moment > due_at(cl, start) else "open"


def template_out(cl: DutyChecklist, names: dict[str, str | None] | None = None, *, with_items: bool = True) -> dict[str, Any]:
    n = names or {}
    out = {
        "id": cl.id, "name": cl.name, "description": cl.description, "scope": cl.scope, "frequency": cl.frequency, "deadline_time": cl.deadline_time.strftime("%H:%M"),
        "department_id": cl.department_id, "position_id": cl.position_id, "department": n.get(f"d{cl.department_id}"), "position": n.get(f"p{cl.position_id}"),
        "is_active": cl.is_active, "item_count": len(cl.items or []),
    }  # fmt: skip
    if with_items:
        out["items"] = cl.items or []
    return out


async def names_map(db: AsyncSession) -> dict[str, str | None]:
    d = {f"d{x.id}": x.name for x in (await db.scalars(select(Department))).all()}
    p = {f"p{x.id}": x.name for x in (await db.scalars(select(Position))).all()}
    return {**d, **p}


def visible_employee_filter(auth: AuthContext, branches: list[Branch]) -> set[int] | None:
    """None = hamma; aks holda ko'rinadigan filial id lari (mudir/koordinator o'z filiallari)."""
    if sees_all(auth):
        return None
    return {b.id for b in branches if auth.user.id in (b.manager_user_id, b.coordinator_user_id)}


async def control(db: AsyncSession, auth: AuthContext, day: date, moment: datetime, *, branch_id: int | None, department_id: int | None, position_id: int | None, status: str | None, limit: int = 600) -> dict[str, Any]:
    branches = list((await db.scalars(select(Branch))).all())
    allowed = visible_employee_filter(auth, branches)
    if allowed is not None and not allowed:
        raise error(403, "forbidden")
    emp_stmt = select(Employee).where(Employee.status == "active", Employee.user_id.is_not(None))
    if allowed is not None:
        emp_stmt = emp_stmt.where(Employee.branch_id.in_(allowed))
    if branch_id:
        emp_stmt = emp_stmt.where(Employee.branch_id == branch_id)
    if department_id:
        emp_stmt = emp_stmt.where(Employee.department_id == department_id)
    if position_id:
        emp_stmt = emp_stmt.where(Employee.position_id == position_id)
    emps = list((await db.scalars(emp_stmt)).all())
    cls = list((await db.scalars(select(DutyChecklist).where(DutyChecklist.is_active.is_(True)))).all())
    by_pos: dict[int, list[DutyChecklist]] = defaultdict(list)
    by_dept: dict[int, list[DutyChecklist]] = defaultdict(list)
    for c in cls:
        (by_pos if c.scope == "position" else by_dept)[c.position_id if c.scope == "position" else c.department_id].append(c)  # type: ignore[index]
    on_leave = await leave_svc.approved_leave_days(db, [e.id for e in emps], day, day) if emps else {}
    pairs = [(e, c) for e in emps if day not in on_leave.get(e.id, set()) for c in (*by_pos.get(e.position_id or 0, []), *by_dept.get(e.department_id or 0, []))]
    runs: dict[tuple[int, int], DutyRun] = {}
    if pairs:
        starts = {period_start(c.frequency, day) for _, c in pairs}
        for r in (await db.scalars(select(DutyRun).where(DutyRun.employee_id.in_({e.id for e, _ in pairs}), DutyRun.period_date.in_(starts)))).all():
            runs[(r.checklist_id, r.employee_id)] = r
    bmap = {b.id: b.name for b in branches}
    dmap = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    rows, per_dept = [], defaultdict(lambda: {"expected": 0, "done": 0})
    kpi = {"expected": 0, "done": 0, "overdue": 0, "open": 0}
    for e, c in pairs:
        start = period_start(c.frequency, day)
        run = runs.get((c.id, e.id))
        if run and run.period_date != start:
            run = None
        st = run_status(c, run, start, moment)
        kpi["expected"] += 1
        kpi[st] += 1
        pd = per_dept[dmap.get(e.department_id or 0, "—")]
        pd["expected"] += 1
        pd["done"] += st == "done"
        if status and status != "all" and st != status:
            continue
        rows.append({
            "employee": {"id": e.id, "name": e.full_name}, "branch": bmap.get(e.branch_id or 0), "department": dmap.get(e.department_id or 0),
            "checklist": {"id": c.id, "name": c.name, "frequency": c.frequency}, "status": st, "due_at": due_at(c, start),
            "completed_at": run.completed_at if run else None, "score_pct": run.score_pct if run else None, "late": bool(run and run.late),
        })  # fmt: skip
    order = {"overdue": 0, "open": 1, "done": 2}
    rows.sort(key=lambda r: (order[r["status"]], r["employee"]["name"]))
    return {
        "date": day, "kpis": {**kpi, "rate": round(kpi["done"] / kpi["expected"] * 100) if kpi["expected"] else None},
        "by_department": sorted(({"name": k, **v, "rate": round(v["done"] / v["expected"] * 100)} for k, v in per_dept.items()), key=lambda x: x["rate"]),
        "total": len(rows), "rows": rows[:limit],
    }  # fmt: skip


async def overdue_scan(db: AsyncSession, moment: datetime, limit: int = 1500) -> list:
    """Muddati o'tgan, bajarilmagan chek-listlar uchun BIR MARTA (davr uchun) xodimga va filial mas'ullariga xabar beradi."""
    today = local_date(moment)
    cls = list((await db.scalars(select(DutyChecklist).where(DutyChecklist.is_active.is_(True)))).all())
    branches = {b.id: b for b in (await db.scalars(select(Branch))).all()}
    notes: list = []
    lead_text: dict[int, list[str]] = defaultdict(list)
    done = 0
    for c in cls:
        start = period_start(c.frequency, today)
        if moment <= due_at(c, start):
            continue
        cond = (Employee.position_id == c.position_id) if c.scope == "position" else (Employee.department_id == c.department_id)
        emps = list((await db.scalars(select(Employee).where(Employee.status == "active", Employee.user_id.is_not(None), cond).limit(limit))).all())
        if not emps:
            continue
        runs = {r.employee_id: r for r in (await db.scalars(select(DutyRun).where(DutyRun.checklist_id == c.id, DutyRun.period_date == start, DutyRun.employee_id.in_([e.id for e in emps])))).all()}
        leave = await leave_svc.approved_leave_days(db, [e.id for e in emps], today, today)
        for e in emps:
            r = runs.get(e.id)
            if (r and (r.completed_at or r.late_notified_at)) or today in leave.get(e.id, set()):
                continue
            if r is None:
                r = DutyRun(checklist_id=c.id, employee_id=e.id, period_date=start, answers={})
                db.add(r)
            r.late_notified_at = moment
            done += 1
            notes += await notify(db, [e.user_id], "duty.overdue", params={"name": c.name}, link="/checklists/my")  # type: ignore[list-item]
            b = branches.get(e.branch_id or 0)
            for lead in dict.fromkeys(u for u in ((b.manager_user_id, b.coordinator_user_id) if b else ()) if u):
                if len(lead_text[lead]) < 12:
                    lead_text[lead].append(f"{e.full_name} — {c.name}")
        if done >= limit:
            break
    for lead, items in lead_text.items():
        notes += await notify(db, [lead], "duty.overdue_lead", params={"text": "; ".join(items)}, link="/checklists/control")
    return notes
