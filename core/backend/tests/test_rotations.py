from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.rotations import Rotation
from app.services import rotations as svc
from app.timeutil import now
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

RT = "/api/v1/rotations"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


async def setup(new_client):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    hr, _ = await as_user(new_client, "hrm", "hr_menejer")
    aud, _ = await as_user(new_client, "auditor", "hr_auditor")
    m_a, m_a_id = await as_user(new_client, "mudira", "mudir")
    m_b, m_b_id = await as_user(new_client, "mudirb", "mudir")
    stranger, _ = await as_user(new_client, "mudirc", "mudir")
    far, far_uid = await as_user(new_client, "far", "farmasevt")
    a = (await hrd.post("/api/v1/branches", json={"number": 71, "name": "F71", "manager_user_id": m_a_id})).json()
    b = (await hrd.post("/api/v1/branches", json={"number": 72, "name": "F72", "manager_user_id": m_b_id})).json()
    async with SessionLocal() as s:
        e = Employee(last_name="Far", first_name="X", full_name="Far X", user_id=far_uid, status="active", branch_id=a["id"], hire_date=date(2026, 1, 1))
        s.add(e)
        await s.commit()
        emp = e.id
    return {"hrd": hrd, "hr": hr, "aud": aud, "m_a": m_a, "m_b": m_b, "stranger": stranger, "far": far, "a": a["id"], "b": b["id"], "emp": emp}


def body(ctx, start=None, end=None, **kw):
    today = date.today()
    return {"employee_id": ctx["emp"], "to_branch_id": ctx["b"], "start_date": str(start or today), "end_date": str(end or today + timedelta(days=5)), "reason": "Xodim yetishmayapti", **kw}


async def branch_of(emp_id):
    async with SessionLocal() as s:
        return (await s.get(Employee, emp_id)).branch_id


async def test_hr_creates_active_rotation_and_returns(new_client):
    ctx = await setup(new_client)
    r = await ctx["hr"].post(RT, json=body(ctx))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"
    assert await branch_of(ctx["emp"]) == ctx["b"]
    assert any(n["kind"] == "rotation.started" for n in await notes(ctx["far"]))
    assert any(n["kind"] == "rotation.started" for n in await notes(ctx["m_b"]))
    # muddati o'tdi -> job uy filialiga qaytaradi
    async with SessionLocal() as s:
        rot = await s.scalar(select(Rotation))
        rot.end_date = date.today() - timedelta(days=1)
        await s.commit()
    async with SessionLocal() as s:
        await svc.run_due(s, now())
        await s.commit()
    assert await branch_of(ctx["emp"]) == ctx["a"]
    assert (await ctx["hr"].get(f"{RT}/1")).json()["status"] == "completed"


async def test_mudir_request_needs_hr_approval(new_client):
    ctx = await setup(new_client)
    assert (await ctx["stranger"].post(RT, json=body(ctx))).status_code == 403  # boshqa filial mudiri
    assert (await ctx["far"].post(RT, json=body(ctx))).status_code == 403
    r = await ctx["m_a"].post(RT, json=body(ctx))
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert await branch_of(ctx["emp"]) == ctx["a"]
    assert any(n["kind"] == "rotation.requested" for n in await notes(ctx["hr"]))
    assert (await ctx["m_a"].post(f"{RT}/1/decide", json={"action": "approve"})).status_code == 403
    d = await ctx["hr"].post(f"{RT}/1/decide", json={"action": "approve"})
    assert d.status_code == 200 and d.json()["status"] == "active"
    assert await branch_of(ctx["emp"]) == ctx["b"]
    assert (await ctx["hr"].post(f"{RT}/1/decide", json={"action": "reject"})).json()["detail"]["code"] == "already_decided"


async def test_future_rotation_starts_by_job_and_reject(new_client):
    ctx = await setup(new_client)
    start = date.today() + timedelta(days=2)
    r = await ctx["hr"].post(RT, json=body(ctx, start=start, end=start + timedelta(days=3)))
    assert r.json()["status"] == "approved"
    assert await branch_of(ctx["emp"]) == ctx["a"]
    async with SessionLocal() as s:
        rot = await s.scalar(select(Rotation))
        rot.start_date = date.today()
        await s.commit()
    async with SessionLocal() as s:
        await svc.run_due(s, now())
        await s.commit()
    assert await branch_of(ctx["emp"]) == ctx["b"]
    # rad etish
    ctx2 = await setup_second(ctx, new_client)
    rr = await ctx2["m"].post(RT, json={**body(ctx), "employee_id": ctx2["emp"], "to_branch_id": ctx["a"]})
    assert rr.status_code == 201, rr.text
    rid = rr.json()["id"]
    dec = await ctx["hr"].post(f"{RT}/{rid}/decide", json={"action": "reject", "note": "Kerak emas"})
    assert dec.json()["status"] == "rejected"


async def setup_second(ctx, new_client):
    m, m_id = await as_user(new_client, "mudird", "mudir")
    async with SessionLocal() as s:
        from app.models.org import Branch

        b = await s.get(Branch, ctx["b"])
        b.coordinator_user_id = m_id
        await s.commit()
        e = Employee(last_name="Boshqa", first_name="Y", full_name="Boshqa Y", status="active", branch_id=ctx["b"], hire_date=date(2026, 1, 1))
        s.add(e)
        await s.commit()
        return {"m": m, "emp": e.id}


async def test_validation_and_cancel(new_client):
    ctx = await setup(new_client)
    h = ctx["hr"]
    assert (await h.post(RT, json=body(ctx, to_branch_id=ctx["a"]))).json()["detail"]["code"] == "same_branch"
    assert (await h.post(RT, json=body(ctx, start=date.today() + timedelta(days=5), end=date.today()))).json()["detail"]["code"] == "date_range_invalid"
    assert (await h.post(RT, json=body(ctx, to_branch_id=9999))).json()["detail"]["code"] == "unknown_branch"
    assert (await h.post(RT, json={**body(ctx), "reason": "x"})).status_code == 422
    r = await h.post(RT, json=body(ctx))
    assert r.status_code == 201
    assert (await h.post(RT, json=body(ctx))).json()["detail"]["code"] == "rotation_exists"
    c = await h.post(f"{RT}/{r.json()['id']}/cancel")
    assert c.json()["status"] == "cancelled"
    assert await branch_of(ctx["emp"]) == ctx["a"]  # darhol qaytdi
    assert (await h.post(f"{RT}/{r.json()['id']}/cancel")).json()["detail"]["code"] == "already_closed"


async def test_visibility(new_client):
    ctx = await setup(new_client)
    await ctx["hr"].post(RT, json=body(ctx))
    assert len((await ctx["aud"].get(RT)).json()) == 1  # auditor ko'radi
    assert len((await ctx["m_b"].get(RT)).json()) == 1  # qabul qiluvchi filial mudiri
    assert (await ctx["stranger"].get(RT)).json() == []
    assert (await ctx["stranger"].get(f"{RT}/1")).status_code == 404
    assert (await ctx["far"].get(RT)).status_code == 403  # farmasevtda rotations.* yo'q


async def test_branch_options_for_lead(new_client):
    ctx = await setup(new_client)
    r = await ctx["m_a"].get(f"{RT}/branches")
    assert r.status_code == 200
    assert {b["name"] for b in r.json()} >= {"F71", "F72"}
    assert (await ctx["far"].get(f"{RT}/branches")).status_code == 403
