from datetime import datetime, time

import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.schedule import ShiftTemplate
from app.services import attendance as svc
from app.services import schedule as sched
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

API = "/api/v1/attendance"
SCH = "/api/v1/schedule"
# Branch koordinatasi (Toshkent) va unga yaqin/uzoq nuqtalar
LAT, LNG = 41.311100, 69.279700
NEAR = {"lat": 41.311150, "lng": 69.279750, "accuracy": 20}
FAR = {"lat": 41.330000, "lng": 69.300000, "accuracy": 20}


class Clock:
    def __init__(self):
        self.t = datetime(2026, 11, 2, 9, 0, tzinfo=tz())

    def set(self, text: str):  # "2026-11-02 09:25" (mahalliy)
        self.t = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=tz())

    def __call__(self):
        return self.t


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr("app.services.attendance.now", c)
    monkeypatch.setattr("app.api.attendance.now", c)
    return c


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def setup_basic(new_client, *, shift_kw=None, geo=True):
    """HR, filial, smena, standart guruh va xodim hisobli foydalanuvchi (farmasevt)."""
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    branch = (
        await hr.post("/api/v1/branches", json={"number": 7, "name": "Filial 7", **({"latitude": LAT, "longitude": LNG, "geofence_radius_m": 100} if geo else {})})
    ).json()
    shift = (
        await hr.post(f"{SCH}/shifts", json={"name": "Kunduzgi", "start_time": "09:00", "end_time": "18:00", "break_minutes": 60, "late_grace_minutes": 10, "early_leave_grace_minutes": 5, **(shift_kw or {})})
    ).json()
    group = (
        await hr.post(f"{SCH}/groups", json={"name": "Ofis", "default_shift_id": shift["id"], "weekly_off_days": [6], "is_default": True})
    ).json()
    pc, uid = await as_user(new_client, "ali", "farmasevt")
    async with SessionLocal() as s:
        emp = Employee(last_name="Aliyev", first_name="Ali", full_name="Aliyev Ali", user_id=uid, branch_id=branch["id"], status="active")
        s.add(emp)
        await s.commit()
        emp_id = emp.id
    return hr, pc, {"branch": branch, "shift": shift, "group": group, "emp_id": emp_id}


# --- Unit -----------------------------------------------------------------------------


def test_compute_metrics():
    shift = ShiftTemplate(start_time=time(9), end_time=time(18), break_minutes=60, late_grace_minutes=10,
                          early_leave_grace_minutes=5, track_lateness=True, kind="fixed")  # fmt: skip
    day = datetime(2026, 11, 2).date()
    start, end = svc.planned_window(shift, day)
    at = lambda h, m: datetime(2026, 11, 2, h, m, tzinfo=tz())  # noqa: E731
    m = svc.compute_metrics(shift, start, end, at(9, 10), at(18, 0))
    assert (m.late, m.early, m.worked) == (0, 0, 470)  # imtiyoz ichida
    m = svc.compute_metrics(shift, start, end, at(9, 11), at(17, 54))
    assert (m.late, m.early) == (11, 6)
    flex = ShiftTemplate(start_time=time(8), end_time=time(7), break_minutes=0, late_grace_minutes=0,
                         early_leave_grace_minutes=0, track_lateness=False, kind="flexible")  # fmt: skip
    s2, e2 = svc.planned_window(flex, day)
    m = svc.compute_metrics(flex, s2, e2, at(12, 0), datetime(2026, 11, 3, 7, 0, tzinfo=tz()))
    assert (m.late, m.early) == (0, 0) and m.worked == 19 * 60


def test_day_status_rules():
    shift = ShiftTemplate(id=1, start_time=time(9), end_time=time(18), break_minutes=0, late_grace_minutes=0,
                          early_leave_grace_minutes=0, track_lateness=True, kind="fixed")  # fmt: skip
    day = datetime(2026, 11, 2).date()
    work = sched.Resolved(day, True, 1, "default")
    off = sched.Resolved(day, False, None, "weekly_off")
    hol = sched.Resolved(day, False, None, "holiday", holiday="B")
    at = lambda d, h: datetime(2026, 11, d, h, 0, tzinfo=tz())  # noqa: E731
    assert svc.day_status(work, None, shift, day, at(2, 8)) == "pending"
    assert svc.day_status(work, None, shift, day, at(2, 19)) == "absent"
    assert svc.day_status(work, None, shift, day, at(3, 8)) == "absent"
    assert svc.day_status(work, None, shift, day, at(1, 8)) == "future"
    assert svc.day_status(work, None, shift, day, at(3, 8), attendance_required=False) == "exempt"
    assert svc.day_status(off, None, None, day, at(3, 8)) == "off"
    assert svc.day_status(hol, None, None, day, at(3, 8)) == "holiday"


# --- Belgilash --------------------------------------------------------------------------


async def test_gps_punch_flow(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client)
    clock.set("2026-11-02 09:25")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 200, r.text
    rec = r.json()["record"]
    assert r.json()["action"] == "check_in" and rec["late_minutes"] == 25 and rec["shift_id"] == ctx["shift"]["id"]
    assert rec["work_date"] == "2026-11-02" and rec["in_distance_m"] < 20

    me = (await pc.get(f"{API}/me")).json()
    assert me["open_record"]["id"] == rec["id"] and me["schedule"]["shift"]["name"] == "Kunduzgi"

    clock.set("2026-11-02 17:30")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    out = r.json()["record"]
    assert r.json()["action"] == "check_out" and out["early_leave_minutes"] == 30
    assert out["worked_minutes"] == (17 * 60 + 30) - (9 * 60 + 25) - 60

    clock.set("2026-11-02 17:40")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_checked_out"


async def test_geofence_and_location_rules(new_client, clock):
    _, pc, _ = await setup_basic(new_client)
    clock.set("2026-11-02 09:00")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **FAR})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "outside_geofence" and r.json()["detail"]["distance"] > 100
    r = await pc.post(f"{API}/punch", json={"method": "gps"})
    assert r.json()["detail"]["code"] == "location_required"
    r = await pc.post(f"{API}/punch", json={"method": "gps", **{**NEAR, "accuracy": 500}})
    assert r.json()["detail"]["code"] == "accuracy_too_low"
    assert (await pc.get(f"{API}/me")).json()["open_record"] is None  # rad etilganlar yozilmadi


async def test_gps_needs_branch_geo(new_client, clock):
    _, pc, _ = await setup_basic(new_client, geo=False)
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "branch_no_geo"


async def test_qr_punch_expiry_and_rotate(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client)
    bid = ctx["branch"]["id"]
    clock.set("2026-11-02 09:00")
    qr = (await hr.get(f"{API}/branches/{bid}/qr")).json()
    assert qr["svg"].startswith("<svg") and "/attendance/punch?t=" in qr["url"] and 0 < qr["expires_in"] <= 60
    assert (await pc.get(f"{API}/branches/{bid}/qr")).status_code == 403  # farmasevtda attendance.qr yo'q

    r = await pc.post(f"{API}/punch", json={"method": "qr", "token": "x.y.z", **NEAR})
    assert r.json()["detail"]["code"] == "qr_invalid"
    r = await pc.post(f"{API}/punch", json={"method": "qr", "token": qr["token"][:-1] + "0", **NEAR})
    assert r.json()["detail"]["code"] == "qr_invalid"

    clock.set("2026-11-02 09:05")  # eski QR muddati o'tdi
    r = await pc.post(f"{API}/punch", json={"method": "qr", "token": qr["token"], **NEAR})
    assert r.json()["detail"]["code"] == "qr_expired"

    fresh = (await hr.get(f"{API}/branches/{bid}/qr")).json()["token"]
    assert (await hr.post(f"{API}/branches/{bid}/qr/rotate")).json()["epoch"] == 1
    r = await pc.post(f"{API}/punch", json={"method": "qr", "token": fresh, **NEAR})
    assert r.json()["detail"]["code"] == "qr_invalid"  # rotatsiyadan keyin eski QR yaroqsiz

    fresh = (await hr.get(f"{API}/branches/{bid}/qr")).json()["token"]
    r = await pc.post(f"{API}/punch", json={"method": "qr", "token": fresh, **NEAR})
    assert r.status_code == 200 and r.json()["record"]["in_method"] == "qr"
    # QR filial geofence'idan tashqarida ishlamaydi (rasm tarqalgan holat)
    await pc.post(f"{API}/punch", json={"method": "qr", "token": fresh, **NEAR})  # too_soon yoki checkout
    clock.set("2026-11-02 12:00")
    far = (await hr.get(f"{API}/branches/{bid}/qr")).json()["token"]
    r = await pc.post(f"{API}/punch", json={"method": "qr", "token": far, **FAR})
    assert r.json()["detail"]["code"] == "outside_geofence"


async def test_too_soon_and_no_profile(new_client, clock):
    _, pc, _ = await setup_basic(new_client)
    clock.set("2026-11-02 09:00")
    assert (await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})).status_code == 200
    clock.set("2026-11-02 09:00")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "too_soon"

    other, _ = await as_user(new_client, "noemp", "farmasevt")
    r = await other.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_employee_profile"


async def test_night_shift_across_midnight(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client, shift_kw={"name": "Tungi", "start_time": "22:00", "end_time": "06:00", "break_minutes": 0})
    clock.set("2026-11-03 21:50")  # smenadan 10 daq oldin (seshanba)
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.json()["record"]["work_date"] == "2026-11-03" and r.json()["record"]["late_minutes"] == 0
    clock.set("2026-11-04 06:10")  # keyingi kun ertalab: ketish, yangi kelish emas
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    rec = r.json()["record"]
    assert r.json()["action"] == "check_out" and rec["work_date"] == "2026-11-03"
    assert rec["early_leave_minutes"] == 0 and rec["worked_minutes"] == 8 * 60 + 20


async def test_unscheduled_day_punch(new_client, clock):
    hr, pc, _ = await setup_basic(new_client)
    clock.set("2026-11-01 11:00")  # yakshanba: dam kuni
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    rec = r.json()["record"]
    assert rec["shift_id"] is None and rec["late_minutes"] == 0 and rec["work_date"] == "2026-11-01"
    clock.set("2026-11-01 15:00")
    await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    d = (await hr.get(f"{API}/daily", params={"date": "2026-11-01"})).json()
    assert d["items"][0]["status"] == "unscheduled"


# --- Hisobotlar -------------------------------------------------------------------------


async def test_daily_and_timesheet(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client)
    async with SessionLocal() as s:
        s.add(Employee(last_name="Bekov", first_name="Bek", full_name="Bekov Bek", status="active"))
        await s.commit()
    clock.set("2026-11-02 09:25")  # Du: Ali kech keldi
    await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    clock.set("2026-11-02 18:00")
    await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})

    clock.set("2026-11-03 12:00")  # Se: Ali kelmadi, hali kun davom etyapti
    d = (await hr.get(f"{API}/daily", params={"date": "2026-11-02"})).json()
    assert d["summary"]["late"] == 1 and d["summary"]["absent"] == 1 and d["total"] == 2
    d3 = (await hr.get(f"{API}/daily", params={"date": "2026-11-03"})).json()
    assert d3["summary"]["pending"] == 2 and d3["summary"]["absent"] == 0
    only = (await hr.get(f"{API}/daily", params={"date": "2026-11-02", "status": "absent"})).json()
    assert [i["employee"]["full_name"] for i in only["items"]] == ["Bekov Bek"]

    clock.set("2026-11-05 10:00")
    t = (await hr.get(f"{API}/timesheet", params={"start": "2026-11-01", "end": "2026-11-04"})).json()
    ali = next(r for r in t["rows"] if r["employee"]["full_name"] == "Aliyev Ali")
    assert [c["status"] for c in ali["cells"]] == ["off", "late", "absent", "absent"]
    assert ali["totals"]["late_count"] == 1 and ali["totals"]["late_minutes"] == 25 and ali["totals"]["absent"] == 2
    assert ali["totals"]["worked_minutes"] == (18 * 60) - (9 * 60 + 25) - 60 and ali["totals"]["worked_days"] == 1

    r = await hr.get(f"{API}/timesheet/export", params={"start": "2026-11-01", "end": "2026-11-04"})
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r = await hr.get(f"{API}/timesheet", params={"start": "2026-01-01", "end": "2026-12-31"})
    assert r.status_code == 400


async def test_exempt_group_not_absent(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client)
    g = ctx["group"]
    await hr.put(f"{SCH}/groups/{g['id']}", json={"name": "Ofis", "default_shift_id": ctx["shift"]["id"], "weekly_off_days": [6], "is_default": True, "attendance_required": False})
    clock.set("2026-11-05 10:00")
    t = (await hr.get(f"{API}/timesheet", params={"start": "2026-11-02", "end": "2026-11-02"})).json()
    assert t["rows"][0]["cells"][0]["status"] == "exempt"


# --- Qo'lda tuzatish --------------------------------------------------------------------


async def test_manual_correction_with_history(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client)
    clock.set("2026-11-05 10:00")
    body = {"employee_id": ctx["emp_id"], "work_date": "2026-11-02", "check_in_at": "2026-11-02T09:00:00+05:00",
            "check_out_at": "2026-11-02T18:00:00+05:00", "shift_id": ctx["shift"]["id"], "reason": "Terminal ishlamadi"}  # fmt: skip
    r = await hr.post(f"{API}/records", json=body)
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["is_manual"] and rec["late_minutes"] == 0 and rec["worked_minutes"] == 480
    assert (await hr.post(f"{API}/records", json=body)).json()["detail"]["code"] == "record_exists"

    r = await hr.put(f"{API}/records/{rec['id']}", json={**body, "check_in_at": "2026-11-02T09:40:00+05:00", "reason": "Aniqlashtirildi"})
    assert r.json()["late_minutes"] == 40
    got = (await hr.get(f"{API}/records/{rec['id']}")).json()
    assert [c["action"] for c in got["corrections"]] == ["update", "create"]
    assert got["corrections"][0]["before"]["late_minutes"] == 0 and got["corrections"][0]["reason"] == "Aniqlashtirildi"

    # sabab majburiy, vaqt mantiqi tekshiriladi
    assert (await hr.put(f"{API}/records/{rec['id']}", json={**body, "reason": "a"})).status_code == 422
    r = await hr.put(f"{API}/records/{rec['id']}", json={**body, "check_out_at": "2026-11-02T08:00:00+05:00"})
    assert r.json()["detail"]["code"] == "out_before_in"
    r = await hr.put(f"{API}/records/{rec['id']}", json={**body, "check_in_at": "2026-11-10T09:00:00+05:00", "check_out_at": None})
    assert r.json()["detail"]["code"] == "time_date_mismatch"

    day = (await hr.get(f"{API}/employees/{ctx['emp_id']}/day", params={"day": "2026-11-02"})).json()
    assert day["record"]["id"] == rec["id"] and day["scheduled_shift"]["name"] == "Kunduzgi"

    assert (await hr.delete(f"{API}/records/{rec['id']}", params={"reason": "Xato kiritilgan"})).status_code == 204
    assert (await hr.get(f"{API}/records/{rec['id']}")).status_code == 404
    audit = (await hr.get("/api/v1/audit", params={"action": "attendance.correct"})).json()
    assert audit["total"] == 3


async def test_attendance_permissions(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client)
    assert (await pc.get(f"{API}/daily", params={"date": "2026-11-02"})).status_code == 403
    assert (await pc.get(f"{API}/timesheet", params={"start": "2026-11-02", "end": "2026-11-02"})).status_code == 403
    assert (await pc.post(f"{API}/records", json={})).status_code == 403
    kor, _ = await as_user(new_client, "k", "koordinator")
    assert (await kor.get(f"{API}/daily", params={"date": "2026-11-02"})).status_code == 200
    assert (await kor.delete(f"{API}/records/1", params={"reason": "abc"})).status_code == 403
    mgr, _ = await as_user(new_client, "m", "hr_menejer")
    assert (await mgr.get(f"{API}/branches/{ctx['branch']['id']}/qr")).status_code == 200


# --- Dashboard (F8) ---------------------------------------------------------------------


async def test_dashboard_matches_timesheet_and_pdf(new_client, clock):
    hr, pc, ctx = await setup_basic(new_client)
    async with SessionLocal() as s:
        s.add(Employee(last_name="Bekov", first_name="Bek", full_name="Bekov Bek", status="active", branch_id=ctx["branch"]["id"]))
        await s.commit()
    clock.set("2026-11-02 09:25")  # Du: Ali kech keldi
    await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    clock.set("2026-11-02 17:30")
    await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    clock.set("2026-11-03 08:55")  # Se: o'z vaqtida
    await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    clock.set("2026-11-03 18:00")
    await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})

    clock.set("2026-11-05 10:00")  # Pa: Du-Se o'tgan, Ch-Pa: Ali kelmagan
    q = {"start": "2026-11-02", "end": "2026-11-04"}
    dash = (await hr.get(f"{API}/dashboard", params=q)).json()
    assert dash["previous"]["kpis"]["employees"] >= 0 and dash["previous"]["end"] < dash["start"]
    sheet = (await hr.get(f"{API}/timesheet", params=q)).json()

    # Bitta manba: dashboard jami = tabel jami
    t = sheet["rows"]
    k = dash["kpis"]
    assert k["attended"] == sum(r["totals"]["worked_days"] for r in t) == 2
    assert k["absent"] == sum(r["totals"]["absent"] for r in t)
    assert k["late_count"] == sum(r["totals"]["late_count"] for r in t) == 1
    assert k["late_minutes"] == sum(r["totals"]["late_minutes"] for r in t) == 25
    assert k["worked_minutes"] == sum(r["totals"]["worked_minutes"] for r in t)
    assert k["employees"] == 2 and k["rate"] == round(2 / (2 + k["absent"]), 4)
    assert k["punctuality"] == 0.5  # 2 kundan 1 tasi kech

    # Kesimlar va dinamika jami bilan mos
    assert sum(r["attended"] for r in dash["by_branch"]) == k["attended"]
    assert sum(r["absent"] for r in dash["by_department"]) == k["absent"]
    assert [d["date"] for d in dash["trend"]] == ["2026-11-02", "2026-11-03", "2026-11-04"]
    assert sum(d["attended"] for d in dash["trend"]) == k["attended"]
    assert dash["trend"][0]["late"] == 1 and dash["trend"][0]["absent"] == 1  # Bekov Du kuni kelmagan
    assert dash["top_late"][0]["employee"]["full_name"] == "Aliyev Ali" and dash["top_late"][0]["late_minutes"] == 25
    assert dash["top_absent"][0]["employee"]["full_name"] == "Bekov Bek"

    # Filtr tabel bilan bir xil ishlaydi
    one = (await hr.get(f"{API}/dashboard", params={**q, "q": "Aliyev"})).json()
    assert one["kpis"]["employees"] == 1 and one["kpis"]["absent"] == 1

    for lang in ("uz", "ru"):
        r = await hr.get(f"{API}/dashboard/pdf", params={**q, "lang": lang})
        assert r.status_code == 200 and r.content[:4] == b"%PDF" and r.headers["content-type"] == "application/pdf"
    audit = (await hr.get("/api/v1/audit", params={"action": "attendance.export_pdf"})).json()
    assert audit["total"] == 2

    assert (await hr.get(f"{API}/dashboard", params={"start": "2026-01-01", "end": "2026-12-31"})).status_code == 400
    assert (await pc.get(f"{API}/dashboard", params=q)).status_code == 403
    assert (await pc.get(f"{API}/dashboard/pdf", params=q)).status_code == 403
