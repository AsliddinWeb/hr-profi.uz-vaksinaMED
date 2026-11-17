"""Kameralar holatini tekshirish (1000+ filial uchun parallel) va oflayn bo'lganlar haqida jamlangan xabar."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cameras import Camera, CameraEvent
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template

register_template(
    "cameras.offline",
    {"uz": "Kameralar o'chdi", "ru": "Камеры отключились"},
    {"uz": "{count} ta kamera oflayn: {names}", "ru": "Камер офлайн: {count} — {names}"},
    "danger",
)
register_template(
    "cameras.back",
    {"uz": "Kameralar qayta ulandi", "ru": "Камеры снова в сети"},
    {"uz": "{count} ta kamera onlayn: {names}", "ru": "Камер снова онлайн: {count} — {names}"},
    "success",
)

PROBE_TIMEOUT = 3.0
CONCURRENCY = 100
FAILS_TO_OFFLINE = 2  # bir martalik uzilishda signal bermaslik uchun
STATION_STALE = timedelta(minutes=3)  # stansiya shu vaqtda signal bermasa — oflayn


async def probe(host: str, port: int, timeout: float = PROBE_TIMEOUT) -> str | None:
    """TCP ulanish: None — kamera javob berdi, aks holda xato matni."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        return None
    except TimeoutError:
        return "timeout"
    except OSError as e:
        return (e.strerror or type(e).__name__)[:200]


def apply_result(db: AsyncSession, c: Camera, ok: bool, err: str | None, moment: datetime) -> str | None:
    """Natijani yozadi; holat o'zgarsa 'online' yoki 'offline' qaytaradi."""
    c.last_check_at = moment
    if ok:
        c.fail_count, c.last_error, c.last_online_at = 0, None, moment
        if c.status != "online":
            changed = "online" if c.status == "offline" else None
            c.status, c.offline_since = "online", None
            db.add(CameraEvent(camera_id=c.id, status="online"))
            return changed
        return None
    c.fail_count = (c.fail_count or 0) + 1
    c.last_error = err
    if c.status != "offline" and c.fail_count >= FAILS_TO_OFFLINE:
        c.status, c.offline_since = "offline", c.offline_since or moment
        db.add(CameraEvent(camera_id=c.id, status="offline", message=err))
        return "offline"
    return None


async def check_cameras(db: AsyncSession, cams: list[Camera], moment: datetime) -> dict[str, list[Camera]]:
    """IP kameralar — TCP orqali, stansiyalar — oxirgi signal vaqti bo'yicha."""
    sem = asyncio.Semaphore(CONCURRENCY)
    ip = [c for c in cams if c.kind == "ip" and c.host]

    async def one(c: Camera) -> tuple[Camera, str | None]:
        async with sem:
            return c, await probe(c.host or "", c.port or 554)

    results = await asyncio.gather(*(one(c) for c in ip))
    changed: dict[str, list[Camera]] = {"online": [], "offline": []}
    for c, err in results:
        st = apply_result(db, c, err is None, err, moment)
        if st:
            changed[st].append(c)
    for c in cams:
        if c.kind == "ip":
            continue
        if c.last_online_at and moment - c.last_online_at > STATION_STALE and c.status == "online":
            c.fail_count = FAILS_TO_OFFLINE
            c.status, c.offline_since, c.last_error, c.last_check_at = "offline", c.last_online_at, "no_signal", moment
            db.add(CameraEvent(camera_id=c.id, status="offline", message="no_signal"))
            changed["offline"].append(c)
    return changed


async def notes_for(db: AsyncSession, changed: dict[str, list[Camera]]) -> list[Any]:
    targets = await users_with_permission(db, "cameras.manage")
    if not targets:
        return []
    notes: list[Any] = []
    for kind, tpl in (("offline", "cameras.offline"), ("online", "cameras.back")):
        cams = changed.get(kind) or []
        if cams:
            names = ", ".join(c.name for c in cams[:5]) + (f" +{len(cams) - 5}" if len(cams) > 5 else "")
            notes += await notify(db, targets, tpl, params={"count": len(cams), "names": names}, link="/cameras?status=" + kind)
    return notes


async def scan(db: AsyncSession, moment: datetime) -> list[Any]:
    cams = list((await db.scalars(select(Camera).where(Camera.is_active.is_(True)))).all())
    return await notes_for(db, await check_cameras(db, cams, moment))
