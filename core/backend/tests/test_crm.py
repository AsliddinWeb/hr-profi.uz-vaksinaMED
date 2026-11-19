from datetime import timedelta

import pytest

from app.db import SessionLocal
from app.services.crm import check_overdue
from app.timeutil import local_date, now
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
R = "/api/v1/crm"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def test_crm_pipeline_automation(new_client):
    boss, boss_id = await as_user(new_client, "crmboss", "tasischi")
    hr, hr_id = await as_user(new_client, "crmhr", "hr_direktor")
    outsider, _ = await as_user(new_client, "crmout", "farmasevt")

    assert (await outsider.get(f"{R}/board")).status_code == 403
    stages = (await boss.get(f"{R}/stages")).json()
    assert [s["name"] for s in stages][:2] == ["Yangi", "Malakali"]
    won = next(s for s in stages if s["is_won"])

    # Yaratish: birinchi bosqich, ehtimollik bosqichdan, avtomatik faoliyat (mas'ul = ega)
    did = (await boss.post(f"{R}/deals", json={"title": "Silk Road — POS", "company": "Silk Road", "amount": 20_000_000, "owner_id": hr_id, "tags": ["Demo"]})).json()["id"]
    d = (await hr.get(f"{R}/deals/{did}")).json()
    assert d["stage_id"] == stages[0]["id"] and d["probability"] == 10 and d["owner"]["id"] == hr_id
    feed = (await hr.get(f"{R}/deals/{did}/feed")).json()
    assert len(feed["planned"]) == 1 and feed["planned"][0]["auto"] and feed["planned"][0]["assignee"]["id"] == hr_id

    # Kanbanda ko'chirish: yangi bosqich ehtimolligi + yangi avtomatik faoliyat + tarix yozuvi
    r = (await hr.post(f"{R}/deals/{did}/move", json={"stage_id": stages[1]["id"]})).json()
    assert r["probability"] == 30
    feed = (await hr.get(f"{R}/deals/{did}/feed")).json()
    assert len(feed["planned"]) == 2
    assert any(i["kind"] == "event" and i["data"]["action"] == "stage" and i["data"]["to"] == "Malakali" for i in feed["items"])

    # O'ng panel: xabar va eslatma; faoliyatni bajarib, keyingisini rejalashtirish
    assert (await hr.post(f"{R}/deals/{did}/messages", json={"kind": "note", "body": "Direktor bilan gaplashildi"})).status_code == 201
    aid = feed["planned"][0]["id"]
    tomorrow = (local_date(now()) + timedelta(days=1)).isoformat()
    assert (await hr.post(f"{R}/activities/{aid}/done", json={"result": "Ko'tarmadi", "next": {"kind": "call", "title": "Qayta qo'ng'iroq", "due_date": tomorrow}})).status_code == 200
    feed = (await hr.get(f"{R}/deals/{did}/feed")).json()
    assert {p["title"] for p in feed["planned"]} >= {"Qayta qo'ng'iroq"}
    assert any(i["kind"] == "note" for i in feed["items"])

    # Maydon o'zgarishi tarixga tushadi
    assert (await hr.put(f"{R}/deals/{did}", json={"title": "Silk Road — POS", "company": "Silk Road", "amount": 25_000_000, "owner_id": hr_id, "tags": ["Demo"]})).status_code == 200
    feed = (await hr.get(f"{R}/deals/{did}/feed")).json()
    assert any(i["kind"] == "event" and i["data"]["action"] == "updated" and "amount" in i["data"]["fields"] for i in feed["items"])

    # Muddati o'tgan faoliyat: worker bir marta xabar beradi
    yesterday = (local_date(now()) - timedelta(days=1)).isoformat()
    assert (await hr.post(f"{R}/deals/{did}/activities", json={"kind": "meeting", "title": "Uchrashuv", "due_date": yesterday})).status_code == 201
    async with SessionLocal() as s:
        n1, _ = await check_overdue(s, now())
        await s.commit()
    async with SessionLocal() as s:
        n2, _ = await check_overdue(s, now())
        await s.commit()
    assert n1 >= 1 and n2 == 0
    board = (await hr.get(f"{R}/board")).json()
    card = next(c for col in board["stages"] for c in col["deals"] if c["id"] == did)
    assert card["next_activity"]["state"] == "overdue"

    # Yutildi: yutilgan bosqich, avtomatik faoliyatlar yopiladi; hisobotda ko'rinadi
    assert (await hr.post(f"{R}/deals/{did}/won")).json()["stage_id"] == won["id"]
    st = (await boss.get(f"{R}/stats")).json()
    assert st["won"] >= 1 and st["won_amount"] >= 25_000_000

    # Yo'qotish va qayta ochish
    did2 = (await hr.post(f"{R}/deals", json={"title": "Orient Pharm"})).json()["id"]
    assert (await hr.post(f"{R}/deals/{did2}/lost", json={"reason": "Narx qimmat"})).status_code == 200
    assert not (await hr.get(f"{R}/deals/{did2}/feed")).json()["planned"]
    assert all(c["id"] != did2 for col in (await hr.get(f"{R}/board")).json()["stages"] for c in col["deals"])
    assert (await hr.post(f"{R}/deals/{did2}/reopen")).status_code == 200
    assert (await hr.get(f"{R}/deals/{did2}/feed")).json()["planned"]
    assert boss_id
