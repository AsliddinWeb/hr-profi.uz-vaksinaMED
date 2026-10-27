"""Realtime: foydalanuvchiga WebSocket orqali hodisa yuborish.

Ko'p jarayonli ishlash uchun hodisalar Redis pub/sub (`rt:user:<id>`) orqali tarqatiladi; har API jarayoni
o'z ulangan socketlariga yetkazadi. Istalgan joydan (API, worker): `await publish(redis, [user_id], type, payload)`.
"""

import asyncio
import json
import logging
from typing import Any, Protocol

from redis.asyncio import Redis

log = logging.getLogger("vaksina.realtime")
CHANNEL_PREFIX = "rt:user:"


class Socket(Protocol):
    async def send_json(self, data: Any) -> None: ...


async def publish(redis: Redis, user_ids: list[int], type_: str, payload: dict | None = None) -> None:
    message = json.dumps({"type": type_, **(payload or {})}, default=str)
    for uid in set(user_ids):
        await redis.publish(f"{CHANNEL_PREFIX}{uid}", message)


class RealtimeHub:
    def __init__(self) -> None:
        self._sockets: dict[int, set[Socket]] = {}

    def add(self, user_id: int, ws: Socket) -> None:
        self._sockets.setdefault(user_id, set()).add(ws)

    def remove(self, user_id: int, ws: Socket) -> None:
        group = self._sockets.get(user_id)
        if group:
            group.discard(ws)
            if not group:
                del self._sockets[user_id]

    def connections(self, user_id: int | None = None) -> int:
        if user_id is not None:
            return len(self._sockets.get(user_id, ()))
        return sum(len(g) for g in self._sockets.values())

    async def dispatch(self, user_id: int, message: dict) -> None:
        for ws in list(self._sockets.get(user_id, ())):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001  (uzilgan socket: keyingi qayta ulanishda tozalanadi)
                self.remove(user_id, ws)

    async def listen(self, redis: Redis) -> None:
        """Redis kanalini tinglaydi. Xatoda qayta ulanadi; bekor qilinsa (shutdown) tugaydi."""
        while True:
            pubsub = redis.pubsub()
            try:
                await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
                async for item in pubsub.listen():
                    if item.get("type") != "pmessage":
                        continue
                    channel = item["channel"]
                    channel = channel.decode() if isinstance(channel, bytes) else channel
                    try:
                        uid = int(channel.removeprefix(CHANNEL_PREFIX))
                        await self.dispatch(uid, json.loads(item["data"]))
                    except (ValueError, json.JSONDecodeError):
                        log.warning("Noto'g'ri realtime xabar: %s", channel)
            except asyncio.CancelledError:
                await pubsub.aclose()
                raise
            except Exception:  # noqa: BLE001
                log.exception("Realtime listener xatosi, 2s dan keyin qayta ulanadi")
                await asyncio.sleep(2)
            finally:
                try:
                    await pubsub.aclose()
                except Exception:  # noqa: BLE001
                    pass
