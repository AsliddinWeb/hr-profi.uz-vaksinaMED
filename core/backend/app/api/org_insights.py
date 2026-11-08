"""Tashkiliy tuzilma tahlili: bo'lim (ichki bo'limlari bilan) yoki butun kompaniya bo'yicha lavozimlar va ularda ishlayotgan
xodimlar, yangi kelganlar / ishdan ketganlar arxivi va asosiy ko'rsatkichlar (soni, staj, oyma-oy kelish-ketish, aylanma)."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.auth import Role, User
from app.models.employees import Employee
from app.models.org import Branch, Position
from app.rbac import matches
from app.services import org as svc
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/org", tags=["org"])

NEW_DAYS = 90


def months_between(a: date, b: date) -> int:
    return max(0, (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0))


def _age(bd: date | None, today: date) -> int | None:
    return None if not bd else today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))


@router.get("/insights")
async def insights(
    department_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.read")),
):
    today = local_date(now())
    depts = await svc.load_departments(db)
    if department_id is not None and department_id not in depts:
        raise error(404, "not_found")
    scope = None if department_id is None else {department_id} | svc.descendants(depts, department_id)
    positions = list((await db.scalars(select(Position).order_by(Position.sort_order, Position.name))).all())
    pos_by_id = {p.id: p for p in positions}
    branches = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}

    stmt = select(Employee)
    if scope is not None:
        stmt = stmt.where(or_(Employee.department_id.in_(scope), Employee.position_id.in_([p.id for p in positions if p.department_id in scope])))
    emps = list((await db.scalars(stmt)).all())
    active = [e for e in emps if e.status == "active"]
    left = [e for e in emps if e.status != "active" and e.dismissal_date]
    see = matches(auth.permissions, "employees.read")

    def card(e: Employee) -> dict[str, Any]:
        p = pos_by_id.get(e.position_id or 0)
        return {
            "id": e.id, "full_name": e.full_name, "photo": bool(e.photo_key), "phone": e.phone if see else None,
            "position": p.name if p else None, "branch": branches.get(e.branch_id or 0), "department": depts[e.department_id].name if e.department_id in depts else None,
            "hire_date": e.hire_date, "tenure_months": months_between(e.hire_date, e.dismissal_date or today) if e.hire_date else None,
            "status": e.status, "dismissal_date": e.dismissal_date, "dismissal_reason": e.dismissal_reason,
        }  # fmt: skip

    # Lavozimlar: qamrovdagi bo'limlar lavozimlari + umumiy lavozimlardan shu yerda ishlayotganlar
    by_pos: dict[int | None, list[Employee]] = defaultdict(list)
    for e in active:
        by_pos[e.position_id].append(e)
    pos_rows = []
    for p in positions:
        in_scope = scope is None or p.department_id in scope or (p.department_id is None and by_pos.get(p.id))
        if not in_scope or (not p.is_active and not by_pos.get(p.id)):
            continue
        staff = sorted(by_pos.get(p.id, []), key=lambda e: e.full_name)
        pos_rows.append({
            "id": p.id, "name": p.name, "department": depts[p.department_id].name if p.department_id in depts else None, "general": p.department_id is None,
            "count": len(staff), "employees": [card(e) for e in staff] if see else [],
        })  # fmt: skip
    no_pos = sorted(by_pos.get(None, []), key=lambda e: e.full_name)

    # 12 oylik kelish/ketish
    start = date(today.year - (1 if today.month < 12 else 0), today.month % 12 + 1, 1)
    months = []
    y, m = start.year, start.month
    for _ in range(12):
        months.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    hires = Counter(e.hire_date.strftime("%Y-%m") for e in emps if e.hire_date and e.hire_date >= start)
    leaves = Counter(e.dismissal_date.strftime("%Y-%m") for e in left if e.dismissal_date >= start)
    tenures = [months_between(e.hire_date, today) for e in active if e.hire_date]
    ages = [a for a in (_age(e.birth_date, today) for e in active) if a]
    left_12 = sum(leaves.values())
    avg_head = (len(active) + left_12 / 2) or 1
    newcomers = sorted((e for e in active if e.hire_date and e.hire_date >= today - timedelta(days=NEW_DAYS)), key=lambda e: e.hire_date, reverse=True)
    leavers = sorted(left, key=lambda e: e.dismissal_date, reverse=True)[:100]
    reasons = Counter((e.dismissal_reason or "other") for e in left if e.dismissal_date >= start)
    return {
        "scope": {"department_id": department_id, "name": depts[department_id].name if department_id else None, "departments": len(scope) if scope is not None else len(depts)},
        "headcount": len(active), "positions_total": len(pos_rows), "vacant_positions": sum(1 for p in pos_rows if p["count"] == 0),
        "positions": pos_rows, "no_position": [card(e) for e in no_pos] if see else [], "no_position_count": len(no_pos),
        "newcomers": [card(e) for e in newcomers] if see else [], "newcomers_count": len(newcomers),
        "leavers": [card(e) for e in leavers] if see else [], "leavers_count": len(left),
        "analytics": {
            "avg_tenure_months": round(sum(tenures) / len(tenures), 1) if tenures else None,
            "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
            "gender": dict(Counter(e.gender or "?" for e in active)),
            "by_branch": sorted(({"name": k or "—", "count": v} for k, v in Counter(branches.get(e.branch_id or 0) for e in active).items()), key=lambda x: -x["count"])[:15],
            "tenure_buckets": {
                "lt3": sum(1 for x in tenures if x < 3), "m3_12": sum(1 for x in tenures if 3 <= x < 12),
                "y1_3": sum(1 for x in tenures if 12 <= x < 36), "gt3y": sum(1 for x in tenures if x >= 36),
            },
            "months": [{"month": mo, "hired": hires.get(mo, 0), "left": leaves.get(mo, 0)} for mo in months],
            "hired_12m": sum(hires.values()), "left_12m": left_12, "turnover_pct": round(left_12 / avg_head * 100, 1),
            "leave_reasons": dict(reasons),
        },
        "can_see_people": see,
    }  # fmt: skip


# --- Shajara (org.xlsx kabi): bo'lim -> boshliq -> bo'ysunuvchi lavozimlar; egasi rasmi bilan yoki VAKANSIYA -----------


@router.get("/scheme")
async def scheme(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.read"))):
    """Tashkiliy tuzilma shajarasi. Ma'lumotlar bo'lim, lavozim (kimga bo'ysunadi, shtat soni) va xodimlardan avtomatik
    yig'iladi; frontend daraxtni shu tekis ro'yxatlardan quradi."""
    see = matches(auth.permissions, "employees.read")
    depts = [d for d in (await svc.load_departments(db)).values() if d.is_active]
    positions = list((await db.scalars(select(Position).where(Position.is_active.is_(True)).order_by(Position.sort_order, Position.id))).all())
    emps = list((await db.scalars(select(Employee).where(Employee.status == "active").order_by(Employee.full_name))).all())
    by_pos: dict[int, list[Employee]] = defaultdict(list)
    for e in emps:
        if e.position_id:
            by_pos[e.position_id].append(e)
    coord_branches = Counter(uid for (uid,) in (await db.execute(select(Branch.coordinator_user_id).where(Branch.coordinator_user_id.is_not(None), Branch.is_active.is_(True)))).all())
    users = {u.id: u for u in (await db.scalars(select(User).join(Role).where(Role.key.in_(["tasischi", "direktor"]), User.is_active.is_(True)))).unique().all()}
    by_role: dict[str, list[User]] = defaultdict(list)
    for u in users.values():
        by_role[u.role.key].append(u)

    def person(e: Employee) -> dict[str, Any]:
        return {"id": e.id, "full_name": e.full_name, "photo": bool(e.photo_key) and see, "branches": coord_branches.get(e.user_id or 0, 0)}

    def occupants(p: Position) -> list[dict[str, Any]]:
        occ = [person(e) for e in by_pos.get(p.id, [])]
        if not occ:  # rahbariyat lavozimlari: tizimdagi Ta'sischi/Direktor hisoblari
            n = p.name.lower()
            key = "tasischi" if ("ta'sischi" in n or "tasischi" in n) and "asist" not in n else "direktor" if n.startswith("direktor") else None
            occ = [{"id": None, "full_name": u.full_name, "photo": False, "branches": 0} for u in by_role.get(key or "", [])]
        return occ

    return {
        "company": request.app.state.client_config.brand["name"],
        "departments": [
            {"id": d.id, "name": d.name, "parent_id": d.parent_id, "reports_to_position_id": d.reports_to_position_id, "yqm": d.yqm, "color": d.color, "sort_order": d.sort_order,
             "headcount": sum(len(by_pos.get(p.id, [])) for p in positions if p.department_id == d.id)}
            for d in sorted(depts, key=lambda x: (x.sort_order, x.name.lower()))
        ],
        "positions": [
            {"id": p.id, "name": p.name, "department_id": p.department_id, "parent_id": p.parent_id, "slots": p.slots, "is_head": p.is_head, "yqm": p.yqm, "occupants": occupants(p)}
            for p in positions
        ],
    }  # fmt: skip
