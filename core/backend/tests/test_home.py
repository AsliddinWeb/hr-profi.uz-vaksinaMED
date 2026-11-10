from datetime import date, timedelta

import pytest

from app.db import SessionLocal
from app.models.answers import LeaveRequest
from app.models.employees import Employee
from app.models.tasks import Task
from app.timeutil import now
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


async def test_home_overview_sections(new_client):
    await make_user("hrh", "hr_direktor")
    hr = new_client()
    assert (await login(hr, "hrh")).status_code == 200
    today = date.today()
    async with SessionLocal() as s:
        e = Employee(last_name="A", first_name="Bir", full_name="A Bir", hire_date=today - timedelta(days=100))
        s.add(e)
        await s.flush()
        s.add(LeaveRequest(employee_id=e.id, kind="day", reason_type="family", start_date=today, end_date=today + timedelta(days=1), status="approved", submitted_at=now()))
        s.add(LeaveRequest(employee_id=e.id, kind="day", reason_type="sick", start_date=today + timedelta(days=3), end_date=today + timedelta(days=3), status="pending_hr", submitted_at=now()))
        s.add(Task(title="T1", status="done", completed_at=now()))
        s.add(Task(title="T2", status="todo", due_at=now() - timedelta(days=1)))
        await s.commit()
    r = await hr.get("/api/v1/home/overview")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["answers"]["on_leave_today"] == 1 and d["answers"]["pending"] == 1
    assert d["tasks"]["done"] == 1 and d["tasks"]["overdue"] == 1 and d["tasks"]["done_rate"] == 50
    assert len(d["tasks"]["trend"]) == 7 and d["tasks"]["trend"][-1]["done"] == 1
    assert "today" in d["attendance"] and len(d["attendance"]["trend"]) == 7
    assert any(step["key"] == "requests" for step in d["chain"])
    assert "letters_open" in d["problems"]

    await make_user("plain", "farmasevt")
    emp = new_client()
    assert (await login(emp, "plain")).status_code == 200
    d2 = (await emp.get("/api/v1/home/overview")).json()
    assert "attendance" not in d2 and "problems" not in d2
