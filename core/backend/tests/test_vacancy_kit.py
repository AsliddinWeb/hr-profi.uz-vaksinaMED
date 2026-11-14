import pytest

from app.db import SessionLocal
from app.models.recruit import Candidate, SourceLink, Vacancy
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


async def test_apply_with_resume_and_vacancy_kit(new_client):
    uid = await make_user("hrkit", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrkit")).status_code == 200
    async with SessionLocal() as s:
        v = Vacancy(title="Farmatsevt — Test", status="open", openings=1, recruiter_id=uid)
        s.add(v)
        await s.flush()
        lk = SourceLink(code="kit12345", vacancy_id=v.id, channel="site", label="Sayt")
        s.add(lk)
        vid = v.id
        await s.commit()
    pub = new_client()
    info = (await pub.get("/api/v1/public/apply/kit12345")).json()
    assert info["title"] == "Farmatsevt — Test" and "competencies" in info
    cv = b"Aliyev Vali Karimovich\nTel: +998 90 123 45 67\nEmail: vali@example.com\nTajriba: 3 yil dorixonada"
    parsed = (await pub.post("/api/v1/public/apply/kit12345/parse", files={"file": ("cv.txt", cv, "text/plain")})).json()
    assert parsed["phone"] and parsed["email"] == "vali@example.com"
    r = await pub.post("/api/v1/public/apply/kit12345/resume", data={"full_name": "Aliyev Vali", "phone": "+998901234567"}, files={"file": ("cv.txt", cv, "text/plain")})
    assert r.status_code == 201, r.text
    assert r.json()["profile_url"].startswith("/profile/")
    async with SessionLocal() as s:
        from sqlalchemy import select

        c = await s.scalar(select(Candidate).where(Candidate.full_name == "Aliyev Vali"))
        assert c and "dorixonada" in (c.resume_text or "")
    kit = (await hr.get(f"/api/v1/recruit/vacancies/{vid}/kit")).json()
    assert kit["stats"]["total"] == 1 and kit["stats"]["with_resume"] == 1 and kit["resumes"][0]["has_resume"] is True
    assert kit["links"][0]["applications"] == 1 and kit["links"][0]["clicks"] >= 1 and kit["vacancy"]["found"] is False


async def test_vacancy_history_records_changes(new_client):
    await make_user("hrhist", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrhist")).status_code == 200
    r = await hr.post("/api/v1/recruit/vacancies", json={"title": "Kassir", "openings": 1})
    assert r.status_code in (200, 201), r.text
    vid = r.json()["id"]
    body = {**r.json(), "title": "Katta kassir", "openings": 2}
    body = {k: body.get(k) for k in ("title", "branch_id", "department_id", "position_id", "description", "requirements", "salary_from", "salary_to", "openings", "recruiter_id", "deadline")}
    assert (await hr.put(f"/api/v1/recruit/vacancies/{vid}", json=body)).status_code == 200
    assert (await hr.post(f"/api/v1/recruit/vacancies/{vid}/status", json={"status": "open"})).status_code == 200
    h = (await hr.get(f"/api/v1/recruit/vacancies/{vid}/history")).json()
    acts = [x["action"] for x in h["items"]]
    assert "vacancy_create" in acts and "vacancy_update" in acts and "vacancy_status" in acts
    upd = next(x for x in h["items"] if x["action"] == "vacancy_update")
    assert upd["data"]["changes"]["title"] == ["Kassir", "Katta kassir"] and upd["actor"]
    only = (await hr.get(f"/api/v1/recruit/vacancies/{vid}/history", params={"kind": "vacancy"})).json()
    assert only["total"] == 3
