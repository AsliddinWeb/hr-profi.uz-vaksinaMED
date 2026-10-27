"""Apteka tarmog'i: filial jamoasi, me'yor bilan solishtirish, bugungi holat, «xodim kerak», ma'lumot sifati."""

from datetime import datetime, time
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.models.employees import Employee
from app.models.org import Branch, Position
from app.models.pharmacy import StaffNeed
from app.rbac import matches
from app.services.notifications import register_template
from app.timeutil import local_date, tz

ROLES = ("manager", "pharmacist", "intern")
ALL_ROLES = (*ROLES, "other")
# Lavozim nomidagi kalit so'zlar (kichik harf). Mijoz lavozimlarini shu so'zlar bilan nomlasa avtomatik aniqlanadi.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "intern": ("stajyor", "stajer", "стажёр", "стажер", "intern"),
    "manager": ("mudir", "мудир", "заведующ", "zaveduyush", "manager"),
    "pharmacist": ("farmasevt", "фармацевт", "provizor", "провизор", "pharmacist"),
}
URGENCIES = ("low", "normal", "urgent")

register_template(
    "pharmacy.need",
    {"uz": "Filialga xodim kerak", "ru": "Филиалу нужен сотрудник"},
    {"uz": "{branch}: {role} × {count} ({urgency})", "ru": "{branch}: {role} × {count} ({urgency})"},
    "warning",
)
register_template(
    "pharmacy.need_filled",
    {"uz": "«Xodim kerak» so'rovi bajarildi", "ru": "Заявка «нужен сотрудник» выполнена"},
    {"uz": "{branch}: {role} × {count}", "ru": "{branch}: {role} × {count}"},
    "success",
)


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "pharmacy.read") or has(auth, "pharmacy.manage")


def visible_clause(auth: AuthContext):
    """Qaysi filiallarni ko'ra oladi: hammasi yoki o'zining (koordinator/mudir)."""
    if sees_all(auth):
        return None
    me = auth.user.id
    return or_(Branch.coordinator_user_id == me, Branch.manager_user_id == me)


def can_see_branch(auth: AuthContext, b: Branch) -> bool:
    return sees_all(auth) or (has(auth, "pharmacy.own") and auth.user.id in (b.coordinator_user_id, b.manager_user_id))


def role_of(position_name: str | None) -> str:
    name = (position_name or "").lower()
    for role in ("intern", "manager", "pharmacist"):  # "stajyor farmasevt" -> stajyor
        if any(k in name for k in KEYWORDS[role]):
            return role
    return "other"


def norm_of(b: Branch) -> dict[str, int]:
    n = b.staff_norm or {}
    return {r: max(int(n.get(r, 0) or 0), 0) for r in ROLES}


def is_open_now(b: Branch, moment: datetime) -> bool | None:
    """Filial hozir ochiqmi: 24 soat -> True; ish vaqti kiritilmagan -> None (noma'lum)."""
    if b.is_24h:
        return True
    if b.open_time is None or b.close_time is None:
        return None
    t = moment.astimezone(tz()).time().replace(second=0, microsecond=0)
    o, c = b.open_time, b.close_time
    return (o <= t < c) if o < c else (t >= o or t < c)  # tungi ish vaqti


async def positions_map(db: AsyncSession) -> dict[int, str]:
    return {p.id: role_of(p.name) for p in (await db.scalars(select(Position))).all()}


def team_counts(b: Branch, members: list[Employee], pos_roles: dict[int, str]) -> dict[str, int]:
    counts = dict.fromkeys(ALL_ROLES, 0)
    for e in members:
        role = pos_roles.get(e.position_id or 0, "other")
        if role == "other" and b.manager_user_id and e.user_id == b.manager_user_id:
            role = "manager"  # filial mudiri sifatida tayinlangan
        counts[role] += 1
    return counts


def gaps(b: Branch, counts: dict[str, int]) -> dict[str, int]:
    norm = norm_of(b)
    return {r: max(norm[r] - counts[r], 0) for r in ROLES if norm[r] > 0 and norm[r] - counts[r] > 0}


async def open_needs(db: AsyncSession, branch_ids: list[int] | None = None) -> dict[int, list[StaffNeed]]:
    stmt = select(StaffNeed).where(StaffNeed.status == "open")
    if branch_ids is not None:
        stmt = stmt.where(StaffNeed.branch_id.in_(branch_ids))
    out: dict[int, list[StaffNeed]] = {}
    for n in (await db.scalars(stmt.order_by(StaffNeed.id))).all():
        out.setdefault(n.branch_id, []).append(n)
    return out


async def today_states(db: AsyncSession, employees: list[Employee], moment: datetime) -> dict[int, dict[str, Any]]:
    """Xodim -> bugungi holat (davomat bilan BIR manba: `day_status`)."""
    from app.api.attendance import _rows

    today = local_date(moment)
    rows = await _rows(db, employees, today, today)
    out = {}
    for e in employees:
        d = rows[e.id][0]
        rec = d["record"]
        out[e.id] = {
            "status": d["status"], "expected": d["cell"].working and d["shift"] is not None,
            "check_in_at": rec.check_in_at if rec else None, "check_out_at": rec.check_out_at if rec else None,
            "late_minutes": rec.late_minutes if rec else 0, "shift": d["shift"],
        }  # fmt: skip
    return out


def summarize_today(states: list[dict[str, Any]]) -> dict[str, int]:
    s = [x["status"] for x in states]
    return {
        "expected": sum(1 for x in states if x["expected"]),
        "here_now": s.count("working"),
        "attended": sum(1 for x in s if x in ("present", "late", "early", "late_early", "working", "no_checkout", "incomplete", "unscheduled")),
        "late": sum(1 for x in s if x in ("late", "late_early")),
        "absent": s.count("absent"),
        "leave": s.count("leave"),
        "pending": s.count("pending"),
    }


def branch_flags(b: Branch, counts: dict[str, int], today: dict[str, int], moment: datetime, needs: list[StaffNeed]) -> list[str]:
    flags = []
    open_now = is_open_now(b, moment)
    if open_now and sum(counts.values()) > 0 and today["here_now"] == 0:
        flags.append("uncovered")
    if gaps(b, counts):
        flags.append("short")
    if needs:
        flags.append("needs")
    return flags


def severity(flags: list[str]) -> str:
    return "uncovered" if "uncovered" in flags else "short" if "short" in flags else "ok"


def quality_issues(b: Branch, counts: dict[str, int], head: int) -> list[str]:
    issues = []
    if not b.manager_user_id and counts["manager"] == 0:
        issues.append("no_manager")
    if not b.coordinator_user_id:
        issues.append("no_coordinator")
    if b.latitude is None:
        issues.append("no_geo")
    if not any(norm_of(b).values()):
        issues.append("no_norm")
    if not b.is_24h and (b.open_time is None or b.close_time is None):
        issues.append("no_hours")
    if not b.phone:
        issues.append("no_phone")
    if not b.address:
        issues.append("no_address")
    if head == 0 and b.is_active:
        issues.append("no_staff")
    if not b.is_active and head > 0:
        issues.append("inactive_with_staff")
    return issues


def fmt_time(t: time | None) -> str | None:
    return t.strftime("%H:%M") if t else None
