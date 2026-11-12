from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require, require_any
from app.models.auth import Role, User
from app.models.employees import Employee
from app.models.org import (
    Branch,
    Department,
    OrgStructure,
    OrgStructureDepartment,
    OrgStructurePosition,
    Position,
)
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
    yqm: str | None = Field(default=None, max_length=1000)
    reports_to_position_id: int | None = None
    create_default_positions: bool = True


class DepartmentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: int | None = None
    head_user_id: int | None = None
    kind: str | None = Field(default=None, pattern=KINDS)
    color: str | None = Field(default=None, pattern=COLOR)
    sort_order: int | None = None
    is_active: bool | None = None
    yqm: str | None = Field(default=None, max_length=1000)
    reports_to_position_id: int | None = None


class PositionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    department_id: int | None = None
    sort_order: int = 0
    yqm: str | None = Field(default=None, max_length=1000)
    parent_id: int | None = None
    slots: int = Field(default=1, ge=0, le=1000)
    is_head: bool = False


class PositionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    department_id: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    yqm: str | None = Field(default=None, max_length=1000)
    parent_id: int | None = None
    slots: int | None = Field(default=None, ge=0, le=1000)
    is_head: bool | None = None


class PositionDutiesIn(BaseModel):
    duties: list[str] = Field(max_length=100)


class StructureIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    source_id: int | None = None


class StructurePatch(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=300)


class StructurePositionIn(BaseModel):
    department_id: int | None = None
    parent_position_id: int | None = None


class StructureDepartmentIn(BaseModel):
    parent_department_id: int | None = None
    reports_to_position_id: int | None = None


def _clean_duties(raw: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        text = " ".join(str(value).split())
        if not text:
            continue
        if len(text) > 1000:
            raise error(400, "duty_too_long")
        key = text.casefold()
        if key not in seen:
            out.append(text)
            seen.add(key)
    return out


async def _check_parent(db: AsyncSession, pos_id: int | None, parent_id: int | None) -> None:
    """Bo'ysunish: rahbar lavozim mavjud bo'lsin va aylana hosil bo'lmasin (A -> B -> A)."""
    if parent_id is None:
        return
    seen: set[int] = set()
    cur: int | None = parent_id
    while cur is not None:
        if cur == pos_id or cur in seen:
            raise error(400, "position_cycle")
        seen.add(cur)
        p = await db.get(Position, cur)
        if not p:
            raise error(400, "unknown_position")
        cur = p.parent_id


async def _check_reports_to(db: AsyncSession, position_id: int | None) -> None:
    if position_id is not None and not await db.get(Position, position_id):
        raise error(400, "unknown_position")


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
        yqm=(body.yqm or "").strip() or None,
        reports_to_position_id=body.reports_to_position_id,
    )
    await _check_reports_to(db, body.reports_to_position_id)
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

    if "reports_to_position_id" in sent and body.reports_to_position_id != dept.reports_to_position_id:
        await _check_reports_to(db, body.reports_to_position_id)
        changes["reports_to_position_id"] = {"from": dept.reports_to_position_id, "to": body.reports_to_position_id}
        dept.reports_to_position_id = body.reports_to_position_id
    for field in ("name", "kind", "color", "sort_order", "is_active", "yqm"):
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


async def _dept_impact(db: AsyncSession, dept_id: int) -> dict[str, int]:
    from app.models.recruit import HireRequest

    async def n(stmt) -> int:
        return await db.scalar(stmt) or 0

    return {
        "children": await n(select(func.count()).select_from(Department).where(Department.parent_id == dept_id)),
        "branches": await n(select(func.count()).select_from(Branch).where(Branch.department_id == dept_id)),
        "positions": await n(select(func.count()).select_from(Position).where(Position.department_id == dept_id)),
        "employees": await n(select(func.count()).select_from(Employee).where(Employee.department_id == dept_id)),
        "requests": await n(select(func.count()).select_from(HireRequest).where(HireRequest.department_id == dept_id)),
    }


@router.get("/departments/{dept_id}/impact")
async def department_impact(dept_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("org.manage"))):
    """O'chirishdan oldin: bo'limga nimalar bog'langan (ular o'chirilmaydi, faqat bo'limdan uziladi)."""
    await _department(db, dept_id)
    return await _dept_impact(db, dept_id)


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: int,
    request: Request,
    detach: bool = False,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    """`detach=true`: ichki bo'limlar yuqori darajaga, filiallar/xodimlar/zayavkalar bo'limsiz, lavozimlar umumiy lavozimga o'tadi;
    keyin faqat bo'limning o'zi o'chadi. Aks holda bog'langan narsa bo'lsa 409."""
    from sqlalchemy import update

    from app.models.recruit import HireRequest

    dept = await _department(db, dept_id)
    impact = await _dept_impact(db, dept_id)
    if not detach:
        if impact["children"]:
            raise error(409, "has_children")
        if impact["branches"]:
            raise error(409, "has_branches")
        if impact["employees"] or await db.scalar(
            select(func.count()).select_from(Employee).join(Position, Position.id == Employee.position_id).where(Position.department_id == dept_id)
        ):
            raise error(409, "has_employees")
    else:
        await db.execute(update(Department).where(Department.parent_id == dept_id).values(parent_id=None))
        await db.execute(update(Branch).where(Branch.department_id == dept_id).values(department_id=None))
        await db.execute(update(Employee).where(Employee.department_id == dept_id).values(department_id=None))
        await db.execute(update(Position).where(Position.department_id == dept_id).values(department_id=None))
        await db.execute(update(HireRequest).where(HireRequest.department_id == dept_id).values(department_id=None))
    await audit(db, request, "org.department_delete", actor=auth.user, entity="department",
                entity_id=dept.id, data={"name": dept.name, "detached": impact if detach else None})  # fmt: skip
    await db.delete(dept)
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
            "yqm": p.yqm,
            "parent_id": p.parent_id,
            "slots": p.slots,
            "is_head": p.is_head,
            "duties": p.duties or [],
        }
        for p in rows
    ]


@router.get("/duties")
async def list_position_duties(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("org.read"))
):
    """Lavozimlar va ularga biriktirilgan umumiy vazifalar bazasi."""
    rows = (await db.execute(
        select(Position, Department.name).outerjoin(Department, Department.id == Position.department_id)
        .where(Position.is_active.is_(True)).order_by(Department.name, Position.sort_order, Position.name)
    )).all()
    return [{"id": p.id, "name": p.name, "department_id": p.department_id, "department": dept,
             "duties": p.duties or []} for p, dept in rows]


@router.put("/positions/{pos_id}/duties")
async def update_position_duties(
    pos_id: int, body: PositionDutiesIn, request: Request,
    db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.manage")),
):
    pos = await db.get(Position, pos_id)
    if not pos:
        raise error(404, "not_found")
    duties = _clean_duties(body.duties)
    if duties != (pos.duties or []):
        pos.duties = duties
        await audit(db, request, "org.position_duties_update", actor=auth.user, entity="position",
                    entity_id=pos.id, data={"count": len(duties)})
        await db.commit()
    return {"id": pos.id, "duties": pos.duties or []}


def _structure_out(s: OrgStructure) -> dict[str, Any]:
    return {"id": s.id, "name": s.name, "description": s.description, "is_default": s.is_default}


async def _structure(db: AsyncSession, structure_id: int) -> OrgStructure:
    item = await db.get(OrgStructure, structure_id)
    if not item:
        raise error(404, "not_found")
    return item


@router.get("/structures")
async def list_structures(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("org.read"))):
    rows = (await db.scalars(select(OrgStructure).order_by(OrgStructure.is_default.desc(), OrgStructure.name))).all()
    return {"items": [_structure_out(s) for s in rows]}


@router.post("/structures", status_code=201)
async def create_structure(body: StructureIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.manage"))):
    name = body.name.strip()
    if len(name) < 2:
        raise error(400, "structure_name_invalid")
    source = await _structure(db, body.source_id) if body.source_id else await db.scalar(select(OrgStructure).where(OrgStructure.is_default.is_(True)))
    structure = OrgStructure(name=name, description=(body.description or "").strip() or None, created_by=auth.user.id)
    db.add(structure)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise error(409, "structure_name_taken") from exc
    source_pos = {x.position_id: x for x in (await db.scalars(select(OrgStructurePosition).where(OrgStructurePosition.structure_id == source.id))).all()} if source else {}
    for p in (await db.scalars(select(Position))).all():
        ref = source_pos.get(p.id)
        db.add(OrgStructurePosition(structure_id=structure.id, position_id=p.id,
                                    department_id=ref.department_id if ref else p.department_id,
                                    parent_position_id=ref.parent_position_id if ref else p.parent_id,
                                    sort_order=ref.sort_order if ref else p.sort_order))
    source_dept = {x.department_id: x for x in (await db.scalars(select(OrgStructureDepartment).where(OrgStructureDepartment.structure_id == source.id))).all()} if source else {}
    for d in (await db.scalars(select(Department))).all():
        ref = source_dept.get(d.id)
        db.add(OrgStructureDepartment(structure_id=structure.id, department_id=d.id,
                                      parent_department_id=ref.parent_department_id if ref else d.parent_id,
                                      reports_to_position_id=ref.reports_to_position_id if ref else d.reports_to_position_id))
    await audit(db, request, "org.structure_create", actor=auth.user, entity="org_structure", entity_id=structure.id,
                data={"name": name, "source_id": source.id if source else None})
    await db.commit()
    return _structure_out(structure)


@router.get("/structures/{structure_id}")
async def get_structure(structure_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("org.read"))):
    item = await _structure(db, structure_id)
    positions = (await db.scalars(select(Position).order_by(Position.department_id, Position.sort_order, Position.name))).all()
    depts = (await db.scalars(select(Department).order_by(Department.sort_order, Department.name))).all()
    pos_links = {x.position_id: x for x in (await db.scalars(select(OrgStructurePosition).where(OrgStructurePosition.structure_id == item.id))).all()}
    dept_links = {x.department_id: x for x in (await db.scalars(select(OrgStructureDepartment).where(OrgStructureDepartment.structure_id == item.id))).all()}
    return {**_structure_out(item),
            "positions": [{"id": p.id, "name": p.name, "department_id": pos_links[p.id].department_id if p.id in pos_links else p.department_id,
                           "parent_position_id": pos_links[p.id].parent_position_id if p.id in pos_links else p.parent_id, "is_active": p.is_active} for p in positions],
            "departments": [{"id": d.id, "name": d.name, "parent_department_id": dept_links[d.id].parent_department_id if d.id in dept_links else d.parent_id,
                             "reports_to_position_id": dept_links[d.id].reports_to_position_id if d.id in dept_links else d.reports_to_position_id, "is_active": d.is_active} for d in depts]}


@router.put("/structures/{structure_id}")
async def update_structure(structure_id: int, body: StructurePatch, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.manage"))):
    item = await _structure(db, structure_id)
    item.name, item.description = body.name.strip(), (body.description or "").strip() or None
    await audit(db, request, "org.structure_update", actor=auth.user, entity="org_structure", entity_id=item.id, data={"name": item.name})
    await _commit(db, "structure_name_taken")
    return _structure_out(item)


@router.put("/structures/{structure_id}/default")
async def set_default_structure(structure_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.manage"))):
    item = await _structure(db, structure_id)
    if not item.is_default:
        await db.execute(update(OrgStructure).where(OrgStructure.is_default.is_(True)).values(is_default=False))
        item.is_default = True
        await audit(db, request, "org.structure_default", actor=auth.user, entity="org_structure", entity_id=item.id)
        await db.commit()
    return _structure_out(item)


@router.delete("/structures/{structure_id}", status_code=204)
async def delete_structure(structure_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.manage"))):
    item = await _structure(db, structure_id)
    if item.is_default:
        raise error(409, "default_structure")
    await audit(db, request, "org.structure_delete", actor=auth.user, entity="org_structure", entity_id=item.id, data={"name": item.name})
    await db.delete(item)
    await db.commit()


@router.put("/structures/{structure_id}/positions/{pos_id}")
async def set_structure_position(structure_id: int, pos_id: int, body: StructurePositionIn, request: Request,
                                 db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.manage"))):
    structure = await _structure(db, structure_id)
    pos = await db.get(Position, pos_id)
    if not pos:
        raise error(404, "not_found")
    if body.department_id is not None and not await db.get(Department, body.department_id):
        raise error(400, "unknown_department")
    if body.parent_position_id is not None and not await db.get(Position, body.parent_position_id):
        raise error(400, "unknown_position")
    if body.parent_position_id == pos_id:
        raise error(400, "position_cycle")
    links = list((await db.scalars(select(OrgStructurePosition).where(OrgStructurePosition.structure_id == structure.id))).all())
    parent_map = {x.position_id: x.parent_position_id for x in links}
    for p in (await db.scalars(select(Position))).all():
        parent_map.setdefault(p.id, p.parent_id)
    parent_map[pos_id] = body.parent_position_id
    seen, cur = {pos_id}, body.parent_position_id
    while cur is not None:
        if cur in seen:
            raise error(400, "position_cycle")
        seen.add(cur)
        cur = parent_map.get(cur)
    link = next((x for x in links if x.position_id == pos_id), None)
    if link is None:
        link = OrgStructurePosition(structure_id=structure.id, position_id=pos.id)
        db.add(link)
    link.department_id, link.parent_position_id = body.department_id, body.parent_position_id
    await audit(db, request, "org.structure_position_update", actor=auth.user, entity="org_structure", entity_id=structure.id,
                data={"position_id": pos.id, "department_id": body.department_id, "parent_position_id": body.parent_position_id})
    await db.commit()
    return {"position_id": pos.id, "department_id": link.department_id, "parent_position_id": link.parent_position_id}


@router.put("/structures/{structure_id}/departments/{dept_id}")
async def set_structure_department(structure_id: int, dept_id: int, body: StructureDepartmentIn, request: Request,
                                   db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("org.manage"))):
    structure = await _structure(db, structure_id)
    dept = await _department(db, dept_id)
    if body.parent_department_id is not None and not await db.get(Department, body.parent_department_id):
        raise error(400, "unknown_parent")
    if body.parent_department_id == dept_id:
        raise error(400, "cycle")
    if body.reports_to_position_id is not None and not await db.get(Position, body.reports_to_position_id):
        raise error(400, "unknown_position")
    links = list((await db.scalars(select(OrgStructureDepartment).where(OrgStructureDepartment.structure_id == structure.id))).all())
    parent_map = {x.department_id: x.parent_department_id for x in links}
    for d in (await db.scalars(select(Department))).all():
        parent_map.setdefault(d.id, d.parent_id)
    parent_map[dept_id] = body.parent_department_id
    seen, cur = {dept_id}, body.parent_department_id
    while cur is not None:
        if cur in seen:
            raise error(409, "cycle")
        seen.add(cur)
        cur = parent_map.get(cur)
    link = next((x for x in links if x.department_id == dept_id), None)
    if link is None:
        link = OrgStructureDepartment(structure_id=structure.id, department_id=dept.id)
        db.add(link)
    link.parent_department_id, link.reports_to_position_id = body.parent_department_id, body.reports_to_position_id
    await audit(db, request, "org.structure_department_update", actor=auth.user, entity="org_structure", entity_id=structure.id,
                data={"department_id": dept.id, "parent_department_id": body.parent_department_id, "reports_to_position_id": body.reports_to_position_id})
    await db.commit()
    return {"department_id": dept.id, "parent_department_id": link.parent_department_id, "reports_to_position_id": link.reports_to_position_id}


@router.post("/positions", status_code=201)
async def create_position(
    body: PositionIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("org.manage")),
):
    if body.department_id is not None:
        await _department(db, body.department_id)
    await _check_parent(db, None, body.parent_id)
    pos = Position(name=body.name.strip(), department_id=body.department_id, sort_order=body.sort_order, yqm=(body.yqm or "").strip() or None,
                   parent_id=body.parent_id, slots=body.slots, is_head=body.is_head)  # fmt: skip
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
    if "parent_id" in sent and body.parent_id != pos.parent_id:
        await _check_parent(db, pos.id, body.parent_id)
        changes["parent_id"] = {"from": pos.parent_id, "to": body.parent_id}
        pos.parent_id = body.parent_id
    for field in ("name", "sort_order", "is_active", "yqm", "slots", "is_head"):
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
