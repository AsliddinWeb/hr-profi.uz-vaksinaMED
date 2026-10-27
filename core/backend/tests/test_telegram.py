import httpx
import pytest
from arq import Retry

from app.bot import handle_update
from app.config import get_settings
from app.db import SessionLocal
from app.models.auth import User
from app.models.notifications import Notification
from app.services import telegram_link as link
from app.services.notifications import notify
from app.telegram import TelegramClient, TelegramError, esc
from app.worker import deliver_telegram, telegram_text
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)


class FakeClient:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


def msg(chat_id, text, chat_type="private", username="ali_tg"):
    return {
        "update_id": 1,
        "message": {
            "chat": {"id": chat_id, "type": chat_type},
            "from": {"username": username},
            "text": text,
        },
    }


async def as_user(new_client, login_name, role="koordinator", **kw):
    uid = await make_user(login_name, role, **kw)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "telegram_bot_token", "123:abc")


async def test_link_code_requires_configured_bot(new_client):
    c, _ = await as_user(new_client, "ali")
    r = await c.post("/api/v1/telegram/link-code")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "telegram_disabled"
    st = (await c.get("/api/v1/telegram/status")).json()
    assert st["enabled"] is False and st["linked"] is False


async def test_full_link_flow_and_status(new_client, app, telegram_on):
    c, uid = await as_user(new_client, "ali")
    await app.state.redis.set("telegram:bot_username", "VaksinaTestBot")

    r = (await c.post("/api/v1/telegram/link-code")).json()
    assert r["url"] == f"https://t.me/VaksinaTestBot?start={r['code']}"

    client = FakeClient()
    await handle_update(msg(555, f"/start {r['code']}"), client=client, redis=app.state.redis, sessions=SessionLocal)
    assert client.sent and "✅" in client.sent[0][1]

    st = (await c.get("/api/v1/telegram/status")).json()
    assert st["linked"] is True and st["telegram_username"] == "ali_tg" and st["notify"] is True
    # Ulangani haqida bildirishnoma ham yaratilgan
    kinds = [n["kind"] for n in (await c.get("/api/v1/notifications")).json()["items"]]
    assert "telegram.linked" in kinds

    # Kod bir martalik
    again = FakeClient()
    await handle_update(msg(777, f"/start {r['code']}"), client=again, redis=app.state.redis, sessions=SessionLocal)
    assert "❌" in again.sent[0][1]


async def test_bad_codes_do_not_link(new_client, app, telegram_on):
    await as_user(new_client, "ali")
    client = FakeClient()
    for text in ("/start nope", "/start ' OR 1=1 --", "/start " + "x" * 100):
        await handle_update(msg(9, text), client=client, redis=app.state.redis, sessions=SessionLocal)
    assert all("❌" in t for _, t in client.sent) and len(client.sent) == 3


async def test_group_chats_are_rejected(app, telegram_on):
    client = FakeClient()
    await handle_update(msg(-100, "/start abcdefghij", chat_type="group"), client=client,
                        redis=app.state.redis, sessions=SessionLocal)
    assert len(client.sent) == 1 and "faqat shaxsiy" in client.sent[0][1]


async def test_stop_and_start_toggle_notifications(new_client, app, telegram_on):
    c, uid = await as_user(new_client, "ali")
    code = await link.create_link_code(app.state.redis, uid)
    client = FakeClient()
    kw = dict(client=client, redis=app.state.redis, sessions=SessionLocal)
    await handle_update(msg(42, f"/start {code}"), **kw)

    await handle_update(msg(42, "/stop"), **kw)
    assert (await c.get("/api/v1/telegram/status")).json()["notify"] is False
    await handle_update(msg(42, "/status"), **kw)
    assert "o'chirilgan" in client.sent[-1][1]
    await handle_update(msg(42, "/start"), **kw)
    assert (await c.get("/api/v1/telegram/status")).json()["notify"] is True


async def test_unlinked_chat_gets_help_and_cannot_stop(app, telegram_on):
    client = FakeClient()
    kw = dict(client=client, redis=app.state.redis, sessions=SessionLocal)
    await handle_update(msg(1, "/stop"), **kw)
    await handle_update(msg(1, "/whatever"), **kw)
    assert len(client.sent) == 2


async def test_relinking_same_chat_moves_it_to_new_account(new_client, app, telegram_on):
    a, a_id = await as_user(new_client, "ali")
    b, b_id = await as_user(new_client, "vali")
    client = FakeClient()
    kw = dict(client=client, redis=app.state.redis, sessions=SessionLocal)
    await handle_update(msg(5, f"/start {await link.create_link_code(app.state.redis, a_id)}"), **kw)
    await handle_update(msg(5, f"/start {await link.create_link_code(app.state.redis, b_id)}"), **kw)
    assert (await a.get("/api/v1/telegram/status")).json()["linked"] is False
    assert (await b.get("/api/v1/telegram/status")).json()["linked"] is True


async def test_unlink_endpoint_and_prefs(new_client, app, telegram_on):
    c, uid = await as_user(new_client, "ali")
    assert (await c.patch("/api/v1/telegram", json={"notify": False})).status_code == 409
    await handle_update(
        msg(8, f"/start {await link.create_link_code(app.state.redis, uid)}"),
        client=FakeClient(), redis=app.state.redis, sessions=SessionLocal,
    )  # fmt: skip
    assert (await c.patch("/api/v1/telegram", json={"notify": False})).json()["notify"] is False
    assert (await c.delete("/api/v1/telegram")).status_code == 204
    assert (await c.get("/api/v1/telegram/status")).json()["linked"] is False


def mock_client(handler) -> TelegramClient:
    return TelegramClient("123:abc", transport=httpx.MockTransport(handler))


async def make_note(uid, title="Salom <b>", body="A & B", link=None):
    async with SessionLocal() as s:
        notes = await notify(s, [uid], "x.custom", title={"uz": title, "ru": "Привет"},
                             body={"uz": body, "ru": "и"}, link=link)  # fmt: skip
        await s.commit()
        return notes[0].id


async def link_chat(uid, chat_id=99, notify_on=True):
    async with SessionLocal() as s:
        await link.link_user(s, uid, chat_id, "tg")
        u = await s.get(User, uid)
        u.telegram_notify = notify_on
        await s.commit()


async def test_worker_sends_escaped_html_to_linked_chat():
    uid = await make_user("ali", "koordinator")
    await link_chat(uid, 99)
    nid = await make_note(uid)
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True, "result": {}})

    result = await deliver_telegram({"telegram": mock_client(handler)}, nid)
    assert result == "sent"
    assert "sendMessage" in seen["url"] and '"chat_id":99' in seen["body"].replace(" ", "")
    # HTML maxsus belgilar ekranlangan (Telegram parse xatosi/injection oldini olish)
    assert "Salom &lt;b&gt;" in seen["body"] and "A &amp; B" in seen["body"]


async def test_worker_skips_when_not_linked_or_muted():
    uid = await make_user("ali", "koordinator")
    nid = await make_note(uid)
    called = []

    def handler(request):
        called.append(1)
        return httpx.Response(200, json={"ok": True, "result": {}})

    ctx = {"telegram": mock_client(handler)}
    assert await deliver_telegram(ctx, nid) == "skipped"  # ulanmagan
    await link_chat(uid, 10, notify_on=False)
    assert await deliver_telegram(ctx, nid) == "skipped"  # o'chirilgan
    assert await deliver_telegram({}, nid) == "disabled"  # bot sozlanmagan
    assert called == []


async def test_worker_unlinks_when_bot_blocked():
    uid = await make_user("ali", "koordinator")
    await link_chat(uid, 11)
    nid = await make_note(uid)

    def handler(request):
        return httpx.Response(403, json={"ok": False, "error_code": 403,
                                         "description": "Forbidden: bot was blocked by the user"})

    assert await deliver_telegram({"telegram": mock_client(handler)}, nid) == "unlinked"
    async with SessionLocal() as s:
        assert (await s.get(User, uid)).telegram_chat_id is None


async def test_worker_retries_on_rate_limit_and_server_errors():
    uid = await make_user("ali", "koordinator")
    await link_chat(uid, 12)
    nid = await make_note(uid)

    def limited(request):
        return httpx.Response(429, json={"ok": False, "error_code": 429, "description": "Too Many",
                                         "parameters": {"retry_after": 7}})

    with pytest.raises(Retry) as exc:
        await deliver_telegram({"telegram": mock_client(limited)}, nid)
    assert exc.value.defer_score == 7000  # 7 soniya (ms)

    def broken(request):
        return httpx.Response(502, text="bad gateway")

    with pytest.raises(Retry):
        await deliver_telegram({"telegram": mock_client(broken)}, nid)
    async with SessionLocal() as s:
        assert (await s.get(User, uid)).telegram_chat_id == 12  # vaqtinchalik xatoda uzilmaydi


async def test_telegram_text_includes_link_only_with_public_url(monkeypatch):
    uid = await make_user("ali", "koordinator")
    nid = await make_note(uid, link="/users")
    async with SessionLocal() as s:
        n = await s.get(Notification, nid)
    assert "/users" not in telegram_text(n, "uz")
    monkeypatch.setattr(get_settings(), "public_url", "https://c1.example.uz/")
    assert telegram_text(n, "uz").endswith("https://c1.example.uz/users")


async def test_client_error_parsing():
    def handler(request):
        return httpx.Response(400, json={"ok": False, "error_code": 400, "description": "Bad Request: chat not found"})

    with pytest.raises(TelegramError) as exc:
        await mock_client(handler).send_message(1, "x")
    assert exc.value.chat_unreachable is True
    assert esc("<a>&") == "&lt;a&gt;&amp;"
