from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.recruit import CandidateTest
from app.timeutil import now
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

RC = "/api/v1/recruit"
PUB = "/api/v1/public"
CARD = {"hard_skills": ["kassa", "farmatsevt"], "soft_skills": ["muloqot"], "languages": ["rus"], "min_experience": 1, "exclusions": [], "questions": ["Eng qiyin mijozingiz haqida gapirib bering"]}


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


async def setup(new_client, app, *, card=True):
    hrd, hrd_id = await as_user(new_client, "hrd", "hr_direktor")
    hr, hr_id = await as_user(new_client, "hrm", "hr_menejer")
    mudir, mudir_id = await as_user(new_client, "mudir", "mudir")
    far, _ = await as_user(new_client, "far", "farmasevt")
    dept = (await hrd.post("/api/v1/org/departments", json={"name": "Dorixona"})).json()
    pos = (await hrd.post("/api/v1/org/positions", json={"name": "Farmasevt", "department_id": dept["id"]})).json()
    if card:
        assert (await hr.put(f"{RC}/requirements/{pos['id']}", json={"profile": CARD})).status_code == 200
    app.state.queue = FakeQueue()
    vid = (await hr.post(f"{RC}/vacancies", json={"title": "Farmasevt", "position_id": pos["id"], "department_id": dept["id"], "recruiter_id": hr_id})).json()["id"]
    await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    cid = (await hr.post(f"{RC}/candidates", json={"full_name": "Karimova Feruza", "phone": "+998931110001", "skills": ["kassa", "farmatsevt"]})).json()["id"]
    aid = (await hr.post(f"{RC}/applications", json={"vacancy_id": vid, "candidate_id": cid})).json()["id"]
    return {"hrd": hrd, "hr": hr, "hr_id": hr_id, "mudir": mudir, "far": far, "aid": aid, "queue": app.state.queue, "pos": pos["id"], "vid": vid}


def questions():
    return [
        {"text": "2 + 2 = ?", "options": ["3", "4", "5"], "correct": [1]},
        {"text": "Tub sonlarni tanlang", "options": ["2", "4", "7", "9"], "correct": [0, 2]},
        {"text": "Poytaxt?", "options": ["Toshkent", "Samarqand"], "correct": [0]},
    ]


def bank(**kw):
    return {"name": "Mantiq 1", "kind": "logic", "time_limit_min": 10, "pass_score": 60, "questions": questions(), **kw}


async def test_scorecard_per_competency_and_visibility(new_client, app):
    ctx = await setup(new_client, app)
    aid = ctx["aid"]
    assert (await ctx["far"].get(f"{RC}/applications/{aid}/scorecard")).status_code == 403
    sc = (await ctx["mudir"].get(f"{RC}/applications/{aid}/scorecard")).json()
    assert [c["key"] for c in sc["competencies"]] == ["kassa", "farmatsevt", "muloqot"] and sc["questions"] == CARD["questions"] and sc["summary"] is None and sc["mine"] is None
    assert (await ctx["mudir"].put(f"{RC}/applications/{aid}/scorecard", json={"scores": {"yoq": 3}})).json()["detail"]["code"] == "unknown_competency"
    assert (await ctx["mudir"].put(f"{RC}/applications/{aid}/scorecard", json={"scores": {"kassa": 9}})).json()["detail"]["code"] == "score_invalid"
    assert (await ctx["mudir"].put(f"{RC}/applications/{aid}/scorecard", json={"scores": {"kassa": 5, "farmatsevt": 4, "muloqot": 3}, "notes": "Yaxshi"})).status_code == 200
    assert (await ctx["hr"].put(f"{RC}/applications/{aid}/scorecard", json={"scores": {"kassa": 3, "farmatsevt": 4, "muloqot": 5}})).status_code == 200
    mine = (await ctx["mudir"].get(f"{RC}/applications/{aid}/scorecard")).json()
    assert mine["mine"]["scores"]["kassa"] == 5 and mine["summary"] is None and "interviewers" not in mine
    hr_view = (await ctx["hr"].get(f"{RC}/applications/{aid}/scorecard")).json()
    assert hr_view["summary"]["interviewers"] == 2 and hr_view["summary"]["by_competency"]["kassa"] == 4.0 and hr_view["summary"]["overall"] == 4.0 and len(hr_view["interviewers"]) == 2
    # kartochkasiz vakansiya: standart kompetensiyalar
    ctx2 = await setup_no_card(new_client, app)
    sc2 = (await ctx2["hr"].get(f"{RC}/applications/{ctx2['aid']}/scorecard")).json()
    assert [c["key"] for c in sc2["competencies"]][0] == "Kasbiy bilim"


async def setup_no_card(new_client, app):
    hr, hr_id = await as_user(new_client, "hrm2", "hr_menejer")
    app.state.queue = FakeQueue()
    vid = (await hr.post(f"{RC}/vacancies", json={"title": "Oddiy", "recruiter_id": hr_id})).json()["id"]
    await hr.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    cid = (await hr.post(f"{RC}/candidates", json={"full_name": "Boshqa Nomzod", "phone": "+998931110002"})).json()["id"]
    return {"hr": hr, "aid": (await hr.post(f"{RC}/applications", json={"vacancy_id": vid, "candidate_id": cid})).json()["id"]}


async def test_test_bank_assign_public_flow_scoring_and_expiry(new_client, app):
    ctx = await setup(new_client, app)
    hr, aid = ctx["hr"], ctx["aid"]
    assert (await ctx["mudir"].post(f"{RC}/tests", json=bank())).status_code == 403
    assert (await hr.post(f"{RC}/tests", json=bank(questions=[{"text": "x", "options": ["a"], "correct": [0]}]))).status_code == 422
    assert (await hr.post(f"{RC}/tests", json=bank(questions=[{"text": "x", "options": ["a", "b"], "correct": [5]}]))).json()["detail"]["code"] == "questions_invalid"
    b = (await hr.post(f"{RC}/tests", json=bank())).json()
    assert b["question_count"] == 3 and all(q["id"] for q in b["questions"])
    assert [x["name"] for x in (await hr.get(f"{RC}/tests")).json()] == ["Mantiq 1"] and (await hr.get(f"{RC}/tests")).json()[0]["questions"] is None  # ro'yxatda javoblar yo'q
    r = await hr.post(f"{RC}/applications/{aid}/tests", json={"bank_id": b["id"]})
    assert r.status_code == 201, r.text
    t = r.json()
    token = t["url"].rsplit("/", 1)[1]
    assert t["status"] == "assigned"
    pub = new_client()
    info = (await pub.get(f"{PUB}/test/{token}")).json()
    assert info["status"] == "assigned" and info["question_count"] == 3 and "questions" not in info  # boshlanmaguncha savollar yo'q
    st = (await pub.post(f"{PUB}/test/{token}/start")).json()
    assert st["status"] == "started" and len(st["questions"]) == 3 and "correct" not in st["questions"][0] and st["questions"][1]["multiple"] is True
    deadline = st["deadline_at"]
    assert (await pub.post(f"{PUB}/test/{token}/start")).json()["deadline_at"] == deadline  # qayta bosilsa vaqt yangilanmaydi
    ids = [q["id"] for q in b["questions"]]
    sub = await pub.post(f"{PUB}/test/{token}/submit", json={"answers": {ids[0]: [1], ids[1]: [0, 2], ids[2]: [1]}})
    assert sub.status_code == 200 and sub.json() == {"status": "submitted"}  # natija nomzodga ko'rsatilmaydi
    assert (await pub.post(f"{PUB}/test/{token}/submit", json={"answers": {}})).json()["detail"]["code"] == "test_closed"
    res = (await hr.get(f"{RC}/applications/{aid}/tests")).json()[0]
    assert res["status"] == "submitted" and res["score_pct"] == 67 and res["passed"] is True and res["url"] is None
    assert any(n["kind"] == "recruit.test_done" for n in await notes(hr))
    # muddati o'tgan test
    t2 = (await hr.post(f"{RC}/applications/{aid}/tests", json={"bank_id": b["id"]})).json()
    tok2 = t2["url"].rsplit("/", 1)[1]
    await pub.post(f"{PUB}/test/{tok2}/start")
    async with SessionLocal() as s:
        row = await s.scalar(select(CandidateTest).where(CandidateTest.token == tok2))
        row.deadline_at = now() - timedelta(minutes=5)
        await s.commit()
    assert (await pub.post(f"{PUB}/test/{tok2}/submit", json={"answers": {ids[0]: [1]}})).json()["detail"]["code"] == "test_expired"
    assert (await pub.get(f"{PUB}/test/{tok2}")).json()["status"] == "expired"
    assert (await pub.get(f"{PUB}/test/yoq")).status_code == 404
    assert (await hr.delete(f"{RC}/tests/{b['id']}")).json()["detail"]["code"] == "in_use"


async def test_background_check_requires_consent_and_syncs_application(new_client, app):
    ctx = await setup(new_client, app)
    hr, aid = ctx["hr"], ctx["aid"]
    assert (await ctx["far"].post(f"{RC}/applications/{aid}/background-check")).status_code == 403
    bg = (await hr.post(f"{RC}/applications/{aid}/background-check")).json()
    assert bg["status"] == "consent_pending" and bg["consent_url"] and [i["key"] for i in bg["items"]] == ["reference", "documents", "social", "other"]
    token = bg["consent_url"].rsplit("/", 1)[1]
    assert (await hr.put(f"{RC}/applications/{aid}/background-check/items", json={"items": []})).json()["detail"]["code"] == "consent_required"
    assert (await hr.post(f"{RC}/applications/{aid}/background-check/finish", json={"decision": "passed"})).json()["detail"]["code"] == "consent_required"
    pub = new_client()
    assert (await pub.get(f"{PUB}/consent/{token}")).json()["name"] == "Karimova Feruza"
    assert (await pub.post(f"{PUB}/consent/{token}/agree")).status_code == 200
    assert any(n["kind"] == "recruit.consent_given" for n in await notes(hr))
    again = (await hr.post(f"{RC}/applications/{aid}/background-check")).json()
    assert again["status"] == "in_progress" and again["consent_at"] and again["consent_url"] is None  # takroran yaratilmaydi
    ok = await hr.put(f"{RC}/applications/{aid}/background-check/items", json={"items": [{"key": "reference", "result": "negative", "note": "Tavsiya bermadi"}, {"key": "documents", "result": "positive"}]})
    assert ok.status_code == 200 and ok.json()["items"][0]["result"] == "negative"
    assert (await hr.put(f"{RC}/applications/{aid}/background-check/items", json={"items": [{"key": "xx", "result": "positive"}]})).json()["detail"]["code"] == "items_invalid"
    assert (await hr.post(f"{RC}/applications/{aid}/background-check/finish", json={"decision": "failed"})).json()["detail"]["code"] == "note_required"
    fin = await hr.post(f"{RC}/applications/{aid}/background-check/finish", json={"decision": "failed", "note": "Oldingi ish joyidan salbiy tavsiya"})
    assert fin.status_code == 200 and fin.json()["status"] == "done"
    ap = (await hr.get(f"{RC}/applications/{aid}")).json()
    assert ap["bg_status"] == "failed" and "salbiy" in ap["bg_note"]
    assert (await hr.put(f"{RC}/applications/{aid}/background-check/items", json={"items": []})).json()["detail"]["code"] == "already_finished"


async def test_final_conclusion_draft_edit_approve(new_client, app):
    ctx = await setup(new_client, app)
    hr, hrd, aid = ctx["hr"], ctx["hrd"], ctx["aid"]
    await hr.put(f"{RC}/applications/{aid}/scorecard", json={"scores": {"kassa": 5, "farmatsevt": 5, "muloqot": 4}})
    b = (await hr.post(f"{RC}/tests", json=bank())).json()
    tok = (await hr.post(f"{RC}/applications/{aid}/tests", json={"bank_id": b["id"]})).json()["url"].rsplit("/", 1)[1]
    pub = new_client()
    await pub.post(f"{PUB}/test/{tok}/start")
    ids = [q["id"] for q in b["questions"]]
    await pub.post(f"{PUB}/test/{tok}/submit", json={"answers": {ids[0]: [1], ids[1]: [0, 2], ids[2]: [0]}})
    assert (await hr.put(f"{RC}/applications/{aid}/conclusion", json={"text": "Matn yozish uchun", "recommendation": "hire"})).json()["detail"]["code"] == "no_draft"
    d = await hr.post(f"{RC}/applications/{aid}/conclusion/draft")
    assert d.status_code == 200, d.text
    dj = d.json()
    assert dj["status"] == "draft" and dj["recommendation"] == "hire" and dj["score"] >= 75 and "Testlar" in dj["draft"] and "jins, yosh, millat va din" in dj["draft"] and dj["inputs"]["interview"] == 4.67
    assert (await hr.put(f"{RC}/applications/{aid}/conclusion", json={"text": "Tahrirlangan xulosa: ishga olish tavsiya etiladi", "recommendation": "reserve"})).json()["recommendation"] == "reserve"
    assert (await hr.post(f"{RC}/applications/{aid}/conclusion/approve")).status_code == 403  # tasdiqlash HR rahbariyatida
    ap = await hrd.post(f"{RC}/applications/{aid}/conclusion/approve")
    assert ap.status_code == 200 and ap.json()["status"] == "approved" and ap.json()["approved_by_name"] == "Hrd"
    assert any(n["kind"] == "recruit.conclusion_approved" for n in await notes(hr))
    assert (await hr.post(f"{RC}/applications/{aid}/conclusion/draft")).json()["detail"]["code"] == "already_approved"
    assert (await hr.get(f"{RC}/applications/{aid}")).json()["conclusion"]["status"] == "approved"
    # fon tekshiruvi o'tmagan bo'lsa tavsiya «olmaslik»
    ctx2 = await setup_no_card(new_client, app)
    await ctx2["hr"].post(f"{RC}/applications/{ctx2['aid']}/background")  # noop (422), so'ng haqiqiy:
    await ctx2["hr"].post(f"{RC}/applications/{ctx2['aid']}/background", json={"status": "failed", "note": "Hujjat soxta"})
    d2 = (await ctx2["hr"].post(f"{RC}/applications/{ctx2['aid']}/conclusion/draft")).json()
    assert d2["recommendation"] == "reject" and "o'tmadi" in d2["draft"]


async def test_offer_template_link_pdf_and_candidate_response(new_client, app):
    ctx = await setup(new_client, app)
    hr, hrd, aid = ctx["hr"], ctx["hrd"], ctx["aid"]
    await hr.post(f"{RC}/applications/{aid}/interview", json={"experience_level": "mid", "hard_skill": 4, "soft_skill": 4})
    o = await hrd.post(f"{RC}/applications/{aid}/offer", json={"level": "pharmacist", "salary": 4_500_000, "start_date": "2026-12-01", "schedule": "2/2, 08:00-20:00", "probation_days": 7, "note": "Sinov muddati 7 kun"})
    assert o.status_code == 200, o.text
    off = o.json()["offer"]
    assert off["status"] == "approved" and off["schedule"] == "2/2, 08:00-20:00" and off["probation_days"] == 7 and off["response"] is None and off["has_link"] is False
    assert (await hr.get(f"{RC}/applications/{aid}/offer/pdf")).status_code == 200
    link = (await hr.post(f"{RC}/applications/{aid}/offer/link")).json()["url"]
    token = link.rsplit("/", 1)[1]
    pdf = await hr.get(f"{RC}/applications/{aid}/offer/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    pub = new_client()
    view = (await pub.get(f"{PUB}/offer/{token}")).json()
    assert view["vacancy"] == "Farmasevt" and view["salary"] == 4_500_000 and view["probation_days"] == 7 and view["schedule"] == "2/2, 08:00-20:00" and view["response"] is None
    assert (await pub.post(f"{PUB}/offer/{token}/respond", json={"answer": "declined"})).json()["detail"]["code"] == "reason_required"
    acc = await pub.post(f"{PUB}/offer/{token}/respond", json={"answer": "accepted"})
    assert acc.status_code == 200 and acc.json()["response"] == "accepted"
    assert any(n["kind"] == "recruit.offer_response" for n in await notes(hr))
    assert (await pub.post(f"{PUB}/offer/{token}/respond", json={"answer": "declined", "reason": "Fikrim o'zgardi"})).json()["detail"]["code"] == "already_answered"
    assert (await hr.get(f"{RC}/applications/{aid}")).json()["offer"]["response"] == "accepted"
    assert (await pub.get(f"{PUB}/offer/yoq")).status_code == 404
    # rad etish: ariza avtomatik yopiladi, sabab va toifa yoziladi
    ctx2 = await setup_second(new_client, app)
    t2 = (await ctx2["hr"].post(f"{RC}/applications/{ctx2['aid']}/offer/link")).json()["url"].rsplit("/", 1)[1]
    dec = await new_client().post(f"{PUB}/offer/{t2}/respond", json={"answer": "declined", "reason": "Oylik kam"})
    assert dec.status_code == 200
    ap = (await ctx2["hr"].get(f"{RC}/applications/{ctx2['aid']}")).json()
    assert ap["stage"] == "rejected" and ap["reject_code"] == "declined" and "Oylik kam" in ap["reject_reason"]


async def setup_second(new_client, app):
    hrd, _ = await as_user(new_client, "hrd9", "hr_direktor")
    app.state.queue = FakeQueue()
    vid = (await hrd.post(f"{RC}/vacancies", json={"title": "Ikkinchi"})).json()["id"]
    await hrd.post(f"{RC}/vacancies/{vid}/status", json={"status": "open"})
    cid = (await hrd.post(f"{RC}/candidates", json={"full_name": "Ikkinchi Nomzod", "phone": "+998931110003"})).json()["id"]
    aid = (await hrd.post(f"{RC}/applications", json={"vacancy_id": vid, "candidate_id": cid})).json()["id"]
    await hrd.post(f"{RC}/applications/{aid}/interview", json={"experience_level": "none", "hard_skill": 3, "soft_skill": 3})
    await hrd.post(f"{RC}/applications/{aid}/offer", json={"level": "intern", "salary": 2_000_000})
    return {"hr": hrd, "aid": aid}

