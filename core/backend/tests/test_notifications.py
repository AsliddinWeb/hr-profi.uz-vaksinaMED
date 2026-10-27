import asyncio

import pytest

from app.realtime import RealtimeHub, publish
from tests.conftest import PASSWORD, login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)


async def as_user(new_client, login_name, role, **kw):
    uid = await make_user(login_name, role, **kw)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def change_password(c):
    r = await c.post(
        "/api/auth/change-password", json={"old_password": PASSWORD, "new_password": "Better-pass1"}
    )
    assert r.status_code == 204


async def test_password_change_creates_notification(new_client):
    c, _ = await as_user(new_client, "ali", "koordinator")
    assert (await c.get("/api/v1/notifications/unread-count")).json() == {"count": 0}
    await change_password(c)

    assert (await c.get("/api/v1/notifications/unread-count")).json() == {"count": 1}
    page = (await c.get("/api/v1/notifications")).json()
    n = page["items"][0]
    assert page["total"] == 1 and n["kind"] == "security.password_changed"
    assert n["title"]["uz"] and n["title"]["ru"] and n["severity"] == "warning"
    assert n["read"] is False


async def test_mark_read_and_read_all(new_client):
    c, _ = await as_user(new_client, "ali", "koordinator")
    await change_password(c)
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    await boss.post("/api/v1/notifications/broadcast", json={"title": "Salom", "everyone": True})

    items = (await c.get("/api/v1/notifications")).json()["items"]
    assert len(items) == 2
    assert (await c.post(f"/api/v1/notifications/{items[0]['id']}/read")).status_code == 204
    assert (await c.get("/api/v1/notifications/unread-count")).json()["count"] == 1
    assert len((await c.get("/api/v1/notifications", params={"unread": "true"})).json()["items"]) == 1
    assert (await c.post("/api/v1/notifications/read-all")).status_code == 204
    assert (await c.get("/api/v1/notifications/unread-count")).json()["count"] == 0


async def test_cannot_read_someone_elses_notification(new_client):
    a, _ = await as_user(new_client, "ali", "koordinator")
    await change_password(a)
    nid = (await a.get("/api/v1/notifications")).json()["items"][0]["id"]
    b, _ = await as_user(new_client, "vali", "koordinator")
    assert (await b.post(f"/api/v1/notifications/{nid}/read")).status_code == 404
    assert (await a.get("/api/v1/notifications/unread-count")).json()["count"] == 1
    assert (await b.get("/api/v1/notifications")).json()["total"] == 0


async def test_broadcast_permission_and_targeting(new_client):
    kor, _ = await as_user(new_client, "kor", "koordinator")
    r = await kor.post("/api/v1/notifications/broadcast", json={"title": "x", "everyone": True})
    assert r.status_code == 403

    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    m1, _ = await as_user(new_client, "m1", "mudir")
    await make_user("off", "mudir", active=False)

    none = await boss.post("/api/v1/notifications/broadcast", json={"title": "x"})
    assert none.status_code == 400 and none.json()["detail"]["code"] == "no_recipients"

    r = await boss.post(
        "/api/v1/notifications/broadcast",
        json={"title": "Yig'ilish {0}", "body": "Soat {soat} da", "role_keys": ["mudir"], "link": "/users"},
    )
    assert r.json() == {"recipients": 1}  # faol mudir faqat m1
    n = (await m1.get("/api/v1/notifications")).json()["items"][0]
    # Foydalanuvchi matnidagi {} shablon sifatida talqin qilinmaydi
    assert n["title"]["uz"] == "Yig'ilish {0}" and n["body"]["uz"] == "Soat {soat} da"
    assert n["title"]["ru"] == "Yig'ilish {0}" and n["link"] == "/users"
    assert (await kor.get("/api/v1/notifications")).json()["total"] == 0


async def test_broadcast_validation(new_client):
    boss, _ = await as_user(new_client, "boss", "hr_direktor")
    bad_link = await boss.post(
        "/api/v1/notifications/broadcast",
        json={"title": "x", "everyone": True, "link": "https://evil.example"},
    )
    assert bad_link.status_code == 422  # faqat ichki ("/...") havolalar


async def test_deliver_enqueues_telegram_only_when_configured(new_client, app, monkeypatch):
    from app.config import get_settings

    c, uid = await as_user(new_client, "ali", "koordinator")
    await change_password(c)
    assert app.state.queue.calls == []  # token yo'q

    monkeypatch.setattr(get_settings(), "telegram_bot_token", "123:abc")
    await c.post(
        "/api/auth/change-password", json={"old_password": "Better-pass1", "new_password": "Third-pass1"}
    )
    assert [call[0] for call in app.state.queue.calls] == ["deliver_telegram"]


class FakeSocket:
    def __init__(self):
        self.messages: list[dict] = []

    async def send_json(self, data):
        self.messages.append(data)


class DeadSocket:
    async def send_json(self, data):
        raise RuntimeError("closed")


async def test_realtime_end_to_end_via_redis(new_client, app):
    """Bildirishnoma yaratilganda ulangan socketga Redis pub/sub orqali yetib boradi."""
    c, uid = await as_user(new_client, "ali", "koordinator")
    hub: RealtimeHub = app.state.hub
    sock = FakeSocket()
    hub.add(uid, sock)
    listener = asyncio.create_task(hub.listen(app.state.redis))
    try:
        await asyncio.sleep(0.1)  # obuna bo'lishini kutamiz
        await change_password(c)
        for _ in range(50):
            if sock.messages:
                break
            await asyncio.sleep(0.05)
    finally:
        listener.cancel()
        await asyncio.gather(listener, return_exceptions=True)

    assert sock.messages and sock.messages[0]["type"] == "notification"
    assert sock.messages[0]["notification"]["kind"] == "security.password_changed"


async def test_hub_isolates_users_and_drops_dead_sockets(app):
    hub = RealtimeHub()
    a, b, dead = FakeSocket(), FakeSocket(), DeadSocket()
    hub.add(1, a)
    hub.add(2, b)
    hub.add(1, dead)
    await hub.dispatch(1, {"type": "x"})
    assert a.messages == [{"type": "x"}] and b.messages == []
    assert hub.connections(1) == 1  # o'lik socket olib tashlandi
    hub.remove(1, a)
    hub.remove(2, b)
    assert hub.connections() == 0


async def test_publish_reaches_only_target_channel(app):
    redis = app.state.redis
    pubsub = redis.pubsub()
    await pubsub.psubscribe("rt:user:*")
    await asyncio.sleep(0.05)
    await publish(redis, [7, 7, 8], "ping", {"a": 1})
    got = []
    for _ in range(10):
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if m:
            got.append(m["channel"])
    await pubsub.aclose()
    assert sorted(got) == ["rt:user:7", "rt:user:8"]  # takroriy id bir marta
