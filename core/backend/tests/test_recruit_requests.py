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


async def test_auto_links_jobs_anketa_daily_dossier(new_client, monkeypatch):
    from sqlalchemy import select

    from app.config import get_settings
    from app.models.employees import Employee
    from app.models.notifications import Notification
    from app.models.recruit import Application

    monkeypatch.setattr(get_settings(), "public_url", "https://hr.test")
    hr, _ = await as_user(new_client, "hrd2", "hr_direktor")
    head, head_id = await as_user(new_client, "bosh2", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Dorixona", head_user_id=head_id)
        p = Position(name="Farmatsevt")
        s.add_all([d, p])
        await s.commit()
        did, pid = d.id, p.id
    r = (await head.post(f"{R}/requests", json={"department_id": did, "position_id": pid})).json()
    vid = (await hr.post(f"{R}/requests/{r['id']}/decide", json={"action": "approve"})).json()["vacancy_id"]
    links = (await hr.get(f"{R}/vacancies/{vid}/dashboard")).json()["links"]
    assert sorted(lk["channel"] for lk in links) == ["site", "telegram"]
    site = next(lk for lk in links if lk["channel"] == "site")
    pub = new_client()
    jobs = (await pub.get("/api/v1/public/jobs")).json()["items"]
    assert any(j["id"] == vid and j["code"] == site["code"] for j in jobs)
    ap = (await pub.post(f"/api/v1/public/apply/{site['code']}", json={"full_name": "Anketa Nomzod", "phone": "+998901112233"})).json()
    token = ap["profile_url"].rsplit("/", 1)[1]
    body = {"full_name": "Anketa Nomzod", "email": "a@b.uz", "languages": ["rus"], "skills": [], "anketa": {"specialty": "Farmatsiya", "experience_years": "5", "salary_text": "8-9 mln", "hack": "x"}}
    prof = (await pub.put(f"/api/v1/public/profile/{token}", json=body)).json()
    assert prof["anketa"]["specialty"] == "Farmatsiya" and "hack" not in prof["anketa"] and prof["fields"]["experience"] == "5 yil"
    assert (await pub.post(f"/api/v1/public/profile/{token}/confirm")).status_code == 200
    async with SessionLocal() as s:
        n = await s.scalar(select(Notification).where(Notification.kind == "recruit.anketa_new").order_by(Notification.id.desc()))
        assert n is not None and "💊 Farmatsiya" in n.body_uz and "Staj: 5 yil" in n.body_uz and "8-9 mln" in n.body_uz
    from datetime import date

    today = date.today().isoformat()
    daily = (await hr.get(f"{R}/daily", params={"start": today, "end": today})).json()
    assert daily["total"]["received"] >= 1 and any(x["source"] == "Veb-sayt (avto)" for x in daily["by_source"])
    assert (await head.get(f"{R}/daily", params={"start": today, "end": today})).status_code == 403
    async with SessionLocal() as s:
        e = Employee(last_name="Nomzod", first_name="Anketa", full_name="Nomzod Anketa", hire_date=date(2024, 1, 15))
        s.add(e)
        await s.flush()
        a = await s.scalar(select(Application).where(Application.vacancy_id == vid))
        a.employee_id = e.id
        await s.commit()
        eid = e.id
    dz = (await hr.get(f"/api/v1/employees/{eid}/dossier")).json()
    assert dz["recruitment"]["vacancy"]["id"] == vid and dz["recruitment"]["link"]["channel"] == "site"
    assert dz["recruitment"]["request"]["number"] == r["number"] and dz["tenure"]["years"] >= 2
    assert dz["recruitment"]["anketa"]["specialty"] == "Farmatsiya"
