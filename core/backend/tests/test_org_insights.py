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


async def test_org_scheme_hierarchy_slots_template(new_client):
    await make_user("hrs", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrs")).status_code == 200
    did = (await hr.post("/api/v1/org/departments", json={"name": "Marketing", "yqm": "Ko'p mijoz", "create_default_positions": False})).json()["id"]
    head = (await hr.post("/api/v1/org/positions", json={"name": "Marketing boshlig'i", "department_id": did, "is_head": True})).json()["id"]
    smm = (await hr.post("/api/v1/org/positions", json={"name": "SMM", "department_id": did, "parent_id": head, "slots": 3, "yqm": "Faol kontent"})).json()["id"]
    # aylana bo'ysunish taqiqlanadi
    assert (await hr.patch(f"/api/v1/org/positions/{head}", json={"parent_id": smm})).json()["detail"]["code"] == "position_cycle"
    async with SessionLocal() as s:
        s.add(Employee(last_name="Smm", first_name="Vali", full_name="Smm Vali", department_id=did, position_id=smm, hire_date=date.today()))
        await s.commit()
    sc = (await hr.get("/api/v1/org/scheme")).json()
    node = next(d for d in sc["departments"] if d["id"] == did)
    assert node["yqm"] == "Ko'p mijoz" and node["headcount"] == 1
    pos = {p["id"]: p for p in sc["positions"]}
    assert pos[head]["is_head"] and pos[smm]["parent_id"] == head and pos[smm]["slots"] == 3 and pos[smm]["occupants"][0]["full_name"] == "Smm Vali"
    # yangi bo'limning standart lavozimlari ham shajaraga bog'lanadi
    d2 = (await hr.post("/api/v1/org/departments", json={"name": "Sifat"})).json()["id"]
    ps = [p for p in (await hr.get("/api/v1/org/positions", params={"department_id": d2})).json()]
    heads = [p for p in ps if p["is_head"]]
    assert len(heads) == 1 and all(p["parent_id"] == heads[0]["id"] for p in ps if not p["is_head"])
    # bo'lim boshqa bo'lim lavozimi ostida chiziladi
    assert (await hr.patch(f"/api/v1/org/departments/{d2}", json={"reports_to_position_id": head})).status_code == 200
    assert next(d for d in (await hr.get("/api/v1/org/scheme")).json()["departments"] if d["id"] == d2)["reports_to_position_id"] == head


async def test_org_template_apply_is_idempotent():
    from app.services.org_template import VAKSINA_ORG, apply_org_template

    async with SessionLocal() as s:
        first = await apply_org_template(s)
        await s.commit()
    async with SessionLocal() as s:
        second = await apply_org_template(s)
        await s.commit()
        assert first["departments"] == len(VAKSINA_ORG) and second == {"departments": 0, "positions": 0}
        from sqlalchemy import select

        shafyor = await s.scalar(select(Position).where(Position.name == "Shafyor"))
        boss = await s.get(Position, shafyor.parent_id)
        moliya = await s.scalar(select(Department).where(Department.name == "Moliya bo'limi"))
        tasischi = await s.get(Position, moliya.reports_to_position_id)
        assert shafyor.slots == 24 and boss.name == "Logistika va mexanik boshlig'i" and boss.is_head and tasischi.name == "Ta'sischi"
