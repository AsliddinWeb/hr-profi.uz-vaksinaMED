from datetime import date, timedelta

import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.org import Branch
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


async def test_segments_crud_dashboard_and_settings(new_client):
    await make_user("hrseg", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrseg")).status_code == 200
    async with SessionLocal() as s:
        b = Branch(name="Seg filial", number=903)
        s.add(b)
        await s.flush()
        s.add_all([
            Employee(last_name="O", first_name="Ofis", full_name="O Ofis", hire_date=date.today() - timedelta(days=50)),
            Employee(last_name="D", first_name="Dori", full_name="D Dori", branch_id=b.id, hire_date=date.today() - timedelta(days=50)),
        ])  # fmt: skip
        await s.commit()
    segs = (await hr.get("/api/v1/segments")).json()
    names = [x["name"] for x in segs]
    assert names[:3] == ["Ofis", "Dorixona", "Hammasi"]
    office = next(x for x in segs if x["scope"] == "office")
    assert office["employees"] >= 1
    new = await hr.post("/api/v1/segments", json={"name": "Ombor", "scope": "office", "sort_order": 9, "color": "#ff8800"})
    assert new.status_code == 201, new.text
    sid = new.json()["id"]
    assert (await hr.put(f"/api/v1/segments/{sid}", json={"name": "Omborxona", "scope": "branch"})).json()["name"] == "Omborxona"
    d = await hr.get(f"/api/v1/segments/{office['id']}/dashboard", params={"start": str(date.today()), "end": str(date.today())})
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["segment"]["id"] == office["id"] and "kpis" in body and "by_position" in body and "top_disciplined" in body
    assert (await hr.delete(f"/api/v1/segments/{sid}")).status_code == 204
    st = (await hr.get("/api/v1/company-settings")).json()
    assert st["values"]["checklists.month_limit"] == 4
    assert (await hr.put("/api/v1/company-settings", json={"checklists.month_limit": 6})).json()["values"]["checklists.month_limit"] == 6
    assert (await hr.put("/api/v1/company-settings", json={"checklists.month_limit": 99})).status_code == 422
    assert (await hr.get("/api/v1/checklists/status/coverage")).json()["limit"] == 6
    await hr.put("/api/v1/company-settings", json={"checklists.month_limit": 4})
    await make_user("farmseg", "farmasevt")
    f = new_client()
    assert (await login(f, "farmseg")).status_code == 200
    assert (await f.post("/api/v1/segments", json={"name": "X"})).status_code == 403
