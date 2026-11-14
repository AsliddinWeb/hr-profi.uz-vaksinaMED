from datetime import timedelta

import pytest

from app.db import SessionLocal
from app.models.recruit import (
    Application,
    Candidate,
    RecruitCall,
    SourceLink,
    Vacancy,
    VacancyChannel,
)
from app.timeutil import now
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


async def test_recruit_analytics_kpi_sources_and_drill(new_client):
    uid = await make_user("hrana", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrana")).status_code == 200
    t = now() - timedelta(hours=2)
    async with SessionLocal() as s:
        v = Vacancy(title="Kassir", status="open", openings=2, recruiter_id=uid, opened_at=t)
        s.add(v)
        await s.flush()
        lk = SourceLink(code="ana12345", vacancy_id=v.id, channel="olx", clicks=10)
        s.add_all([lk, VacancyChannel(vacancy_id=v.id, channel="olx", cost=600000, posted_by=uid)])
        await s.flush()
        cands = [Candidate(full_name=f"Nomzod {i}", phone=f"+99890000000{i}") for i in range(4)]
        s.add_all(cands)
        await s.flush()
        s.add_all([
            Application(vacancy_id=v.id, candidate_id=cands[0].id, stage="hired", applied_at=t, stage_changed_at=t, hired_at=t + timedelta(hours=1), source_link_id=lk.id, recruiter_id=uid),
            Application(vacancy_id=v.id, candidate_id=cands[1].id, stage="rejected", reject_code="salary", applied_at=t, stage_changed_at=t, source_link_id=lk.id, recruiter_id=uid),
            Application(vacancy_id=v.id, candidate_id=cands[2].id, stage="interview", interview_at=t, applied_at=t, stage_changed_at=t, recruiter_id=uid),
            Application(vacancy_id=v.id, candidate_id=cands[3].id, stage="new", applied_at=t, stage_changed_at=t, recruiter_id=uid),
        ])
        # 3 ta qo'ng'iroq, lekin faqat 1 nomzod: qo'ng'iroqlar soni nomzodlar soniga aralashmaydi
        s.add_all([RecruitCall(recruiter_id=uid, candidate_id=cands[3].id, vacancy_id=v.id, outcome=o, direction="out", called_at=t) for o in ("no_answer", "no_answer", "callback")])
        await s.commit()

    r = await hr.get("/api/v1/recruit/analytics")
    assert r.status_code == 200, r.text
    d = r.json()
    k = d["kpi"]
    assert k["applications"] == 4 and k["candidates"] == 4 and k["calls"] == 3 and k["called_candidates"] == 1
    assert k["hired"] == 1 and k["rejected"] == 1 and k["interview_invited"] == 2 and k["contacted"] == 4
    assert d["formulas"]["hiring_conversion"] == 25.0 and d["formulas"]["contact_rate"] == 100.0
    olx = next(x for x in d["sources"] if x["source"] == "olx")
    assert olx["applications"] == 2 and olx["hired"] == 1 and olx["clicks"] == 10 and olx["cost_per_hire"] == 600000
    assert d["reasons"] == [{"code": "salary", "count": 1, "pct": 100.0}]
    assert sum(d["hours"]) == 4 and d["recruiters"][0]["hired"] == 1 and d["recruiters"][0]["calls"] == 3

    drill = (await hr.get("/api/v1/recruit/analytics/list", params={"metric": "hired"})).json()
    assert drill["total"] == 1 and drill["items"][0]["name"] == "Nomzod 0"
    only = (await hr.get("/api/v1/recruit/analytics", params={"source": "olx"})).json()
    assert only["kpi"]["applications"] == 2

    staff = new_client()
    await make_user("anaxodim", "farmasevt")
    assert (await login(staff, "anaxodim")).status_code == 200
    assert (await staff.get("/api/v1/recruit/analytics")).status_code == 403


async def test_attendance_and_candidate_timeline(new_client):
    uid = await make_user("hrtl", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrtl")).status_code == 200
    t = now() - timedelta(hours=3)
    async with SessionLocal() as s:
        v = Vacancy(title="Farmatsevt", status="open", openings=1, recruiter_id=uid, opened_at=t)
        c = Candidate(full_name="Timeline Nomzod", phone="+998901112233")
        s.add_all([v, c])
        await s.flush()
        a = Application(vacancy_id=v.id, candidate_id=c.id, stage="interview", interview_at=t, applied_at=t, stage_changed_at=t, recruiter_id=uid)
        s.add(a)
        s.add(RecruitCall(recruiter_id=uid, phone="+998901112233", outcome="suitable", direction="out", called_at=t))
        await s.flush()
        aid, cid = a.id, c.id
        await s.commit()
    r = await hr.post(f"/api/v1/recruit/applications/{aid}/attendance", json={"attended": False, "note": "telefonni ko'tarmadi"})
    assert r.status_code == 200 and r.json()["interview_attended"] is False
    d = (await hr.get("/api/v1/recruit/analytics")).json()
    assert d["kpi"]["no_show"] == 1 and d["kpi"]["interview_attended"] == 0
    tl = (await hr.get(f"/api/v1/recruit/candidates/{cid}/timeline")).json()
    acts = [x["action"] for x in tl["items"]]
    assert "applied" in acts and "interview_scheduled" in acts and "no_show" in acts and "call" in acts
    assert tl["counts"]["call"] == 1
    assert (await hr.post(f"/api/v1/recruit/applications/{aid}/attendance", json={"attended": True})).json()["interview_attended"] is True
    d = (await hr.get("/api/v1/recruit/analytics")).json()
    assert d["kpi"]["interview_attended"] == 1 and d["kpi"]["no_show"] == 0
