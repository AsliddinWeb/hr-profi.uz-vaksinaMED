from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.employees import Employee, EmployeeEvent
from app.models.org import Department, Position
from app.services import recruit as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

R = "/api/v1/recruit"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=tz())

RESUME = """Karimov Aziz Bahodirovich
Tug'ilgan: 14.03.1998
Telefon: +998 90 123-45-67, 71 200 30 40
Email: Aziz.Karimov@Mail.uz
Manzil: Toshkent, Chilonzor 5
Ko'nikmalar: Farmatsevtika, Mijozlar bilan ishlash; Excel
"""


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.recruit",):
        monkeypatch.setattr(f"{mod}.now", fn, raising=False)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    mgr, mgr_id = await as_user(new_client, "menejer", "hr_menejer")
    far, _ = await as_user(new_client, "far", "farmasevt")
    boss, _ = await as_user(new_client, "boss", "direktor")
    async with SessionLocal() as s:
        d = Department(name="Dorixona", kind="pharmacy")
        s.add(d)
        await s.flush()
        p = Position(name="Farmasevt", department_id=d.id)
        s.add(p)
        await s.commit()
        dep, pos = d.id, p.id
    br = (await hr.post("/api/v1/branches", json={"number": 1, "name": "Filial 1"})).json()
    return {"hr": hr, "hr_id": hr_id, "mgr": mgr, "mgr_id": mgr_id, "far": far, "boss": boss, "dep": dep, "pos": pos, "branch": br["id"]}


async def mk_vacancy(c, ctx, open_=True, **kw):
    body = {"title": "Farmasevt", "branch_id": ctx["branch"], "department_id": ctx["dep"], "position_id": ctx["pos"], "openings": 1, "recruiter_id": ctx["mgr_id"], **kw}
    r = await c.post(f"{R}/vacancies", json=body)
    assert r.status_code == 201, r.text
    v = r.json()
    if open_:
        assert (await c.post(f"{R}/vacancies/{v['id']}/status", json={"status": "open"})).status_code == 200
    return v


async def mk_candidate(c, name="Karimov Aziz Bahodirovich", phone="+998901234567", **kw):
    r = await c.post(f"{R}/candidates", json={"full_name": name, "phone": phone, "source": "referral", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_parse_resume_unit():
    f = svc.parse_resume(RESUME)
    assert f["full_name"] == "Karimov Aziz Bahodirovich" and f["phone"] == "+998901234567"
    assert f["email"] == "aziz.karimov@mail.uz" and f["birth_date"] == "1998-03-14" and f["address"].startswith("Toshkent")
    assert {"Farmatsevtika", "Excel"} <= set(f["skills"]) and "excel" not in f["skills"]
    assert svc.parse_resume("faqat matn bor lekin hech narsa yo'q 123") == {}
    assert svc.split_name("Aliyev Vali") == ("Aliyev", "Vali", None) and svc.split_name("A B C D")[2] == "C D"


async def test_vacancy_lifecycle_and_permissions(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    assert (await ctx["far"].get(f"{R}/vacancies")).status_code == 403
    assert (await ctx["boss"].post(f"{R}/vacancies", json={"title": "Xyz"})).status_code == 403  # direktor faqat ko'radi
    assert (await ctx["boss"].get(f"{R}/vacancies")).status_code == 200
    assert (await hr.post(f"{R}/vacancies", json={"title": "Xyz", "salary_from": 5, "salary_to": 1})).json()["detail"]["code"] == "salary_range_invalid"
    assert (await hr.post(f"{R}/vacancies", json={"title": "Xyz", "recruiter_id": ctx["hr_id"] + 999})).json()["detail"]["code"] == "unknown_recruiter"
    v = await mk_vacancy(hr, ctx, open_=False)
    assert v["status"] == "draft" and v["funnel"]["new"] == 0
    # ochilmagan vakansiyaga ariza yo'q
    c = await mk_candidate(hr)
    r = await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c["id"]})
    assert r.json()["detail"]["code"] == "vacancy_not_open"
    assert (await hr.post(f"{R}/vacancies/{v['id']}/status", json={"status": "open"})).json()["opened_at"]
    assert (await hr.post(f"{R}/vacancies/{v['id']}/status", json={"status": "open"})).status_code == 409
    r = await hr.put(f"{R}/vacancies/{v['id']}", json={"title": "Katta farmasevt", "recruiter_id": ctx["mgr_id"], "openings": 2})
    assert r.status_code == 200 and r.json()["title"] == "Katta farmasevt" and r.json()["openings"] == 2
    assert (await hr.get(f"{R}/vacancies", params={"status": "active", "q": "katta"})).json()["total"] == 1
    # o'chirish: arizasiz bo'lsa
    assert (await hr.delete(f"{R}/vacancies/{v['id']}")).status_code == 204
    v2 = await mk_vacancy(hr, ctx)
    await hr.post(f"{R}/applications", json={"vacancy_id": v2["id"], "candidate_id": c["id"]})
    assert (await hr.delete(f"{R}/vacancies/{v2['id']}")).json()["detail"]["code"] == "vacancy_in_use"
    assert (await hr.get("/api/v1/audit", params={"action": "recruit.vacancy_create"})).json()["total"] == 2


async def test_candidates_parse_dedupe_and_files(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    r = await hr.post(f"{R}/candidates/parse", json={"text": RESUME})
    assert r.status_code == 200 and r.json()["engine"] == "rules" and "phone" in r.json()["found"]
    assert (await ctx["boss"].post(f"{R}/candidates/parse", json={"text": RESUME})).status_code == 403
    c = await mk_candidate(hr, skills=["Excel", "excel ", "Word"], email="A@B.uz")
    assert c["skills"] == ["Excel", "excel", "Word"] and c["email"] == "a@b.uz"
    dup = await hr.post(f"{R}/candidates", json={"full_name": "Aziz Karimov", "phone": "90 123 45 67"})  # bir shaxs (umumiy so'z): takroriy kartochka ochilmaydi
    assert dup.status_code == 409 and dup.json()["detail"]["id"] == c["id"]
    assert (await hr.post(f"{R}/candidates", json={"full_name": "Odam Bor", "phone": "123"})).json()["detail"]["code"] == "phone_invalid"
    other = await mk_candidate(hr, "Aliyev Vali", "+998931112233")
    assert (await hr.put(f"{R}/candidates/{other['id']}", json={"full_name": "Karimov Vali", "phone": "+998901234567"})).status_code == 409  # shu raqamning egasi bilan bir shaxs (umumiy so'z)
    assert (await hr.put(f"{R}/candidates/{other['id']}", json={"full_name": "Aliyev Valijon", "phone": "+998931112233", "note": "Yaxshi"})).json()["note"] == "Yaxshi"
    assert (await hr.get(f"{R}/candidates", params={"q": "valijon"})).json()["total"] == 1
    assert (await hr.get(f"{R}/candidates", params={"q": "90 123"})).json()["total"] == 1

    up = await hr.post(f"{R}/candidates/{c['id']}/files", files={"file": ("cv.pdf", b"%PDF-1.4 cv", "application/pdf")})
    assert up.status_code == 201, up.text
    assert (await ctx["boss"].get(f"{R}/candidates/{c['id']}/files/{up.json()['id']}")).status_code == 200
    assert len((await hr.get(f"{R}/candidates/{c['id']}")).json()["files"]) == 1
    assert (await hr.delete(f"{R}/candidates/{c['id']}/files/{up.json()['id']}")).status_code == 204
    v = await mk_vacancy(hr, ctx)
    await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c["id"]})
    assert (await hr.delete(f"{R}/candidates/{c['id']}")).json()["detail"]["code"] == "candidate_in_use"
    assert (await hr.delete(f"{R}/candidates/{other['id']}")).status_code == 204


async def test_pipeline_stages_reject_reopen(new_client, clock):
    ctx = await setup(new_client)
    hr, mgr = ctx["hr"], ctx["mgr"]
    v = await mk_vacancy(hr, ctx)
    c = await mk_candidate(hr)
    r = await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c["id"], "note": "Telegramdan"})
    a = r.json()
    assert a["stage"] == "new" and a["recruiter"]["id"] == ctx["mgr_id"]
    assert (await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c["id"]})).json()["detail"]["code"] == "already_applied"
    # recruiter (menejer) ga xabar
    assert "recruit.new_application" in [n["kind"] for n in (await mgr.get("/api/v1/notifications")).json()["items"]]

    assert (await mgr.post(f"{R}/applications/{a['id']}/stage", json={"stage": "interview"})).json()["detail"]["code"] == "interview_time_required"
    assert (await mgr.post(f"{R}/applications/{a['id']}/stage", json={"stage": "hired"})).status_code == 422
    r = await mgr.post(f"{R}/applications/{a['id']}/stage", json={"stage": "screening", "note": "Telefon suhbat", "rating": 4})
    assert r.status_code == 200 and r.json()["stage"] == "screening" and r.json()["rating"] == 4
    when = (NOW + timedelta(days=2)).isoformat()
    r = await mgr.post(f"{R}/applications/{a['id']}/stage", json={"stage": "interview", "interview_at": when})
    assert r.json()["stage"] == "interview" and datetime.fromisoformat(r.json()["interview_at"]) == NOW + timedelta(days=2)
    assert (await mgr.post(f"{R}/applications/{a['id']}/comments", json={"body": "Yaxshi ko'rindi"})).status_code == 201
    assert (await ctx["far"].get(f"{R}/applications/{a['id']}")).status_code == 403

    d = (await ctx["boss"].get(f"{R}/applications/{a['id']}")).json()
    assert [e["action"] for e in d["events"]] == ["applied", "stage", "rating", "stage", "comment"] and d["can"]["manage"] is False
    board = (await hr.get(f"{R}/board", params={"vacancy_id": v["id"]})).json()
    assert board["interview"]["total"] == 1 and board["new"]["total"] == 0

    assert (await hr.post(f"{R}/applications/{a['id']}/reject", json={"reason": "x"})).status_code == 422
    r = await hr.post(f"{R}/applications/{a['id']}/reject", json={"reason": "Tajriba yetarli emas"})
    assert r.json()["stage"] == "rejected" and r.json()["reject_reason"]
    assert (await hr.post(f"{R}/applications/{a['id']}/stage", json={"stage": "offer"})).status_code == 409
    assert (await hr.post(f"{R}/applications/{a['id']}/reject", json={"reason": "yana bir marta"})).status_code == 409
    assert (await hr.post(f"{R}/applications/{a['id']}/reopen")).json()["stage"] == "screening"
    assert (await hr.post(f"{R}/applications/{a['id']}/reopen")).status_code == 409
    assert (await hr.get(f"{R}/applications", params={"stage": "open", "vacancy_id": v["id"], "q": "karimov"})).json()["total"] == 1
    for act in ("stage", "reject", "reopen"):
        assert (await hr.get("/api/v1/audit", params={"action": f"recruit.{act}"})).json()["total"] >= 1


async def test_hire_creates_employee_and_closes_vacancy(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    v = await mk_vacancy(hr, ctx)
    c = await mk_candidate(hr, birth_date="1998-03-14", email="aziz@mail.uz", address="Toshkent")
    a = (await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c["id"]})).json()
    # faqat "taklif" bosqichida
    assert (await hr.post(f"{R}/applications/{a['id']}/hire", json={})).json()["detail"]["code"] == "invalid_transition"
    await hr.post(f"{R}/applications/{a['id']}/stage", json={"stage": "offer"})
    # employees.create yo'q rol (hr_menejer bor, direktor yo'q): direktor recruit.manage ham yo'q
    assert (await ctx["boss"].post(f"{R}/applications/{a['id']}/hire", json={})).status_code == 403
    r = await hr.post(f"{R}/applications/{a['id']}/hire", json={"hire_date": "2026-11-15"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["application"]["stage"] == "hired" and out["application"]["employee_id"] == out["employee_id"] and out["vacancy_closed"] is True
    async with SessionLocal() as s:
        e = await s.get(Employee, out["employee_id"])
        assert (e.last_name, e.first_name, e.middle_name) == ("Karimov", "Aziz", "Bahodirovich")
        assert e.phone == "+998901234567" and e.branch_id == ctx["branch"] and e.position_id == ctx["pos"] and e.status == "active" and e.hire_date.isoformat() == "2026-11-15"
        ev = (await s.scalars(select(EmployeeEvent).where(EmployeeEvent.employee_id == e.id))).all()
        assert [x.kind for x in ev] == ["hired"] and ev[0].data["source"] == "recruit"
    assert (await hr.get(f"{R}/vacancies/{v['id']}")).json()["status"] == "closed"
    assert (await hr.get(f"/api/v1/employees/{out['employee_id']}")).status_code == 200
    # qayta yollab bo'lmaydi, audit
    assert (await hr.post(f"{R}/applications/{a['id']}/hire", json={})).status_code == 409
    assert (await hr.get("/api/v1/audit", params={"action": "recruit.hire"})).json()["total"] == 1
    assert "recruit.hired" in [n["kind"] for n in (await ctx["mgr"].get("/api/v1/notifications")).json()["items"]]
    # yopilgan vakansiyaga ariza yo'q
    c2 = await mk_candidate(hr, "Valiyev Sher", "+998909998877")
    assert (await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c2["id"]})).json()["detail"]["code"] == "vacancy_not_open"


async def test_hire_duplicate_and_name_checks(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    v = await mk_vacancy(hr, ctx, openings=2)
    async with SessionLocal() as s:
        s.add(Employee(last_name="Bor", first_name="Odam", full_name="Bor Odam", phone="+998905550000", status="active"))
        await s.commit()
    c = await mk_candidate(hr, "Yangi Odam", "+998905550000")
    a = (await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c["id"]})).json()
    await hr.post(f"{R}/applications/{a['id']}/stage", json={"stage": "offer"})
    r = await hr.post(f"{R}/applications/{a['id']}/hire", json={})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "possible_duplicate" and r.json()["detail"]["matches"]
    r = await hr.post(f"{R}/applications/{a['id']}/hire", json={"confirm_duplicate": True})
    assert r.status_code == 200 and r.json()["vacancy_closed"] is False  # 2 ta o'rindan biri
    # bitta so'zli ism: ism kerak
    c3 = await mk_candidate(hr, "Aliyev", "+998901110000")
    a3 = (await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c3["id"]})).json()
    await hr.post(f"{R}/applications/{a3['id']}/stage", json={"stage": "offer"})
    assert (await hr.post(f"{R}/applications/{a3['id']}/hire", json={})).json()["detail"]["code"] == "name_incomplete"
    r = await hr.post(f"{R}/applications/{a3['id']}/hire", json={"first_name": "Vali"})
    assert r.status_code == 200 and r.json()["vacancy_closed"] is True


async def test_summary(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    v = await mk_vacancy(hr, ctx, openings=3)
    ids = []
    for i, src in enumerate(("referral", "referral", "olx")):
        c = await mk_candidate(hr, f"Test Odam{i}", f"+99890000000{i}", source=src)
        ids.append((await hr.post(f"{R}/applications", json={"vacancy_id": v["id"], "candidate_id": c["id"]})).json()["id"])
    await hr.post(f"{R}/applications/{ids[0]}/stage", json={"stage": "offer"})
    clock["t"] = NOW + timedelta(days=4)
    await hr.post(f"{R}/applications/{ids[0]}/hire", json={})
    await hr.post(f"{R}/applications/{ids[1]}/reject", json={"reason": "Mos emas"})
    day = NOW.date().isoformat()
    s = (await ctx["boss"].get(f"{R}/summary", params={"start": day, "end": (NOW + timedelta(days=5)).date().isoformat()})).json()
    assert s["applied"] == 3 and s["hired"] == 1 and s["rejected"] == 1 and s["avg_days_to_hire"] == 4.0 and s["open_vacancies"] == 1
    assert {x["source"]: (x["applied"], x["hired"]) for x in s["sources"]} == {"referral": (2, 1), "olx": (1, 0)}
    assert s["stages"]["new"] == 1
    assert (await hr.get(f"{R}/summary", params={"start": "2020-01-01", "end": "2026-12-31"})).status_code == 400
