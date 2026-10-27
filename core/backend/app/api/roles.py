from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import plans
from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.auth import Role, RolePermission, User
from app.rbac import PERMISSIONS, SUPERUSER_ROLE, covers
from app.services.audit import audit

router = APIRouter(prefix="/v1", tags=["roles"])


class PermissionsIn(BaseModel):
    permissions: list[str]


def _valid_permission(key: str) -> bool:
    if key == "*" or key in PERMISSIONS:
        return True
    if key.endswith(".*"):
        prefix = key[:-1]  # "users."
        return any(p.startswith(prefix) for p in PERMISSIONS)
    return False


@router.get("/permissions")
async def permission_catalog(_: AuthContext = Depends(require("roles.read"))):
    return [{"key": k, **v} for k, v in sorted(PERMISSIONS.items())]


@router.get("/roles")
async def list_roles(
    db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("roles.read"))
):
    counts = dict(
        (await db.execute(select(User.role_id, func.count()).group_by(User.role_id))).all()
    )
    roles = (await db.scalars(select(Role).order_by(Role.id))).all()
    return [
        {
            "id": r.id,
            "key": r.key,
            "name_uz": r.name_uz,
            "name_ru": r.name_ru,
            "is_system": r.is_system,
            "locked": r.key == SUPERUSER_ROLE,
            "users": counts.get(r.id, 0),
            "permissions": sorted(r.permission_keys),
        }
        for r in roles
    ]


@router.put("/roles/{role_id}/permissions")
async def set_role_permissions(
    role_id: int,
    body: PermissionsIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("roles.manage")),
):
    plans.require_feature("custom_roles")  # rollar ruxsatlarini sozlash: PRO va undan yuqori
    role = await db.get(Role, role_id)
    if not role:
        raise error(404, "not_found")
    if role.key == SUPERUSER_ROLE:
        raise error(409, "role_locked")

    new = set(body.permissions)
    unknown = [p for p in new if not _valid_permission(p)]
    if unknown:
        raise error(400, "unknown_permission", permissions=sorted(unknown))
    old = role.permission_keys
    # Faqat o'zingizda bor ruxsatlarni bera/olib tashlay olasiz (o'zgarish qamrovi)
    if not covers(auth.permissions, new | old):
        raise error(403, "cannot_grant_permission")

    for rp in list(role.permissions):
        if rp.permission not in new:
            role.permissions.remove(rp)
    for perm in sorted(new - old):
        role.permissions.append(RolePermission(permission=perm))
    # Rol huquqi o'zgargan foydalanuvchilarning ruxsatlari keyingi so'rovda yangilanadi (DB dan o'qiladi)
    await audit(
        db, request, "role.permissions_update", actor=auth.user, entity="role", entity_id=role.id,
        data={"role": role.key, "added": sorted(new - old), "removed": sorted(old - new)},
    )  # fmt: skip
    await db.commit()
    return {"id": role.id, "key": role.key, "permissions": sorted(new)}
