import asyncio
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db import SessionLocal
from app.deps import load_auth

router = APIRouter()
log = logging.getLogger("vaksina.ws")

PING_TIMEOUT = 45  # shu vaqt ichida mijozdan hech narsa kelmasa sessiya qayta tekshiriladi
CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN_ORIGIN = 4403


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Cross-site WebSocket hijacking oldini olish: Origin Host bilan mos bo'lishi kerak."""
    if not origin:
        return True  # brauzer bo'lmagan mijoz (cookie baribir kerak)
    return urlparse(origin).netloc == (host or "")


async def _still_valid(ws: WebSocket) -> bool:
    async with SessionLocal() as session:
        try:
            await load_auth(ws, session)
        except Exception:  # noqa: BLE001
            return False
    return True


@router.websocket("/ws/notifications")
async def notifications_ws(ws: WebSocket) -> None:
    if not origin_allowed(ws.headers.get("origin"), ws.headers.get("host")):
        await ws.close(code=CLOSE_FORBIDDEN_ORIGIN)
        return

    async with SessionLocal() as session:
        try:
            auth = await load_auth(ws, session)
        except Exception:  # noqa: BLE001
            await ws.close(code=CLOSE_UNAUTHENTICATED)
            return
    user_id = auth.user.id

    hub = ws.app.state.hub
    await ws.accept()
    hub.add(user_id, ws)
    try:
        await ws.send_json({"type": "hello"})
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=PING_TIMEOUT)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            except TimeoutError:
                # Mijoz jim: sessiya bekor qilingan bo'lishi mumkin
                if not await _still_valid(ws):
                    await ws.close(code=CLOSE_UNAUTHENTICATED)
                    return
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.exception("WebSocket xatosi")
    finally:
        hub.remove(user_id, ws)
