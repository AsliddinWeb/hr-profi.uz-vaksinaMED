import pytest

from app.db import SessionLocal
from app.models.org import Department, Position
from app.models.recruit import Candidate
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
R = "/api/v1/recruit"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def test_request_flow_dashboard_compare(new_client):
    hr, _ = await as_user(new_client, "hrd", "hr_direktor")
    head, head_id = await as_user(new_client, "bosh", "farmasevt")
    other, _ = await as_user(new_client, "boshqa", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Moliya", head_user_id=head_id)
        p = Position(name="Buxgalter")
        s.add_all([d, p])
        await s.commit()
        did, pid = d.id, p.id
    body = {"department_id": did, "position_id": pid, "count": 2, "reason": "Yangi loyiha"}
    assert (await other.post(f"{R}/requests", json=body)).status_code == 403
    r = (await head.post(f"{R}/requests", json=body)).json()
    assert r["number"].startswith("ZY-") and r["status"] == "pending" and r["can"]["decide"] is False
    assert (await hr.post(f"{R}/requests/{r['id']}/decide", json={"action": "reject"})).json()["detail"]["code"] == "note_required"
    ok = (await hr.post(f"{R}/requests/{r['id']}/decide", json={"action": "approve"})).json()
    assert ok["status"] == "approved" and ok["vacancy_id"]
    vid = ok["vacancy_id"]
    await hr.post(f"{R}/calls", json={"outcome": "suitable", "vacancy_id": vid, "direction": "in"})
    await hr.post(f"{R}/calls", json={"outcome": "unsuitable", "vacancy_id": vid})
    await hr.post(f"{R}/calls", json={"outcome": "no_answer", "vacancy_id": vid})
    dash = (await hr.get(f"{R}/vacancies/{vid}/dashboard")).json()
    assert dash["calls"] == {"in": 1, "out": 2, "screened": 2, "suitable": 1, "no_answer": 1} and dash["vacancy"]["openings"] == 2
    assert dash["request"]["number"] == r["number"] and dash["days"][-1]["in"] == 1
    assert (await head.get(f"{R}/vacancies/{vid}/dashboard")).status_code == 403
    async with SessionLocal() as s:
        cs = [Candidate(full_name=f"Nomzod {i}", phone=f"+99890000000{i}", skills=["Excel"]) for i in range(3)]
        s.add_all(cs)
        await s.commit()
        ids = ",".join(str(c.id) for c in cs)
    cmp = (await hr.get(f"{R}/compare", params={"ids": ids})).json()["items"]
    assert [c["full_name"] for c in cmp] == ["Nomzod 0", "Nomzod 1", "Nomzod 2"]
    assert (await hr.get(f"{R}/compare", params={"ids": str(cs[0].id)})).json()["detail"]["code"] == "compare_count"
