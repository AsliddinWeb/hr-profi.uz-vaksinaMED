"""Xodimlar: normallashtirish, tekshiruvlar, dublikat izlash, tarix, serializatsiya."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.auth import User
from app.models.employees import Employee, EmployeeEvent
from app.models.org import Branch, Department, Position
from app.models.schedule import WorkGroup

PHONE_RE_LEN = 12
PASSPORT_RE = re.compile(r"^[A-Z]{2}\d{7}$")
PINFL_RE = re.compile(r"^\d{14}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DISMISS_REASONS = ("own_will", "contract_end", "discipline", "reduction", "other")
DOC_KINDS = ("passport", "contract", "diploma", "medical", "certificate", "other")


def normalize_phone(raw: str | None) -> str | None:
    """+998XXXXXXXXX ko'rinishiga keltiradi. Bo'sh = None. Yaroqsiz = ValueError."""
    if raw is None or not raw.strip():
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == PHONE_RE_LEN and digits.startswith("998"):
        return "+" + digits
    raise ValueError("phone_invalid")


def normalize_passport(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    value = re.sub(r"[\s\-]", "", raw).upper()
    if not PASSPORT_RE.match(value):
        raise ValueError("passport_invalid")
    return value


def normalize_pinfl(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    value = re.sub(r"\s", "", raw)
    if not PINFL_RE.match(value):
        raise ValueError("pinfl_invalid")
    return value


def normalize_email(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    value = raw.strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("email_invalid")
    return value


def build_full_name(last: str, first: str, middle: str | None) -> str:
    return " ".join(p for p in (last.strip(), first.strip(), (middle or "").strip()) if p)


def name_key(full_name: str) -> str:
    return re.sub(r"\s+", " ", full_name.strip().lower())


def mask_passport(value: str | None) -> str | None:
    return f"{value[:2]}•••{value[-3:]}" if value else None


def mask_pinfl(value: str | None) -> str | None:
    return f"{value[:3]}••••••••{value[-3:]}" if value else None


# --- Bog'liq obyektlarni tekshirish -------------------------------------------------


async def validate_assignment(
    db: AsyncSession, department_id: int | None, position_id: int | None, branch_id: int | None
) -> None:
    dept = None
    if department_id is not None:
        dept = await db.get(Department, department_id)
        if not dept or not dept.is_active:
            raise error(400, "unknown_department")
    if position_id is not None:
        pos = await db.get(Position, position_id)
        if not pos or not pos.is_active:
            raise error(400, "unknown_position")
        # Lavozim shu bo'limniki yoki umumiy (bo'limsiz) bo'lishi kerak
        if pos.department_id is not None and pos.department_id != department_id:
            raise error(400, "position_department_mismatch")
    if branch_id is not None:
        branch = await db.get(Branch, branch_id)
        if not branch or not branch.is_active:
            raise error(400, "unknown_branch")


async def validate_work_group(db: AsyncSession, group_id: int | None) -> None:
    if group_id is None:
        return
    group = await db.get(WorkGroup, group_id)
    if not group or not group.is_active:
        raise error(400, "unknown_group")


# --- Dublikatlar -------------------------------------------------------------------


@dataclass
class Match:
    employee: Employee
    reasons: list[str]  # pinfl | passport | phone | name_birth

    @property
    def hard(self) -> bool:
        return bool({"pinfl", "passport"} & set(self.reasons))


async def find_duplicates(
    db: AsyncSession,
    *,
    pinfl: str | None,
    passport_no: str | None,
    phone: str | None,
    full_name: str,
    birth_date: date | None,
    exclude_id: int | None = None,
) -> list[Match]:
    conds = []
    if pinfl:
        conds.append(Employee.pinfl == pinfl)
    if passport_no:
        conds.append(Employee.passport_no == passport_no)
    if phone:
        conds.append(or_(Employee.phone == phone, Employee.phone2 == phone))
    if birth_date:
        conds.append(
            (func.lower(Employee.full_name) == name_key(full_name)) & (Employee.birth_date == birth_date)
        )
    if not conds:
        return []
    stmt = select(Employee).where(or_(*conds))
    if exclude_id is not None:
        stmt = stmt.where(Employee.id != exclude_id)
    found: list[Match] = []
    for e in (await db.scalars(stmt)).all():
        reasons = []
        if pinfl and e.pinfl == pinfl:
            reasons.append("pinfl")
        if passport_no and e.passport_no == passport_no:
            reasons.append("passport")
        if phone and phone in (e.phone, e.phone2):
            reasons.append("phone")
        if birth_date and e.birth_date == birth_date and name_key(e.full_name) == name_key(full_name):
            reasons.append("name_birth")
        found.append(Match(e, reasons))
    return found


def match_out(m: Match) -> dict[str, Any]:
    e = m.employee
    return {
        "id": e.id,
        "employee_no": e.employee_no,
        "full_name": e.full_name,
        "phone": e.phone,
        "status": e.status,
        "reasons": m.reasons,
    }


async def duplicate_groups(db: AsyncSession) -> list[list[Employee]]:
    """Barcha xodimlar bo'yicha dublikat guruhlari (telefon, ism+tug'ilgan sana, pinfl, pasport)."""
    employees = (await db.scalars(select(Employee).order_by(Employee.id))).all()
    parent: dict[int, int] = {e.id: e.id for e in employees}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    seen: dict[tuple[str, Any], int] = {}
    for e in employees:
        keys: list[tuple[str, Any]] = []
        if e.pinfl:
            keys.append(("pinfl", e.pinfl))
        if e.passport_no:
            keys.append(("passport", e.passport_no))
        for ph in {e.phone, e.phone2} - {None}:
            keys.append(("phone", ph))
        if e.birth_date:
            keys.append(("name_birth", (name_key(e.full_name), e.birth_date)))
        for k in keys:
            if k in seen:
                union(e.id, seen[k])
            else:
                seen[k] = e.id

    groups: dict[int, list[Employee]] = {}
    for e in employees:
        groups.setdefault(find(e.id), []).append(e)
    return [g for g in groups.values() if len(g) > 1]


# --- Tarix -------------------------------------------------------------------------


def add_event(
    db: AsyncSession,
    employee_id: int,
    kind: str,
    effective: date,
    *,
    data: dict[str, Any] | None = None,
    note: str | None = None,
    actor_id: int | None = None,
) -> None:
    db.add(
        EmployeeEvent(
            employee_id=employee_id,
            kind=kind,
            effective_date=effective,
            data=data,
            note=(note or None) and note[:500],
            actor_id=actor_id,
        )
    )


# --- Serializatsiya ------------------------------------------------------------------


@dataclass
class Refs:
    departments: dict[int, str]
    positions: dict[int, str]
    branches: dict[int, tuple[int | None, str]]
    users: dict[int, User]
    groups: dict[int, str]


async def load_refs(db: AsyncSession, employees: list[Employee]) -> Refs:
    dept_ids = {e.department_id for e in employees if e.department_id}
    pos_ids = {e.position_id for e in employees if e.position_id}
    br_ids = {e.branch_id for e in employees if e.branch_id}
    user_ids = {e.user_id for e in employees if e.user_id}
    group_ids = {e.work_group_id for e in employees if e.work_group_id}
    departments = (
        {d.id: d.name for d in (await db.scalars(select(Department).where(Department.id.in_(dept_ids)))).all()}
        if dept_ids
        else {}
    )
    positions = (
        {p.id: p.name for p in (await db.scalars(select(Position).where(Position.id.in_(pos_ids)))).all()}
        if pos_ids
        else {}
    )
    branches = (
        {b.id: (b.number, b.name) for b in (await db.scalars(select(Branch).where(Branch.id.in_(br_ids)))).all()}
        if br_ids
        else {}
    )
    users = (
        {u.id: u for u in (await db.scalars(select(User).where(User.id.in_(user_ids)))).unique().all()}
        if user_ids
        else {}
    )
    groups = (
        {g.id: g.name for g in (await db.scalars(select(WorkGroup).where(WorkGroup.id.in_(group_ids)))).all()}
        if group_ids
        else {}
    )
    return Refs(departments, positions, branches, users, groups)


def employee_out(e: Employee, refs: Refs, auth: AuthContext) -> dict[str, Any]:
    sensitive = auth.can("employees.sensitive")
    user = refs.users.get(e.user_id) if e.user_id else None
    branch = refs.branches.get(e.branch_id) if e.branch_id else None
    out: dict[str, Any] = {
        "id": e.id,
        "employee_no": e.employee_no,
        "last_name": e.last_name,
        "first_name": e.first_name,
        "middle_name": e.middle_name,
        "full_name": e.full_name,
        "gender": e.gender,
        "phone": e.phone,
        "phone2": e.phone2,
        "email": e.email,
        "has_photo": e.photo_key is not None,
        "department": {"id": e.department_id, "name": refs.departments.get(e.department_id)} if e.department_id else None,
        "position": {"id": e.position_id, "name": refs.positions.get(e.position_id)} if e.position_id else None,
        "branch": {"id": e.branch_id, "number": branch[0], "name": branch[1]} if e.branch_id and branch else None,
        "work_group": {"id": e.work_group_id, "name": refs.groups.get(e.work_group_id)} if e.work_group_id else None,
        "status": e.status,
        "hire_date": e.hire_date,
        "dismissal_date": e.dismissal_date,
        "dismissal_reason": e.dismissal_reason,
        "dismissal_note": e.dismissal_note,
        "user": {"id": user.id, "login": user.login, "is_active": user.is_active} if user else None,
        "sensitive": sensitive,
    }
    if sensitive:
        out.update(birth_date=e.birth_date, address=e.address, passport_no=e.passport_no, pinfl=e.pinfl)
    else:
        out.update(birth_date=None, address=None, passport_no=mask_passport(e.passport_no), pinfl=mask_pinfl(e.pinfl))
    return out
