import pytest

from app.db import SessionLocal
from app.models.org import Department, Position
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
R = "/api/v1/recruit"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


FULL = {
    "general": {"title": "Marketing menejeri"}, "goal": "Brendni rivojlantirish", "functions": ["Kampaniyalar"],
    "education": {"level": "Oliy"}, "kpi": [{"name": "Lead", "target": "100"}], "portrait": "Faol, kreativ",
}


async def test_profile_required_before_request(new_client):
    hr, _ = await as_user(new_client, "hrd", "hr_direktor")
    head, head_id = await as_user(new_client, "bosh", "farmasevt")
    far, _ = await as_user(new_client, "far", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Marketing", head_user_id=head_id)
        p = Position(name="Marketing menejeri")
        s.add_all([d, p])
        await s.commit()
        did, pid = d.id, p.id
    assert (await far.post(f"{R}/competencies", json={"name": "SQL", "category": "hard"})).status_code == 403
    ids = {}
    for name, cat in (("Raqamli marketing", "hard"), ("Muloqot", "soft"), ("Jamoa boshqaruvi", "management")):
        r = await hr.post(f"{R}/competencies", json={"name": name, "category": cat})
        assert r.status_code == 201, r.text
        ids[cat] = r.json()["id"]
    assert (await hr.post(f"{R}/competencies", json={"name": "muloqot", "category": "soft"})).status_code == 409
    lst = (await hr.get(f"{R}/competencies", params={"category": "hard"})).json()
    assert lst["counts"]["hard"] == 1 and lst["counts"]["soft"] == 1 and lst["total"] == 1

    # profil yo'q -> zayafka bloklanadi
    body = {"department_id": did, "position_id": pid, "count": 1}
    assert (await head.post(f"{R}/requests", json=body)).json()["detail"]["code"] == "profile_not_approved"

    prof = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    assert prof["status"] == "draft" and prof["version"] == 1 and prof["can"]["edit"]
    comps = [{"competency_id": i, "required_level": 3, "ideal_level": 4} for i in ids.values()]
    half = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": {"goal": "x"}, "competencies": comps[:1]})).json()
    assert 0 < half["filled_pct"] < 100
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "submit"})).json()["detail"]["code"] == "profile_incomplete"
    full = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": FULL, "competencies": comps})).json()
    assert full["filled_pct"] == 100 and len(full["competencies"]) == 3
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "submit"})).json()["status"] == "pending"
    ap = (await hr.get(f"{R}/approvals")).json()
    assert ap["counts"]["profile"] == 1 and ap["items"][0]["code"] == f"PP-{prof['id']:03d}"
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "return"})).json()["detail"]["code"] == "note_required"
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "approve"})).json()["status"] == "approved"

    got = (await head.get(f"{R}/profiles/approved/{pid}")).json()
    assert got["profile"]["version"] == 1 and got["required"] is True
    r = await head.post(f"{R}/requests", json=body)
    assert r.status_code == 201, r.text
    dash = (await hr.get(f"{R}/competency-dashboard")).json()
    assert dash["approved"] == 1 and dash["competencies"] == 3 and dash["pending_requests"] == 1
    # yangi versiya oldingidan nusxa
    v2 = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    assert v2["version"] == 2 and len(v2["competencies"]) == 3
    lst = (await hr.get(f"{R}/profiles")).json()["items"]
    assert any(i["position"]["id"] == pid and i["profile"]["version"] == 2 for i in lst)


async def test_overview(new_client):
    hr, _ = await as_user(new_client, "hrov", "hr_direktor")
    r = await hr.get(f"{R}/overview", params={"days": 30})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["dynamics"]) == 6 and d["funnel"][0]["stage"] == "requests" and "deltas" in d


async def test_funnel_report(new_client):
    hr, _ = await as_user(new_client, "hrfr", "hr_direktor")
    r = await hr.get(f"{R}/funnel-report", params={"days": 90})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [s["stage"] for s in d["stages"]] == ["requests", "vacancies", "found", "screening", "interview", "test", "offer", "hired"]
    assert set(d["kpi"]) == {"candidates", "hired", "conversion", "avg_close_days"}
