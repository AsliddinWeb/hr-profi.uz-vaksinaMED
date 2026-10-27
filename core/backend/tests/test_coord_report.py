from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.attendance_issues import AttendanceExplanation
from app.models.employees import Employee
from app.services import coord_report as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

API = "/api/v1/coord-report"
T0 = datetime(2026, 11, 3, 20, 0, tzinfo=tz())  # seshanba 20:00


@pytest.fixture
def clock(monkeypatch):
    fn = lambda: T0  # noqa: E731
    for target in ("app.api.coord_report.now", "app.api.attendance.now", "app.services.attendance.now"):
        monkeypatch.setattr(target, fn)


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    coord, coord_id = await as_user(new_client, "coord", "koordinator")
    other, _ = await as_user(new_client, "coord2", "koordinator")
    branch = (await hr.post("/api/v1/branches", json={"number": 3, "name": "F3", "coordinator_user_id": coord_id})).json()
    shift = (await hr.post("/api/v1/schedule/shifts", json={"name": "2-smena", "start_time": "17:00", "end_time": "23:59", "late_grace_minutes": 0})).json()
    await hr.post("/api/v1/schedule/groups", json={"name": "Dorixona", "default_shift_id": shift["id"], "weekly_off_days": [6], "is_default": True})
    ids = {}
    async with SessionLocal() as s:
        for key, name in (("absent", "Kelmagan Ali"), ("late", "Kech Vali"), ("ok", "Vaqtli Soli")):
            e = Employee(last_name=name.split()[0], first_name=name.split()[1], full_name=name, branch_id=branch["id"], status="active")
            s.add(e)
            await s.flush()
            ids[key] = e.id
        day = T0.date()
        start = datetime(2026, 11, 3, 17, 0, tzinfo=tz())
        for key, arrived, late in (("late", start + timedelta(minutes=22), 22), ("ok", start, 0)):
            s.add(AttendanceRecord(employee_id=ids[key], work_date=day, shift_id=shift["id"], planned_start=start, planned_end=start + timedelta(hours=7), check_in_at=arrived, in_method="qr", late_minutes=late, track_lateness=True))
        # Kelmagan xodim kecha ham kelmagan edi
        await s.commit()
    return {"hr": hr, "coord": coord, "other": other, "ids": ids, "branch": branch}


async def test_report_groups_and_explanations(new_client, clock):
    ctx = await setup(new_client)
    r = await ctx["coord"].get(API)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["coordinators"]) == 1
    sh = data["coordinators"][0]["shifts"]
    assert len(sh) == 1 and sh[0]["name"] == "2-smena" and sh[0]["start"] == "17:00"
    assert [x["full_name"] for x in sh[0]["absent"]] == ["Kelmagan Ali"]
    assert [(x["full_name"], x["arrived"]) for x in sh[0]["late"]] == [("Kech Vali", "17:22")]
    assert data["coordinators"][0]["absent"] == 1 and data["coordinators"][0]["late"] == 1

    # boshqa koordinatorga bu filial ko'rinmaydi; HR hammasini ko'radi
    assert (await ctx["other"].get(API)).json()["coordinators"] == []
    assert len((await ctx["hr"].get(API)).json()["coordinators"]) == 1

    # matn: mijoz shabloni
    async with SessionLocal() as s:
        rep = await svc.build(s, T0.date(), T0)
        text = svc.render_text(rep, rep["coordinators"][0], "uz")
    assert "2-smena (17:00–23:59): 2 kishi" in text and "Kelmaganlar: 1" in text and "Kechikkanlar: 1" in text and "jarima" in text

    # izoh: faqat o'z koordinatori yoki HR; sabab va chora majburiy
    body = {"employee_id": ctx["ids"]["absent"], "work_date": "2026-11-03", "kind": "absent", "reason": "Kasal bo'lgan", "measures": "Ogohlantirildi"}
    assert (await ctx["other"].post(f"{API}/explain", json=body)).status_code == 403
    assert (await ctx["coord"].post(f"{API}/explain", json={**body, "measures": ""})).status_code == 422
    r = await ctx["coord"].post(f"{API}/explain", json=body)
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    # hisobotda yo'q holatga izoh yozib bo'lmaydi
    assert (await ctx["coord"].post(f"{API}/explain", json={**body, "employee_id": ctx["ids"]["ok"]})).status_code == 404
    again = (await ctx["coord"].get(API)).json()
    assert again["coordinators"][0]["shifts"][0]["absent"][0]["explanation"]["status"] == "submitted"


async def test_send_creates_explanations_and_overdue(new_client, clock):
    ctx = await setup(new_client)
    assert (await ctx["coord"].post(f"{API}/send")).status_code == 403
    r = await ctx["hr"].post(f"{API}/send")
    assert r.status_code == 200 and r.json()["sent"] == 2  # koordinatorga + HR ga
    async with SessionLocal() as s:
        rows = (await s.scalars(select(AttendanceExplanation))).all()
        assert {(x.kind, x.status) for x in rows} == {("absent", "pending"), ("late", "pending")}
        assert all(x.due_at == T0 + timedelta(hours=svc.EXPLAIN_HOURS) for x in rows)
        # qayta yuborilsa takrorlanmaydi
        rep = await svc.build(s, T0.date(), T0)
        assert await svc.sync_explanations(s, rep, T0) == 0
        # muddat o'tmaguncha xabar yo'q, o'tgach bir marta
        assert await svc.overdue_check(s, T0 + timedelta(hours=23)) == []
        notes = await svc.overdue_check(s, T0 + timedelta(hours=25))
        assert len(notes) == 2 and {n.kind for n in notes} == {"coord_report.overdue"}
        assert await svc.overdue_check(s, T0 + timedelta(hours=30)) == []
