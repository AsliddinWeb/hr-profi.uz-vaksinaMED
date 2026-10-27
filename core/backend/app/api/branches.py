from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import get_session
from app.deps import AuthContext, error, require
from app.geo import valid_coordinates
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch, Department
from app.services.audit import audit
from app.services.notifications import deliver, notify

router = APIRouter(prefix="/v1/branches", tags=["branches"])


class BranchBase(BaseModel):
    number: int | None = Field(default=None, ge=1, le=999_999)
    name: str = Field(min_length=1, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    district: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_m: int = Field(default=100, ge=10, le=5000)

    @model_validator(mode="after")
    def _coords(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("coords_pair")
        if self.latitude is not None and not valid_coordinates(self.latitude, self.longitude):
            raise ValueError("coords_range")
        return self


class BranchIn(BranchBase):
    department_id: int | None = None
    manager_user_id: int | None = None
    coordinator_user_id: int | None = None
    is_active: bool = True


class BranchPatch(BaseModel):
    number: int | None = Field(default=None, ge=1, le=999_999)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    district: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    department_id: int | None = None
    manager_user_id: int | None = None
    coordinator_user_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_m: int | None = Field(default=None, ge=10, le=5000)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _coords(self):
        sent = self.model_fields_set
        if ("latitude" in sent) != ("longitude" in sent):
            raise ValueError("coords_pair")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("coords_pair")
        if self.latitude is not None and not valid_coordinates(self.latitude, self.longitude):
            raise ValueError("coords_range")
        return self


def _f(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def branch_out(b: Branch, manager: str | None, coordinator: str | None, department: str | None) -> dict:
    return {
        "id": b.id,
        "number": b.number,
        "name": b.name,
        "address": b.address,
        "district": b.district,
        "phone": b.phone,
        "department_id": b.department_id,
        "department_name": department,
        "manager_user_id": b.manager_user_id,
        "manager_name": manager,
        "coordinator_user_id": b.coordinator_user_id,
        "coordinator_name": coordinator,
        "latitude": _f(b.latitude),
        "longitude": _f(b.longitude),
        "geofence_radius_m": b.geofence_radius_m,
        "is_active": b.is_active,
    }


Manager = aliased(User)
Coordinator = aliased(User)


def _select():
    return (
        select(Branch, Manager.full_name, Coordinator.full_name, Department.name)
        .outerjoin(Manager, Manager.id == Branch.manager_user_id)
        .outerjoin(Coordinator, Coordinator.id == Branch.coordinator_user_id)
        .outerjoin(Department, Department.id == Branch.department_id)
    )


async def _one(db: AsyncSession, branch_id: int) -> dict:
    row = (await db.execute(_select().where(Branch.id == branch_id))).first()
    if not row:
        raise error(404, "not_found")
    return branch_out(*row)


async def _check_refs(db: AsyncSession, **ids: int | None) -> dict[str, User | Department | None]:
    out: dict[str, Any] = {}
    for key, value in ids.items():
        if value is None:
            out[key] = None
        elif key == "department_id":
            dept = await db.get(Department, value)
            if not dept:
                raise error(400, "unknown_department")
            out[key] = dept
        else:
            user = await db.get(User, value)
            if not user or not user.is_active:
                raise error(400, "unknown_user", field=key)
            out[key] = user
    return out


@router.get("")
async def list_branches(
    q: str | None = None,
    department_id: int | None = None,
    coordinator_id: int | None = None,
    manager_id: int | None = None,
    no_manager: bool = False,
    no_geo: bool = False,
    active: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("branches.read")),
):
    stmt = _select()
    if q and q.strip():
        term = q.strip().lstrip("№#")
        like = f"%{q.strip()}%"
        conds = [Branch.name.ilike(like), Branch.address.ilike(like), Branch.district.ilike(like)]
        if term.isdigit():
            conds.append(Branch.number == int(term))
        stmt = stmt.where(or_(*conds))
    if department_id:
        stmt = stmt.where(Branch.department_id == department_id)
    if coordinator_id:
        stmt = stmt.where(Branch.coordinator_user_id == coordinator_id)
    if manager_id:
        stmt = stmt.where(Branch.manager_user_id == manager_id)
    if no_manager:
        stmt = stmt.where(Branch.manager_user_id.is_(None))
    if no_geo:
        stmt = stmt.where(Branch.latitude.is_(None))
    if active is not None:
        stmt = stmt.where(Branch.is_active.is_(active))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await db.execute(
            stmt.order_by(Branch.number.is_(None), Branch.number, Branch.name)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    s = (
        await db.execute(
            select(
                func.count(),
                func.count(Branch.manager_user_id),
                func.count(Branch.latitude),
                func.count(case((Branch.is_active.is_(True), 1))),
            )
        )
    ).one()
    summary = {"total": s[0], "with_manager": s[1], "with_geo": s[2], "active": s[3]}
    return {
        "total": total or 0,
        "page": page,
        "size": size,
        "summary": summary,
        "items": [branch_out(*r) for r in rows],
    }


@router.get("/map")
async def branches_map(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("branches.read"))
):
    """Xarita uchun yengil ro'yxat: faqat joylashuvi bor filiallar."""
    rows = (await db.execute(_select().where(Branch.latitude.is_not(None)))).all()
    return [
        {
            "id": b.id,
            "number": b.number,
            "name": b.name,
            "latitude": _f(b.latitude),
            "longitude": _f(b.longitude),
            "radius": b.geofence_radius_m,
            "manager_name": m,
            "coordinator_name": c,
            "is_active": b.is_active,
        }
        for b, m, c, _d in rows
    ]


@router.get("/{branch_id}")
async def get_branch(
    branch_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("branches.read")),
):
    return await _one(db, branch_id)


@router.post("", status_code=201)
async def create_branch(
    body: BranchIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("branches.manage")),
):
    refs = await _check_refs(
        db,
        department_id=body.department_id,
        manager_user_id=body.manager_user_id,
        coordinator_user_id=body.coordinator_user_id,
    )
    data = body.model_dump()
    branch = Branch(**{**data, "name": body.name.strip()})
    db.add(branch)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "branch_number_taken") from exc

    notes = []
    params = {"name": branch.name}
    link = "/branches"
    for key, kind in (
        ("manager_user_id", "branch.manager_assigned"),
        ("coordinator_user_id", "branch.coordinator_assigned"),
    ):
        user = refs[key]
        if user and user.id != auth.user.id:
            notes += await notify(db, [user.id], kind, params=params, link=link)
    await audit(db, request, "branch.create", actor=auth.user, entity="branch", entity_id=branch.id,
                data={"name": branch.name, "number": branch.number})  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    return await _one(db, branch.id)


@router.patch("/{branch_id}")
async def update_branch(
    branch_id: int,
    body: BranchPatch,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("branches.manage")),
):
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise error(404, "not_found")
    sent = body.model_fields_set
    refs = await _check_refs(
        db,
        **{
            k: getattr(body, k)
            for k in ("department_id", "manager_user_id", "coordinator_user_id")
            if k in sent
        },
    )
    changes: dict[str, Any] = {}
    notes: list = []
    nullable = {"number", "address", "district", "phone", "department_id", "manager_user_id",
                "coordinator_user_id", "latitude", "longitude"}  # fmt: skip
    for field in sent:
        value = getattr(body, field)
        if value is None and field not in nullable:
            continue
        if isinstance(value, str):
            value = value.strip() or (None if field in nullable else value)
        current = getattr(branch, field)
        cmp_current = float(current) if isinstance(current, Decimal) else current
        if cmp_current == value:
            continue
        changes[field] = {"from": cmp_current, "to": value}
        setattr(branch, field, value)
        kind = {
            "manager_user_id": "branch.manager_assigned",
            "coordinator_user_id": "branch.coordinator_assigned",
        }.get(field)
        user = refs.get(field)
        if kind and user and user.id != auth.user.id:
            notes += await notify(db, [user.id], kind, params={"name": branch.name}, link="/branches")

    if changes:
        await audit(db, request, "branch.update", actor=auth.user, entity="branch",
                    entity_id=branch.id, data=changes)  # fmt: skip
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise error(409, "branch_number_taken") from exc
        await deliver(request.app, notes)
    return await _one(db, branch_id)


@router.delete("/{branch_id}", status_code=204)
async def delete_branch(
    branch_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("branches.manage")),
):
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise error(404, "not_found")
    if await db.scalar(select(func.count()).select_from(Employee).where(Employee.branch_id == branch_id)):
        raise error(409, "has_employees")
    await audit(db, request, "branch.delete", actor=auth.user, entity="branch", entity_id=branch.id,
                data={"name": branch.name, "number": branch.number})  # fmt: skip
    await db.delete(branch)  # F4 dan keyin xodimi bor filial o'chirilmaydi (RESTRICT)
    await db.commit()


class BulkRow(BaseModel):
    number: int | None = None
    name: str | None = None
    address: str | None = None
    district: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_m: int | None = None


class BulkIn(BaseModel):
    rows: list[BulkRow] = Field(max_length=1000)
    dry_run: bool = True


def _row_errors(row: BulkRow, seen: set[int]) -> list[str]:
    errs: list[str] = []
    if not (row.name and row.name.strip()):
        errs.append("name_required")
    if row.number is not None:
        if row.number < 1:
            errs.append("number_invalid")
        elif row.number in seen:
            errs.append("number_duplicate")
        seen.add(row.number)
    if (row.latitude is None) != (row.longitude is None):
        errs.append("coords_pair")
    elif row.latitude is not None and not valid_coordinates(row.latitude, row.longitude):
        errs.append("coords_range")
    if row.geofence_radius_m is not None and not 10 <= row.geofence_radius_m <= 5000:
        errs.append("radius_range")
    return errs


@router.post("/bulk")
async def bulk_import(
    body: BulkIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("branches.manage")),
):
    """Ommaviy import: `number` bo'yicha mavjudini yangilaydi, bo'lmasa yaratadi.

    Hammasi yoki hech narsa: birorta qatorda xato bo'lsa, hech narsa saqlanmaydi.
    `dry_run=true` faqat tekshiradi va nima bo'lishini ko'rsatadi.
    """
    seen: set[int] = set()
    errors = []
    for i, row in enumerate(body.rows, start=1):
        for code in _row_errors(row, seen):
            errors.append({"row": i, "code": code})

    numbers = [r.number for r in body.rows if r.number is not None]
    existing = (
        {b.number: b for b in (await db.scalars(select(Branch).where(Branch.number.in_(numbers)))).all()}
        if numbers
        else {}
    )
    created = sum(1 for r in body.rows if r.number is None or r.number not in existing)
    updated = len(body.rows) - created
    result = {"created": created, "updated": updated, "errors": errors, "applied": False}
    if errors or body.dry_run:
        return result

    for row in body.rows:
        fields = {
            k: (v.strip() if isinstance(v, str) else v)
            for k, v in row.model_dump(exclude_none=True).items()
        }
        branch = existing.get(row.number) if row.number is not None else None
        if branch:
            for k, v in fields.items():
                setattr(branch, k, v)
        else:
            db.add(Branch(**fields))
    await audit(db, request, "branch.bulk_import", actor=auth.user, entity="branch",
                data={"created": created, "updated": updated})  # fmt: skip
    await db.commit()
    result["applied"] = True
    return result
