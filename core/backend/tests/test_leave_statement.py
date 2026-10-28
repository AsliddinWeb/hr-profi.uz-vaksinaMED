from datetime import date

import pytest
from sqlalchemy import select

from app.bot import handle_update
from app.db import SessionLocal
from app.models.answers import LeaveRequest
from app.models.auth import User
from tests.test_answers import T0, A, as_user, day_req, setup

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)


@pytest.fixture
def clock(monkeypatch):
    fn = lambda: T0  # noqa: E731
    monkeypatch.setattr("app.api.answers.now", fn)
    monkeypatch.setattr("app.api.attendance.now", fn)
    monkeypatch.setattr("app.services.attendance.now", fn)


class FakeClient:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []
        self.docs: list[tuple[int, str, bytes, str | None]] = []

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id, filename, data, caption=None):
        self.docs.append((chat_id, filename, data, caption))


class QueueSpy:
    def __init__(self):
        self.calls = []

    async def enqueue(self, function, *args, defer_seconds=None):
        self.calls.append((function, *args))


async def approved_request(ctx):
    r = (await ctx["emp"].post(f"{A}/requests", json=day_req())).json()
    d = await ctx["coord"].post(f"{A}/requests/{r['id']}/decision", json={"action": "approve"})
    assert d.status_code == 200, d.text
    return r["id"]


async def link_chat(login, chat_id):
    async with SessionLocal() as s:
        u = await s.scalar(select(User).where(User.login == login))
        u.telegram_chat_id, u.telegram_notify = chat_id, True
        await s.commit()


async def say(chat_id, text, client):
    import fakeredis.aioredis

    update = {"update_id": 1, "message": {"chat": {"id": chat_id, "type": "private"}, "text": text, "from": {"username": "x"}}}
    await handle_update(update, client=client, redis=fakeredis.aioredis.FakeRedis(decode_responses=True), sessions=SessionLocal)


async def test_statement_issued_on_approval_pdf_and_verify(new_client, clock, app):
    app.state.queue = QueueSpy()
    ctx = await setup(new_client)
    rid = await approved_request(ctx)
    assert app.state.queue.calls == [("deliver_statement_telegram", rid)]
    async with SessionLocal() as s:
        req = await s.get(LeaveRequest, rid)
        assert req.statement_no.startswith("JO-2026-") and req.statement_code and req.statement_hash
        code, no = req.statement_code, req.statement_no
    pdf = await ctx["emp"].get(f"{A}/requests/{rid}/statement")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and no in pdf.headers["content-disposition"]
    assert (await ctx["hr"].get(f"{A}/requests/{rid}/statement", params={"lang": "ru"})).status_code == 200
    # ochiq tekshiruv (kirishsiz)
    pub = new_client()
    v = await pub.get(f"/api/v1/public/leave/{code}")
    assert v.status_code == 200
    j = v.json()
    assert j["valid"] and j["intact"] and j["number"] == no and j["employee"] == "Aliyev A." and "reason" not in j
    assert (await pub.get(f"/api/v1/public/leave/{code}", params={"hash": j["hash_prefix"]})).json()["hash_match"] is True
    assert (await pub.get("/api/v1/public/leave/yoq-kod")).status_code == 404
    # sana o'zgartirilsa yaxlitlik buziladi
    async with SessionLocal() as s:
        req = await s.get(LeaveRequest, rid)
        req.end_date = date(2026, 11, 30)
        await s.commit()
    assert (await pub.get(f"/api/v1/public/leave/{code}")).json()["intact"] is False


async def test_statement_not_for_pending_or_strangers(new_client, clock, app):
    app.state.queue = QueueSpy()
    ctx = await setup(new_client)
    r = (await ctx["emp"].post(f"{A}/requests", json=day_req())).json()
    assert (await ctx["emp"].get(f"{A}/requests/{r['id']}/statement")).json()["detail"]["code"] == "not_approved"
    rid = await approved_request(ctx) if False else r["id"]
    await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "approve"})
    other, _ = await as_user(new_client, "ali2", "farmasevt")
    assert (await other.get(f"{A}/requests/{rid}/statement")).status_code == 404


async def test_bot_javob_overview_and_bildirgi(new_client, clock, app):
    app.state.queue = QueueSpy()
    ctx = await setup(new_client)
    await approved_request(ctx)
    await link_chat("hr", 111)
    await link_chat("ali", 222)
    c = FakeClient()
    await say(111, "/javob", c)
    text = "\n".join(m for _, m in c.messages)
    assert "Jami filial" in text and "Aliyev Ali" in text and "F5" in text and "✅" in text
    c2 = FakeClient()
    await say(222, "/javob", c2)  # oddiy xodim
    assert "faqat HR" in c2.messages[0][1]
    await say(222, "/bildirgi", c2)
    assert len(c2.docs) == 1 and c2.docs[0][2].startswith(b"%PDF") and c2.docs[0][1].startswith("JO-2026-")
    c3 = FakeClient()
    await say(111, "/bildirgi", c3)  # HR da xodim kartochkasi yo'q
    assert "biriktirilmagan" in c3.messages[0][1]
