from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch
from app.timeutil import now
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


async def test_revision_flow(new_client):
    await make_user("hrr", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrr")).status_code == 200
    async with SessionLocal() as s:
        b = Branch(name="Rev filial", number=901)
        s.add(b)
        await s.commit()
        bid = b.id
        me = await s.scalar(select(User.id).where(User.login == "hrr"))
    r = (await hr.get("/api/v1/revisions/branches")).json()
    assert next(i for i in r["items"] if i["id"] == bid)["status"] == "never"
    t = await hr.post("/api/v1/revisions/tasks", json={"branch_id": bid, "revizor_user_id": me, "planned_date": str(date.today()), "kind": "cycle"})
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    assert (await hr.post("/api/v1/revisions/tasks", json={"branch_id": bid, "revizor_user_id": me, "planned_date": str(date.today())})).status_code == 409
    assert (await hr.get("/api/v1/revisions/tasks")).json()["counts"]["today"] == 1
    assert (await hr.post(f"/api/v1/revisions/tasks/{tid}/start")).json()["status"] == "in_progress"
    sub = await hr.post(f"/api/v1/revisions/tasks/{tid}/submit", json={"result_note": "ok", "shortage_amount": 15000, "score": 92})
    assert sub.json()["status"] == "review"
    assert (await hr.post(f"/api/v1/revisions/tasks/{tid}/approve", json={"note": "rahmat"})).json()["status"] == "done"
    item = next(i for i in (await hr.get("/api/v1/revisions/branches")).json()["items"] if i["id"] == bid)
    assert item["status"] == "on_plan" and item["days_left"] == 90
    cal = (await hr.get("/api/v1/revisions/calendar", params={"month": date.today().strftime("%Y-%m")})).json()
    assert any(i["id"] == tid for i in cal["items"])

    await make_user("farm1", "farmasevt")
    f = new_client()
    assert (await login(f, "farm1")).status_code == 200
    assert (await f.get("/api/v1/revisions/branches")).status_code == 403


async def test_ratings_flow(new_client):
    await make_user("hrq", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrq")).status_code == 200
    async with SessionLocal() as s:
        b = Branch(name="Baho filial", number=902)
        s.add(b)
        await s.flush()
        e = Employee(last_name="S", first_name="Smena", full_name="S Smena", branch_id=b.id, hire_date=date.today() - timedelta(days=10))
        s.add(e)
        await s.flush()
        s.add(AttendanceRecord(employee_id=e.id, work_date=date.today(), branch_id=b.id, check_in_at=now() - timedelta(hours=1), in_method="qr"))
        await s.commit()
        bid, eid = b.id, e.id
    q = await hr.post(f"/api/v1/ratings/qr/{bid}/create")
    assert q.status_code == 200, q.text
    token = q.json()["url"].rsplit("/", 1)[1]
    assert (await hr.get(f"/api/v1/ratings/qr/{bid}/svg")).headers["content-type"].startswith("image/svg")
    pub = new_client()
    page = (await pub.get(f"/api/v1/public/rate/{token}")).json()
    assert page["branch"].endswith("Baho filial") and page["staff"][0]["id"] == eid
    ok = await pub.post(f"/api/v1/public/rate/{token}", json={"target": "pharmacy", "stars": 1, "cleanliness": 3, "assortment": 4, "comment": "sekin", "name": "Ali Vali", "phone": "+998901234567"})
    assert ok.status_code == 201, ok.text
    assert (await pub.post(f"/api/v1/public/rate/{token}", json={"target": "pharmacy", "stars": 5, "cleanliness": 5, "assortment": 5, "name": "Ali Vali", "phone": "+998901234567"})).status_code == 429
    assert (await pub.post(f"/api/v1/public/rate/{token}", json={"target": "employee", "employee_id": eid, "stars": 5, "name": "Ali Vali", "phone": "+998901234567"})).status_code == 201
    lst = (await hr.get("/api/v1/ratings", params={"target": "pharmacy", "branch_id": bid})).json()
    assert lst["count"] == 1 and lst["low"] == 1 and lst["items"][0]["cleanliness"] == "Qoniqarli" and lst["items"][0]["customer"]["phone"] == "+998901234567"
    st = (await hr.get("/api/v1/ratings/stats", params={"branch_id": bid})).json()
    assert st["total"] == 2 and st["complaints"] == 1 and st["employees"][0]["id"] == eid
    assert (await hr.get("/api/v1/ratings/export")).status_code == 200
    rot = (await hr.post(f"/api/v1/ratings/qr/{bid}/rotate")).json()
    assert rot["version"] == 2 and (await pub.get(f"/api/v1/public/rate/{token}")).status_code == 404
