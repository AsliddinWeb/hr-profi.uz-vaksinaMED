"""Idempotent boshlang'ich ma'lumotlar: rollar va ularning DEFAULT ruxsatlari.

- Yo'q rollar yaratiladi.
- Yangi versiyada qo'shilgan default ruxsatlar mavjud rollarga BIR MARTA beriladi. Berilgan juftliklar
  `app_meta` da yoziladi, shuning uchun administrator olib tashlagan ruxsat qayta tiklanmaydi.
"""

import json
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, RolePermission
from app.rbac import SYSTEM_ROLES

log = logging.getLogger("vaksina.seed")
META_KEY = "rbac.granted_defaults"


async def _load_granted(session: AsyncSession) -> set[str]:
    raw = await session.scalar(text("SELECT value FROM app_meta WHERE key = :k"), {"k": META_KEY})
    return set(json.loads(raw)) if raw else set()


async def _save_granted(session: AsyncSession, granted: set[str]) -> None:
    await session.execute(
        text(
            "INSERT INTO app_meta (key, value) VALUES (:k, :v) "
            "ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = now()"
        ),
        {"k": META_KEY, "v": json.dumps(sorted(granted))},
    )


async def ensure_roles(session: AsyncSession) -> int:
    roles = {r.key: r for r in (await session.scalars(select(Role))).all()}
    granted = await _load_granted(session)
    changed = 0

    for rd in SYSTEM_ROLES:
        role = roles.get(rd.key)
        is_new = role is None
        if role is None:
            role = Role(key=rd.key, name_uz=rd.uz, name_ru=rd.ru, is_system=True)
            role.permissions = []
            session.add(role)
            roles[rd.key] = role
            changed += 1
        have = {p.permission for p in role.permissions}
        for perm in rd.permissions:
            pair = f"{rd.key}:{perm}"
            if pair in granted and not is_new:
                continue
            granted.add(pair)
            if perm not in have:
                role.permissions.append(RolePermission(permission=perm))
                changed += 1

    await _save_granted(session, granted)
    await session.commit()
    if changed:
        log.info("Rol/ruxsat o'zgarishlari: %d", changed)
    return changed
