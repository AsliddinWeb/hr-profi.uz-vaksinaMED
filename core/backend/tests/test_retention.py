from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.auth import User
from app.models.employees import Employee
from app.models.retention import RetentionCase
from app.models.tasks import Task
from app.services import retention as svc
from app.timeutil import now, tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

RT = "/api/v1/retention"
OF = "/api/v1/offboarding"
CT = "/api/v1/control"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


async def setup(new_client):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    hr, hr_id = await as_user(new_client, "hrm", "hr_menejer")
    aud, _ = await as_user(new_client, "auditor", "hr_auditor")
    mudir, mudir_id = await as_user(new_client, "mudir", "mudir")
    stranger, _ = await as_user(new_client, "mudir2", "mudir")
    far, far_uid = await as_user(new_client, "far", "farmasevt")
    branch = (await hrd.post("/api/v1/branches", json={"number": 61, "name": "F61", "manager_user_id": mudir_id})).json()
    async with SessionLocal() as s:
        e = Employee(last_name="Far", first_name="X", full_name="Far X", user_id=far_uid, status="active", branch_id=branch["id"], hire_date=date(2026, 1, 1))
        s.add(e)
        await s.commit()
        emp = e.id
    return {"hrd": hrd, "hr": hr, "hr_id": hr_id, "aud": aud, "mudir": mudir, "stranger": stranger, "far": far, "emp": emp}


async def test_case_flow_stay(new_client):
    ctx = await setup(new_client)
    body = {"employee_id": ctx["emp"], "risk_level": "high", "note": "Boshqa ish qidiryapti"}
    assert (await ctx["stranger"].post(f"{RT}/cases", json=body)).status_code == 403  # boshqa filial mudiri
    assert (await ctx["far"].post(f"{RT}/cases", json=body)).status_code == 403
    r = await ctx["mudir"].post(f"{RT}/cases", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await ctx["mudir"].post(f"{RT}/cases", json=body)).json()["detail"]["code"] == "case_exists"
    assert any(n["kind"] == "retention.new" for n in await notes(ctx["hr"]))
    assert (await ctx["stranger"].get(f"{RT}/cases/{cid}")).status_code == 404
    assert [c["id"] for c in (await ctx["mudir"].get(f"{RT}/cases")).json()] == [cid]
    assert (await ctx["stranger"].get(f"{RT}/cases")).json() == []

    # suhbatsiz "qoladi" qarori yo'q; faqat HR suhbat/qaror; auditor faqat xulosa yoza oladi
    assert (await ctx["mudir"].post(f"{RT}/cases/{cid}/interview", json={"note": "Suhbat"})).status_code == 403
    assert (await ctx["hr"].post(f"{RT}/cases/{cid}/decide", json={"decision": "stay"})).json()["detail"]["code"] == "interview_required"
    assert (await ctx["hr"].post(f"{RT}/cases/{cid}/interview", json={"note": "Maosh past, ko'tarish va'da qilindi"})).status_code == 200
    assert (await ctx["aud"].post(f"{RT}/cases/{cid}/audit", json={"note": "Konflikt yo'q"})).status_code == 200
    assert (await ctx["aud"].post(f"{RT}/cases/{cid}/decide", json={"decision": "stay"})).status_code == 403
    r = await ctx["hr"].post(f"{RT}/cases/{cid}/decide", json={"decision": "stay", "note": "Qoladi"})
    assert r.status_code == 200 and r.json()["status"] == "retained" and r.json()["offboarding_id"] is None
    assert [e["action"] for e in r.json()["events"]] == ["created", "hr", "auditor", "decision"]
    assert (await ctx["hr"].post(f"{RT}/cases/{cid}/decide", json={"decision": "leave"})).json()["detail"]["code"] == "already_decided"
    assert any(n["kind"] == "retention.decided" for n in await notes(ctx["mudir"]))


async def test_leave_decision_offboarding_and_completion(new_client):
    ctx = await setup(new_client)
    cid = (await ctx["mudir"].post(f"{RT}/cases", json={"employee_id": ctx["emp"], "note": "Ariza berdi", "notice_date": "2026-10-01", "planned_leave_date": "2026-10-20"})).json()
    assert cid["source"] == "notice" and cid["risk_level"] == "high"
    r = await ctx["hr"].post(f"{RT}/cases/{cid['id']}/decide", json={"decision": "leave", "note": "Ketadi"})
    oid = r.json()["offboarding_id"]
    assert r.json()["status"] == "leaving" and oid
    assert any(n["kind"] == "offboarding.opened" for n in await notes(ctx["hrd"]))

    # exit-intervyusiz yopib bo'lmaydi; sabab va xavf turlari tekshiriladi
    assert (await ctx["hrd"].post(f"{OF}/{oid}/complete", json={"leave_date": "2026-10-20"})).json()["detail"]["code"] == "exit_required"
    assert (await ctx["hr"].post(f"{OF}/{oid}/exit", json={"reason_type": "salary", "reason_text": "Maosh past", "risks": ["xato"]})).json()["detail"]["code"] == "risk_invalid"
    r = await ctx["hr"].post(f"{OF}/{oid}/exit", json={"reason_type": "salary", "reason_text": "Maosh past", "prevent_text": "Bonusni qayta ko'rish", "risks": ["understaff", "others_leaving"]})
    assert r.status_code == 200 and r.json()["risks"] == ["understaff", "others_leaving"]
    assert any(n["kind"] == "offboarding.reasons" for n in await notes(ctx["hrd"]))

    # choralar -> topshiriqlar (Nazorat belgisi bilan)
    r = await ctx["hr"].post(f"{OF}/{oid}/measures", json={"measures": [{"title": "Bonus tizimini ko'rib chiqish", "assignee_id": ctx["hr_id"], "due_at": "2026-10-05T10:00:00+05:00"}]})
    assert r.status_code == 201 and r.json()["added"] == 1
    async with SessionLocal() as s:
        t = (await s.scalars(select(Task))).one()
        assert "nazorat" in t.labels and f"offboarding-{oid}" in t.labels
    got = (await ctx["hrd"].get(f"{OF}/{oid}")).json()
    assert got["measures"][0]["status"] == "todo" and got["can"]["approve"]

    # HRD tasdiqlaydi (HR tasdiqlay olmaydi); yakunlash: faqat bo'shatish huquqi bor rol
    assert (await ctx["hr"].post(f"{OF}/{oid}/approve")).status_code == 403
    assert (await ctx["hrd"].post(f"{OF}/{oid}/approve")).status_code == 200
    assert (await ctx["hr"].post(f"{OF}/{oid}/complete", json={"leave_date": "2026-10-20"})).status_code == 200
    async with SessionLocal() as s:
        emp = await s.get(Employee, ctx["emp"])
        user = await s.get(User, emp.user_id)
        assert emp.status == "dismissed" and user.is_active is False
    assert any(n["kind"] == "offboarding.done" for n in await notes(ctx["hrd"]))
    assert (await login(ctx["far"], "far")).status_code != 200  # dostup yopilgan

    # sabablar bazasi
    a = (await ctx["hrd"].get(f"{OF}/analytics", params={"start": "2026-01-01", "end": "2026-12-31"})).json()
    assert a["total"] == 1 and a["reasons"] == {"salary": 1} and a["risks"]["understaff"] == 1 and a["branches"] == {"F61": 1}
    assert (await ctx["far"].get(f"{OF}/analytics", params={"start": "2026-01-01", "end": "2026-12-31"})).status_code in (401, 403)


async def test_meetings_and_control_overview(new_client):
    ctx = await setup(new_client)
    cid = (await ctx["mudir"].post(f"{RT}/cases", json={"employee_id": ctx["emp"], "note": "Charchagan"})).json()["id"]
    # holat 10 kun oldin yaratilgan deb olamiz
    async with SessionLocal() as s:
        c = await s.get(RetentionCase, cid)
        c.created_at = now() - timedelta(days=10)
        await s.commit()
    ov = (await ctx["aud"].get(f"{CT}/overview")).json()
    assert ov["counts"]["interview_overdue"] == 1 and ov["counts"]["decision_overdue"] == 1 and ov["counts"]["no_meeting"] == 1 and ov["meeting"]["due"]
    assert (await ctx["mudir"].get(f"{CT}/overview")).status_code == 403

    r = await ctx["hr"].post(f"{RT}/meetings", json={"held_on": date.today().isoformat(), "summary": "Muhokama: bonus", "case_ids": [cid]})
    assert r.status_code == 201 and r.json()["cases"] == 1
    assert (await ctx["mudir"].post(f"{RT}/meetings", json={"held_on": "2026-10-20", "summary": "x yy"})).status_code == 403
    ov = (await ctx["aud"].get(f"{CT}/overview")).json()
    assert ov["counts"]["no_meeting"] == 0 and not ov["meeting"]["due"]
    assert any(n["kind"] == "retention.meeting" for n in await notes(ctx["aud"]))
    assert len((await ctx["aud"].get(f"{RT}/meetings")).json()) == 1


async def test_auto_scan_creates_cases_for_low_score(new_client):
    await setup(new_client)
    async with SessionLocal() as s:
        moment = datetime(2026, 11, 2, 7, 0, tzinfo=tz())

        async def low(*_a, **_k):
            return {"score": 30.0, "components": [{"key": "a", "value": 30, "weight": 1, "available": True}, {"key": "b", "value": 30, "weight": 1, "available": True}]}

        svc.growth.employee_score, orig = low, svc.growth.employee_score
        try:
            created, notes_ = await svc.auto_scan(s, moment)
        finally:
            svc.growth.employee_score = orig
        await s.commit()
        assert created == 1 and notes_
        again, _ = await svc.auto_scan(s, moment)  # takror yaratilmaydi
        assert again == 0
        case = (await s.scalars(select(RetentionCase))).one()
        assert case.source == "auto" and "30" in case.note
