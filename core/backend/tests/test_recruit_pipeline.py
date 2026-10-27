import json

import pytest
from sqlalchemy import select

from app.bot import handle_update
from app.db import SessionLocal
from app.models.recruit import Application, Candidate
from tests.conftest import login, make_user
from tests.test_telegram import FakeClient, msg

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

PH = "/api/v1/pharmacy"
RC = "/api/v1/recruit"
PUB = "/api/v1/public/apply"


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


class FakeQueue:
    def __init__(self):
        self.jobs: list[tuple] = []

    async def enqueue(self, function, *args, defer_seconds=None):
        self.jobs.append((function, *args))


async def setup(new_client, app):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    hr, _ = await as_user(new_client, "hrm", "hr_menejer")
    branch = (await hrd.post("/api/v1/branches", json={"number": 31, "name": "F31"})).json()
    vid = (await hrd.post(f"{PH}/needs", json={"branch_id": branch["id"], "role": "pharmacist", "count": 1})).json()["vacancy_id"]
    link = (await hr.post(f"{RC}/vacancies/{vid}/links", json={"channel": "telegram"})).json()
    app.state.queue = FakeQueue()
    return {"hrd": hrd, "hr": hr, "vid": vid, "link": link, "queue": app.state.queue}


async def apply_via_web(ctx, new_client, phone="+998901234567"):
    anon = new_client()
    assert (await anon.post(f"{PUB}/{ctx['link']['code']}", json={"full_name": "Karimov Aziz", "phone": phone})).status_code == 201
    async with SessionLocal() as s:
        return (await s.scalars(select(Application).order_by(Application.id.desc()))).first().id


async def test_interview_level_offer_approval(new_client, app):
    ctx = await setup(new_client, app)
    aid = await apply_via_web(ctx, new_client)
    hr, hrd = ctx["hr"], ctx["hrd"]
    offer = {"level": "pharmacist", "salary": 4_000_000, "start_date": "2026-11-20"}

    # suhbatsiz offer yo'q; tajribasiz nomzodga faqat stajyor ochiladi
    assert (await hr.post(f"{RC}/applications/{aid}/offer", json=offer)).json()["detail"]["code"] == "interview_required"
    r = await hr.post(f"{RC}/applications/{aid}/interview", json={"experience_level": "none", "hard_skill": 2, "soft_skill": 4, "notes": "Yangi"})
    assert r.status_code == 200 and r.json()["stages_unlocked"] == ["intern"]
    assert (await hr.post(f"{RC}/applications/{aid}/offer", json=offer)).json()["detail"]["code"] == "level_not_unlocked"
    await hr.post(f"{RC}/applications/{aid}/interview", json={"experience_level": "mid", "hard_skill": 4, "soft_skill": 4})

    # fon tekshiruvdan o'tmagan nomzodga offer yo'q (sabab shart)
    assert (await hr.post(f"{RC}/applications/{aid}/background", json={"status": "failed"})).json()["detail"]["code"] == "note_required"
    await hr.post(f"{RC}/applications/{aid}/background", json={"status": "failed", "note": "Soxta hujjat"})
    assert (await hr.post(f"{RC}/applications/{aid}/offer", json=offer)).json()["detail"]["code"] == "background_failed"
    await hr.post(f"{RC}/applications/{aid}/background", json={"status": "passed"})

    r = await hr.post(f"{RC}/applications/{aid}/offer", json=offer)
    assert r.status_code == 200 and r.json()["offer"]["status"] == "pending_hrd" and r.json()["stage"] == "new"
    # HR menejer o'zi tasdiqlay olmaydi; HRD rad etsa izoh shart
    assert (await hr.post(f"{RC}/applications/{aid}/offer/decide", json={"action": "approve"})).status_code == 403
    assert (await hrd.post(f"{RC}/applications/{aid}/offer/decide", json={"action": "reject"})).json()["detail"]["code"] == "note_required"
    r = await hrd.post(f"{RC}/applications/{aid}/offer/decide", json={"action": "approve", "note": "OK"})
    assert r.json()["offer"]["status"] == "approved" and r.json()["stage"] == "offer"
    # nomzod botga yozmagan: Telegramga yuborib bo'lmaydi
    assert (await hr.post(f"{RC}/applications/{aid}/offer/send")).json()["detail"]["code"] == "candidate_no_telegram"
    assert ctx["queue"].jobs == []


async def test_invite_and_offer_reach_candidate_telegram(new_client, app):
    ctx = await setup(new_client, app)
    aid = await apply_via_web(ctx, new_client)
    async with SessionLocal() as s:
        c = (await s.scalars(select(Candidate))).one()
        c.telegram_chat_id = 4242
        await s.commit()
    r = await ctx["hr"].post(f"{RC}/applications/{aid}/invite", json={"interview_at": "2026-11-05T14:30:00+05:00", "place": "Bosh ofis, 2-qavat"})
    assert r.status_code == 200 and r.json()["stage"] == "interview" and r.json()["telegram_sent"] is True
    fn, chat, text = ctx["queue"].jobs[0]
    assert fn == "deliver_candidate_telegram" and chat == 4242 and "05.11.2026 14:30" in text and "Bosh ofis" in text
    await ctx["hrd"].post(f"{RC}/applications/{aid}/interview", json={"experience_level": "high", "hard_skill": 5, "soft_skill": 5})
    await ctx["hrd"].post(f"{RC}/applications/{aid}/offer", json={"level": "senior", "salary": 6_000_000})  # HRD o'zi: darhol tasdiqlangan
    assert (await ctx["hrd"].post(f"{RC}/applications/{aid}/offer/send")).status_code == 200
    assert "Katta farmatsevt" in ctx["queue"].jobs[1][2] and "6 000 000" in ctx["queue"].jobs[1][2]


async def test_ai_scan_stores_recommendation(new_client, app, monkeypatch):
    ctx = await setup(new_client, app)
    aid = await apply_via_web(ctx, new_client)
    assert (await ctx["hr"].post(f"{RC}/applications/{aid}/ai-scan")).json()["detail"]["code"] == "ai_disabled"

    async def fake_post(model, system, user, max_tokens):
        assert "<data>" in user and "Karimov" not in system
        return json.dumps({"score": 82, "summary": "Mos", "strengths": ["muloqot"], "risks": ["tajriba kam"], "questions": ["Smena?"], "recommendation": "advance"}), 10, 20

    monkeypatch.setattr("app.services.ai.configured", lambda: True)
    monkeypatch.setattr("app.services.ai._post", fake_post)
    r = await ctx["hr"].post(f"{RC}/applications/{aid}/ai-scan")
    assert r.status_code == 200, r.text
    scan = r.json()["ai_scan"]
    assert scan["score"] == 82 and scan["recommendation"] == "advance" and scan["risks"] == ["tajriba kam"]


async def test_telegram_bot_candidate_flow(new_client, app):
    ctx = await setup(new_client, app)
    client, redis = FakeClient(), app.state.redis
    code = ctx["link"]["code"]
    await handle_update(msg(9001, f"/start apply_{code}"), client=client, redis=redis, sessions=SessionLocal)
    assert "vakansiyasi" in client.sent[-1][1]
    await handle_update(msg(9001, "Al"), client=client, redis=redis, sessions=SessionLocal)
    assert "to'liq" in client.sent[-1][1]
    await handle_update(msg(9001, "Valiyev Sardor"), client=client, redis=redis, sessions=SessionLocal)
    await handle_update(msg(9001, "12"), client=client, redis=redis, sessions=SessionLocal)
    assert "noto'g'ri" in client.sent[-1][1]
    await handle_update(msg(9001, "+998901112233"), client=client, redis=redis, sessions=SessionLocal)
    assert "qabul qilindi" in client.sent[-1][1]
    async with SessionLocal() as s:
        c = (await s.scalars(select(Candidate))).one()
        assert c.full_name == "Valiyev Sardor" and c.telegram_chat_id == 9001 and c.source == "telegram"
        assert (await s.scalars(select(Application))).one().source_link_id == ctx["link"]["id"]
    # rezyume matni keyin kelsa saqlanadi; qisqa gap e'tiborsiz
    await handle_update(msg(9001, "Men 5 yil dorixonada ishlaganman. " * 5), client=client, redis=redis, sessions=SessionLocal)
    assert "Rezyume qabul" in client.sent[-1][1]
    async with SessionLocal() as s:
        assert "5 yil" in (await s.scalars(select(Candidate))).one().resume_text
    await handle_update(msg(9002, "/start apply_yaroqsiz1"), client=client, redis=redis, sessions=SessionLocal)
    assert "yopilgan" in client.sent[-1][1]


async def test_call_log_and_recruiter_report(new_client, app):
    ctx = await setup(new_client, app)
    await apply_via_web(ctx, new_client)
    hr = ctx["hr"]
    for outcome in ("suitable", "suitable", "unsuitable", "no_answer"):
        assert (await hr.post(f"{RC}/calls", json={"outcome": outcome, "phone": "+998901234567"})).status_code == 201
    assert (await hr.post(f"{RC}/calls", json={"outcome": "suitable", "phone": "12"})).json()["detail"]["code"] == "phone_invalid"
    rep = (await hr.get(f"{RC}/recruiter-report", params={"start": "2026-01-01", "end": "2026-12-31"})).json()
    row = next(x for x in rep["items"] if x["recruiter"] == "Hrm")
    assert row["calls"] == 4 and row["suitable"] == 2 and row["unsuitable"] == 1 and row["no_answer"] == 1
    assert sum(x["applications"] for x in rep["items"]) == 1
