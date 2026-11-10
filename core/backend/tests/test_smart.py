"""AI suhbat, Whisper (soxta), ovoz chiqarib o'qish va onlayn konferensiya."""

import json
from datetime import UTC

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.employees import Employee
from app.models.org import Position
from app.models.recruit import Application, Candidate, PositionRequirement, Vacancy
from app.models.tasks import Task
from app.services.speech import reading_score
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


def test_reading_score():
    acc, missed = reading_score("Dori vositasini retsept bo'yicha bering va mijozga tushuntiring", "dori vositasini retsept bo‘yicha bering mijozga")
    assert 70 <= acc < 100 and "tushuntiring" in missed and "va" in missed
    assert reading_score("", "x") == (0, [])


@pytest.fixture
def fake_ai(monkeypatch):
    cfg = get_settings().model_copy(update={"anthropic_api_key": "sk-test", "openai_api_key": "sk-test"})
    monkeypatch.setattr("app.services.ai.get_settings", lambda: cfg)
    monkeypatch.setattr("app.services.speech.get_settings", lambda: cfg)
    state = {"calls": 0}

    async def post(model, system, user, max_tokens):
        state["calls"] += 1
        if "savollarini tuzing" in system:
            return json.dumps({"questions": [{"kind": "hard", "skill": "Dori", "text": f"Hard savol {i}"} for i in range(3)] + [{"kind": "soft", "skill": None, "text": f"Soft savol {i}"} for i in range(3)]}), 10, 10
        return json.dumps({"scores": [{"id": f"q{i}", "score": 8 if i <= 3 else 6, "feedback": "Yaxshi"} for i in range(1, 7)], "hard": 0, "soft": 0, "summary": "Mos nomzod"}), 10, 10

    async def transcribe(data, mime, lang="uz"):
        return "Men 5 yil dorixonada ishlaganman"

    monkeypatch.setattr("app.services.ai._post", post)
    monkeypatch.setattr("app.services.speech.transcribe", transcribe)
    return state


async def _application():
    async with SessionLocal() as s:
        p = Position(name="Farmatsevt-AI")
        s.add(p)
        await s.flush()
        s.add(PositionRequirement(position_id=p.id, requirements="Farmatsiya ma'lumoti", profile={"hard_skills": ["Dori bilimi", "Kassa"], "soft_skills": ["Muloqot"]}))
        v = Vacancy(title="Farmatsevt", position_id=p.id, status="open", openings=1)
        c = Candidate(full_name="Nomzod AI", phone="+998901234500")
        s.add_all([v, c])
        await s.flush()
        from app.timeutil import now

        a = Application(vacancy_id=v.id, candidate_id=c.id, stage="screening", applied_at=now(), stage_changed_at=now())
        s.add(a)
        await s.commit()
        return a.id, p.id


async def test_ai_interview_template_manual_grade(new_client):
    hr, _ = await as_user(new_client, "hrai1", "hr_direktor")
    aid, _pid = await _application()
    iv = (await hr.post("/api/v1/ai-interviews", json={"application_id": aid})).json()
    assert iv["title"] == "Farmatsevt-AI" and len(iv["questions"]) == 6 and "Dori bilimi" in iv["questions"][0]["text"]  # AI'siz: kartochka shabloni
    pub = new_client()
    tok = iv["token"]
    assert (await pub.post(f"/api/v1/public/interview/{tok}/submit")).json()["detail"]["code"] == "no_answers"
    assert (await pub.post(f"/api/v1/public/interview/{tok}/answer", json={"qid": "q9", "text": "x"})).status_code == 400
    assert (await pub.post(f"/api/v1/public/interview/{tok}/answer", json={"qid": "q1", "text": "Bilaman"})).status_code == 200
    assert (await pub.post(f"/api/v1/public/interview/{tok}/voice", data={"qid": "q1"}, files={"file": ("a.webm", WEBM, "audio/webm")})).json()["detail"]["code"] == "speech_disabled"
    assert (await pub.post(f"/api/v1/public/interview/{tok}/submit")).json()["submitted"]
    assert (await pub.post(f"/api/v1/public/interview/{tok}/answer", json={"qid": "q2", "text": "kech"})).json()["detail"]["code"] == "already_submitted"
    assert (await hr.post(f"/api/v1/ai-interviews/{iv['id']}/grade")).json()["detail"]["code"] == "ai_disabled"
    g = (await hr.post(f"/api/v1/ai-interviews/{iv['id']}/grade", json={"hard_pct": 70, "soft_pct": 80, "summary": "OK"})).json()
    assert g["status"] == "graded" and g["hard_pct"] == 70


async def test_ai_interview_ai_and_voice(new_client, fake_ai):
    hr, _ = await as_user(new_client, "hrai2", "hr_direktor")
    aid, _pid = await _application()
    iv = (await hr.post("/api/v1/ai-interviews", json={"application_id": aid})).json()
    assert iv["questions"][0]["text"] == "Hard savol 0" and (await hr.get("/api/v1/ai-interviews/meta")).json() == {"ai": True, "speech": True}
    pub = new_client()
    tok = iv["token"]
    v = (await pub.post(f"/api/v1/public/interview/{tok}/voice", data={"qid": "q1"}, files={"file": ("a.webm", WEBM, "audio/webm")})).json()
    assert v["transcript"].startswith("Men 5 yil") and v["answers"]["q1"]["text"].startswith("Men 5 yil")
    assert (await pub.post(f"/api/v1/public/interview/{tok}/voice", data={"qid": "q1"}, files={"file": ("a.txt", b"hello", "text/plain")})).status_code == 415
    for q in ("q2", "q4"):
        await pub.post(f"/api/v1/public/interview/{tok}/answer", json={"qid": q, "text": "Javob"})
    assert (await pub.post(f"/api/v1/public/interview/{tok}/submit")).status_code == 200
    r = (await hr.get(f"/api/v1/ai-interviews/{iv['id']}")).json()
    assert r["status"] == "graded" and r["hard_pct"] == 80 and r["soft_pct"] == 60 and r["summary"] == "Mos nomzod"
    async with SessionLocal() as s:
        a = await s.get(Application, aid)
        assert a.hard_skill == 4 and a.soft_skill == 3  # 80% -> 4/5, 60% -> 3/5


async def test_read_aloud(new_client, fake_ai):
    hr, _ = await as_user(new_client, "hrra", "hr_direktor")
    intern, uid = await as_user(new_client, "stajra", "stajyor")
    async with SessionLocal() as s:
        p = Position(name="Farm-RA")
        s.add(p)
        await s.flush()
        s.add(Employee(last_name="O'qiydi", first_name="Laylo", full_name="O'qiydi Laylo", user_id=uid, position_id=p.id, status="active"))
        await s.commit()
        pid = p.id
    track = (await hr.post("/api/v1/preboarding/tracks", json={"position_id": pid})).json()
    sid = track["stages"][0]["id"]
    await hr.put(f"/api/v1/preboarding/stages/{sid}", json={"title": "1-bosqich", "description": "Men 5 yil dorixonada ishlaganman va mijozlarga yordam berganman", "audience": "all", "url": None, "slides_url": None, "questions": [], "published": True})
    await intern.get("/api/v1/preboarding/my")
    r = (await intern.post(f"/api/v1/preboarding/my/stages/{sid}/read-aloud", files={"file": ("a.webm", WEBM, "audio/webm")})).json()
    assert 50 <= r["accuracy"] < 100 and "mijozlarga" in r["missed"] and r["attempts"] == 1
    res = (await hr.get(f"/api/v1/preboarding/tracks/{track['id']}/read-aloud")).json()["items"]
    assert res[0]["best"] == r["accuracy"] and res[0]["attempts"] == 1


async def test_conference_flow(new_client, monkeypatch):
    cfg = get_settings().model_copy(update={"livekit_api_key": "k", "livekit_api_secret": "s" * 32})
    monkeypatch.setattr("app.services.calls.get_settings", lambda: cfg)
    hr, hr_id = await as_user(new_client, "hrconf", "hr_direktor")
    a, a_id = await as_user(new_client, "confa", "farmasevt")
    b, b_id = await as_user(new_client, "confb", "farmasevt")
    out, _ = await as_user(new_client, "confout", "farmasevt")
    async with SessionLocal() as s:
        p = Position(name="Konf-farm")
        s.add(p)
        await s.flush()
        for uid, n in ((a_id, "A"), (b_id, "B")):
            s.add(Employee(last_name=n, first_name="X", full_name=f"{n} X", user_id=uid, position_id=p.id, status="active"))
        await s.commit()
        pid = p.id
    from datetime import datetime, timedelta

    body = {"title": "Yangi dori", "starts_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(), "duration_min": 30, "audience": {"position_ids": [pid]},
            "tasks": [{"title": "Testni topshirish", "due_days": 2}], "recording_url": "https://youtu.be/x"}  # fmt: skip
    assert (await a.post("/api/v1/conferences", json=body)).status_code == 403
    assert (await hr.post("/api/v1/conferences", json={**body, "audience": {}})).json()["detail"]["code"] == "audience_required"
    c = (await hr.post("/api/v1/conferences", json=body)).json()
    assert (await out.get(f"/api/v1/conferences/{c['id']}")).status_code == 404  # auditoriyada emas
    assert [x["id"] for x in (await a.get("/api/v1/conferences")).json()["items"]] == [c["id"]]
    j = (await hr.post(f"/api/v1/conferences/{c['id']}/join")).json()
    assert j["host"] and j["token"] and (await hr.get(f"/api/v1/conferences/{c['id']}")).json()["status"] == "live"
    assert (await a.post(f"/api/v1/conferences/{c['id']}/join")).status_code == 200
    assert (await a.post(f"/api/v1/conferences/{c['id']}/heartbeat")).status_code == 204
    assert (await a.post(f"/api/v1/conferences/{c['id']}/end")).status_code == 403
    r = (await hr.post(f"/api/v1/conferences/{c['id']}/end")).json()
    rep = r["report"]
    assert r["status"] == "ended" and rep["invited"] == 3 and rep["attended"] == 2 and [x["user_id"] for x in rep["absent"]] == [b_id] and rep["tasks_created"] == 2
    async with SessionLocal() as s:
        ts = {(t.assignee_id, t.title) for t in (await s.scalars(select(Task).where(Task.labels.contains(["onlayn-dars"])))).all()}
    assert (a_id, "Testni topshirish") in ts and (b_id, "Darsni o'zlashtirish: Yangi dori") in ts and not any(u == hr_id for u, _ in ts)
    assert (await a.post(f"/api/v1/conferences/{c['id']}/join")).json()["detail"]["code"] == "conference_closed"
