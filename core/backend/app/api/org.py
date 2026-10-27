from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require, require_any
from app.models.auth import Role, User
from app.models.employees import Employee
from app.models.org import Branch, Department, Position
from app.services import org as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify

router = APIRouter(prefix="/v1/org", tags=["org"])

KINDS = "^(office|pharmacy|warehouse|other)$"
COLOR = r"^#[0-9a-fA-F]{6}$"


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None
    head_user_id: int | None = None
    kind: str = Field(default="office", pattern=KINDS)
    color: str | None = Field(default=None, pattern=COLOR)
    sort_order: int = 0
    create_default_positions: bool = True


class DepartmentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: int | None = None
    head_user_id: int | None = None
    kind: str | None = Field(default=None, pattern=KINDS)
    color: str | None = Field(default=None, pattern=COLOR)
    sort_order: int | None = None
    is_active: bool | None = None


class PositionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    department_id: int | None = None
    sort_order: int = 0


class PositionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    department_id: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


async def _active_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise error(400, "unknown_user")
    return user


async def _department(db: AsyncSession, dept_id: int) -> Department:
    dept = await db.get(Department, dept_id)
    if not dept:
        raise error(404, "not_found")
    return dept


async def _commit(db: AsyncSession, conflict_code: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, conflict_code) from exc


@router.get("/tree")
async def tree(
    request: Request,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("org.read")),
):
    depts = await svc.load_departments(db)
    cnt = await svc.counts(db)
    heads = await svc.user_refs(db, {d.head_user_id for d in depts.values()})
    leaders = (
        await db.scalars(
            select(User)
            .join(Role)
            .where(Role.key.in_(["tasischi", "direktor"]), User.is_active.is_(True))
            .order_by(Role.id, User.full_name)
        )
    ).unique().all()
    return {
        "company": request.app.state.client_config.brand["name"],
        "leadership": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "role_key": u.role.key,
                "role_name_uz": u.role.name_uz,
                "role_name_ru": u.role.name_ru,
            }
            for u in leaders
        ],
        "roots": svc.build_tree(depts, heads, cnt),
    }


@router.get("/departments")
async def list_departments(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("org.read"))
):
    depts = await svc.load_departments(db)
    cnt = await svc.counts(db)
    heads = await svc.user_refs(db, {d.head_user_id for d in depts.values()})
    ordered = sorted(depts.values(), key=lambda d: (d.sort_order, d.name.lower()))
    return [
        {**svc.department_out(d, heads, cnt), "depth": svc.depth_of(depts, d.id)} for d in ordered
    ]


@router.post("/departments", status_code=201)
async def create_department(
    body: DepartmentIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    depts = await svc.load_departments(db)
    if body.parent_id is not None:
        if body.parent_id not in depts:
            raise error(400, "unknown_parent")
        if svc.depth_of(depts, body.parent_id) >= svc.MAX_DEPTH:
            raise error(400, "too_deep", max=svc.MAX_DEPTH)
    head = await _active_user(db, body.head_user_id) if body.head_user_id else None

    dept = Department(
        name=body.name.strip(),
        parent_id=body.parent_id,
        head_user_id=body.head_user_id,
        kind=body.kind,
        color=body.color,
        sort_order=body.sort_order,
    )
    db.add(dept)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "department_name_taken") from exc

    names = request.app.state.client_config.settings.get("org", {}).get(
        "default_positions", svc.DEFAULT_POSITIONS
    )
    if body.create_default_positions:
        await svc.create_default_positions(db, dept, list(names))

    notes = (
        await notify(db, [head.id], "org.head_assigned", params={"name": dept.name}, link="/org")
        if head and head.id != auth.user.id
        else []
    )
    await audit(db, request, "org.department_create", actor=auth.user, entity="department",
                entity_id=dept.id, data={"name": dept.name, "parent_id": dept.parent_id})  # fmt: skip
    await db.commit()
    await deliver(request.app, notes)
    return {"id": dept.id}


@router.patch("/departments/{dept_id}")
async def update_department(
    dept_id: int,
    body: DepartmentPatch,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    depts = await svc.load_departments(db)
    dept = depts.get(dept_id)
    if not dept:
        raise error(404, "not_found")
    sent = body.model_fields_set
    changes: dict[str, Any] = {}
    notes: list = []

    if "parent_id" in sent and body.parent_id != dept.parent_id:
        if body.parent_id is not None:
            if body.parent_id not in depts:
                raise error(400, "unknown_parent")
            if body.parent_id == dept_id or body.parent_id in svc.descendants(depts, dept_id):
                raise error(409, "cycle")
            if svc.depth_of(depts, body.parent_id) + svc.subtree_height(depts, dept_id) > svc.MAX_DEPTH:
                raise error(400, "too_deep", max=svc.MAX_DEPTH)
        changes["parent_id"] = {"from": dept.parent_id, "to": body.parent_id}
        dept.parent_id = body.parent_id

    if "head_user_id" in sent and body.head_user_id != dept.head_user_id:
        head = await _active_user(db, body.head_user_id) if body.head_user_id else None
        changes["head_user_id"] = {"from": dept.head_user_id, "to": body.head_user_id}
        dept.head_user_id = body.head_user_id
        if head and head.id != auth.user.id:
            notes = await notify(
                db, [head.id], "org.head_assigned", params={"name": dept.name}, link="/org"
            )

    for field in ("name", "kind", "color", "sort_order", "is_active"):
        if field in sent and getattr(body, field) is not None or (field == "color" and field in sent):
            value = getattr(body, field)
            if isinstance(value, str) and field == "name":
                value = value.strip()
            if getattr(dept, field) != value:
                changes[field] = {"from": getattr(dept, field), "to": value}
                setattr(dept, field, value)

    if changes:
        await audit(db, request, "org.department_update", actor=auth.user, entity="department",
                    entity_id=dept.id, data=changes)  # fmt: skip
        await _commit(db, "department_name_taken")
        await deliver(request.app, notes)
    return {"id": dept.id}


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    dept = await _department(db, dept_id)
    if await db.scalar(select(func.count()).select_from(Department).where(Department.parent_id == dept_id)):
        raise error(409, "has_children")
    if await db.scalar(select(func.count()).select_from(Branch).where(Branch.department_id == dept_id)):
        raise error(409, "has_branches")
    if await db.scalar(select(func.count()).select_from(Employee).where(Employee.department_id == dept_id)):
        raise error(409, "has_employees")
    if await db.scalar(
        select(func.count())
        .select_from(Employee)
        .join(Position, Position.id == Employee.position_id)
        .where(Position.department_id == dept_id)
    ):
        raise error(409, "has_employees")
    await audit(db, request, "org.department_delete", actor=auth.user, entity="department",
                entity_id=dept.id, data={"name": dept.name})  # fmt: skip
    await db.delete(dept)  # lavozimlar CASCADE bilan o'chadi
    await db.commit()


@router.get("/positions")
async def list_positions(
    department_id: int | None = None,
    include_inactive: bool = True,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("org.read")),
):
    stmt = select(Position)
    if department_id is not None:
        stmt = stmt.where(Position.department_id == department_id)
    if not include_inactive:
        stmt = stmt.where(Position.is_active.is_(True))
    rows = (await db.scalars(stmt.order_by(Position.department_id, Position.sort_order, Position.name))).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "department_id": p.department_id,
            "sort_order": p.sort_order,
            "is_active": p.is_active,
        }
        for p in rows
    ]


@router.post("/positions", status_code=201)
async def create_position(
    body: PositionIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    if body.department_id is not None:
        await _department(db, body.department_id)
    pos = Position(name=body.name.strip(), department_id=body.department_id, sort_order=body.sort_order)
    db.add(pos)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "position_name_taken") from exc
    await audit(db, request, "org.position_create", actor=auth.user, entity="position",
                entity_id=pos.id, data={"name": pos.name, "department_id": pos.department_id})  # fmt: skip
    await db.commit()
    return {"id": pos.id}


@router.patch("/positions/{pos_id}")
async def update_position(
    pos_id: int,
    body: PositionPatch,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    pos = await db.get(Position, pos_id)
    if not pos:
        raise error(404, "not_found")
    sent = body.model_fields_set
    changes: dict[str, Any] = {}
    if "department_id" in sent and body.department_id != pos.department_id:
        if body.department_id is not None:
            await _department(db, body.department_id)
        changes["department_id"] = {"from": pos.department_id, "to": body.department_id}
        pos.department_id = body.department_id
    for field in ("name", "sort_order", "is_active"):
        value = getattr(body, field)
        if field in sent and value is not None:
            value = value.strip() if isinstance(value, str) else value
            if getattr(pos, field) != value:
                changes[field] = {"from": getattr(pos, field), "to": value}
                setattr(pos, field, value)
    if changes:
        await audit(db, request, "org.position_update", actor=auth.user, entity="position",
                    entity_id=pos.id, data=changes)  # fmt: skip
        await _commit(db, "position_name_taken")
    return {"id": pos.id}


@router.delete("/positions/{pos_id}", status_code=204)
async def delete_position(
    pos_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    pos = await db.get(Position, pos_id)
    if not pos:
        raise error(404, "not_found")
    if await db.scalar(select(func.count()).select_from(Employee).where(Employee.position_id == pos_id)):
        raise error(409, "has_employees")
    await audit(db, request, "org.position_delete", actor=auth.user, entity="position",
                entity_id=pos.id, data={"name": pos.name})  # fmt: skip
    await db.delete(pos)  # F4 da xodimlar bog'langach RESTRICT bo'ladi
    await db.commit()


@router.get("/assignable-users")
async def assignable_users(
    q: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require_any("org.manage", "branches.manage", "employees.accounts")),
):
    """Boshliq/mudir/koordinator tanlash uchun faol foydalanuvchilar (users.read talab qilinmaydi)."""
    stmt = select(User).where(User.is_active.is_(True))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.login.ilike(like)))
    rows = (await db.scalars(stmt.order_by(User.full_name).limit(limit))).unique().all()
    return [
        {"id": u.id, "full_name": u.full_name, "role_name_uz": u.role.name_uz, "role_name_ru": u.role.name_ru}
        for u in rows
    ]
