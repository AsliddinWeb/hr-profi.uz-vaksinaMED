from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.auth import User
from app.models.employees import Employee, EmployeeEvent
from app.models.org import Branch, Department, Position
from app.services import auth as auth_svc
from app.services import employees as svc
from app.services import schedule as schedule_svc
from app.services.audit import audit
from app.services.employee_accounts import create_account, link_account
from app.services.notifications import deliver, notify
from app.services.org import descendants, load_departments

router = APIRouter(prefix="/v1/employees", tags=["employees"])

SENSITIVE_FIELDS = ("birth_date", "address", "passport_no", "pinfl")


class PersonBase(BaseModel):
    """Shaxsiy ma'lumotlar maydonlari uchun umumiy tekshiruvlar."""

    @field_validator("phone", "phone2", mode="before", check_fields=False)
    @classmethod
    def _phone(cls, v):
        return svc.normalize_phone(v) if isinstance(v, str) else v

    @field_validator("passport_no", mode="before", check_fields=False)
    @classmethod
    def _passport(cls, v):
        return svc.normalize_passport(v) if isinstance(v, str) else v

    @field_validator("pinfl", mode="before", check_fields=False)
    @classmethod
    def _pinfl(cls, v):
        return svc.normalize_pinfl(v) if isinstance(v, str) else v

    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def _email(cls, v):
        return svc.normalize_email(v) if isinstance(v, str) else v

    @field_validator("birth_date", check_fields=False)
    @classmethod
    def _birth(cls, v: date | None):
        if v is None:
            return v
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if v.year < 1920 or age < 14:
            raise ValueError("birth_date_invalid")
        return v


class EmployeeCreate(PersonBase):
    last_name: str = Field(min_length=1, max_length=80)
    first_name: str = Field(min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    gender: str | None = Field(default=None, pattern="^[mf]$")
    phone: str | None = None
    phone2: str | None = None
    email: str | None = None
    address: str | None = Field(default=None, max_length=300)
    passport_no: str | None = None
    pinfl: str | None = None
    department_id: int | None = None
    position_id: int | None = None
    branch_id: int | None = None
    work_group_id: int | None = None
    hire_date: date | None = None
    confirm_duplicate: bool = False
    create_account: bool = False
    role_key: str | None = None


class EmployeeUpdate(PersonBase):
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    gender: str | None = Field(default=None, pattern="^[mf]$")
    phone: str | None = None
    phone2: str | None = None
    email: str | None = None
    address: str | None = Field(default=None, max_length=300)
    passport_no: str | None = None
    pinfl: str | None = None
    hire_date: date | None = None
    work_group_id: int | None = None
    confirm_duplicate: bool = False


class TransferIn(BaseModel):
    department_id: int | None = None
    position_id: int | None = None
    branch_id: int | None = None
    effective_date: date
    note: str | None = Field(default=None, max_length=500)


class DismissIn(BaseModel):
    date: date
    reason: str = Field(pattern="^(own_will|contract_end|discipline|reduction|other)$")
    note: str | None = Field(default=None, max_length=500)
    block_account: bool = True


class ReinstateIn(BaseModel):
    date: date
    note: str | None = Field(default=None, max_length=500)
    reactivate_account: bool = False


async def get_employee(db: AsyncSession, employee_id: int) -> Employee:
    e = await db.get(Employee, employee_id)
    if not e:
        raise error(404, "not_found")
    return e


async def one_out(db: AsyncSession, e: Employee, auth: AuthContext) -> dict[str, Any]:
    refs = await svc.load_refs(db, [e])
    return svc.employee_out(e, refs, auth)


def _needs_sensitive(auth: AuthContext, fields: set[str]) -> None:
    if fields & set(SENSITIVE_FIELDS) and not auth.can("employees.sensitive"):
        raise error(403, "forbidden", permission="employees.sensitive")


async def _snapshot(db: AsyncSession, department_id, position_id, branch_id) -> dict[str, Any]:
    dept = await db.get(Department, department_id) if department_id else None
    pos = await db.get(Position, position_id) if position_id else None
    br = await db.get(Branch, branch_id) if branch_id else None
    return {
        "department": {"id": dept.id, "name": dept.name} if dept else None,
        "position": {"id": pos.id, "name": pos.name} if pos else None,
        "branch": {"id": br.id, "number": br.number, "name": br.name} if br else None,
    }


@router.get("")
async def list_employees(
    q: str | None = None,
    department_id: int | None = None,
    include_children: bool = True,
    branch_id: int | None = None,
    position_id: int | None = None,
    work_group_id: int | None = None,
    status: str | None = Query(default=None, pattern="^(active|dismissed)$"),
    has_account: bool | None = None,
    sort: str = Query(default="full_name", pattern="^(full_name|employee_no|hire_date)$"),
    desc: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.read")),
):
    stmt = select(Employee)
    if q and q.strip():
        term = q.strip().lstrip("№#")
        like = f"%{q.strip()}%"
        conds = [Employee.full_name.ilike(like)]
        digits = "".join(c for c in q if c.isdigit())
        if term.isdigit():
            conds.append(Employee.employee_no == int(term))
        if len(digits) >= 4:
            conds.append(Employee.phone.like(f"%{digits}%"))
        stmt = stmt.where(or_(*conds))
    if department_id:
        ids = {department_id}
        if include_children:
            ids |= descendants(await load_departments(db), department_id)
        stmt = stmt.where(Employee.department_id.in_(ids))
    if branch_id:
        stmt = stmt.where(Employee.branch_id == branch_id)
    if position_id:
        stmt = stmt.where(Employee.position_id == position_id)
    if work_group_id:
        stmt = stmt.where(await schedule_svc.group_condition(db, work_group_id))
    if status:
        stmt = stmt.where(Employee.status == status)
    if has_account is not None:
        stmt = stmt.where(Employee.user_id.is_not(None) if has_account else Employee.user_id.is_(None))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = {"full_name": Employee.full_name, "employee_no": Employee.employee_no, "hire_date": Employee.hire_date}[sort]
    order = (col.desc() if desc else col.asc(), Employee.id)
    rows = (await db.scalars(stmt.order_by(*order).offset((page - 1) * size).limit(size))).all()
    refs = await svc.load_refs(db, list(rows))

    s = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(Employee.status == "active"),
                func.count().filter(Employee.status == "dismissed"),
                func.count(Employee.user_id),
            )
        )
    ).one()
    return {
        "total": total or 0,
        "page": page,
        "size": size,
        "summary": {"total": s[0], "active": s[1], "dismissed": s[2], "with_account": s[3]},
        "items": [svc.employee_out(e, refs, auth) for e in rows],
    }


@router.post("", status_code=201)
async def create_employee(
    body: EmployeeCreate,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.create")),
):
    _needs_sensitive(auth, {f for f in SENSITIVE_FIELDS if getattr(body, f)})
    await svc.validate_assignment(db, body.department_id, body.position_id, body.branch_id)
    await svc.validate_work_group(db, body.work_group_id)
    full_name = svc.build_full_name(body.last_name, body.first_name, body.middle_name)

    matches = await svc.find_duplicates(
        db, pinfl=body.pinfl, passport_no=body.passport_no, phone=body.phone,
        full_name=full_name, birth_date=body.birth_date,
    )  # fmt: skip
    if matches and (any(m.hard for m in matches) or not body.confirm_duplicate):
        code = "duplicate_identifier" if any(m.hard for m in matches) else "possible_duplicate"
        raise error(409, code, matches=[svc.match_out(m) for m in matches])
    if body.create_account and not body.role_key:
        raise error(400, "role_required")

    hire = body.hire_date or date.today()
    emp = Employee(
        last_name=body.last_name.strip(), first_name=body.first_name.strip(),
        middle_name=(body.middle_name or "").strip() or None, full_name=full_name,
        birth_date=body.birth_date, gender=body.gender, phone=body.phone, phone2=body.phone2,
        email=body.email, address=body.address, passport_no=body.passport_no, pinfl=body.pinfl,
        department_id=body.department_id, position_id=body.position_id, branch_id=body.branch_id,
        work_group_id=body.work_group_id, status="active", hire_date=hire,
    )  # fmt: skip
    db.add(emp)
    try:
        await db.flush()
    except IntegrityError as exc:  # parallel so'rovda identifikator band bo'lib qolsa
        await db.rollback()
        raise error(409, "duplicate_identifier", matches=[]) from exc
    await db.refresh(emp)

    snap = await _snapshot(db, emp.department_id, emp.position_id, emp.branch_id)
    svc.add_event(db, emp.id, "hired", hire, data=snap, actor_id=auth.user.id)

    password = None
    user = None
    if body.create_account and body.role_key:
        user, password = await create_account(db, emp, body.role_key, auth)

    await audit(db, request, "employee.create", actor=auth.user, entity="employee", entity_id=emp.id,
                data={"name": emp.full_name, "employee_no": emp.employee_no,
                      "account": user.login if user else None})  # fmt: skip
    await db.commit()
    await request.app.state.events.emit("employee.created", employee_id=emp.id, employee_no=emp.employee_no, full_name=emp.full_name)
    return {
        "employee": await one_out(db, emp, auth),
        "temp_password": password,
        "login": user.login if user else None,
    }


@router.get("/{employee_id}")
async def get_one(
    employee_id: int,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.read")),
):
    return await one_out(db, await get_employee(db, employee_id), auth)


@router.patch("/{employee_id}")
async def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.update")),
):
    emp = await get_employee(db, employee_id)
    sent = body.model_fields_set - {"confirm_duplicate"}
    _needs_sensitive(auth, sent)
    if "work_group_id" in sent:
        await svc.validate_work_group(db, body.work_group_id)
    changes: dict[str, Any] = {}
    sensitive_keys = {"passport_no", "pinfl", "birth_date", "address"}

    required = {"last_name", "first_name"}
    for field in sent:
        value = getattr(body, field)
        if isinstance(value, str):
            value = value.strip() or None
        if field in required and not value:
            raise error(422, "validation")
        if getattr(emp, field) != value:
            changes[field] = value

    if not changes:
        return await one_out(db, emp, auth)

    last = changes.get("last_name", emp.last_name)
    first = changes.get("first_name", emp.first_name)
    middle = changes["middle_name"] if "middle_name" in changes else emp.middle_name
    full_name = svc.build_full_name(last, first, middle)
    watch = {"pinfl", "passport_no", "phone", "phone2", "birth_date", "last_name", "first_name", "middle_name"}
    if changes.keys() & watch:
        matches = await svc.find_duplicates(
            db,
            pinfl=changes.get("pinfl", emp.pinfl) if "pinfl" in changes else None,
            passport_no=changes.get("passport_no", emp.passport_no) if "passport_no" in changes else None,
            phone=changes.get("phone") if "phone" in changes else None,
            full_name=full_name,
            birth_date=changes.get("birth_date", emp.birth_date),
            exclude_id=emp.id,
        )
        # Faqat o'zgartirilgan sabab bo'yicha (eskidan mavjud dublikat qayta so'ralmasin)
        relevant = [m for m in matches if m.hard or not body.confirm_duplicate]
        if relevant:
            code = "duplicate_identifier" if any(m.hard for m in relevant) else "possible_duplicate"
            raise error(409, code, matches=[svc.match_out(m) for m in relevant])

    for field, value in changes.items():
        setattr(emp, field, value)
    emp.full_name = full_name
    if emp.user_id and ({"phone"} | {"last_name", "first_name", "middle_name"}) & changes.keys():
        user = await db.get(User, emp.user_id)
        if user:
            user.full_name = full_name
            if "phone" in changes:
                user.phone = emp.phone
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "duplicate_identifier", matches=[]) from exc

    logged = {k: ("***" if k in sensitive_keys else (str(v) if isinstance(v, date) else v)) for k, v in changes.items()}
    await audit(db, request, "employee.update", actor=auth.user, entity="employee", entity_id=emp.id, data=logged)
    await db.commit()
    return await one_out(db, emp, auth)


@router.get("/{employee_id}/events")
async def events(
    employee_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("employees.read")),
):
    await get_employee(db, employee_id)
    rows = (
        await db.execute(
            select(EmployeeEvent, User.full_name)
            .outerjoin(User, User.id == EmployeeEvent.actor_id)
            .where(EmployeeEvent.employee_id == employee_id)
            .order_by(EmployeeEvent.effective_date.desc(), EmployeeEvent.id.desc())
        )
    ).all()
    return [
        {
            "id": ev.id,
            "kind": ev.kind,
            "effective_date": ev.effective_date,
            "data": ev.data,
            "note": ev.note,
            "actor": actor,
            "created_at": ev.created_at,
        }
        for ev, actor in rows
    ]


@router.post("/{employee_id}/transfer")
async def transfer(
    employee_id: int,
    body: TransferIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.transfer")),
):
    emp = await get_employee(db, employee_id)
    changes, notes = await transfer_one(db, emp, body, auth)
    await audit(db, request, "employee.transfer", actor=auth.user, entity="employee", entity_id=emp.id,
                data={"changes": changes, "date": str(body.effective_date)})  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    return await one_out(db, emp, auth)


async def transfer_one(
    db: AsyncSession, emp: Employee, body: TransferIn, auth: AuthContext
) -> tuple[dict, list]:
    """Bitta xodimni o'tkazadi (ommaviy amal ham shundan foydalanadi). Commit qilmaydi.

    (o'zgarishlar, bildirishnomalar) qaytaradi: bildirishnomalar commitdan keyin `deliver` qilinadi.
    """
    if emp.status != "active":
        raise error(409, "employee_dismissed")
    sent = body.model_fields_set
    new = {
        "department_id": body.department_id if "department_id" in sent else emp.department_id,
        "position_id": body.position_id if "position_id" in sent else emp.position_id,
        "branch_id": body.branch_id if "branch_id" in sent else emp.branch_id,
    }
    if all(getattr(emp, k) == v for k, v in new.items()):
        raise error(400, "no_changes")
    if emp.hire_date and body.effective_date < emp.hire_date:
        raise error(400, "date_before_hire")
    await svc.validate_assignment(db, new["department_id"], new["position_id"], new["branch_id"])

    before = await _snapshot(db, emp.department_id, emp.position_id, emp.branch_id)
    after = await _snapshot(db, **new)
    changes = {k: {"from": before[k], "to": after[k]} for k in before if before[k] != after[k]}
    for k, v in new.items():
        setattr(emp, k, v)
    svc.add_event(db, emp.id, "transfer", body.effective_date, data={"changes": changes},
                  note=body.note, actor_id=auth.user.id)  # fmt: skip

    notes: list = []
    if emp.user_id:
        labels = {"department": "Bo'lim", "position": "Lavozim", "branch": "Filial"}
        summary = "; ".join(f"{labels[k]}: {(c['to'] or {}).get('name') or '—'}" for k, c in changes.items())
        notes = await notify(db, [emp.user_id], "employee.transferred", params={"summary": summary})
    return changes, notes


@router.post("/{employee_id}/dismiss")
async def dismiss(
    employee_id: int,
    body: DismissIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.dismiss")),
):
    emp = await get_employee(db, employee_id)
    await dismiss_one(db, emp, body, auth)
    await audit(db, request, "employee.dismiss", actor=auth.user, entity="employee", entity_id=emp.id,
                data={"reason": body.reason, "date": str(body.date), "block_account": body.block_account})  # fmt: skip
    await db.commit()
    await request.app.state.events.emit("employee.dismissed", employee_id=emp.id, full_name=emp.full_name, date=body.date, reason=body.reason)
    return await one_out(db, emp, auth)


async def dismiss_one(db: AsyncSession, emp: Employee, body: DismissIn, auth: AuthContext) -> None:
    """Bitta xodimni bo'shatadi (ommaviy amal ham shundan foydalanadi). Commit qilmaydi."""
    from app.api.users import last_superuser_guard

    if emp.status != "active":
        raise error(409, "already_dismissed")
    if body.date > date.today():
        raise error(400, "date_in_future")
    if emp.hire_date and body.date < emp.hire_date:
        raise error(400, "date_before_hire")
    if body.reason == "other" and not (body.note or "").strip():
        raise error(400, "note_required")

    user = await db.get(User, emp.user_id) if emp.user_id else None
    if user and body.block_account and user.is_active:
        if user.id == auth.user.id:
            raise error(409, "cannot_deactivate_self")
        await last_superuser_guard(db, user)
        user.is_active = False
        await auth_svc.revoke_user_sessions(db, user.id)

    emp.status = "dismissed"
    emp.dismissal_date = body.date
    emp.dismissal_reason = body.reason
    emp.dismissal_note = (body.note or None) and body.note[:500]
    snap = await _snapshot(db, emp.department_id, emp.position_id, emp.branch_id)
    svc.add_event(db, emp.id, "dismissed", body.date, data={**snap, "reason": body.reason},
                  note=body.note, actor_id=auth.user.id)  # fmt: skip


@router.post("/{employee_id}/reinstate")
async def reinstate(
    employee_id: int,
    body: ReinstateIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.dismiss")),
):
    emp = await get_employee(db, employee_id)
    await reinstate_one(db, emp, body, auth)
    await audit(db, request, "employee.reinstate", actor=auth.user, entity="employee", entity_id=emp.id,
                data={"date": str(body.date), "reactivate_account": body.reactivate_account})  # fmt: skip
    await db.commit()
    return await one_out(db, emp, auth)


async def reinstate_one(db: AsyncSession, emp: Employee, body: ReinstateIn, auth: AuthContext) -> None:
    if emp.status != "dismissed":
        raise error(409, "not_dismissed")
    if emp.dismissal_date and body.date < emp.dismissal_date:
        raise error(400, "date_before_dismissal")
    emp.status = "active"
    emp.dismissal_date = emp.dismissal_reason = emp.dismissal_note = None
    if body.reactivate_account and emp.user_id:
        user = await db.get(User, emp.user_id)
        if user:
            user.is_active = True
    snap = await _snapshot(db, emp.department_id, emp.position_id, emp.branch_id)
    svc.add_event(db, emp.id, "reinstated", body.date, data=snap, note=body.note, actor_id=auth.user.id)


class AccountIn(BaseModel):
    role_key: str | None = None
    user_id: int | None = None


@router.post("/{employee_id}/account")
async def account_create_or_link(
    employee_id: int,
    body: AccountIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.accounts")),
):
    """`role_key` -> yangi hisob yaratadi (vaqtinchalik parol qaytaradi); `user_id` -> mavjud hisobni ulaydi."""
    emp = await get_employee(db, employee_id)
    if bool(body.role_key) == bool(body.user_id):
        raise error(400, "role_or_user")
    password = None
    if body.role_key:
        user, password = await create_account(db, emp, body.role_key, auth)
    else:
        if emp.user_id is not None:
            raise error(409, "account_exists")
        user = await link_account(db, emp, body.user_id)  # type: ignore[arg-type]
    await audit(db, request, "employee.account_create" if password else "employee.account_link",
                actor=auth.user, entity="employee", entity_id=emp.id, data={"login": user.login})  # fmt: skip
    await db.commit()
    return {"login": user.login, "temp_password": password, "employee": await one_out(db, emp, auth)}


@router.delete("/{employee_id}/account", status_code=204)
async def account_unlink(
    employee_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.accounts")),
):
    emp = await get_employee(db, employee_id)
    if emp.user_id is None:
        return
    if emp.user_id == auth.user.id:
        raise error(409, "cannot_unlink_self")
    emp.user_id = None
    await audit(db, request, "employee.account_unlink", actor=auth.user, entity="employee", entity_id=emp.id)
    await db.commit()
