import base64
import hashlib
import json
from datetime import datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.db import SessionLocal
from app.services import calls as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

C = "/api/v1/calls"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=tz())
KEY, SECRET = "testkey", "s" * 40


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    monkeypatch.setattr("app.api.calls.now", lambda: state["t"])
    cfg = get_settings().model_copy(update={"livekit_api_key": KEY, "livekit_api_secret": SECRET})
    for mod in ("app.services.calls", "app.api.calls"):
        monkeypatch.setattr(f"{mod}.get_settings", lambda: cfg)

    async def no_room(*a, **k):
        return True

    monkeypatch.setattr("app.services.calls._twirp", no_room)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def setup(new_client):
    a, a_id = await as_user(new_client, "ali", "farmasevt")
    b, b_id = await as_user(new_client, "bob", "farmasevt")
    d, d_id = await as_user(new_client, "dil", "farmasevt")
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    return {"a": a, "a_id": a_id, "b": b, "b_id": b_id, "d": d, "d_id": d_id, "hr": hr, "hr_id": hr_id}


async def kinds(c):
    return [n["kind"] for n in (await c.get("/api/v1/notifications")).json()["items"]]


def hook(event: dict, secret: str = SECRET) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    tok = jwt.encode({"iss": KEY, "exp": 9999999999, "sha256": base64.b64encode(hashlib.sha256(body).digest()).decode()}, secret, algorithm="HS256")
    return body, {"Authorization": tok, "Content-Type": "application/webhook+json"}


async def test_direct_call_accept_and_history(new_client, clock):
    ctx = await setup(new_client)
    r = await ctx["a"].post(C, json={"kind": "direct", "media": "audio", "invitee_ids": [ctx["b_id"]]})
    assert r.status_code == 201, r.text
    call = r.json()
    assert call["status"] == "ringing" and call["peer"] == "Bob" and "calls.incoming" in await kinds(ctx["b"])
    inc = (await ctx["b"].get(f"{C}/incoming")).json()
    assert [x["id"] for x in inc] == [call["id"]] and inc[0]["caller"] == "Ali"
    assert (await ctx["d"].get(f"{C}/{call['id']}")).status_code == 404
    # takror chaqiruv
    assert (await ctx["a"].post(C, json={"kind": "direct", "invitee_ids": [ctx["b_id"]]})).json()["detail"]["code"] == "already_calling"

    r = await ctx["b"].post(f"{C}/{call['id']}/token")
    assert r.status_code == 200
    claims = jwt.decode(r.json()["token"], SECRET, algorithms=["HS256"], issuer=KEY)
    assert claims["sub"] == f"u{ctx['b_id']}" and claims["video"]["roomJoin"] is True and claims["video"]["room"].startswith("call-")
    assert (await ctx["b"].get(f"{C}/{call['id']}")).json()["status"] == "active"
    assert (await ctx["b"].get(f"{C}/incoming")).json() == []
    assert (await ctx["a"].post(f"{C}/{call['id']}/token")).status_code == 200

    clock["t"] = NOW + timedelta(minutes=5)
    await ctx["b"].post(f"{C}/{call['id']}/leave")
    d = (await ctx["a"].get(f"{C}/{call['id']}")).json()
    assert d["status"] == "active" and d["online"] == 1
    clock["t"] = NOW + timedelta(minutes=6)
    await ctx["a"].post(f"{C}/{call['id']}/leave")
    d = (await ctx["a"].get(f"{C}/{call['id']}")).json()
    assert d["status"] == "ended" and d["duration"] == 360 and d["end_reason"] == "empty"
    secs = {p["name"]: p["seconds"] for p in d["participants"]}
    assert secs == {"Ali": 360, "Bob": 300}
    assert (await ctx["b"].post(f"{C}/{call['id']}/token")).status_code == 409
    hist = (await ctx["a"].get(C)).json()
    assert hist["total"] == 1 and (await ctx["d"].get(C)).json()["total"] == 0


async def test_decline_cancel_and_missed(new_client, clock):
    ctx = await setup(new_client)
    c1 = (await ctx["a"].post(C, json={"kind": "direct", "invitee_ids": [ctx["b_id"]]})).json()
    assert (await ctx["a"].post(f"{C}/{c1['id']}/decline")).status_code == 404
    r = await ctx["b"].post(f"{C}/{c1['id']}/decline")
    assert r.json()["status"] == "declined" and "calls.declined" in await kinds(ctx["a"])
    assert (await ctx["b"].post(f"{C}/{c1['id']}/token")).status_code == 409

    # chaqiruvchi o'zi chiqib ketdi: bekor
    c2 = (await ctx["a"].post(C, json={"kind": "direct", "invitee_ids": [ctx["b_id"]]})).json()
    await ctx["a"].post(f"{C}/{c2['id']}/token")
    await ctx["a"].post(f"{C}/{c2['id']}/leave")
    d = (await ctx["b"].get(f"{C}/{c2['id']}")).json()
    assert d["status"] == "cancelled" and (await ctx["b"].get(f"{C}/incoming")).json() == []

    # javob berilmadi: 45 s dan keyin missed
    c3 = (await ctx["a"].post(C, json={"kind": "direct", "invitee_ids": [ctx["b_id"]]})).json()
    clock["t"] = NOW + timedelta(seconds=30)
    async with SessionLocal() as db:
        assert (await svc.watch(db, clock["t"]))[0] == 0
    clock["t"] = NOW + timedelta(seconds=60)
    assert (await ctx["b"].get(f"{C}/incoming")).json() == []
    async with SessionLocal() as db:
        missed, _, notes = await svc.watch(db, clock["t"])
        await db.commit()
    assert missed == 1 and notes
    d = (await ctx["b"].get(f"{C}/{c3['id']}")).json()
    assert d["status"] == "missed" and "calls.missed" in await kinds(ctx["b"])
    assert (await ctx["b"].post(f"{C}/{c3['id']}/token")).status_code == 409


async def test_conference_flow_update_end_and_visibility(new_client, clock):
    ctx = await setup(new_client)
    soon = (NOW + timedelta(hours=3)).isoformat()
    r = await ctx["a"].post(C, json={"kind": "conference", "title": "Haftalik", "scheduled_at": soon, "invitee_ids": [ctx["b_id"], ctx["d_id"]]})
    assert r.status_code == 201, r.text
    conf = r.json()
    assert conf["status"] == "scheduled" and len(conf["participants"]) == 3 and conf["can"]["edit"]
    assert "calls.invited" in await kinds(ctx["b"]) and (await ctx["d"].get(C, params={"scope": "live"})).json()["total"] == 1
    # juda erta
    assert (await ctx["b"].post(f"{C}/{conf['id']}/token")).json()["detail"]["code"] == "too_early"
    # mezbon istalgan paytda kira oladi
    assert (await ctx["a"].post(f"{C}/{conf['id']}/token")).status_code == 200
    assert (await ctx["a"].get(f"{C}/{conf['id']}")).json()["status"] == "active"
    assert (await ctx["b"].post(f"{C}/{conf['id']}/token")).status_code == 200
    assert (await ctx["b"].post(f"{C}/{conf['id']}/end")).status_code == 403

    # tahrirlash faqat boshlanmaganda
    assert (await ctx["a"].put(f"{C}/{conf['id']}", json={"kind": "conference", "title": "x", "invitee_ids": [ctx["b_id"]]})).status_code == 409
    # boshqa konferensiya: ishtirokchilarni almashtirish
    c2 = (await ctx["a"].post(C, json={"kind": "conference", "scheduled_at": soon, "invitee_ids": [ctx["b_id"]]})).json()
    r = await ctx["a"].put(f"{C}/{c2['id']}", json={"kind": "conference", "title": "Yangi", "scheduled_at": soon, "media": "audio", "invitee_ids": [ctx["d_id"]]})
    assert r.status_code == 200 and sorted(p["name"] for p in r.json()["participants"]) == ["Ali", "Dil"] and r.json()["media"] == "audio"
    assert (await ctx["b"].get(f"{C}/{c2['id']}")).status_code == 404
    assert (await ctx["b"].put(f"{C}/{c2['id']}", json={"kind": "conference", "invitee_ids": [ctx["a_id"]]})).status_code in (403, 404)

    # tarixni ko'rish: faqat calls.read/manage
    assert (await ctx["d"].get(C, params={"scope": "all"})).status_code == 403
    assert (await ctx["hr"].get(C, params={"scope": "all"})).json()["total"] == 2
    assert (await ctx["hr"].get(f"{C}/{conf['id']}")).status_code == 200

    clock["t"] = NOW + timedelta(minutes=30)
    r = await ctx["hr"].post(f"{C}/{conf['id']}/end")  # administrator tugatadi
    assert r.json()["status"] == "ended" and r.json()["end_reason"] == "admin" and r.json()["duration"] == 1800
    assert {p["name"]: p["status"] for p in r.json()["participants"]}["Bob"] == "left"
    assert (await ctx["a"].post(f"{C}/{conf['id']}/end")).status_code == 409


async def test_conference_empty_watch_and_validation(new_client, clock):
    ctx = await setup(new_client)
    assert (await ctx["a"].post(C, json={"kind": "direct", "invitee_ids": [ctx["b_id"], ctx["d_id"]]})).json()["detail"]["code"] == "direct_one_user"
    assert (await ctx["a"].post(C, json={"kind": "conference", "invitee_ids": []})).json()["detail"]["code"] == "invitee_required"
    assert (await ctx["a"].post(C, json={"kind": "conference", "invitee_ids": [999999]})).json()["detail"]["code"] == "unknown_user"
    conf = (await ctx["a"].post(C, json={"kind": "conference", "invitee_ids": [ctx["b_id"]]})).json()
    await ctx["b"].post(f"{C}/{conf['id']}/token")
    await ctx["b"].post(f"{C}/{conf['id']}/leave")
    assert (await ctx["a"].get(f"{C}/{conf['id']}")).json()["status"] == "active"  # konferensiya darhol tugamaydi
    async with SessionLocal() as db:
        await svc.watch(db, NOW + timedelta(minutes=10))
        await db.commit()
    assert (await ctx["a"].get(f"{C}/{conf['id']}")).json()["status"] == "active"
    async with SessionLocal() as db:
        await svc.watch(db, NOW + timedelta(minutes=20))
        await db.commit()
    d = (await ctx["a"].get(f"{C}/{conf['id']}")).json()
    assert d["status"] == "ended" and d["end_reason"] == "empty"


async def test_webhook_signature_and_events(new_client, clock):
    ctx = await setup(new_client)
    call = (await ctx["a"].post(C, json={"kind": "direct", "invitee_ids": [ctx["b_id"]]})).json()
    room = (await ctx["a"].post(f"{C}/{call['id']}/token")).json()["room"]

    body, headers = hook({"event": "participant_joined", "room": {"name": room}, "participant": {"identity": f"u{ctx['b_id']}"}})
    bad_body, bad_headers = hook({"event": "participant_joined", "room": {"name": room}, "participant": {"identity": f"u{ctx['b_id']}"}}, secret="x" * 40)
    assert (await ctx["a"].post(f"{C}/webhook", content=bad_body, headers=bad_headers)).status_code == 401
    assert (await ctx["a"].post(f"{C}/webhook", content=body + b" ", headers=headers)).status_code == 401  # tana o'zgargan
    assert (await ctx["a"].post(f"{C}/webhook", content=body)).status_code == 401
    assert (await ctx["a"].post(f"{C}/webhook", content=body, headers=headers)).status_code == 200
    d = (await ctx["a"].get(f"{C}/{call['id']}")).json()
    assert d["status"] == "active" and d["online"] == 2

    clock["t"] = NOW + timedelta(minutes=2)
    for who in (ctx["a_id"], ctx["b_id"]):
        b2, h2 = hook({"event": "participant_left", "room": {"name": room}, "participant": {"identity": f"u{who}"}})
        assert (await ctx["a"].post(f"{C}/webhook", content=b2, headers=h2)).status_code == 200
    d = (await ctx["a"].get(f"{C}/{call['id']}")).json()
    assert d["status"] == "ended" or d["online"] == 0


async def test_disabled_without_keys(new_client, monkeypatch):
    ctx = await setup(new_client)
    cfg = get_settings().model_copy(update={"livekit_api_key": "", "livekit_api_secret": ""})
    monkeypatch.setattr("app.services.calls.get_settings", lambda: cfg)
    monkeypatch.setattr("app.api.calls.get_settings", lambda: cfg)
    assert (await ctx["a"].get(f"{C}/config")).json()["enabled"] is False
    r = await ctx["a"].post(C, json={"kind": "direct", "invitee_ids": [ctx["b_id"]]})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "calls_disabled"
