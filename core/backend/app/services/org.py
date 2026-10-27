"""Tashkiliy tuzilma yordamchilari: daraxt, tsikl tekshiruvi, standart lavozimlar."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.org import Branch, Department, Position

MAX_DEPTH = 6
DEFAULT_POSITIONS = ["Bo'lim boshlig'i", "Xodim"]


async def load_departments(db: AsyncSession) -> dict[int, Department]:
    return {d.id: d for d in (await db.scalars(select(Department))).all()}


def descendants(depts: dict[int, Department], root_id: int) -> set[int]:
    children: dict[int | None, list[int]] = {}
    for d in depts.values():
        children.setdefault(d.parent_id, []).append(d.id)
    out: set[int] = set()
    stack = [root_id]
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def depth_of(depts: dict[int, Department], dept_id: int | None) -> int:
    """Bo'limning chuqurligi (ildiz = 1). `None` = 0."""
    depth, seen = 0, set()
    while dept_id is not None and dept_id not in seen:
        seen.add(dept_id)
        depth += 1
        dept_id = depts[dept_id].parent_id
    return depth


def subtree_height(depts: dict[int, Department], root_id: int) -> int:
    """root dan eng chuqur avlodgacha qatlamlar soni (root bilan birga)."""
    children: dict[int | None, list[int]] = {}
    for d in depts.values():
        children.setdefault(d.parent_id, []).append(d.id)

    def h(node: int) -> int:
        return 1 + max((h(c) for c in children.get(node, [])), default=0)

    return h(root_id)


async def counts(db: AsyncSession) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}

    def bucket(i: int) -> dict[str, int]:
        return out.setdefault(i, {"positions": 0, "branches": 0, "children": 0})

    for dept_id, n in (
        await db.execute(
            select(Position.department_id, func.count())
            .where(Position.department_id.is_not(None))
            .group_by(Position.department_id)
        )
    ).all():
        bucket(dept_id)["positions"] = n
    for dept_id, n in (
        await db.execute(
            select(Branch.department_id, func.count())
            .where(Branch.department_id.is_not(None))
            .group_by(Branch.department_id)
        )
    ).all():
        bucket(dept_id)["branches"] = n
    for parent_id, n in (
        await db.execute(
            select(Department.parent_id, func.count())
            .where(Department.parent_id.is_not(None))
            .group_by(Department.parent_id)
        )
    ).all():
        bucket(parent_id)["children"] = n
    return out


async def user_refs(db: AsyncSession, ids: set[int | None]) -> dict[int, dict[str, Any]]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = (await db.scalars(select(User).where(User.id.in_(wanted)))).unique().all()
    return {u.id: {"id": u.id, "full_name": u.full_name, "is_active": u.is_active} for u in rows}


def department_out(
    d: Department, heads: dict[int, dict], cnt: dict[int, dict[str, int]]
) -> dict[str, Any]:
    c = cnt.get(d.id, {})
    return {
        "id": d.id,
        "name": d.name,
        "parent_id": d.parent_id,
        "kind": d.kind,
        "color": d.color,
        "sort_order": d.sort_order,
        "is_active": d.is_active,
        "head": heads.get(d.head_user_id) if d.head_user_id else None,
        "positions": c.get("positions", 0),
        "branches": c.get("branches", 0),
        "children": c.get("children", 0),
    }


def build_tree(
    depts: dict[int, Department], heads: dict[int, dict], cnt: dict[int, dict[str, int]]
) -> list[dict[str, Any]]:
    by_parent: dict[int | None, list[Department]] = {}
    for d in depts.values():
        by_parent.setdefault(d.parent_id, []).append(d)

    def node(d: Department) -> dict[str, Any]:
        out = department_out(d, heads, cnt)
        kids = sorted(by_parent.get(d.id, []), key=lambda x: (x.sort_order, x.name.lower()))
        out["children"] = [node(k) for k in kids]
        out["children_count"] = len(kids)
        return out

    roots = sorted(by_parent.get(None, []), key=lambda x: (x.sort_order, x.name.lower()))
    return [node(r) for r in roots]


async def create_default_positions(
    db: AsyncSession, department: Department, names: list[str]
) -> list[Position]:
    created = []
    for i, name in enumerate(dict.fromkeys(n.strip() for n in names if n.strip())):
        p = Position(name=name[:120], department_id=department.id, sort_order=i)
        db.add(p)
        created.append(p)
    await db.flush()
    return created
