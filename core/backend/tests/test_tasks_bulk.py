from datetime import date

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.notifications import NotificationPref
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

T = "/api/v1/tasks"
N = "/api/v1/notifications"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c, **params):
    return (await c.get(N, params=params)).json()["items"]


async def setup(new_client):
    hrd, hrd_id = await as_user(new_client, "hrd", "hr_direktor")
    mudir, mudir_id = await as_user(new_client, "mudir", "mudir")
    a, a_id = await as_user(new_client, "ali", "farmasevt")
    b, b_id = await as_user(new_client, "vali", "farmasevt")
    c, c_id = await as_user(new_client, "gani", "farmasevt")
    d1 = (await hrd.post("/api/v1/org/departments", json={"name": "Dorixona"})).json()
    d2 = (await hrd.post("/api/v1/org/departments", json={"name": "Ofis"})).json()
    async with SessionLocal() as s:
        s.add_all([
            Employee(last_name="A", first_name="Ali", full_name="A Ali", user_id=a_id, status="active", department_id=d1["id"], hire_date=date(2026, 1, 1)),
            Employee(last_name="V", first_name="Vali", full_name="V Vali", user_id=b_id, status="active", department_id=d1["id"], hire_date=date(2026, 1, 1)),
            Employee(last_name="G", first_name="Gani", full_name="G Gani", user_id=c_id, status="active", department_id=d2["id"], hire_date=date(2026, 1, 1)),
        ])
        await s.commit()
    return {"hrd": hrd, "hrd_id": hrd_id, "mudir": mudir, "a": a, "a_id": a_id, "b": b, "b_id": b_id, "c": c, "c_id": c_id, "d1": d1["id"], "d2": d2["id"]}


async def test_audience_preview_and_bulk_by_department(new_client):
    ctx = await setup(new_client)
    assert (await ctx["a"].get(f"{T}/audience", params={"department_id": ctx["d1"]})).status_code == 403  # farmasevt boshqalarga bera olmaydi
    pv = (await ctx["hrd"].get(f"{T}/audience", params={"department_id": ctx["d1"]})).json()
    assert pv["count"] == 2 and {p["name"] for p in pv["people"]} == {"Ali", "Vali"}
    assert (await ctx["hrd"].get(f"{T}/audience")).json() == {"count": 0, "people": []}
    r = await ctx["hrd"].post(f"{T}/bulk", json={"title": "Narxlarni yangilang", "department_id": ctx["d1"], "priority": "high"})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["created"] == 2 and len(j["task_ids"]) == 2 and j["batch_id"]
    # har biriga alohida topshiriq va bildirishnoma
    first = await ctx["hrd"].get(f"{T}/{j['task_ids'][0]}")
    t1 = first.json()
    assert t1["step"] == "new" and t1["batch_id"] == j["batch_id"]
    assert any(n["kind"] == "tasks.assigned" for n in await notes(ctx["a"])) and any(n["kind"] == "tasks.assigned" for n in await notes(ctx["b"]))
    assert not any(n["kind"] == "tasks.assigned" for n in await notes(ctx["c"]))  # boshqa bo'lim
    # ijrochilar ro'yxati + filtr birga, takrorlanmaydi
    r2 = await ctx["hrd"].post(f"{T}/bulk", json={"title": "Aralash", "assignee_ids": [ctx["a_id"], ctx["c_id"]], "department_id": ctx["d1"]})
    assert r2.json()["created"] == 3  # ali, gani + vali (ali takrorlanmadi)
    assert (await ctx["hrd"].post(f"{T}/bulk", json={"title": "Bo'sh"})).json()["detail"]["code"] == "no_assignees"
    assert (await ctx["a"].post(f"{T}/bulk", json={"title": "x", "assignee_ids": [ctx["b_id"]]})).status_code == 403
    assert (await ctx["hrd"].post(f"{T}/bulk", json={"title": "x", "assignee_ids": [99999]})).json()["detail"]["code"] == "unknown_user"


async def test_accept_chain_and_batch_progress(new_client):
    ctx = await setup(new_client)
    j = (await ctx["hrd"].post(f"{T}/bulk", json={"title": "Hisobot", "assignee_ids": [ctx["a_id"], ctx["b_id"]]})).json()
    ids = j["task_ids"]
    # ali o'z topshirig'ini topadi
    ta = None
    for tid in ids:
        r = await ctx["a"].get(f"{T}/{tid}")
        if r.status_code == 200 and r.json()["assignee"]["id"] == ctx["a_id"]:
            ta = r.json()
    assert ta and ta["step"] == "new" and ta["accepted_at"] is None
    assert (await ctx["b"].post(f"{T}/{ta['id']}/accept")).status_code in (403, 404)  # boshqaning topshirig'ini qabul qila olmaydi
    ac = await ctx["a"].post(f"{T}/{ta['id']}/accept")
    assert ac.status_code == 200 and ac.json()["step"] == "accepted" and ac.json()["accepted_at"]
    assert any(n["kind"] == "tasks.accepted" for n in await notes(ctx["hrd"]))
    assert (await ctx["hrd"].get(f"{T}/{ta['id']}")).json()["step"] == "accepted"
    mv = await ctx["a"].post(f"{T}/{ta['id']}/move", json={"status": "in_progress"})
    assert mv.json()["step"] == "in_progress"
    assert (await ctx["a"].post(f"{T}/{ta['id']}/accept")).json()["detail"]["code"] == "cannot_accept"
    # guruh progressi faqat yaratuvchiga
    bt = (await ctx["hrd"].get(f"{T}/{ta['id']}/batch")).json()
    assert bt["total"] == 2 and bt["by_step"] == {"in_progress": 1, "new": 1} and len(bt["items"]) == 2
    assert (await ctx["a"].get(f"{T}/{ta['id']}/batch")).json()["total"] == 0


async def test_notification_prefs_and_categories(new_client):
    ctx = await setup(new_client)
    pr = (await ctx["a"].get(f"{N}/preferences")).json()["categories"]
    cats = {c["key"]: c for c in pr}
    assert cats["tasks"]["mandatory"] is False and cats["tasks"]["muted"] is False
    assert cats["answers"]["mandatory"] is True and cats["security"]["mandatory"] is True
    # tasks toifasini o'chirish; majburiy toifa o'chmaydi
    assert (await ctx["a"].put(f"{N}/preferences", json={"muted": ["tasks", "answers", "yoq"]})).status_code == 204
    cats = {c["key"]: c for c in (await ctx["a"].get(f"{N}/preferences")).json()["categories"]}
    assert cats["tasks"]["muted"] is True and cats["answers"]["muted"] is False
    async with SessionLocal() as s:
        assert (await s.scalar(select(NotificationPref).where(NotificationPref.user_id == ctx["a_id"]))).muted == ["tasks"]
    await ctx["hrd"].post(f"{T}/bulk", json={"title": "Sinov", "assignee_ids": [ctx["a_id"], ctx["b_id"]]})
    assert not any(n["kind"] == "tasks.assigned" for n in await notes(ctx["a"]))  # o'chirilgan
    assert any(n["kind"] == "tasks.assigned" for n in await notes(ctx["b"]))
    # toifa filtri
    got = await notes(ctx["b"], category="tasks")
    assert got and all(n["kind"].startswith("tasks.") for n in got)
    assert await notes(ctx["b"], category="needs") == []
    assert (await ctx["b"].get(f"{N}", params={"category": "Bad!"})).status_code == 422
