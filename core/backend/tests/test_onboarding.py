from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.internship import InternshipEnrollment
from app.models.org import Position
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

IN = "/api/v1/internship"
T0 = datetime(2026, 11, 3, 10, 0, tzinfo=tz())


@pytest.fixture
def clock(monkeypatch):
    fn = lambda: T0  # noqa: E731
    for target in ("app.api.internship.now", "app.api.onboarding.now", "app.services.internship.now"):
        monkeypatch.setattr(target, fn, raising=False)


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


async def setup(new_client):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    mentor, mentor_id = await as_user(new_client, "trener", "koordinator")
    mudir, mudir_id = await as_user(new_client, "mudir", "mudir")
    intern, intern_uid = await as_user(new_client, "stajyor1", "stajyor")
    other, other_uid = await as_user(new_client, "stajyor2", "stajyor")
    branch = (await hrd.post("/api/v1/branches", json={"number": 41, "name": "F41", "address": "Chilonzor 5", "manager_user_id": mudir_id})).json()
    async with SessionLocal() as s:
        pos = Position(name="Farmasevt-stajyor")
        s.add(pos)
        await s.flush()
        emps = []
        for name, uid in (("Stajyor1", intern_uid), ("Stajyor2", other_uid)):
            e = Employee(last_name=name, first_name="X", full_name=f"{name} X", user_id=uid, status="active", branch_id=branch["id"], position_id=pos.id)
            s.add(e)
            emps.append(e)
        await s.commit()
        emp1, emp2, pid = emps[0].id, emps[1].id, pos.id
    pre = (await hrd.post(f"{IN}/programs", json={"name": "Preboarding", "pass_score": 60})).json()
    step = (await hrd.post(f"{IN}/programs/{pre['id']}/steps", json={"kind": "text", "title": "Qoidalar", "description": "O'qing"})).json()
    onb = (await hrd.post(f"{IN}/programs", json={"name": "Farmasevt 90 kun", "phase": "onboarding", "position_id": pid, "duration_days": 90})).json()
    await hrd.post(f"{IN}/programs/{onb['id']}/steps", json={"kind": "text", "title": "1-oy", "description": "x"})
    return {"hrd": hrd, "mentor": mentor, "mentor_id": mentor_id, "mudir": mudir, "intern": intern, "other": other, "emp1": emp1, "emp2": emp2, "pre": pre["id"], "step": step["id"], "onb": onb["id"], "branch": branch}


async def enroll(ctx):
    r = await ctx["hrd"].post(f"{IN}/enrollments", json={"program_id": ctx["pre"], "employee_id": ctx["emp1"], "mentor_id": ctx["mentor_id"]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_package_sent_when_test_passed(new_client, clock):
    ctx = await setup(new_client)
    eid = await enroll(ctx)
    assert (await ctx["intern"].post(f"{IN}/enrollments/{eid}/steps/{ctx['step']}/done")).status_code == 200
    mine = [n for n in await notes(ctx["intern"]) if n["kind"] == "internship.package"]
    assert mine and "F41" in mine[0]["body"]["uz"] and "Chilonzor 5" in mine[0]["body"]["uz"] and "Trener" in mine[0]["body"]["uz"]
    boss = [n for n in await notes(ctx["mudir"]) if n["kind"] == "internship.package"]
    assert boss and "Stajyor1 X keladi" in boss[0]["body"]["uz"]
    # HR qayta yubora oladi, begona yo'q
    assert (await ctx["hrd"].post(f"{IN}/enrollments/{eid}/package")).json()["sent"] >= 2
    assert (await ctx["other"].post(f"{IN}/enrollments/{eid}/package")).status_code in (403, 404)


async def test_daily_feedback_and_day7_decision(new_client, clock):
    ctx = await setup(new_client)
    eid = await enroll(ctx)
    d = (await ctx["intern"].get(f"{IN}/enrollments/{eid}/daily")).json()
    assert d["today"] == 1 and len(d["days"]) == 7 and d["can"]["report"] and not d["can"]["decide"]
    # kelajak kuni uchun hisobot yo'q; 1-kun mumkin; boshqa stajyor yozolmaydi
    assert (await ctx["intern"].put(f"{IN}/enrollments/{eid}/daily/2", json={"seen": "x"})).json()["detail"]["code"] == "day_invalid"
    assert (await ctx["other"].put(f"{IN}/enrollments/{eid}/daily/1", json={"seen": "x"})).status_code in (403, 404)
    assert (await ctx["intern"].put(f"{IN}/enrollments/{eid}/daily/1", json={"seen": "Kassa", "understood": "Qoidalar", "done": "Tovar qabul"})).status_code == 200

    # fidbek: trener, filial mudiri; stajyorning o'zi va begona yozolmaydi
    assert (await ctx["mentor"].post(f"{IN}/enrollments/{eid}/daily/1/feedback", json={"text": "Yaxshi"})).json()["role"] == "trainer"
    assert (await ctx["mudir"].post(f"{IN}/enrollments/{eid}/daily/1/feedback", json={"text": "Vaqtida keldi"})).json()["role"] == "zav"
    assert (await ctx["intern"].post(f"{IN}/enrollments/{eid}/daily/1/feedback", json={"text": "Men"})).status_code == 403
    day1 = (await ctx["hrd"].get(f"{IN}/enrollments/{eid}/daily")).json()["days"][0]
    assert day1["done"] == "Tovar qabul" and {f["role"] for f in day1["feedback"]} == {"trainer", "zav"}

    # qaror: faqat boshqaruvchi; "mos emas" uchun izoh shart
    assert (await ctx["mentor"].post(f"{IN}/enrollments/{eid}/decision", json={"decision": "fit"})).status_code == 403
    assert (await ctx["hrd"].post(f"{IN}/enrollments/{eid}/decision", json={"decision": "not_fit"})).json()["detail"]["code"] == "note_required"
    r = await ctx["hrd"].post(f"{IN}/enrollments/{eid}/decision", json={"decision": "fit", "note": "Mos"})
    assert r.status_code == 200 and r.json()["next_enrollment_id"] and not r.json()["onboarding_program_missing"]
    assert (await ctx["hrd"].post(f"{IN}/enrollments/{eid}/decision", json={"decision": "fit"})).json()["detail"]["code"] == "already_decided"
    async with SessionLocal() as s:
        nxt = await s.get(InternshipEnrollment, r.json()["next_enrollment_id"])
        assert nxt.phase == "onboarding" and nxt.program_id == ctx["onb"] and nxt.due_date == T0.date() + timedelta(days=90) and nxt.mentor_id == ctx["mentor_id"]
        assert (await s.get(InternshipEnrollment, eid)).status == "completed"
    assert any(n["kind"] == "internship.onboarding" for n in await notes(ctx["intern"]))


async def test_not_fit_cancels(new_client, clock):
    ctx = await setup(new_client)
    eid = await enroll(ctx)
    r = await ctx["hrd"].post(f"{IN}/enrollments/{eid}/decision", json={"decision": "not_fit", "note": "Tayyor emas"})
    assert r.status_code == 200 and r.json()["next_enrollment_id"] is None
    assert (await ctx["hrd"].get(f"{IN}/enrollments/{eid}")).json()["status"] == "cancelled"


async def test_classes_and_attendance(new_client, clock):
    ctx = await setup(new_client)
    body = {"title": "Erkin savdoga tayyorlash", "kind": "lesson", "starts_at": "2026-11-05T15:00:00+05:00", "place": "O'quv xona", "trainer_id": ctx["mentor_id"], "employee_ids": [ctx["emp1"], ctx["emp2"]]}
    assert (await ctx["intern"].post(f"{IN}/classes", json=body)).status_code == 403
    r = await ctx["hrd"].post(f"{IN}/classes", json=body)
    assert r.status_code == 201 and r.json()["count"] == 2
    cid = r.json()["id"]
    inv = [n for n in await notes(ctx["intern"]) if n["kind"] == "class.invite"]
    assert inv and "05.11.2026 15:00" in inv[0]["body"]["uz"]
    assert any(n["kind"] == "class.invite" for n in await notes(ctx["mudir"]))

    assert len((await ctx["intern"].get(f"{IN}/classes")).json()) == 1
    # qatnashuvni faqat trener/HR belgilaydi
    marks = {"marks": [{"employee_id": ctx["emp1"], "present": True}, {"employee_id": ctx["emp2"], "present": False}]}
    assert (await ctx["intern"].post(f"{IN}/classes/{cid}/attendance", json=marks)).status_code == 403
    assert (await ctx["mentor"].post(f"{IN}/classes/{cid}/attendance", json=marks)).json() == {"absent": 1}
    assert any(n["kind"] == "class.absent" and "Stajyor2" in n["body"]["uz"] for n in await notes(ctx["mudir"]))
    got = (await ctx["hrd"].get(f"{IN}/classes/{cid}")).json()
    assert got["present"] == 1 and got["attendance_marked_at"]
    assert (await ctx["mentor"].post(f"{IN}/classes/{cid}/attendance", json={"marks": [{"employee_id": 999, "present": True}]})).json()["detail"]["code"] == "marks_invalid"


async def test_kadr_flow(new_client, clock):
    ctx = await setup(new_client)
    kadr, _ = await as_user(new_client, "kadrovik", "hr_menejer")
    async with SessionLocal() as s:
        emp = (await s.scalars(select(Employee).where(Employee.id == ctx["emp1"]))).one()
        emp.hire_date = date.today()
        await s.commit()
    assert (await ctx["intern"].get("/api/v1/kadr")).status_code == 403
    rows = (await kadr.get("/api/v1/kadr")).json()
    assert rows[0]["employee_id"] == ctx["emp1"] and rows[0]["status"] == "waiting_docs"
    assert (await kadr.post(f"/api/v1/kadr/{ctx['emp1']}/order", json={})).json()["detail"]["code"] == "docs_required"
    assert (await kadr.post(f"/api/v1/kadr/{ctx['emp1']}/docs", json={"note": "Pasport, diplom"})).status_code == 200
    assert (await kadr.post(f"/api/v1/kadr/{ctx['emp1']}/docs", json={})).json()["detail"]["code"] == "already_decided"
    assert any(n["kind"] == "kadr.docs" for n in await notes(ctx["intern"]))
    assert (await kadr.post(f"/api/v1/kadr/{ctx['emp1']}/order", json={"order_no": "17-k"})).status_code == 200
    assert (await kadr.get("/api/v1/kadr")).json()[0]["status"] == "order_ready"
    assert any(n["kind"] == "kadr.order" and "17-k" in n["body"]["uz"] for n in await notes(ctx["mudir"]))
