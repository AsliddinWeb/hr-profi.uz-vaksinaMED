import pytest

from app.db import SessionLocal
from app.models.org import Department
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
R = "/api/v1/org/goals"
Y = 2026


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


def goal(**kw):
    return {"title": "Savdoni oshirish", "metric": "Oylik savdo", "unit": "mln so'm", "baseline": 800, "target": 1000, "deadline": f"{Y}-12-31", **kw}


async def test_goals_lifecycle(new_client):
    boss, _ = await as_user(new_client, "boss", "tasischi")
    head, head_uid = await as_user(new_client, "head", "farmasevt")
    other, _ = await as_user(new_client, "other", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Savdo", head_user_id=head_uid, yqm="Sotilgan mahsulot")
        s.add(d)
        await s.commit()
        dept = d.id
    url = f"{R}/departments/{dept}?year={Y}"

    assert (await other.post(url, json=goal())).status_code == 403
    assert (await head.post(url, json=goal(deadline="2027-01-10"))).json()["detail"]["code"] == "deadline_year"
    gid = (await head.post(url, json=goal())).json()["id"]
    gid2 = (await head.post(url, json=goal(title="Kadrlar qo'nimsizligi", metric="Ketganlar", baseline=20, target=10))).json()["id"]
    assert (await head.put(f"{R}/items/{gid2}", json=goal(title="Qo'nimsizlikni kamaytirish", metric="Ketganlar %", baseline=20, target=10))).status_code == 200

    assert (await head.post(f"{R}/departments/{dept}/submit?year={Y}")).json()["status"] == "pending"
    assert (await head.post(f"{R}/departments/{dept}/approve?year={Y}")).status_code == 403
    assert (await boss.post(f"{R}/departments/{dept}/return?year={Y}", json={"note": "Muddatni aniqlang"})).json()["status"] == "draft"
    assert (await head.post(f"{R}/departments/{dept}/submit?year={Y}")).status_code == 200
    assert (await boss.post(f"{R}/departments/{dept}/approve?year={Y}")).json()["status"] == "approved"
    assert (await head.post(url, json=goal())).json()["detail"]["code"] == "plan_locked"
    assert (await head.put(f"{R}/items/{gid}", json=goal(target=2000))).status_code == 409
    assert (await head.delete(f"{R}/items/{gid}")).status_code == 409

    assert (await head.put(f"{R}/items/{gid}/progress", json={"current": 900})).json()["progress"] == 50
    assert (await head.put(f"{R}/items/{gid2}/progress", json={"current": 15})).json()["progress"] == 50

    ch = (await head.post(f"{R}/departments/{dept}/changes?year={Y}", json={"action": "update", "goal_id": gid, "values": goal(target=1200), "reason": "Yangi filial ochildi"})).json()["id"]
    assert (await head.post(f"{R}/departments/{dept}/changes?year={Y}", json={"action": "remove", "goal_id": gid, "reason": "Takror"})).json()["detail"]["code"] == "change_pending"
    assert (await head.post(f"{R}/changes/{ch}/decide", json={"approve": True})).status_code == 403
    assert (await boss.post(f"{R}/changes/{ch}/decide", json={"approve": True})).json()["status"] == "approved"
    assert (await boss.post(f"{R}/changes/{ch}/decide", json={"approve": True})).status_code == 409
    rm = (await head.post(f"{R}/departments/{dept}/changes?year={Y}", json={"action": "remove", "goal_id": gid2, "reason": "Bo'lim qayta tuzildi"})).json()["id"]
    assert (await boss.post(f"{R}/changes/{rm}/decide", json={"approve": False, "note": "Kerak"})).json()["status"] == "rejected"
    add = (await head.post(f"{R}/departments/{dept}/changes?year={Y}", json={"action": "add", "values": goal(title="Yangi maqsad"), "reason": "Investor talabi"})).json()["id"]
    assert (await boss.post(f"{R}/changes/{add}/decide", json={"approve": True})).json()["goal_id"]

    data = (await boss.get(url)).json()
    assert data["plan"]["status"] == "approved" and data["department"]["yqm"] == "Sotilgan mahsulot"
    by_id = {g["id"]: g for g in data["goals"]}
    assert by_id[gid]["target"] == 1200 and by_id[gid]["progress"] == 25
    assert len(data["goals"]) == 3
    assert [c["status"] for c in data["changes"]] == ["approved", "rejected", "approved"]
    assert data["changes"][-1]["before"]["target"] == 1000

    ov = (await boss.get(f"{R}?year={Y}")).json()
    row = next(r for r in ov["departments"] if r["id"] == dept)
    assert row["status"] == "approved" and row["goals"] == 3 and row["pending_changes"] == 0 and ov["can_approve"]


async def test_submit_requires_goals(new_client):
    hr, _ = await as_user(new_client, "hrg", "hr_direktor")
    async with SessionLocal() as s:
        d = Department(name="Moliya")
        s.add(d)
        await s.commit()
        dept = d.id
    gid = (await hr.post(f"{R}/departments/{dept}?year={Y}", json=goal())).json()["id"]
    assert (await hr.delete(f"{R}/items/{gid}")).status_code == 204
    assert (await hr.post(f"{R}/departments/{dept}/submit?year={Y}")).json()["detail"]["code"] == "no_goals"
    assert (await hr.put(f"{R}/items/{gid}/progress", json={"current": 1})).status_code == 404


async def test_goal_tasks_and_ranking(new_client):
    boss, _ = await as_user(new_client, "boss2", "tasischi")
    head, head_uid = await as_user(new_client, "head2", "farmasevt")
    other, _ = await as_user(new_client, "other2", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Marketing", head_user_id=head_uid)
        s.add(d)
        await s.commit()
        dept = d.id
    gid = (await head.post(f"{R}/departments/{dept}?year={Y}", json=goal())).json()["id"]

    assert (await other.post(f"{R}/items/{gid}/tasks", json={"title": "Kontent reja"})).status_code == 403
    t1 = (await head.post(f"{R}/items/{gid}/tasks", json={"title": "Kontent reja", "due_date": f"{Y}-03-01"})).json()["id"]
    t2 = (await head.post(f"{R}/items/{gid}/tasks", json={"title": "Hamkorlar bilan uchrashuv", "owner_user_id": head_uid})).json()["id"]
    assert (await head.put(f"{R}/tasks/{t1}/progress", json={"progress": 80})).json()["progress"] == 80
    assert (await head.put(f"{R}/tasks/{t2}/progress", json={"progress": 40})).status_code == 200
    assert (await head.put(f"{R}/tasks/{t2}/progress", json={"progress": 140})).status_code == 422

    g = (await boss.get(f"{R}/departments/{dept}?year={Y}")).json()["goals"][0]
    assert [t["title"] for t in g["tasks"]] == ["Kontent reja", "Hamkorlar bilan uchrashuv"]
    assert g["task_progress"] == 60 and g["progress"] is None and g["effective_progress"] == 60
    row = next(r for r in (await boss.get(f"{R}?year={Y}")).json()["departments"] if r["id"] == dept)
    assert row["progress"] == 60 and row["tasks"] == 2

    assert (await other.delete(f"{R}/tasks/{t2}")).status_code == 403
    assert (await head.delete(f"{R}/tasks/{t2}")).status_code == 204
    assert (await boss.get(f"{R}/departments/{dept}?year={Y}")).json()["goals"][0]["task_progress"] == 80


async def test_strategy_swot(new_client):
    boss, _ = await as_user(new_client, "boss3", "tasischi")
    emp, _ = await as_user(new_client, "emp3", "farmasevt")
    empty = (await boss.get(f"{R}/strategy?year={Y}")).json()
    assert empty["strengths"] == [] and empty["can_edit"]
    body = {"strengths": ["Kuchli brend", "  "], "weaknesses": ["Kam filial"], "opportunities": [], "threats": ["Raqobat"]}
    assert (await emp.put(f"{R}/strategy?year={Y}", json=body)).status_code == 403
    saved = (await boss.put(f"{R}/strategy?year={Y}", json=body)).json()
    assert saved["strengths"] == ["Kuchli brend"] and saved["threats"] == ["Raqobat"]
    assert (await boss.put(f"{R}/strategy?year={Y}", json={**body, "opportunities": ["Yangi hudud"]})).json()["opportunities"] == ["Yangi hudud"]
    assert (await boss.get(f"{R}/strategy?year={Y + 1}")).json()["weaknesses"] == []
