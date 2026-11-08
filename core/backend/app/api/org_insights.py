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


# --- Sxema (shablon ko'rinishi): bo'lim -> boshliq -> raqamlangan lavozimlar, egalari yoki VAKANSIYA ----------------


def _is_head_position(name: str) -> bool:
    n = name.lower()
    return "boshlig" in n or "rahbar" in n or "начальник" in n or "руководител" in n


@router.get("/scheme")
async def scheme(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.read"))):
    """Tashkiliy tuzilma sxemasi: ma'lumotlar bo'lim, lavozim va xodimlardan avtomatik yig'iladi (qo'lda chizilmaydi)."""
    see = matches(auth.permissions, "employees.read")
    depts = await svc.load_departments(db)
    positions = list((await db.scalars(select(Position).where(Position.is_active.is_(True)).order_by(Position.sort_order, Position.id))).all())
    emps = list((await db.scalars(select(Employee).where(Employee.status == "active").order_by(Employee.full_name))).all())
    by_pos: dict[int, list[Employee]] = defaultdict(list)
    by_user = {e.user_id: e for e in emps if e.user_id}
    for e in emps:
        if e.position_id:
            by_pos[e.position_id].append(e)

    def person(e: Employee) -> dict[str, Any]:
        return {"id": e.id, "full_name": e.full_name, "photo": bool(e.photo_key) and see}

    users = {u.id: u for u in (await db.scalars(select(User).where(User.id.in_([d.head_user_id for d in depts.values() if d.head_user_id])))).unique().all()} if depts else {}

    def node(d: Any) -> dict[str, Any]:
        own = [p for p in positions if p.department_id == d.id]
        head = None
        if d.head_user_id and d.head_user_id in users:
            e = by_user.get(d.head_user_id)
            head = person(e) if e else {"id": None, "full_name": users[d.head_user_id].full_name, "photo": False}
        rows = []
        for p in own:
            occ = by_pos.get(p.id, [])
            if _is_head_position(p.name):
                if head is None and occ:
                    head = person(occ[0])
                continue
            rows.append({"id": p.id, "name": p.name, "yqm": p.yqm, "occupants": [person(e) for e in occ]})
        kids = sorted((c for c in depts.values() if c.parent_id == d.id and c.is_active), key=lambda x: (x.sort_order, x.name.lower()))
        return {"id": d.id, "name": d.name, "yqm": d.yqm, "color": d.color, "head": head, "positions": rows, "children": [node(k) for k in kids],
                "headcount": sum(len(by_pos.get(p.id, [])) for p in own)}  # fmt: skip

    roots = sorted((d for d in depts.values() if d.parent_id is None and d.is_active), key=lambda x: (x.sort_order, x.name.lower()))
    leaders = (await db.scalars(select(User).join(Role).where(Role.key.in_(["tasischi", "direktor"]), User.is_active.is_(True)).order_by(Role.id, User.full_name))).unique().all()
    return {
        "company": request.app.state.client_config.brand["name"],
        "leadership": [{"role": u.role.name_uz, "role_ru": u.role.name_ru, **(person(by_user[u.id]) if u.id in by_user else {"id": None, "full_name": u.full_name, "photo": False})} for u in leaders],
        "departments": [node(d) for d in roots],
        "general": [{"id": p.id, "name": p.name, "yqm": p.yqm, "occupants": [person(e) for e in by_pos.get(p.id, [])]} for p in positions if p.department_id is None],
    }  # fmt: skip
