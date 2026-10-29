from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.recruit import Application, Candidate, InterviewInvite, Vacancy
from app.services import recruit_core as core
from app.timeutil import now, tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

RC = "/api/v1/recruit"
PUB = "/api/v1/public"


class FakeQueue:
    def __init__(self):
        self.jobs: list[tuple] = []

    async def enqueue(self, function, *args, defer_seconds=None):
        self.jobs.append((function, *args))


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


async def setup(new_client, app):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    hr, hr_id = await as_user(new_client, "hrm", "hr_menejer")
    dept = (await hrd.post("/api/v1/org/departments", json={"name": "Dorixona"})).json()
    pos = (await hrd.post("/api/v1/org/positions", json={"name": "Farmasevt", "department_id": dept["id"]})).json()
    app.state.queue = FakeQueue()
    return {"hrd": hrd, "hr": hr, "hr_id": hr_id, "pos": pos["id"], "dept": dept["id"], "queue": app.state.queue}


CARD = {"hard_skills": ["kassa", "farmatsevt"], "languages": ["rus"], "min_experience": 2, "exclusions": ["sudlangan"], "education": "O'rta maxsus"}


async def test_competency_card_versions_and_vacancy_autofill(new_client, app):
    ctx = await setup(new_client, app)
    hr, pos = ctx["hr"], ctx["pos"]
    r = await hr.put(f"{RC}/requirements/{pos}", json={"requirements": None, "competencies": [], "profile": {**CARD, "duties": "Mijozga xizmat"}})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["version"] == 1 and j["profile"]["hard_skills"] == ["kassa", "farmatsevt"] and j["profile"]["min_experience"] == 2
    same = await hr.put(f"{RC}/requirements/{pos}", json={"requirements": None, "competencies": [], "profile": {**CARD, "duties": "Mijozga xizmat"}})
    assert same.json()["version"] == 1  # o'zgarish yo'q: versiya oshmaydi
    up = await hr.put(f"{RC}/requirements/{pos}", json={"requirements": None, "competencies": [], "profile": {**CARD, "duties": "Mijozga xizmat", "min_experience": 3}, "note": "Tajriba oshirildi"})
    assert up.json()["version"] == 2
    vs = (await hr.get(f"{RC}/requirements/{pos}/versions")).json()
    assert len(vs) == 1 and vs[0]["version"] == 1 and vs[0]["note"] == "Tajriba oshirildi" and vs[0]["snapshot"]["profile"]["min_experience"] == 2
    # vakansiya talablari kartochkadan avtomatik to'ldiriladi
    v = await hr.post(f"{RC}/vacancies", json={"title": "Farmasevt", "position_id": pos, "department_id": ctx["dept"]})
    assert v.status_code == 201, v.text
    req = v.json()["requirements"]
    assert "kassa" in req and "kamida 3 yil" in req and "rus" in req
    v2 = await hr.post(f"{RC}/vacancies", json={"title": "Boshqa", "position_id": pos, "department_id": ctx["dept"], "requirements": "Maxsus talab"})
    assert v2.json()["requirements"] == "Maxsus talab"


async def test_vacancy_sla_warn_overdue_and_close_ads(new_client, app):
    ctx = await setup(new_client, app)
    hr = ctx["hr"]
    vid = (await hr.post(f"{RC}/vacancies", json={"title": "Vak", "recruiter_id": ctx["hr_id"]})).json()["id"]
    o = await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    assert o.json()["deadline"] == str(date.today() + timedelta(days=14)) or o.json()["deadline"] is not None
    await hr.post(f"{RC}/vacancies/{vid}/channels", json={"channel": "olx", "url": "https://olx.uz/x"})
    # muddat 1 kun qoldi -> ogohlantirish (bir marta)
    async with SessionLocal() as s:
        v = await s.get(Vacancy, vid)
        v.deadline = date.today() + timedelta(days=1)
        await s.commit()
    async with SessionLocal() as s:
        assert len(await core.sla_scan(s, now())) >= 1
        await s.commit()
    assert any(n["kind"] == "recruit.sla_warn" for n in await notes(hr))
    async with SessionLocal() as s:
        assert await core.sla_scan(s, now()) == []
    # muddat o'tdi -> alohida «o'tdi» xabari
    async with SessionLocal() as s:
        v = await s.get(Vacancy, vid)
        v.deadline = date.today() - timedelta(days=1)
        await s.commit()
    async with SessionLocal() as s:
        await core.sla_scan(s, now())
        await s.commit()
    assert any(n["kind"] == "recruit.sla_overdue" for n in await notes(hr))
    # yopilganda ochiq e'lonlar haqida eslatma; kanal yopilgach eslatma yo'q
    c = await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "closed"})
    assert c.status_code == 200
    assert any(n["kind"] == "recruit.close_ads" for n in await notes(hr))


async def test_pinfl_duplicate_phone_ownership_and_merge(new_client, app):
    ctx = await setup(new_client, app)
    hr = ctx["hr"]
    a = await hr.post(f"{RC}/candidates", json={"full_name": "Karimov Aziz", "phone": "+998901112233", "pinfl": "12345678901234"})
    assert a.status_code == 201, a.text
    aid = a.json()["id"]
    assert (await hr.post(f"{RC}/candidates", json={"full_name": "Boshqa Odam", "pinfl": "12345678901234"})).json()["detail"]["code"] == "candidate_exists"
    assert (await hr.post(f"{RC}/candidates", json={"full_name": "Aziz Karimov", "phone": "+998901112233"})).json()["detail"]["code"] == "candidate_exists"  # bir shaxs
    # raqam boshqa odamga o'tdi: yangi kartochka, eski egalik tarixda yopiladi
    b = await hr.post(f"{RC}/candidates", json={"full_name": "Yusupova Dilnoza", "phone": "+998901112233"})
    assert b.status_code == 201, b.text
    bid = b.json()["id"]
    look = (await hr.get(f"{RC}/candidates/by-phone", params={"phone": "+998901112233"})).json()
    assert look["current"]["id"] == bid and len(look["history"]) == 2
    assert {h["candidate"]["id"]: h["current"] for h in look["history"]} == {aid: False, bid: True}
    assert (await hr.get(f"{RC}/candidates/{aid}")).json()["phone"] is None
    assert (await hr.get(f"{RC}/candidates/by-phone", params={"phone": "+998909999999"})).json()["current"] is None
    # takroriy kartochkani birlashtirish
    vid = (await hr.post(f"{RC}/vacancies", json={"title": "Vak"})).json()["id"]
    await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    await hr.post(f"{RC}/applications", json={"vacancy_id": vid, "candidate_id": bid})
    m = await hr.post(f"{RC}/candidates/{aid}/merge", json={"secondary_ids": [bid]})
    assert m.status_code == 200 and m.json()["applications"] == 1
    assert (await hr.get(f"{RC}/candidates/{bid}")).status_code == 404
    assert len((await hr.get(f"{RC}/candidates/{aid}")).json()["applications"]) == 1
    assert (await hr.post(f"{RC}/candidates/{aid}/merge", json={"secondary_ids": [aid]})).json()["detail"]["code"] == "merge_self"


async def test_profile_link_public_anketa_match_and_confirm(new_client, app):
    ctx = await setup(new_client, app)
    hr, pos = ctx["hr"], ctx["pos"]
    await hr.put(f"{RC}/requirements/{pos}", json={"profile": CARD})
    vid = (await hr.post(f"{RC}/vacancies", json={"title": "Farmasevt", "position_id": pos, "department_id": ctx["dept"], "recruiter_id": ctx["hr_id"]})).json()["id"]
    await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    cid = (await hr.post(f"{RC}/candidates", json={"full_name": "Karimova Feruza", "phone": "+998931110001", "resume_text": "Farmatsevt va kassa bo'yicha 3 yil ishlaganman. Rus tilini bilaman."})).json()["id"]
    aid = (await hr.post(f"{RC}/applications", json={"vacancy_id": vid, "candidate_id": cid})).json()["id"]
    link = (await hr.post(f"{RC}/candidates/{cid}/profile-link")).json()
    token = link["url"].rsplit("/", 1)[1]
    pub = new_client()
    v = await pub.get(f"{PUB}/profile/{token}")
    assert v.status_code == 200 and v.json()["fields"]["phone"] == "+998931110001" and v.json()["confirmed_at"] is None
    assert (await pub.get(f"{PUB}/profile/yoq-token")).status_code == 404
    up = await pub.put(f"{PUB}/profile/{token}", json={"full_name": "Karimova Feruza", "address": "Toshkent", "experience": "3 yil", "expected_salary": 4500000, "languages": ["rus", "ingliz"], "skills": ["kassa", "farmatsevt"], "about": "Mas'uliyatli"})
    assert up.status_code == 200 and up.json()["fields"]["expected_salary"] == 4500000 and up.json()["sources"]["expected_salary"] == "anketa"
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    f = await pub.post(f"{PUB}/profile/{token}/file", files={"file": ("rezyume.pdf", pdf, "application/pdf")})
    assert f.status_code == 201 and len(f.json()["files"]) == 1
    assert (await pub.post(f"{PUB}/profile/{token}/file", files={"file": ("x.exe", b"MZ\x90\x00", "application/octet-stream")})).status_code == 415
    cf = await pub.post(f"{PUB}/profile/{token}/confirm")
    assert cf.status_code == 200 and cf.json()["confirmed_at"]
    ap = (await hr.get(f"{RC}/applications/{aid}")).json()
    assert ap["match_score"] is not None and ap["match_score"] >= 80 and ap["match_detail"]["excluded"] == []
    assert any(n["kind"] == "recruit.match_ok" for n in await notes(hr))
    # tahrirdan keyin qayta tasdiqlanadi; istisno mezoni topilsa ball 0
    await pub.put(f"{PUB}/profile/{token}", json={"full_name": "Karimova Feruza", "about": "Avval sudlangan", "skills": ["kassa"], "languages": [], "experience": "3 yil"})
    assert (await pub.get(f"{PUB}/profile/{token}")).json()["confirmed_at"] is None
    r = await hr.post(f"{RC}/applications/{aid}/rescore")
    assert r.json()["match_score"] == 0 and r.json()["match_detail"]["excluded"] == ["sudlangan"]
    # staff profil ko'rinishi manbalar bilan
    sp = (await hr.get(f"{RC}/candidates/{cid}/profile")).json()
    assert sp["sources"]["about"] == "anketa" and sp["applications"][0]["match_score"] == 0


async def test_interview_invitation_slots_choose_reply_and_reminders(new_client, app):
    ctx = await setup(new_client, app)
    hr = ctx["hr"]
    vid = (await hr.post(f"{RC}/vacancies", json={"title": "Farmasevt", "recruiter_id": ctx["hr_id"], "salary_from": 3000000, "salary_to": 5000000})).json()["id"]
    await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    async with SessionLocal() as s:
        c = Candidate(full_name="Nomzod Bir", phone="+998931110009", telegram_chat_id=777, skills=[])
        s.add(c)
        await s.commit()
        cid = c.id
    aid = (await hr.post(f"{RC}/applications", json={"vacancy_id": vid, "candidate_id": cid})).json()["id"]
    t1, t2 = (now() + timedelta(days=2)).replace(microsecond=0), (now() + timedelta(days=3)).replace(microsecond=0)
    past = (await hr.post(f"{RC}/applications/{aid}/invitation", json={"slots": [(now() - timedelta(hours=1)).isoformat()]})).json()
    assert past["detail"]["code"] == "slot_in_past"
    r = await hr.post(f"{RC}/applications/{aid}/invitation", json={"slots": [t1.isoformat(), t2.isoformat()], "mode": "online", "place": "Bosh ofis", "map_url": "https://maps.example/x", "contact_phone": "+998901112233"})
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "sent" and inv["telegram_sent"] is True and inv["meeting_url"].startswith("https://meet.jit.si/") and len(inv["slots"]) == 2
    assert any(j[0] == "deliver_candidate_telegram" and j[1] == 777 and inv["url"] in j[2] for j in ctx["queue"].jobs)
    token = inv["url"].rsplit("/", 1)[1]
    pub = new_client()
    view = (await pub.get(f"{PUB}/invite/{token}")).json()
    assert view["vacancy"] == "Farmasevt" and view["salary_from"] == 3000000 and len(view["slots"]) == 2 and view["meeting_url"] is None  # video havola tanlangach ochiladi
    assert (await pub.post(f"{PUB}/invite/{token}/choose", json={"slot": (now() + timedelta(days=9)).isoformat()})).json()["detail"]["code"] == "slot_invalid"
    ch = await pub.post(f"{PUB}/invite/{token}/choose", json={"slot": t2.isoformat()})
    assert ch.status_code == 200 and ch.json()["status"] == "scheduled" and ch.json()["meeting_url"]
    ap = (await hr.get(f"{RC}/applications/{aid}")).json()
    assert ap["stage"] == "interview" and ap["interview_at"].startswith(t2.astimezone(tz()).strftime("%Y-%m-%d")) or ap["interview_at"]
    assert any(n["kind"] == "recruit.invite_chosen" for n in await notes(hr))
    # eslatmalar: suhbatdan 20 soat oldin -> kunlik, 1 soat oldin -> 2 soatlik (har biri bir marta)
    async with SessionLocal() as s:
        out = await core.reminder_scan(s, t2 - timedelta(hours=20))
        await s.commit()
    assert len(out) == 1 and out[0][0] == 777 and "ertaga" in out[0][1]
    async with SessionLocal() as s:
        assert await core.reminder_scan(s, t2 - timedelta(hours=19)) == []
        out2 = await core.reminder_scan(s, t2 - timedelta(hours=1))
        await s.commit()
    assert len(out2) == 1 and "2 soatdan keyin" in out2[0][1]
    # javob: kelaman -> xabar; kela olmayman -> «declined», eslatma to'xtaydi
    assert (await pub.post(f"{PUB}/invite/{token}/reply", json={"answer": "coming"})).json()["reply"] == "coming"
    nc = await pub.post(f"{PUB}/invite/{token}/reply", json={"answer": "not_coming"})
    assert nc.json()["status"] == "declined"
    assert (await pub.post(f"{PUB}/invite/{token}/choose", json={"slot": t1.isoformat()})).json()["detail"]["code"] == "invite_closed"
    assert (await hr.get(f"{RC}/applications/{aid}/invitation")).json()["status"] == "declined"
    # bitta vaqt berilsa darhol belgilanadi; eski taklif bekor qilinadi
    one = await hr.post(f"{RC}/applications/{aid}/invitation", json={"slots": [t1.isoformat()]})
    assert one.json()["status"] == "scheduled"
    async with SessionLocal() as s:
        rows = (await s.scalars(select(InterviewInvite).where(InterviewInvite.application_id == aid).order_by(InterviewInvite.id))).all()
        assert [r.status for r in rows] == ["declined", "scheduled"]
        assert (await s.get(Application, aid)).interview_at is not None


async def test_my_day_funnel_and_reject_codes(new_client, app):
    ctx = await setup(new_client, app)
    hr = ctx["hr"]
    v1 = (await hr.post(f"{RC}/vacancies", json={"title": "Ads yo'q", "recruiter_id": ctx["hr_id"]})).json()["id"]
    v2 = (await hr.post(f"{RC}/vacancies", json={"title": "Ads bor", "recruiter_id": ctx["hr_id"]})).json()["id"]
    for vid in (v1, v2):
        await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    await hr.post(f"{RC}/vacancies/{v2}/channels", json={"channel": "olx"})
    cands = []
    for i in range(4):
        cands.append((await hr.post(f"{RC}/candidates", json={"full_name": f"Nomzod Raqam{i}", "phone": f"+99893111000{i}"})).json()["id"])
    apps = [(await hr.post(f"{RC}/applications", json={"vacancy_id": v1, "candidate_id": c})).json()["id"] for c in cands]
    await hr.post(f"{RC}/applications/{apps[0]}/stage", json={"stage": "screening"})
    await hr.post(f"{RC}/applications/{apps[1]}/stage", json={"stage": "screening"})
    await hr.post(f"{RC}/applications/{apps[1]}/stage", json={"stage": "interview", "interview_at": (now() + timedelta(hours=3)).isoformat()})
    # rad etish: sabab matni majburiy, toifa voronkada hisoblanadi
    assert (await hr.post(f"{RC}/applications/{apps[2]}/reject", json={"reason": "x"})).status_code == 422
    assert (await hr.post(f"{RC}/applications/{apps[2]}/reject", json={"reason": "Telefon ko'tarmadi", "code": "no_answer"})).json()["reject_code"] == "no_answer"
    assert (await hr.post(f"{RC}/applications/{apps[3]}/reject", json={"reason": "Oylik kam", "code": "salary"})).status_code == 200
    assert (await hr.post(f"{RC}/applications/{apps[3]}/reopen")).status_code == 200
    await hr.post(f"{RC}/applications/{apps[3]}/reject", json={"reason": "Oylik kam", "code": "salary"})
    f = (await hr.get(f"{RC}/funnel", params={"vacancy_id": v1})).json()
    steps = {s["stage"]: s["count"] for s in f["steps"]}
    assert f["total"] == 4 and steps["new"] == 4 and steps["screening"] == 3 and steps["interview"] == 1 and steps["hired"] == 0  # reopen -> screening yetgan
    assert f["rejected"] == 2 and {r["code"]: r["count"] for r in f["reasons"]} == {"no_answer": 1, "salary": 1}
    # qayta qo'ng'iroq va kunlik ekran
    await hr.post(f"{RC}/calls", json={"outcome": "callback", "phone": "+998931110000", "vacancy_id": v1, "callback_date": str(date.today())})
    d = (await hr.get(f"{RC}/my-day")).json()
    assert {v["title"] for v in d["vacancies"]} == {"Ads yo'q", "Ads bor"} and [v["title"] for v in d["without_ads"]] == ["Ads yo'q"]
    assert len(d["interviews"]) == 1 and d["interviews"][0]["today"] in (True, False) and len(d["callbacks"]) == 1 and d["calls_today"] == 1
    assert (await hr.get(f"{RC}/my-day", params={"recruiter_id": 999999})).status_code in (200, 403)
    assert datetime.now(tz()).year >= 2026
