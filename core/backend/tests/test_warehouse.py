from datetime import datetime

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.schedule import ShiftTemplate, WorkGroup
from app.models.warehouse import Warehouse
from app.services import warehouse as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

W = "/api/v1/warehouse"
D = "2026-11-10"


def at(h, m=0, day=10):
    return datetime(2026, 11, day, h, m, tzinfo=tz())


@pytest.fixture
def clock(monkeypatch):
    state = {"t": at(19, 30)}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.warehouse", "app.api.attendance", "app.services.attendance"):
        monkeypatch.setattr(f"{mod}.now", fn)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def mk_emp(name):
    async with SessionLocal() as s:
        e = Employee(last_name=name, first_name="X", full_name=f"{name} X", status="active")
        s.add(e)
        await s.commit()
        return e.id


async def setup(new_client, min_on_duty=2):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    boss, _ = await as_user(new_client, "boss", "direktor")
    far, _ = await as_user(new_client, "far", "farmasevt")
    r = await hr.post(W, json={"name": "Markaziy ombor", "min_on_duty": min_on_duty})
    assert r.status_code == 201, r.text
    wh = r.json()
    ids = {n: await mk_emp(n) for n in ("Aziz", "Bobur", "Sardor")}
    for e in ids.values():
        assert (await hr.post(f"{W}/{wh['id']}/staff", json={"employee_id": e})).status_code == 201
    return {"hr": hr, "boss": boss, "far": far, "wh": wh, "ids": ids}


async def rec(ctx, name, start, end=None, day=D):
    body = {"employee_id": ctx["ids"][name], "work_date": day, "check_in_at": f"{day}T{start}:00+05:00", "shift_id": ctx["wh"]["shift"]["id"], "reason": "Test"}
    if end:
        body["check_out_at"] = end
    r = await ctx["hr"].post("/api/v1/attendance/records", json=body)
    assert r.status_code == 201, r.text


def test_window_and_coverage_units():
    sh = ShiftTemplate(start_time=datetime(2000, 1, 1, 8).time(), end_time=datetime(2000, 1, 1, 7).time(), kind="flexible")
    d, s, e = svc.window_for(sh, at(12))
    assert (d.isoformat(), s, e) == (D, at(8), at(7, day=11))
    assert svc.window_for(sh, at(3, day=11))[0].isoformat() == D  # tun: hali kechagi oyna
    assert svc.window_for(sh, at(7, 30, day=11))[0].isoformat() == "2026-11-10"  # 07:00-08:00 oralig'i: oxirgi oyna
    assert svc.window_for(sh, at(8, 5, day=11))[0].isoformat() == "2026-11-11"
    iv = [svc.Interval(at(8, 30), at(18)), svc.Interval(at(9), at(19)), svc.Interval(at(18), at(7, day=11))]
    c = svc.coverage(iv, at(8), at(7, day=11), 2)
    # 08:00-08:30: 0 kishi (30), 08:30-09:00: 1 (30), 09:00-18:00: 2, 18:00-19:00: 2 (B, C), 19:00-07:00: 1 (720)
    assert c == {"peak": 2, "lowest": 0, "gap_minutes": 30 + 30 + 720}
    assert svc.coverage([], at(8), at(9), 1)["gap_minutes"] == 60


async def test_create_preset_permissions_and_staff(new_client, clock):
    ctx = await setup(new_client)
    hr, boss, wh = ctx["hr"], ctx["boss"], ctx["wh"]
    assert wh["shift"]["kind"] == "flexible" and (wh["shift"]["start"], wh["shift"]["end"], wh["shift"]["min_work_minutes"]) == ("08:00", "07:00", 540)
    async with SessionLocal() as s:
        g = await s.get(WorkGroup, wh["work_group"]["id"])
        assert g.category == "warehouse" and g.default_shift_id == wh["shift"]["id"] and g.observe_holidays is False
    assert (await ctx["far"].get(W)).status_code == 403
    assert (await boss.post(W, json={"name": "Boshqa"})).status_code == 403
    assert (await boss.get(W)).json()[0]["status"]["staff"] == 3
    assert (await hr.post(W, json={"name": "markaziy OMBOR"})).json()["detail"]["code"] == "warehouse_exists"
    # mavjud guruhdan foydalanish: band guruh qabul qilinmaydi
    assert (await hr.post(W, json={"name": "Ikkinchi", "work_group_id": wh["work_group"]["id"]})).json()["detail"]["code"] == "group_taken"
    assert (await hr.post(W, json={"name": "Uchinchi", "work_group_id": 99999})).json()["detail"]["code"] == "unknown_group"
    # xodimlar tarkibi
    aziz = ctx["ids"]["Aziz"]
    assert (await hr.post(f"{W}/{wh['id']}/staff", json={"employee_id": aziz})).json()["detail"]["code"] == "already_in_warehouse"
    assert [x["name"] for x in (await boss.get(f"{W}/{wh['id']}/staff")).json()] == ["Aziz X", "Bobur X", "Sardor X"]
    other = (await hr.post(W, json={"name": "Filial ombori"})).json()
    r = await hr.post(f"{W}/{other['id']}/staff", json={"employee_id": aziz})
    assert r.json()["moved_from"] == "Markaziy ombor"  # boshqa ombordan ko'chiriladi
    assert len((await boss.get(f"{W}/{wh['id']}/staff")).json()) == 2
    assert (await hr.delete(f"{W}/{other['id']}/staff/{aziz}")).status_code == 204
    assert (await hr.delete(f"{W}/{other['id']}/staff/{aziz}")).status_code == 404
    async with SessionLocal() as s:
        assert (await s.get(Employee, aziz)).work_group_id is None
    r = await hr.put(f"{W}/{wh['id']}", json={"name": "Markaziy ombor", "min_on_duty": 3, "work_group_id": wh["work_group"]["id"], "max_shift_hours": 12, "alert_grace_min": 10})
    assert r.json()["min_on_duty"] == 3 and r.json()["max_shift_hours"] == 12
    # ombor o'chirilsa guruh va smena saqlanadi
    assert (await hr.delete(f"{W}/{other['id']}")).status_code == 204
    async with SessionLocal() as s:
        assert await s.get(WorkGroup, other["work_group"]["id"]) is not None
    for a in ("create", "update", "delete", "staff_add", "staff_remove"):
        assert (await hr.get("/api/v1/audit", params={"action": f"warehouse.{a}"})).json()["total"] >= 1, a


async def test_status_gap_and_long_open(new_client, clock):
    ctx = await setup(new_client)
    boss, wid = ctx["boss"], ctx["wh"]["id"]
    clock["t"] = at(19, 30)
    await rec(ctx, "Aziz", "08:30")  # ochiq
    await rec(ctx, "Bobur", "09:00", f"{D}T19:00:00+05:00")
    await rec(ctx, "Sardor", "08:15", f"{D}T18:00:00+05:00")
    st = (await boss.get(f"{W}/{wid}/status")).json()
    assert st["in_window"] is True and st["on_duty"] == 1 and st["gap"] is True and st["window"]["min_work_minutes"] == 540
    by = {x["employee"]["name"]: x for x in st["staff"]}
    assert by["Aziz X"]["on_duty"] and by["Aziz X"]["worked_minutes"] == 660 and by["Aziz X"]["met_min"] is True and by["Aziz X"]["remaining_minutes"] == 0
    assert by["Bobur X"]["worked_minutes"] == 600 and by["Bobur X"]["met_min"] is True and by["Sardor X"]["worked_minutes"] == 585
    clock["t"] = at(20)
    allst = (await boss.get(f"{W}/status")).json()
    assert len(allst) == 1 and allst[0]["warehouse"]["name"] == "Markaziy ombor"
    # tun: uzoq ochiq smena
    clock["t"] = at(1, 0, day=11)
    st = (await boss.get(f"{W}/{wid}/status")).json()
    assert st["window"]["date"] == D and st["long_open"][0]["name"] == "Aziz X" and st["long_open"][0]["hours"] == 16.5
    # 07:00-08:00: oyna yo'q, yetishmovchilik hisoblanmaydi
    clock["t"] = at(7, 30, day=11)
    st = (await boss.get(f"{W}/{wid}/status")).json()
    assert st["in_window"] is False and st["gap"] is False
    # ertasi kuni 08:05: yangi oyna, hech kim kelmagan
    clock["t"] = at(8, 5, day=11)
    st = (await boss.get(f"{W}/{wid}/status")).json()
    assert st["in_window"] is True and st["on_duty"] == 0 and st["gap"] is True and st["window"]["date"] == "2026-11-11"


async def test_control_report_matches_hand_calculation(new_client, clock):
    ctx = await setup(new_client)
    boss, wid = ctx["boss"], ctx["wh"]["id"]
    await rec(ctx, "Aziz", "08:30")
    await rec(ctx, "Bobur", "09:00", f"{D}T19:00:00+05:00")
    await rec(ctx, "Sardor", "08:15", f"{D}T18:00:00+05:00")
    clock["t"] = at(8, 0, day=11)
    r = (await boss.get(f"{W}/{wid}/control", params={"start": D, "end": D})).json()
    day = r["days"][0]
    # 08:00-08:15: 0 kishi (15), 08:15-08:30: 1 (15), 08:30-09:00: 2, 09:00-18:00: 3, 18:00-19:00: 2, 19:00-07:00: 1 (720)
    assert (day["peak"], day["lowest"], day["gap_minutes"], day["staff_in"], day["open"]) == (3, 0, 15 + 15 + 720, 3, 1)
    emp = {e["employee"]["name"]: e for e in r["employees"]}
    assert emp["Bobur X"]["worked_minutes"] == 600 and emp["Sardor X"]["worked_minutes"] == 585 and emp["Aziz X"]["no_checkout"] == 1 and emp["Aziz X"]["worked_minutes"] == 0
    assert r["totals"]["worked_hours"] == 19.8 and r["totals"]["gap_days"] == 1 and r["totals"]["min_work_minutes"] == 540
    assert (await boss.get(f"{W}/{wid}/control", params={"start": "2026-10-01", "end": "2026-12-31"})).status_code == 400
    assert (await ctx["far"].get(f"{W}/{wid}/control", params={"start": D, "end": D})).status_code == 403


async def test_below_min_and_watch_alerts_once(new_client, clock):
    ctx = await setup(new_client)
    hr, wid = ctx["hr"], ctx["wh"]["id"]
    await rec(ctx, "Sardor", "08:15", f"{D}T12:00:00+05:00")  # 3 soat 45 daqiqa: minimumdan kam
    clock["t"] = at(21, 0)
    st = (await hr.get(f"{W}/{wid}/status")).json()
    s = next(x for x in st["staff"] if x["employee"]["name"] == "Sardor X")
    assert s["met_min"] is False and s["worked_minutes"] == 225
    ctl = (await hr.get(f"{W}/{wid}/control", params={"start": D, "end": D})).json()
    assert next(e for e in ctl["employees"] if e["employee"]["name"] == "Sardor X")["below_min"] == 1

    # kuzatuvchi: yetishmovchilik grace (20 daq) dan keyin bir marta xabar
    async def tick(moment):
        async with SessionLocal() as db:
            sent, _ = await svc.watch(db, moment)
            await db.commit()
            return sent

    assert await tick(at(21, 2)) == 0  # yetishmovchilik boshlandi
    assert await tick(at(21, 12)) == 0  # grace tugamadi
    assert await tick(at(21, 25)) == 1  # xabar
    assert await tick(at(21, 35)) == 0  # takror yo'q
    kinds = [n["kind"] for n in (await hr.get("/api/v1/notifications")).json()["items"]]
    assert kinds.count("warehouse.gap") == 1
    # tiklanish: ikki kishi ishga keldi => holat tozalanadi, keyingi yetishmovchilikda yana xabar
    await rec(ctx, "Aziz", "21:30")
    await rec(ctx, "Bobur", "21:30")
    assert await tick(at(21, 45)) == 0
    async with SessionLocal() as db:
        w = (await db.scalars(select(Warehouse))).first()
        assert w.gap_since is None and w.gap_notified is False
