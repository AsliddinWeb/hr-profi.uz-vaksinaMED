from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.answers import LeaveRequest
from app.models.employees import Employee
from app.services import answers as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

A = "/api/v1/answers"
T0 = datetime(2026, 11, 2, 10, 0, tzinfo=tz())  # dushanba 10:00


@pytest.fixture
def clock(monkeypatch):
    state = {"t": T0}
    fn = lambda: state["t"]  # noqa: E731
    monkeypatch.setattr("app.api.answers.now", fn)
    monkeypatch.setattr("app.api.attendance.now", fn)
    monkeypatch.setattr("app.services.attendance.now", fn)
    return state


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def setup(new_client, *, with_coordinator=True):
    """HR, koordinator (filial koordinatori), xodim (farmasevt)."""
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    coord, coord_id = await as_user(new_client, "coord", "koordinator")
    emp, emp_uid = await as_user(new_client, "ali", "farmasevt")
    branch = (
        await hr.post("/api/v1/branches", json={"number": 5, "name": "F5", **({"coordinator_user_id": coord_id} if with_coordinator else {})})
    ).json()
    async with SessionLocal() as s:
        e = Employee(last_name="Aliyev", first_name="Ali", full_name="Aliyev Ali", user_id=emp_uid, branch_id=branch["id"], status="active")
        s.add(e)
        await s.commit()
        emp_id = e.id
    return {"hr": hr, "coord": coord, "emp": emp, "coord_id": coord_id, "emp_id": emp_id, "emp_uid": emp_uid, "branch": branch}


def day_req(**kw):
    return {"kind": "day", "reason_type": "family", "reason": "Oilaviy sabab", "start_date": "2026-11-04", "end_date": "2026-11-05", **kw}


async def notifications(c):
    return (await c.get("/api/notifications")).json()


async def test_routing_to_coordinator_and_approval(new_client, clock):
    ctx = await setup(new_client)
    r = await ctx["emp"].post(f"{A}/requests", json=day_req())
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending_coordinator" and req["escalate_at"] and req["can_cancel"]
    rid = req["id"]

    # koordinatorga bildirishnoma, inboxda ko'rinadi
    inbox = (await ctx["coord"].get(f"{A}/requests", params={"scope": "inbox"})).json()
    assert [i["id"] for i in inbox["items"]] == [rid] and inbox["items"][0]["can_decide"]
    assert (await ctx["coord"].get(f"{A}/inbox/count")).json() == {"count": 1}
    assert (await ctx["emp"].get(f"{A}/inbox/count")).json() == {"count": 0}

    # xodim o'zi qaror chiqara olmaydi; rad uchun izoh shart
    assert (await ctx["emp"].post(f"{A}/requests/{rid}/decision", json={"action": "approve"})).status_code == 403
    r = await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "reject"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "note_required"

    r = await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "approve", "note": "Mayli"})
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_level"] == "coordinator"
    assert (await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "reject", "note": "x"})).json()["detail"]["code"] == "already_decided"

    d = (await ctx["emp"].get(f"{A}/requests/{rid}")).json()
    assert [e["action"] for e in d["events"]] == ["submitted", "approved"] and d["coordinator"] == "Coord"
    assert (await ctx["hr"].get("/api/v1/audit", params={"action": "answers.approved"})).json()["total"] == 1


async def test_direct_to_hr_without_coordinator(new_client, clock):
    ctx = await setup(new_client, with_coordinator=False)
    req = (await ctx["emp"].post(f"{A}/requests", json=day_req())).json()
    assert req["status"] == "pending_hr" and req["escalate_at"] is None
    assert (await ctx["coord"].get(f"{A}/requests/{req['id']}")).status_code == 404  # unga tegishli emas
    assert (await ctx["hr"].get(f"{A}/inbox/count")).json() == {"count": 1}
    r = await ctx["hr"].post(f"{A}/requests/{req['id']}/decision", json={"action": "reject", "note": "Smenada odam yetmaydi"})
    assert r.json()["status"] == "rejected" and r.json()["decided_level"] == "hr"


async def test_escalation_after_8_hours(new_client, clock):
    ctx = await setup(new_client)
    rid = (await ctx["emp"].post(f"{A}/requests", json=day_req())).json()["id"]

    async def run(at):
        async with SessionLocal() as s:
            due, notes = await svc.escalate_due(s, at)
            await s.commit()
            return len(due), notes

    # 7 soat 59 daqiqada hali eskalatsiya yo'q
    n, _ = await run(T0 + timedelta(hours=8) - timedelta(minutes=1))
    assert n == 0
    assert (await ctx["hr"].get(f"{A}/requests/{rid}")).json()["status"] == "pending_coordinator"

    n, notes = await run(T0 + timedelta(hours=8))
    assert n == 1 and {x.kind for x in notes} == {"answers.escalated", "answers.escalated_employee"}
    d = (await ctx["hr"].get(f"{A}/requests/{rid}")).json()
    assert d["status"] == "pending_hr" and d["escalated_at"] and [e["action"] for e in d["events"]] == ["submitted", "escalated"]
    assert get_settings().answers_escalation_hours == 8

    # qayta ishga tushirsa takrorlanmaydi; koordinator endi qaror chiqara olmaydi, HR chiqara oladi
    assert (await run(T0 + timedelta(hours=20)))[0] == 0
    assert (await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "approve"})).status_code in (403, 404)
    assert (await ctx["coord"].get(f"{A}/inbox/count")).json() == {"count": 0}
    assert (await ctx["hr"].post(f"{A}/requests/{rid}/decision", json={"action": "approve"})).json()["status"] == "approved"

    # tasdiqlangan so'rov eskalatsiya qilinmaydi
    async with SessionLocal() as s:
        r = await s.get(LeaveRequest, rid)
        assert r.escalate_at is None


async def test_decision_before_deadline_prevents_escalation(new_client, clock):
    ctx = await setup(new_client)
    rid = (await ctx["emp"].post(f"{A}/requests", json=day_req())).json()["id"]
    await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "approve"})
    async with SessionLocal() as s:
        due, _ = await svc.escalate_due(s, T0 + timedelta(days=3))
    assert due == []


async def test_validation_and_overlap(new_client, clock):
    ctx = await setup(new_client)
    e = ctx["emp"]
    r = await e.post(f"{A}/requests", json=day_req(start_date="2026-10-01", end_date="2026-10-02"))
    assert r.json()["detail"]["code"] == "date_too_old"
    assert (await e.post(f"{A}/requests", json=day_req(start_date="2026-11-10", end_date="2026-11-05"))).json()["detail"]["code"] == "range_invalid"
    assert (await e.post(f"{A}/requests", json=day_req(start_date="2026-11-10", end_date="2026-12-31"))).json()["detail"]["code"] == "range_too_long"
    assert (await e.post(f"{A}/requests", json=day_req(reason_type="other", reason="x"))).status_code == 422
    h = {"kind": "hourly", "reason_type": "personal", "start_date": "2026-11-03"}
    assert (await e.post(f"{A}/requests", json={**h, "start_time": "15:00", "end_time": "14:00"})).json()["detail"]["code"] == "time_invalid"
    assert (await e.post(f"{A}/requests", json={**h, "start_time": "15:00", "end_time": "15:05"})).json()["detail"]["code"] == "hourly_length"

    assert (await e.post(f"{A}/requests", json={**h, "start_time": "15:00", "end_time": "17:00"})).status_code == 201
    # vaqt kesishadi / kesishmaydi
    assert (await e.post(f"{A}/requests", json={**h, "start_time": "16:00", "end_time": "18:00"})).json()["detail"]["code"] == "overlap"
    assert (await e.post(f"{A}/requests", json={**h, "start_time": "17:00", "end_time": "18:00"})).status_code == 201
    # kunlik so'rov o'sha sanaga to'g'ri kelsa
    assert (await e.post(f"{A}/requests", json=day_req(start_date="2026-11-02", end_date="2026-11-03"))).json()["detail"]["code"] == "overlap"
    # o'tgan sana (7 kun ichida) mumkin
    assert (await e.post(f"{A}/requests", json=day_req(reason_type="sick", start_date="2026-10-28", end_date="2026-10-29"))).status_code == 201


async def test_cancel_rules(new_client, clock):
    ctx = await setup(new_client)
    rid = (await ctx["emp"].post(f"{A}/requests", json=day_req())).json()["id"]
    assert (await ctx["coord"].post(f"{A}/requests/{rid}/cancel")).status_code in (403, 404)
    r = await ctx["emp"].post(f"{A}/requests/{rid}/cancel")
    assert r.json()["status"] == "cancelled"
    assert (await ctx["emp"].post(f"{A}/requests/{rid}/cancel")).json()["detail"]["code"] == "cannot_cancel"
    # bekor qilingach sana bo'shaydi
    assert (await ctx["emp"].post(f"{A}/requests", json=day_req())).status_code == 201
    # tasdiqlangan, lekin boshlanmagan so'rovni bekor qilish mumkin; boshlangan bo'lsa yo'q
    rid2 = (await ctx["emp"].post(f"{A}/requests", json=day_req(start_date="2026-11-02", end_date="2026-11-02", kind="day"))).json()["id"]
    await ctx["hr"].post(f"{A}/requests/{rid2}/decision", json={"action": "approve"})
    assert (await ctx["emp"].post(f"{A}/requests/{rid2}/cancel")).json()["detail"]["code"] == "cannot_cancel"


async def test_visibility_calendar_and_notifications(new_client, clock):
    ctx = await setup(new_client)
    other, other_uid = await as_user(new_client, "bob", "farmasevt")
    rid = (await ctx["emp"].post(f"{A}/requests", json=day_req())).json()["id"]
    assert (await other.get(f"{A}/requests/{rid}")).status_code == 404
    assert (await other.get(f"{A}/requests", params={"scope": "all"})).json()["total"] == 0
    assert (await other.get(f"{A}/requests", params={"scope": "inbox"})).status_code == 403
    assert (await ctx["emp"].get(f"{A}/requests", params={"scope": "mine"})).json()["total"] == 1

    cal = (await ctx["hr"].get(f"{A}/calendar", params={"month": "2026-11"})).json()
    assert [i["employee"]["full_name"] for i in cal["items"]] == ["Aliyev Ali"] and cal["items"][0]["status"] == "pending_coordinator"
    assert (await other.get(f"{A}/calendar", params={"month": "2026-11"})).json()["items"] == []
    assert (await ctx["hr"].get(f"{A}/calendar", params={"month": "2026-12"})).json()["items"] == []

    n_coord = [n["kind"] for n in (await ctx["coord"].get("/api/v1/notifications")).json()["items"]]
    assert "answers.new" in n_coord
    await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "reject", "note": "Smena band"})
    n_emp = (await ctx["emp"].get("/api/v1/notifications")).json()["items"]
    assert n_emp[0]["kind"] == "answers.rejected" and "Smena band" in n_emp[0]["body"]["uz"]


async def test_approved_leave_shows_in_attendance(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    shift = (await hr.post("/api/v1/schedule/shifts", json={"name": "K", "start_time": "09:00", "end_time": "18:00"})).json()
    await hr.post("/api/v1/schedule/groups", json={"name": "Ofis", "default_shift_id": shift["id"], "weekly_off_days": [6], "is_default": True})
    rid = (await ctx["emp"].post(f"{A}/requests", json=day_req(start_date="2026-11-03", end_date="2026-11-04"))).json()["id"]
    clock["t"] = T0 + timedelta(days=5)  # 7-noyabr
    q = {"start": "2026-11-02", "end": "2026-11-05"}
    sheet = (await hr.get("/api/v1/attendance/timesheet", params=q)).json()["rows"][0]
    assert [c["status"] for c in sheet["cells"]] == ["absent", "absent", "absent", "absent"]  # hali tasdiqlanmagan

    await ctx["coord"].post(f"{A}/requests/{rid}/decision", json={"action": "approve"})
    sheet = (await hr.get("/api/v1/attendance/timesheet", params=q)).json()["rows"][0]
    assert [c["status"] for c in sheet["cells"]] == ["absent", "leave", "leave", "absent"]
    assert sheet["totals"]["absent"] == 2  # ruxsatli kunlar kelmagan hisoblanmaydi
    dash = (await hr.get("/api/v1/attendance/dashboard", params=q)).json()
    assert dash["kpis"]["absent"] == 2 and dash["statuses"]["leave"] == 2


async def test_permissions_matrix(new_client, clock):
    ctx = await setup(new_client)
    mgr, _ = await as_user(new_client, "m", "hr_menejer")
    assert (await mgr.get(f"{A}/requests", params={"scope": "all"})).status_code == 200
    stajyor, _ = await as_user(new_client, "s", "stajyor")
    assert (await stajyor.post(f"{A}/requests/1/decision", json={"action": "approve"})).status_code == 403
    # xodim kartasi yo'q foydalanuvchi so'rov yubora olmaydi
    r = await stajyor.post(f"{A}/requests", json=day_req())
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_employee_profile"
    async with SessionLocal() as s:
        assert (await s.scalar(select(LeaveRequest.id))) is None
    assert ctx
