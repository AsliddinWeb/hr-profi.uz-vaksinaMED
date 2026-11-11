"""Login paytida qurilmani tekshirish. Nazorat majburiy bo'lmagan foydalanuvchida faqat qayd etiladi (hech qachon to'silmaydi)."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.devices import DeviceSettings, UserDevice
from app.timeutil import now

KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class DeviceDenied(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def label(ua: str | None) -> str:
    ua = ua or ""
    browser = next((b for k, b in (("Edg/", "Edge"), ("OPR/", "Opera"), ("YaBrowser", "Yandex"), ("Chrome/", "Chrome"), ("Firefox/", "Firefox"), ("Safari/", "Safari")) if k in ua), "Brauzer")
    osname = next((o for k, o in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"), ("Mac OS", "macOS"), ("Linux", "Linux")) if k in ua), "")
    return f"{browser} · {osname}" if osname else browser


async def settings(db: AsyncSession) -> DeviceSettings:
    s = await db.get(DeviceSettings, 1)
    if not s:
        s = DeviceSettings(id=1, enforce_roles=[], enforce_user_ids=[], auto_approve_first=True)
        db.add(s)
        await db.flush()
    return s


def enforced(s: DeviceSettings, user: User) -> bool:
    role_key = user.role.key if getattr(user, "role", None) else None
    return user.id in (s.enforce_user_ids or []) or (role_key is not None and role_key in (s.enforce_roles or []))


async def check(db: AsyncSession, user: User, device_key: str | None, ip: str | None, ua: str | None) -> UserDevice | None:
    """Qurilmani qayd etadi. Majburiy nazoratda: bloklangan -> DeviceDenied('device_blocked'),
    yangi/tasdiqlanmagan -> DeviceDenied('device_pending') (so'rov yaratiladi). Kalit yo'q bo'lsa (eski klient) nazoratsiz o'tadi."""
    if not device_key or not KEY_RE.match(device_key):
        s = await settings(db)
        if enforced(s, user):
            raise DeviceDenied("device_unknown")
        return None
    s = await settings(db)
    moment = now()
    dev = await db.scalar(select(UserDevice).where(UserDevice.user_id == user.id, UserDevice.device_key == device_key))
    must = enforced(s, user)
    if not dev:
        has_any = await db.scalar(select(UserDevice.id).where(UserDevice.user_id == user.id, UserDevice.status == "approved").limit(1))
        status = "approved" if (not must or (not has_any and s.auto_approve_first)) else "pending"
        dev = UserDevice(user_id=user.id, device_key=device_key, label=label(ua), user_agent=(ua or "")[:300] or None, first_ip=ip, last_ip=ip,
                         status=status, is_primary=not has_any, first_seen=moment, last_seen=moment)  # fmt: skip
        db.add(dev)
        await db.flush()
    else:
        dev.last_seen, dev.last_ip = moment, ip
        if ua:
            dev.user_agent, dev.label = ua[:300], label(ua)
    if dev.status == "blocked":
        raise DeviceDenied("device_blocked")
    if must and dev.status != "approved":
        raise DeviceDenied("device_pending")
    return dev
