from datetime import date, time

import pytest

from app.models.schedule import Holiday
from app.services import schedule as svc
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

API = "/api/v1/schedule"


async def as_user(new_client, login_name, role):
    await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c


async def hr(new_client):
    return await as_user(new_client, "hr", "hr_direktor")


def shift(**kw):
    return {"name": "Kunduzgi", "start_time": "09:00", "end_time": "18:00", "break_minutes": 60, **kw}


async def mk_shift(c, **kw):
    r = await c.post(f"{API}/shifts", json=shift(**kw))
    assert r.status_code == 201, r.text
    return r.json()


async def mk_group(c, **kw):
    body = {"name": "Ofis", "category": "office", "weekly_off_days": [6], **kw}
    r = await c.post(f"{API}/groups", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def mk_emp(c, name="Vali", **kw):
    r = await c.post(
        "/api/v1/employees",
        json={"last_name": "Aliyev", "first_name": name, "phone": f"90 {abs(hash(name)) % 9000000 + 1000000}", **kw},
    )
    assert r.status_code == 201, r.text
    return r.json()["employee"]


# --- Unit ----------------------------------------------------------------------------


def test_shift_minutes():
    assert svc.shift_minutes(time(9), time(18)) == 540
    assert svc.shift_minutes(time(22), time(6)) == 480  # tungi
    assert svc.shift_minutes(time(9), time(9)) == 1440  # 24 soat
    assert svc.is_overnight(time(22), time(6))
    assert not svc.is_overnight(time(9), time(18))


def test_holidays_exact_year_beats_yearly():
    rows = [
        Holiday(year=None, month=3, day=21, name="Yillik", kind="holiday"),
        Holiday(year=2026, month=3, day=21, name="Aniq", kind="workday"),
    ]
    out = svc.holidays_in_range(rows, date(2026, 3, 20), date(2026, 3, 22))
    assert out[date(2026, 3, 21)].name == "Aniq"
    assert svc.holidays_in_range(rows, date(2027, 3, 21), date(2027, 3, 21))[date(2027, 3, 21)].name == "Yillik"


# --- Smena turlari ---------------------------------------------------------------------


async def test_shift_crud_and_validation(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    assert s["duration_minutes"] == 540 and s["overnight"] is False and s["track_lateness"] is True

    night = await mk_shift(c, name="Tungi", start_time="22:00", end_time="06:00", break_minutes=0)
    assert night["overnight"] is True and night["duration_minutes"] == 480

    day24 = await mk_shift(c, name="Sutkalik", start_time="09:00", end_time="09:00", break_minutes=0)
    assert day24["duration_minutes"] == 1440

    flex = await mk_shift(c, name="Erkin", kind="flexible", start_time="08:00", end_time="08:00")
    assert flex["track_lateness"] is False

    r = await c.post(f"{API}/shifts", json=shift(name="kunduzgi"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "shift_name_taken"

    r = await c.post(f"{API}/shifts", json=shift(name="X", break_minutes=600, start_time="09:00", end_time="10:00"))
    assert r.status_code == 422

    r = await c.put(f"{API}/shifts/{s['id']}", json=shift(end_time="19:00"))
    assert r.status_code == 200 and r.json()["duration_minutes"] == 600
    assert (await c.delete(f"{API}/shifts/{night['id']}")).status_code == 204


async def test_shift_in_use_cannot_be_deleted(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    await mk_group(c, default_shift_id=s["id"])
    r = await c.delete(f"{API}/shifts/{s['id']}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "shift_in_use"


# --- Guruhlar --------------------------------------------------------------------------


async def test_group_rules(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    g1 = await mk_group(c, default_shift_id=s["id"], is_default=True)
    g2 = await mk_group(c, name="Ombor", category="warehouse", is_default=True)
    groups = (await c.get(f"{API}/groups")).json()
    assert {g["name"]: g["is_default"] for g in groups} == {"Ofis": False, "Ombor": True}

    r = await c.post(f"{API}/groups", json={"name": "ofis", "weekly_off_days": []})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "group_name_taken"
    r = await c.post(f"{API}/groups", json={"name": "A", "weekly_off_days": [0, 1, 2, 3, 4, 5, 6]})
    assert r.status_code == 422
    r = await c.post(f"{API}/groups", json={"name": "B", "weekly_off_days": [7]})
    assert r.status_code == 422
    r = await c.post(f"{API}/groups", json={"name": "C", "default_shift_id": 9999})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_shift"

    # Standart guruhni o'chirib yoki o'chirmay qo'yib bo'lmaydi
    r = await c.put(f"{API}/groups/{g2['id']}", json={"name": "Ombor", "is_default": False})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "default_group_required"
    assert (await c.delete(f"{API}/groups/{g2['id']}")).status_code == 409

    # A'zosi bor guruhni o'chirib bo'lmaydi
    await mk_emp(c, work_group_id=g1["id"])
    r = await c.delete(f"{API}/groups/{g1['id']}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "group_has_members"


# --- Bayramlar -------------------------------------------------------------------------


async def test_holidays(new_client):
    c = await hr(new_client)
    r = await c.post(f"{API}/holidays/seed", json={"year": 2026})
    assert r.status_code == 201 and r.json()["created"] == len(svc.FIXED_HOLIDAYS_UZ)
    assert (await c.post(f"{API}/holidays/seed", json={"year": 2026})).json()["created"] == 0
    assert len((await c.get(f"{API}/holidays", params={"year": 2026})).json()) == len(svc.FIXED_HOLIDAYS_UZ)

    r = await c.post(f"{API}/holidays", json={"name": "Dup", "date": "2026-09-01"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "holiday_date_taken"

    r = await c.post(f"{API}/holidays", json={"name": "Hayit", "date": "2026-03-20"})
    assert r.status_code == 201
    hid = r.json()["id"]
    assert (await c.put(f"{API}/holidays/{hid}", json={"name": "Ro'za hayit", "date": "2026-03-20"})).status_code == 200
    assert (await c.delete(f"{API}/holidays/{hid}")).status_code == 204


# --- Shablonlar ------------------------------------------------------------------------


async def test_patterns(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    r = await c.post(f"{API}/patterns", json={"name": "2/2", "cycle": [{"shift_id": s["id"]}, {"shift_id": s["id"]}, {"shift_id": None}, {"shift_id": None}]})
    assert r.status_code == 201
    r = await c.post(f"{API}/patterns", json={"name": "Bo'sh", "cycle": [{"shift_id": None}]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "pattern_no_work_days"
    r = await c.post(f"{API}/patterns", json={"name": "X", "cycle": [{"shift_id": 999}]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_shift"


# --- Grafik: aniqlash va tuzish --------------------------------------------------------


async def test_board_resolution_precedence(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    g = await mk_group(c, default_shift_id=s["id"], weekly_off_days=[6], is_default=True)
    await c.post(f"{API}/holidays", json={"name": "Bayram", "date": "2026-10-01"})  # payshanba
    e = await mk_emp(c, work_group_id=g["id"])

    # 2026-09-28 dushanba .. 2026-10-04 yakshanba
    q = {"start": "2026-09-28", "end": "2026-10-04"}
    row = (await c.get(f"{API}/board", params=q)).json()["rows"][0]
    reasons = [x["reason"] for x in row["cells"]]
    assert reasons == ["default", "default", "default", "holiday", "default", "default", "weekly_off"]
    assert row["employee"]["group"] == "Ofis"

    # Aniq yozuv bayramdan ustun
    r = await c.post(f"{API}/employees/{e['id']}/days", json={"dates": ["2026-10-01"], "mode": "shift", "shift_id": s["id"]})
    assert r.status_code == 200
    row = (await c.get(f"{API}/board", params=q)).json()["rows"][0]
    assert row["cells"][3]["reason"] == "entry" and row["cells"][3]["explicit"]

    # Tozalash: guruh qoidasiga qaytadi
    await c.post(f"{API}/employees/{e['id']}/days", json={"dates": ["2026-10-01"], "mode": "clear"})
    row = (await c.get(f"{API}/board", params=q)).json()["rows"][0]
    assert row["cells"][3]["reason"] == "holiday"

    # Ko'chirilgan ish kuni yakshanbada ham ishlanadi
    await c.post(f"{API}/holidays", json={"name": "Ish kuni", "kind": "workday", "date": "2026-10-04"})
    row = (await c.get(f"{API}/board", params=q)).json()["rows"][0]
    assert row["cells"][6]["working"] is True

    # Diapazon cheklovi
    r = await c.get(f"{API}/board", params={"start": "2026-01-01", "end": "2026-12-31"})
    assert r.status_code == 400


async def test_group_not_observing_holidays(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    g = await mk_group(c, name="Dorixona", category="pharmacy", default_shift_id=s["id"], weekly_off_days=[], observe_holidays=False, is_default=True)
    await c.post(f"{API}/holidays", json={"name": "Bayram", "date": "2026-10-01"})
    await mk_emp(c, work_group_id=g["id"])
    row = (await c.get(f"{API}/board", params={"start": "2026-10-01", "end": "2026-10-01"})).json()["rows"][0]
    assert row["cells"][0]["reason"] == "default" and row["cells"][0]["working"]


async def test_apply_modes(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    night = await mk_shift(c, name="Tungi", start_time="22:00", end_time="06:00", break_minutes=0)
    g = await mk_group(c, default_shift_id=s["id"], is_default=True)
    e1 = await mk_emp(c, "Ali", work_group_id=g["id"])
    e2 = await mk_emp(c, "Bobur", work_group_id=g["id"])

    base = {"group_id": g["id"], "start": "2026-11-02", "end": "2026-11-08"}  # du..ya

    # dry_run hech narsa yozmaydi
    r = await c.post(f"{API}/apply", json={**base, "mode": "shift", "shift_id": night["id"], "dry_run": True})
    assert r.json() == {"employees": 2, "to_create": 14, "to_update": 0, "to_delete": 0, "skipped": 0, "applied": False}
    row = (await c.get(f"{API}/board", params={"start": "2026-11-02", "end": "2026-11-02"})).json()["rows"][0]
    assert not row["cells"][0]["explicit"]

    # Faqat ish kunlari
    r = await c.post(f"{API}/apply", json={**base, "mode": "shift", "shift_id": night["id"], "weekdays": [0, 1, 2, 3, 4], "dry_run": False})
    assert r.json()["applied"] and r.json()["to_create"] == 10

    # overwrite=False mavjudini o'tkazadi
    r = await c.post(f"{API}/apply", json={**base, "mode": "off", "weekdays": [0], "overwrite": False, "dry_run": False})
    assert r.json()["skipped"] == 2 and r.json()["to_create"] == 0

    # overwrite=True yangilaydi
    r = await c.post(f"{API}/apply", json={**base, "mode": "off", "weekdays": [0], "dry_run": False})
    assert r.json()["to_update"] == 2
    cells = (await c.get(f"{API}/employees/{e1['id']}", params={"month": "2026-11"})).json()["days"]
    assert cells[1]["reason"] == "entry_off" and cells[2]["shift_id"] == night["id"]

    # Tozalash
    r = await c.post(f"{API}/apply", json={**base, "mode": "clear", "dry_run": False})
    assert r.json()["to_delete"] == 10
    cells = (await c.get(f"{API}/employees/{e2['id']}", params={"month": "2026-11"})).json()["days"]
    assert not any(d["explicit"] for d in cells)


async def test_apply_pattern_stagger_and_skip_holidays(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    g = await mk_group(c, default_shift_id=s["id"], is_default=True)
    await mk_emp(c, "Ali", work_group_id=g["id"])
    await mk_emp(c, "Bobur", work_group_id=g["id"])
    p = (await c.post(f"{API}/patterns", json={"name": "1/1", "cycle": [{"shift_id": s["id"]}, {"shift_id": None}]})).json()

    r = await c.post(f"{API}/apply", json={"group_id": g["id"], "start": "2026-11-02", "end": "2026-11-05", "mode": "pattern", "pattern_id": p["id"], "stagger": True, "dry_run": False})
    assert r.status_code == 200
    rows = (await c.get(f"{API}/board", params={"start": "2026-11-02", "end": "2026-11-05"})).json()["rows"]
    work = {x["employee"]["full_name"].split()[1]: [c_["working"] for c_ in x["cells"]] for x in rows}
    assert work["Ali"] == [True, False, True, False]
    assert work["Bobur"] == [False, True, False, True]

    await c.post(f"{API}/holidays", json={"name": "B", "date": "2026-11-03"})
    r = await c.post(f"{API}/apply", json={"group_id": g["id"], "start": "2026-11-02", "end": "2026-11-04", "mode": "off", "skip_holidays": True, "dry_run": True})
    assert r.json()["to_create"] + r.json()["to_update"] == 4  # 2 xodim x 2 kun (bayram o'tkazildi)


async def test_apply_validation(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    base = {"start": "2026-11-02", "end": "2026-11-08", "mode": "shift", "shift_id": s["id"]}
    assert (await c.post(f"{API}/apply", json=base)).status_code == 422  # kimga?
    assert (await c.post(f"{API}/apply", json={**base, "employee_ids": [1], "end": "2028-01-01"})).status_code == 422
    r = await c.post(f"{API}/apply", json={**base, "employee_ids": [999]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "no_employees"
    e = await mk_emp(c)
    r = await c.post(f"{API}/apply", json={**base, "employee_ids": [e["id"]], "shift_id": 999})
    assert r.json()["detail"]["code"] == "unknown_shift"


async def test_dismissed_employee_not_scheduled(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    e = await mk_emp(c)
    await c.post(f"/api/v1/employees/{e['id']}/dismiss", json={"date": str(date.today()), "reason": "own_will"})
    r = await c.post(f"{API}/employees/{e['id']}/days", json={"dates": ["2026-11-02"], "mode": "shift", "shift_id": s["id"]})
    assert r.status_code == 409


async def test_bulk_assign_group_and_employee_filter(new_client):
    c = await hr(new_client)
    g = await mk_group(c)
    e1 = await mk_emp(c, "Ali")
    await mk_emp(c, "Bobur")
    r = await c.post("/api/v1/employees/bulk", json={"action": "assign_group", "ids": [e1["id"]], "params": {"work_group_id": g["id"]}})
    assert r.status_code == 200, r.text
    lst = (await c.get("/api/v1/employees", params={"work_group_id": g["id"]})).json()
    assert [x["id"] for x in lst["items"]] == [e1["id"]]
    assert lst["items"][0]["work_group"]["name"] == "Ofis"
    r = await c.post("/api/v1/employees/bulk", json={"action": "assign_group", "ids": [e1["id"]], "params": {"work_group_id": 999}})
    assert r.status_code == 400
    r = await c.post("/api/v1/employees", json={"last_name": "Z", "first_name": "Z", "phone": "90 111 22 33", "work_group_id": 999})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_group"


async def test_permissions(new_client):
    mgr = await as_user(new_client, "m", "hr_menejer")
    assert (await mgr.get(f"{API}/shifts")).status_code == 200
    assert (await mgr.post(f"{API}/shifts", json=shift())).status_code == 403
    koor = await as_user(new_client, "k", "koordinator")
    assert (await koor.get(f"{API}/board", params={"start": "2026-11-02", "end": "2026-11-03"})).status_code == 200
    r = await koor.post(f"{API}/apply", json={"employee_ids": [1], "start": "2026-11-02", "end": "2026-11-03", "mode": "off"})
    assert r.status_code == 403
    far = await as_user(new_client, "f", "farmasevt")
    assert (await far.get(f"{API}/shifts")).status_code == 403


async def test_default_group_includes_unassigned_employees(new_client):
    c = await hr(new_client)
    s = await mk_shift(c)
    g = await mk_group(c, default_shift_id=s["id"], is_default=True)
    other = await mk_group(c, name="Ombor", category="warehouse")
    await mk_emp(c, "Ali")  # guruhsiz -> standart guruh
    await mk_emp(c, "Bobur", work_group_id=other["id"])
    q = {"start": "2026-11-02", "end": "2026-11-02"}
    rows = (await c.get(f"{API}/board", params={**q, "group_id": g["id"]})).json()["rows"]
    assert [r["employee"]["group"] for r in rows] == ["Ofis"]
    groups = {x["name"]: x["members"] for x in (await c.get(f"{API}/groups")).json()}
    assert groups == {"Ofis": 1, "Ombor": 1}
    r = await c.post(f"{API}/apply", json={"group_id": g["id"], "start": "2026-11-02", "end": "2026-11-02", "mode": "off", "dry_run": True})
    assert r.json()["employees"] == 1
    lst = (await c.get("/api/v1/employees", params={"work_group_id": g["id"]})).json()
    assert lst["total"] == 1
