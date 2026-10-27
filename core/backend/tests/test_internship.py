from datetime import datetime, timedelta

import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from app.services import internship as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

IN = "/api/v1/internship"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=tz())
QUESTIONS = [
    {"text": "2+2?", "options": ["3", "4", "5"], "correct": [1]},
    {"text": "Tez yordam raqami?", "options": ["101", "102", "103"], "correct": [0, 2]},
]


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    monkeypatch.setattr("app.api.internship.now", fn, raising=False)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def mk_emp(name, user_id=None):
    async with SessionLocal() as s:
        e = Employee(last_name=name, first_name="X", full_name=f"{name} X", user_id=user_id, status="active")
        s.add(e)
        await s.commit()
        return e.id


async def setup(new_client):
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    mentor, mentor_id = await as_user(new_client, "mudir", "mudir")
    intern, intern_uid = await as_user(new_client, "stajyor1", "stajyor")
    other, other_uid = await as_user(new_client, "stajyor2", "stajyor")
    far, _ = await as_user(new_client, "far", "farmasevt")
    boss, _ = await as_user(new_client, "boss", "direktor")
    emp = await mk_emp("Stajyor1", intern_uid)
    emp2 = await mk_emp("Stajyor2", other_uid)
    prog = (await hr.post(f"{IN}/programs", json={"name": "Farmasevt kursi", "pass_score": 70})).json()
    s1 = (await hr.post(f"{IN}/programs/{prog['id']}/steps", json={"kind": "video", "title": "Tanishuv", "url": "https://example.com/v"})).json()
    s2 = (await hr.post(f"{IN}/programs/{prog['id']}/steps", json={"kind": "text", "title": "Qoidalar", "description": "O'qing"})).json()
    s3 = (await hr.post(f"{IN}/programs/{prog['id']}/steps", json={"kind": "test", "title": "Yakuniy test", "questions": QUESTIONS, "max_attempts": 2})).json()
    return {"hr": hr, "mentor": mentor, "mentor_id": mentor_id, "intern": intern, "other": other, "far": far, "boss": boss, "emp": emp, "emp2": emp2, "prog": prog["id"], "s1": s1["id"], "s2": s2["id"], "s3": s3["id"], "q": s3["questions"]}


async def enroll(ctx, **kw):
    r = await ctx["hr"].post(f"{IN}/enrollments", json={"program_id": ctx["prog"], "employee_id": ctx["emp"], "mentor_id": ctx["mentor_id"], **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_grade_unit():
    from app.models.internship import InternshipStep

    s = InternshipStep(questions=svc.clean_questions(QUESTIONS))
    qs = s.questions
    assert svc.grade(s, {qs[0]["id"]: [1], qs[1]["id"]: [2, 0]}) == (100, [])
    assert svc.grade(s, {qs[0]["id"]: [1], qs[1]["id"]: [0]}) == (50, [qs[1]["id"]])  # qisman to'g'ri = noto'g'ri
    assert svc.grade(s, {}) == (0, [qs[0]["id"], qs[1]["id"]])
    assert [q["multiple"] for q in svc.public_questions(s)] == [False, True] and "correct" not in svc.public_questions(s)[0]


async def test_program_and_step_crud_permissions(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    assert (await hr.post(f"{IN}/programs", json={"name": "farmasevt kursi"})).status_code == 409
    assert (await ctx["intern"].post(f"{IN}/programs", json={"name": "Y"})).status_code == 403
    assert (await ctx["far"].get(f"{IN}/programs")).status_code == 403
    assert (await hr.post(f"{IN}/programs/{ctx['prog']}/steps", json={"kind": "video", "title": "V"})).json()["detail"]["code"] == "url_required"
    assert (await hr.post(f"{IN}/programs/{ctx['prog']}/steps", json={"kind": "test", "title": "T", "questions": []})).json()["detail"]["code"] == "questions_invalid"
    bad = {"kind": "test", "title": "T", "questions": [{"text": "q", "options": ["a", "b"], "correct": [5]}]}
    assert (await hr.post(f"{IN}/programs/{ctx['prog']}/steps", json=bad)).json()["detail"]["code"] == "questions_invalid"
    assert (await hr.post(f"{IN}/programs/{ctx['prog']}/steps", json={"kind": "video", "title": "V", "url": "ftp://x"})).json()["detail"]["code"] == "url_invalid"
    # tartib
    d = (await hr.get(f"{IN}/programs/{ctx['prog']}")).json()
    assert [s["position"] for s in d["steps_list"]] == [0, 1, 2] and d["steps_list"][2]["questions"][0]["correct"] == [1]
    r = await hr.put(f"{IN}/programs/{ctx['prog']}/order", json={"ids": [ctx["s3"], ctx["s1"], ctx["s2"]]})
    assert r.status_code == 200
    assert [s["id"] for s in (await hr.get(f"{IN}/programs/{ctx['prog']}")).json()["steps_list"]] == [ctx["s3"], ctx["s1"], ctx["s2"]]
    assert (await hr.put(f"{IN}/programs/{ctx['prog']}/order", json={"ids": [ctx["s1"]]})).status_code == 400
    await hr.put(f"{IN}/programs/{ctx['prog']}/order", json={"ids": [ctx["s1"], ctx["s2"], ctx["s3"]]})
    # fayl
    up = await hr.post(f"{IN}/steps/{ctx['s2']}/file", files={"file": ("qoida.pdf", b"%PDF-1.4 q", "application/pdf")})
    assert up.status_code == 201 and up.json()["file"]["name"] == "qoida.pdf"
    assert (await hr.get(f"{IN}/steps/{ctx['s2']}/file")).status_code == 200
    assert (await ctx["intern"].get(f"{IN}/steps/{ctx['s2']}/file")).status_code == 404  # biriktirilmagan
    await enroll(ctx)
    assert (await ctx["intern"].get(f"{IN}/steps/{ctx['s2']}/file")).status_code == 200
    assert (await hr.delete(f"{IN}/programs/{ctx['prog']}")).json()["detail"]["code"] == "program_in_use"
    assert (await hr.get("/api/v1/audit", params={"action": "internship.step_create"})).json()["total"] == 3


async def test_enroll_rules(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    empty = (await hr.post(f"{IN}/programs", json={"name": "Bo'sh"})).json()
    assert (await hr.post(f"{IN}/enrollments", json={"program_id": empty["id"], "employee_id": ctx["emp"]})).json()["detail"]["code"] == "program_empty"
    assert (await hr.post(f"{IN}/enrollments", json={"program_id": ctx["prog"], "employee_id": 99999})).json()["detail"]["code"] == "unknown_employee"
    far_uid = await make_user("rand", "farmasevt")
    assert (await hr.post(f"{IN}/enrollments", json={"program_id": ctx["prog"], "employee_id": ctx["emp"], "mentor_id": far_uid})).json()["detail"]["code"] == "unknown_mentor"
    assert (await ctx["mentor"].post(f"{IN}/enrollments", json={"program_id": ctx["prog"], "employee_id": ctx["emp"]})).status_code == 403
    e = await enroll(ctx, due_date="2026-11-20")
    assert e["status"] == "active" and e["progress"] == {"required": 3, "done": 0, "percent": 0, "avg_score": None} and e["mentor"]["id"] == ctx["mentor_id"]
    assert (await hr.post(f"{IN}/enrollments", json={"program_id": ctx["prog"], "employee_id": ctx["emp"]})).json()["detail"]["code"] == "already_enrolled"
    kinds = lambda c: [n["kind"] for n in c]  # noqa: E731
    assert "internship.enrolled" in kinds((await ctx["intern"].get("/api/v1/notifications")).json()["items"])
    assert "internship.enrolled" in kinds((await ctx["mentor"].get("/api/v1/notifications")).json()["items"])
    assert [x["id"] for x in (await hr.get(f"{IN}/employees", params={"q": "Stajyor"})).json()] == [ctx["emp"], ctx["emp2"]]
    assert {m["id"] for m in (await hr.get(f"{IN}/mentors")).json()} >= {ctx["mentor_id"]}
    # ko'rinish doirasi
    assert (await ctx["other"].get(f"{IN}/enrollments/{e['id']}")).status_code == 404
    assert (await ctx["far"].get(f"{IN}/enrollments")).status_code == 403
    assert (await ctx["intern"].get(f"{IN}/enrollments")).json()["total"] == 1
    assert (await ctx["other"].get(f"{IN}/enrollments")).json()["total"] == 0
    assert (await ctx["mentor"].get(f"{IN}/enrollments", params={"scope": "mentor"})).json()["total"] == 1
    assert (await ctx["mentor"].get(f"{IN}/enrollments", params={"scope": "all"})).status_code == 403
    assert (await ctx["boss"].get(f"{IN}/enrollments", params={"scope": "all"})).json()["total"] == 1
    assert (await ctx["intern"].get(f"{IN}/summary")).json()["my_active"] == 1


async def test_full_internship_flow(new_client, clock):
    ctx = await setup(new_client)
    hr, intern, mentor = ctx["hr"], ctx["intern"], ctx["mentor"]
    e = await enroll(ctx)
    base = f"{IN}/enrollments/{e['id']}"
    d = (await intern.get(base)).json()
    assert [s["state"] for s in d["steps"]] == ["available", "locked", "locked"] and d["can"]["learn"] is True
    assert "correct" not in d["steps"][2]["questions"][0]  # stajyor to'g'ri javobni ko'rmaydi
    # ketma-ketlik
    assert (await intern.post(f"{base}/steps/{ctx['s2']}/done")).json()["detail"]["code"] == "step_locked"
    assert (await hr.post(f"{base}/steps/{ctx['s1']}/done")).status_code == 403  # stajyor emas
    assert (await mentor.post(f"{base}/steps/{ctx['s1']}/done")).status_code == 403
    assert (await intern.post(f"{base}/steps/{ctx['s1']}/done")).status_code == 200
    d = (await intern.post(f"{base}/steps/{ctx['s2']}/done")).json()
    assert d["progress"]["done"] == 2 and d["progress"]["percent"] == 67 and [s["state"] for s in d["steps"]] == ["done", "done", "available"]
    assert (await intern.post(f"{base}/steps/{ctx['s3']}/done")).json()["detail"]["code"] == "use_submit"
    q = ctx["q"]
    bad = {"answers": {q[0]["id"]: [0], q[1]["id"]: [1]}}
    r = await intern.post(f"{base}/steps/{ctx['s3']}/submit", json=bad)
    assert r.json()["score"] == 0 and r.json()["passed"] is False and len(r.json()["wrong"]) == 2 and r.json()["attempts_left"] == 1
    half = {"answers": {q[0]["id"]: [1], q[1]["id"]: [0]}}  # 50% < 70
    r = await intern.post(f"{base}/steps/{ctx['s3']}/submit", json=half)
    assert r.json()["score"] == 50 and r.json()["attempts_left"] == 0
    assert (await intern.post(f"{base}/steps/{ctx['s3']}/submit", json=half)).json()["detail"]["code"] == "attempts_exhausted"
    # murabbiy tiklaydi
    assert (await intern.post(f"{base}/steps/{ctx['s3']}/reset")).status_code == 403
    r = await mentor.post(f"{base}/steps/{ctx['s3']}/reset")
    assert r.status_code == 200 and r.json()["steps"][2]["attempts"] == 0
    good = {"answers": {q[0]["id"]: [1], q[1]["id"]: [2, 0]}}
    clock["t"] = NOW + timedelta(hours=3)
    r = await intern.post(f"{base}/steps/{ctx['s3']}/submit", json=good)
    assert r.json() == {"score": 100, "passed": True, "wrong": [], "threshold": 70, "attempts": 1, "attempts_left": 1, "status": "ready"}
    assert (await intern.post(f"{base}/steps/{ctx['s3']}/submit", json=good)).json()["detail"]["code"] == "invalid_transition"  # tayyor bo'lgach yopiq
    d = (await hr.get(base)).json()
    assert d["status"] == "ready" and d["final_score"] == 100.0 and d["progress"]["percent"] == 100 and d["can"]["confirm"] is True
    kinds = lambda c: [n["kind"] for n in c]  # noqa: E731
    assert "internship.ready" in kinds((await mentor.get("/api/v1/notifications")).json()["items"])
    assert "internship.ready" in kinds((await hr.get("/api/v1/notifications")).json()["items"])
    assert (await mentor.get(f"{IN}/summary")).json()["to_confirm"] == 1
    # tasdiqlash: stajyor o'zi qila olmaydi
    assert (await intern.post(f"{base}/confirm", json={})).status_code == 403
    assert (await ctx["boss"].post(f"{base}/confirm", json={})).status_code == 403
    r = await mentor.post(f"{base}/confirm", json={"note": "Ishga tayyor"})
    assert r.status_code == 200 and r.json()["status"] == "completed" and r.json()["completed_at"]
    assert (await mentor.post(f"{base}/confirm", json={})).status_code == 409
    assert "internship.completed" in kinds((await intern.get("/api/v1/notifications")).json()["items"])
    for act in ("enroll", "step_done", "test", "reset", "confirm"):
        assert (await hr.get("/api/v1/audit", params={"action": f"internship.{act}"})).json()["total"] >= 1, act
    # qayta biriktirish mumkin (tugagan)
    assert (await hr.post(f"{IN}/enrollments", json={"program_id": ctx["prog"], "employee_id": ctx["emp"]})).status_code == 201


async def test_cancel_and_overdue(new_client, clock):
    ctx = await setup(new_client)
    e = await enroll(ctx, due_date="2026-11-05")
    row = (await ctx["hr"].get(f"{IN}/enrollments", params={"scope": "all"})).json()["items"][0]
    assert row["overdue"] is True
    r = await ctx["hr"].post(f"{IN}/enrollments/{e['id']}/cancel", json={"note": "Ketdi"})
    assert r.json()["status"] == "cancelled"
    assert (await ctx["hr"].post(f"{IN}/enrollments/{e['id']}/cancel", json={})).status_code == 409
    assert (await ctx["intern"].post(f"{IN}/enrollments/{e['id']}/steps/{ctx['s1']}/done")).status_code == 409
    assert (await ctx["hr"].delete(f"{IN}/programs/{ctx['prog']}")).json()["detail"]["code"] == "program_in_use"
