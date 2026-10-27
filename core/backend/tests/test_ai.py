import json

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.ai import AiRequest
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

A = "/api/v1/ai"
H = "/api/v1/helpdesk"


@pytest.fixture
def llm(monkeypatch):
    """Claude chaqiruvini almashtiradi: javob va chaqiruvlar yozuvi."""
    cfg = get_settings().model_copy(update={"anthropic_api_key": "sk-test"})
    monkeypatch.setattr("app.services.ai.get_settings", lambda: cfg)
    state = {"reply": "Qisqa xulosa.", "calls": [], "fail": False}

    async def fake(model, system, user, max_tokens):
        state["calls"].append({"model": model, "system": system, "user": user})
        if state["fail"]:
            raise RuntimeError("http_500")
        return state["reply"], 120, 30

    monkeypatch.setattr("app.services.ai._post", fake)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def mk_ticket(c, **kw):
    r = await c.post(H, json={"title": "Printer ishlamayapti", "description": "Chek chiqmayapti", **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def test_disabled_without_key(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    st = (await hr.get(f"{A}/status")).json()
    assert st["configured"] is False and st["enabled"] is False
    t = await mk_ticket(hr)
    r = await hr.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "ai_disabled"


async def test_summarize_cache_visibility_and_audit_log(new_client, llm):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    req, req_id = await as_user(new_client, "ali", "farmasevt")
    other, _ = await as_user(new_client, "bob", "farmasevt")
    t = await mk_ticket(req)
    await hr.post(f"{H}/{t['id']}/comments", json={"body": "Yashirin eslatma: parol 1234", "internal": True})
    await hr.post(f"{H}/{t['id']}/comments", json={"body": "Tekshiramiz"})

    r = await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})
    assert r.status_code == 200 and r.json() == {**r.json(), "text": "Qisqa xulosa.", "cached": False}
    sent = llm["calls"][0]["user"]
    assert sent.startswith("<data>") and "Chek chiqmayapti" in sent and "Tekshiramiz" in sent
    assert "parol 1234" not in sent  # ichki izoh modelga ketmaydi
    assert "o'zbek" in llm["calls"][0]["system"] and "MA'LUMOT" in llm["calls"][0]["system"]

    # o'sha matn: keshdan, model chaqirilmaydi
    assert (await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})).json()["cached"] is True
    assert len(llm["calls"]) == 1
    # yangi izoh -> kirish o'zgardi -> qayta so'raladi; refresh ham so'raydi
    await req.post(f"{H}/{t['id']}/comments", json={"body": "Hali ham ishlamayapti"})
    llm["reply"] = "Yangilangan xulosa."
    assert (await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})).json()["text"] == "Yangilangan xulosa."
    await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"], "refresh": True})
    assert len(llm["calls"]) == 3
    # ruscha alohida kesh
    assert (await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"], "lang": "ru"})).json()["cached"] is False
    # begona foydalanuvchi ko'ra olmaydi
    assert (await other.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})).status_code == 404
    assert (await req.post(f"{A}/summarize", json={"entity": "ticket", "id": 99999})).status_code == 404

    async with SessionLocal() as db:
        rows = (await db.scalars(select(AiRequest))).all()
    assert len(rows) == 4 and all(x.ok and x.input_tokens == 120 and x.output_tokens == 30 and x.user_id == req_id for x in rows)


async def test_failure_limit_and_settings(new_client, llm):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    req, _ = await as_user(new_client, "ali", "farmasevt")
    t = await mk_ticket(req)
    llm["fail"] = True
    r = await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})
    assert r.status_code == 502, r.text
    assert r.json()["detail"]["code"] == "ai_failed"
    async with SessionLocal() as db:
        row = (await db.scalars(select(AiRequest))).one()
    assert row.ok is False and row.error == "http_500"
    llm["fail"] = False

    # sozlamalar faqat ai.manage
    assert (await req.get(f"{A}/settings")).status_code == 403
    assert (await req.put(f"{A}/settings", json={"enabled": True, "model": "claude-haiku-5-5", "daily_limit": 5})).status_code == 403
    s = (await hr.get(f"{A}/settings")).json()
    assert s["configured"] and s["enabled"] and s["features"] == {"summary": True, "resume": True, "ticket": True, "scan": True}
    r = await hr.put(f"{A}/settings", json={"enabled": True, "model": "claude-sonnet-5-5", "daily_limit": 2, "features": {"summary": True, "resume": False}})
    assert r.json()["daily_limit"] == 2 and r.json()["features"]["resume"] is False and r.json()["features"]["ticket"] is True
    assert (await hr.put(f"{A}/settings", json={"enabled": True, "model": "bad model!", "daily_limit": 2})).status_code == 422

    # kunlik limit: 1 ta xato so'rov hisobga kirgan, yana 1 ta ruxsat, uchinchisi 429
    assert (await req.get(f"{A}/status")).json()["remaining"] == 1
    assert (await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})).status_code == 200
    r = await req.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"], "refresh": True})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "ai_limit"
    assert llm["calls"][-1]["model"] == "claude-sonnet-5-5"

    # funksiyani o'chirish va umuman o'chirish
    await hr.put(f"{A}/settings", json={"enabled": True, "model": "claude-haiku-5-5", "daily_limit": 50, "features": {"summary": False}})
    assert (await hr.post(f"{A}/summarize", json={"entity": "ticket", "id": t["id"]})).json()["detail"]["code"] == "ai_disabled"
    u = (await hr.get(f"{A}/usage")).json()
    assert u["requests"] == 2 and u["failed"] == 1 and u["input_tokens"] == 120
    assert (await req.get(f"{A}/usage")).status_code == 403


async def test_resume_parse_uses_ai_with_fallback(new_client, llm):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    text = "Karimov Aziz\nTelefon: 90 123 45 67\nFarmatsevt, 3 yil tajriba, Excel biladi."
    llm["reply"] = "```json\n" + json.dumps({"full_name": "karimov  aziz", "phone": "+998901234567", "email": "bad-email", "birth_date": "1999-02-30", "address": None, "skills": ["Excel", " ", "Farmatsevt"]}) + "\n```"
    r = await hr.post("/api/v1/recruit/candidates/parse", json={"text": text})
    d = r.json()
    assert r.status_code == 200 and d["engine"] == "ai"
    assert d["fields"]["full_name"] == "karimov aziz" and d["fields"]["phone"] == "+998901234567"
    assert "email" not in d["fields"] and "birth_date" not in d["fields"]  # noto'g'ri qiymatlar tashlanadi
    assert d["fields"]["skills"] == ["Excel", "Farmatsevt"]
    assert llm["calls"][0]["user"].startswith("<data>")

    llm["reply"] = "kechirasiz, JSON bera olmadim"
    d = (await hr.post("/api/v1/recruit/candidates/parse", json={"text": text})).json()
    assert d["engine"] == "rules" and d["fields"]["phone"] == "+998901234567"


async def test_ticket_suggest(new_client, llm):
    req, _ = await as_user(new_client, "ali", "farmasevt")
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    printer = (await hr.post(f"{H}/categories", json={"name": "Printer va skaner"})).json()
    llm["reply"] = json.dumps({"title": "Printer chek chiqarmayapti", "category_id": printer["id"], "priority": "urgent"})
    r = await req.post(f"{A}/ticket-suggest", json={"text": "Kassadagi printer ertalabdan beri chek chiqarmayapti"})
    assert r.json()["fields"] == {"title": "Printer chek chiqarmayapti", "category_id": printer["id"], "priority": "urgent"}
    assert f"{printer['id']}: {printer['name']}" in llm["calls"][0]["system"]
    llm["reply"] = json.dumps({"title": "x", "category_id": 99999, "priority": "kritik"})
    assert (await req.post(f"{A}/ticket-suggest", json={"text": "Boshqa muammo haqida uzun matn"})).json()["fields"] == {"title": "x"}


async def test_global_search_respects_permissions(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    ali, ali_id = await as_user(new_client, "ali", "farmasevt")
    bob, _ = await as_user(new_client, "bob", "farmasevt")
    t = await mk_ticket(ali, title="Kassa printeri buzildi")
    await mk_ticket(bob, title="Kassa monitori")
    await hr.post("/api/v1/needs", json={"title": "Kassa uchun qog'oz"})

    def kinds(r):
        return {g["type"]: [i["title"] for i in g["items"]] for g in r.json()["groups"]}

    k = kinds(await hr.get("/api/v1/search", params={"q": "kassa"}))
    assert sorted(k["tickets"]) == ["Kassa monitori", "Kassa printeri buzildi"] and k["needs"] == ["Kassa uchun qog'oz"]
    k = kinds(await ali.get("/api/v1/search", params={"q": "kassa"}))
    assert k["tickets"] == ["Kassa printeri buzildi"] and "needs" not in k and "employees" not in k
    link = next(i["link"] for g in (await ali.get("/api/v1/search", params={"q": "printeri"})).json()["groups"] for i in g["items"])
    assert link == f"/helpdesk/{t['id']}"
    # foydalanuvchi nomi bo'yicha xodim topiladi (faqat employees.read bilan)
    assert (await ali.get("/api/v1/search", params={"q": "zzzz"})).json() == {"q": "zzzz", "total": 0, "groups": []}
    assert (await ali.get("/api/v1/search", params={"q": "k"})).status_code == 422
    # maxsus belgilar literal sifatida qidiriladi
    assert (await hr.get("/api/v1/search", params={"q": "%%"})).json()["total"] == 0
