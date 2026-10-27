from datetime import datetime

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.attendance import AttendanceCorrection, AttendanceRecord
from app.models.employees import Employee
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

A = "/api/v1/attendance-issues"
T0 = datetime(2026, 11, 2, 21, 0, tzinfo=tz())  # dushanba 21:00


@pytest.fixture
def clock(monkeypatch):
    fn = lambda: T0  # noqa: E731
    monkeypatch.setattr("app.api.attendance_issues.now", fn)
    monkeypatch.setattr("app.api.attendance.now", fn)
    monkeypatch.setattr("app.services.attendance.now", fn)


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def setup(new_client, *, with_coordinator=True):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    coord, coord_id = await as_user(new_client, "coord", "koordinator")
    emp, emp_uid = await as_user(new_client, "zayn", "farmasevt")
    branch = (await hr.post("/api/v1/branches", json={"number": 7, "name": "F7", **({"coordinator_user_id": coord_id} if with_coordinator else {})})).json()
    async with SessionLocal() as s:
        e = Employee(last_name="Fazliddinov", first_name="Zayniddin", full_name="Fazliddinov Zayniddin", user_id=emp_uid, branch_id=branch["id"], status="active")
        s.add(e)
        await s.commit()
        emp_id = e.id
    return {"hr": hr, "coord": coord, "emp": emp, "emp_id": emp_id}


def body(**kw):
    return {"work_date": "2026-11-02", "kind": "missed_in", "method_tried": "face", "claimed_in": "2026-11-02T17:00:00", "comment": "QR ishlamadi, Face ID o'tmadi", **kw}


async def test_coordinator_then_hr_fixes_record(new_client, clock):
    ctx = await setup(new_client)
    r = await ctx["emp"].post(A, json=body())
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    assert r.json()["status"] == "pending_coordinator" and r.json()["can_cancel"]

    # bir sanaga ikkinchi faol so'rov mumkin emas
    assert (await ctx["emp"].post(A, json=body())).json()["detail"]["code"] == "issue_exists"
    # xodim o'zi qaror chiqara olmaydi; koordinator yakuniy qaror chiqara olmaydi
    assert (await ctx["emp"].post(f"{A}/{iid}/verify", json={"action": "confirm"})).status_code == 403
    assert (await ctx["coord"].post(f"{A}/{iid}/decide", json={"action": "approve"})).status_code == 403

    inbox = (await ctx["coord"].get(A, params={"scope": "inbox"})).json()
    assert [i["id"] for i in inbox["items"]] == [iid] and inbox["items"][0]["can_verify"]
    r = await ctx["coord"].post(f"{A}/{iid}/verify", json={"action": "confirm", "note": "Filialda edi"})
    assert r.status_code == 200 and r.json()["status"] == "pending_hr"

    r = await ctx["hr"].post(f"{A}/{iid}/decide", json={"action": "approve", "note": "QR buzilgan"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert [h["action"] for h in r.json()["history"]] == ["submitted", "verified", "approved"]

    async with SessionLocal() as s:
        rec = (await s.scalars(select(AttendanceRecord).where(AttendanceRecord.employee_id == ctx["emp_id"]))).one()
        assert rec.is_manual and rec.check_in_at.astimezone(tz()).hour == 17 and rec.check_out_at is None
        corr = (await s.scalars(select(AttendanceCorrection).where(AttendanceCorrection.employee_id == ctx["emp_id"]))).one()
        assert corr.action == "create" and f"#{iid}" in corr.reason
    assert (await ctx["hr"].post(f"{A}/{iid}/decide", json={"action": "reject", "note": "x"})).json()["detail"]["code"] == "already_decided"


async def test_wrong_checkout_removes_checkout_and_direct_to_hr(new_client, clock):
    ctx = await setup(new_client, with_coordinator=False)
    async with SessionLocal() as s:
        s.add(AttendanceRecord(employee_id=ctx["emp_id"], work_date=datetime(2026, 11, 2).date(), check_in_at=datetime(2026, 11, 2, 17, 5, tzinfo=tz()), check_out_at=datetime(2026, 11, 2, 20, 30, tzinfo=tz()), in_method="face", out_method="face"))
        await s.commit()
    r = await ctx["emp"].post(A, json={"work_date": "2026-11-02", "kind": "wrong_checkout", "method_tried": "face", "comment": "20:30 da ketish bo'lib yozilgan"})
    assert r.status_code == 201 and r.json()["status"] == "pending_hr"
    iid = r.json()["id"]
    assert (await ctx["hr"].post(f"{A}/{iid}/decide", json={"action": "approve"})).json()["status"] == "approved"
    async with SessionLocal() as s:
        rec = (await s.scalars(select(AttendanceRecord).where(AttendanceRecord.employee_id == ctx["emp_id"]))).one()
        assert rec.check_out_at is None and rec.check_in_at.astimezone(tz()).minute == 5
        assert (await s.scalars(select(AttendanceCorrection).where(AttendanceCorrection.employee_id == ctx["emp_id"]))).one().action == "update"


async def test_validation_reject_and_cancel(new_client, clock):
    ctx = await setup(new_client)
    assert (await ctx["emp"].post(A, json=body(work_date="2026-11-03"))).status_code == 400  # kelajak
    assert (await ctx["emp"].post(A, json=body(work_date="2026-10-01"))).json()["detail"]["code"] == "date_too_old"
    assert (await ctx["emp"].post(A, json={**body(), "claimed_in": None})).status_code == 422  # vaqt shart
    iid = (await ctx["emp"].post(A, json=body())).json()["id"]
    r = await ctx["coord"].post(f"{A}/{iid}/verify", json={"action": "reject"})
    assert r.json()["detail"]["code"] == "note_required"
    r = await ctx["coord"].post(f"{A}/{iid}/verify", json={"action": "reject", "note": "Filialda yo'q edi"})
    assert r.json()["status"] == "rejected"
    assert (await ctx["emp"].post(f"{A}/{iid}/cancel")).json()["detail"]["code"] == "cannot_cancel"
    iid2 = (await ctx["emp"].post(A, json=body())).json()["id"]
    assert (await ctx["emp"].post(f"{A}/{iid2}/cancel")).json()["status"] == "cancelled"
    assert (await ctx["emp"].get(A, params={"scope": "mine"})).json()["total"] == 2
