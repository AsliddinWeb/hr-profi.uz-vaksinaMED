from datetime import date, timedelta

import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.org import Department, Position
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


async def test_org_insights_positions_archive_analytics(new_client):
    await make_user("hrx", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrx")).status_code == 200
    today = date.today()
    async with SessionLocal() as s:
        d = Department(name="Sotuv")
        s.add(d)
        await s.flush()
        p1, p2 = Position(name="Sotuvchi", department_id=d.id), Position(name="Kassir", department_id=None)
        s.add_all([p1, p2])
        await s.flush()
        s.add_all([
            Employee(last_name="A", first_name="Bir", full_name="A Bir", department_id=d.id, position_id=p1.id, hire_date=today - timedelta(days=20), gender="f"),
            Employee(last_name="B", first_name="Ikki", full_name="B Ikki", department_id=d.id, position_id=p2.id, hire_date=today - timedelta(days=800), gender="m"),
            Employee(last_name="C", first_name="Uch", full_name="C Uch", department_id=d.id, position_id=p1.id, hire_date=today - timedelta(days=400), status="dismissed", dismissal_date=today - timedelta(days=10), dismissal_reason="own_will"),
        ])  # fmt: skip
        await s.commit()
        did = d.id
    r = (await hr.get("/api/v1/org/insights", params={"department_id": did})).json()
    assert r["headcount"] == 2 and r["newcomers_count"] == 1 and r["leavers_count"] == 1
    pos = {p["name"]: p for p in r["positions"]}
    assert pos["Sotuvchi"]["count"] == 1 and pos["Kassir"]["general"] and pos["Kassir"]["count"] == 1
    assert r["analytics"]["left_12m"] == 1 and r["analytics"]["hired_12m"] >= 1 and r["leavers"][0]["dismissal_reason"] == "own_will"
    tree = (await hr.get("/api/v1/org/tree")).json()
    assert next(n for n in tree["roots"] if n["id"] == did)["employees"] == 2
    assert (await hr.get("/api/v1/org/insights", params={"department_id": 999999})).status_code == 404


async def test_org_scheme_yqm_head_and_vacancy(new_client):
    await make_user("hrs", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrs")).status_code == 200
    d = (await hr.post("/api/v1/org/departments", json={"name": "Marketing", "yqm": "Ko'p mijoz", "create_default_positions": False})).json()
    did = d["id"]
    head_pos = (await hr.post("/api/v1/org/positions", json={"name": "Bo'lim boshlig'i", "department_id": did})).json()["id"]
    smm = (await hr.post("/api/v1/org/positions", json={"name": "SMM", "department_id": did, "yqm": "Faol kontent"})).json()["id"]
    await hr.post("/api/v1/org/positions", json={"name": "Brending", "department_id": did})
    async with SessionLocal() as s:
        s.add_all([
            Employee(last_name="Bosh", first_name="Ali", full_name="Bosh Ali", department_id=did, position_id=head_pos, hire_date=date.today()),
            Employee(last_name="Smm", first_name="Vali", full_name="Smm Vali", department_id=did, position_id=smm, hire_date=date.today()),
        ])  # fmt: skip
        await s.commit()
    sc = (await hr.get("/api/v1/org/scheme")).json()
    node = next(n for n in sc["departments"] if n["id"] == did)
    assert node["yqm"] == "Ko'p mijoz" and node["head"]["full_name"] == "Bosh Ali"
    rows = {p["name"]: p for p in node["positions"]}
    assert "Bo'lim boshlig'i" not in rows and rows["SMM"]["yqm"] == "Faol kontent"
    assert rows["SMM"]["occupants"][0]["full_name"] == "Smm Vali" and rows["Brending"]["occupants"] == []
    assert (await hr.patch(f"/api/v1/org/positions/{smm}", json={"yqm": "Yangi"})).status_code == 200
    assert next(p for p in (await hr.get("/api/v1/org/positions", params={"department_id": did})).json() if p["id"] == smm)["yqm"] == "Yangi"
