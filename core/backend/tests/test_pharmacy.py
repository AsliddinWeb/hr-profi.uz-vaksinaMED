from datetime import datetime, time

import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.org import Branch, Department, Position
from app.services import pharmacy as svc
from app.timeutil import tz
from tests.conftest import login, make_user

P = "/api/v1/pharmacy"
NOW = datetime(2026, 11, 2, 10, 0, tzinfo=tz())  # dushanba 10:00


def test_role_of():
    assert svc.role_of("Mudir") == "manager" and svc.role_of("Заведующий аптекой") == "manager"
    assert svc.role_of("Farmasevt") == "pharmacist" and svc.role_of("Старший фармацевт") == "pharmacist"
    assert svc.role_of("Stajyor farmasevt") == "intern"  # stajyor farmasevtdan ustun
    assert svc.role_of("Haydovchi") == "other" and svc.role_of(None) == "other"
    b = Branch(staff_norm={"manager": 1, "pharmacist": 2})
    assert svc.norm_of(b) == {"manager": 1, "pharmacist": 2, "intern": 0}
    assert svc.is_open_now(Branch(is_24h=True), NOW) is True
    assert svc.is_open_now(Branch(is_24h=False), NOW) is None
    assert svc.is_open_now(Branch(is_24h=False, open_time=time(9), close_time=time(21)), NOW) is True
    assert svc.is_open_now(Branch(is_24h=False, open_time=time(22), close_time=time(6)), NOW) is False  # tungi
    assert svc.is_open_now(Branch(is_24h=False, open_time=time(22), close_time=time(6)), NOW.replace(hour=23)) is True


@pytest.fixture
def clock(monkeypatch):
    fn = lambda: NOW  # noqa: E731
    for mod in ("app.api.pharmacy", "app.api.attendance", "app.services.attendance"):
        monkeypatch.setattr(f"{mod}.now", fn)


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def mk_employee(name, branch_id, position_id, user_id=None):
    async with SessionLocal() as s:
        e = Employee(last_name=name, first_name="X", full_name=f"{name} X", branch_id=branch_id, position_id=position_id, user_id=user_id, status="active")
        s.add(e)
        await s.commit()
        return e.id


async def setup(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    coord, coord_id = await as_user(new_client, "coord", "koordinator")
    other_coord, other_id = await as_user(new_client, "coord2", "koordinator")
    async with SessionLocal() as s:
        d = Department(name="Dorixona tarmog'i", kind="pharmacy")
        s.add(d)
        await s.flush()
        pos = {n: Position(name=n, department_id=d.id) for n in ("Mudir", "Farmasevt", "Stajyor", "Haydovchi")}
        s.add_all(pos.values())
        await s.commit()
        pos_ids = {n: p.id for n, p in pos.items()}
    shift = (await hr.post("/api/v1/schedule/shifts", json={"name": "K", "start_time": "09:00", "end_time": "21:00"})).json()
    await hr.post("/api/v1/schedule/groups", json={"name": "Dorixona", "default_shift_id": shift["id"], "weekly_off_days": [6], "is_default": True})
    a = (await hr.post("/api/v1/branches", json={"number": 1, "name": "Filial 1", "district": "Yunusobod", "latitude": 41.3, "longitude": 69.3, "coordinator_user_id": coord_id, "address": "A", "phone": "71 111 11 11"})).json()
    b = (await hr.post("/api/v1/branches", json={"number": 2, "name": "Filial 2", "district": "Chilonzor", "coordinator_user_id": other_id})).json()
    return {"hr": hr, "coord": coord, "coord_id": coord_id, "coord2": other_coord, "a": a["id"], "b": b["id"], "pos": pos_ids, "shift": shift["id"]}


async def profile(c, branch_id, **kw):
    body = {"staff_norm": {"manager": 1, "pharmacist": 2, "intern": 0}, "is_24h": False, "open_time": "09:00", "close_time": "21:00", **kw}
    r = await c.put(f"{P}/branches/{branch_id}/profile", json=body)
    assert r.status_code == 200, r.text


async def test_overview_flags_and_today_state(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    await profile(hr, ctx["a"])
    mudir = await mk_employee("Mudirov", ctx["a"], ctx["pos"]["Mudir"])
    far = await mk_employee("Farmasevtov", ctx["a"], ctx["pos"]["Farmasevt"])

    o = (await hr.get(f"{P}/overview")).json()
    a = next(i for i in o["items"] if i["id"] == ctx["a"])
    assert a["counts"]["manager"] == 1 and a["counts"]["pharmacist"] == 1 and a["gaps"] == {"pharmacist": 1}
    assert a["today"]["expected"] == 2 and a["today"]["here_now"] == 0
    assert set(a["flags"]) == {"uncovered", "short"} and a["severity"] == "uncovered"  # ochiq, lekin hech kim kelmagan
    assert o["items"][0]["id"] == ctx["a"]  # eng og'ir holat tepada
    assert o["kpis"]["branches"] == 2 and o["kpis"]["uncovered"] == 1 and o["kpis"]["headcount"] == 2

    # farmasevt keldi: yopilmagan yozilma -> "hozir bor"
    await hr.post("/api/v1/attendance/records", json={"employee_id": far, "work_date": "2026-11-02", "check_in_at": "2026-11-02T09:05:00+05:00", "shift_id": ctx["shift"], "reason": "Test yozuv"})
    a = next(i for i in (await hr.get(f"{P}/overview")).json()["items"] if i["id"] == ctx["a"])
    assert a["today"]["here_now"] == 1 and a["today"]["late"] == 0 and a["flags"] == ["short"] and a["severity"] == "short"
    assert (await hr.get(f"{P}/overview", params={"only": "uncovered"})).json()["total"] == 0
    assert (await hr.get(f"{P}/overview", params={"only": "short"})).json()["total"] == 2  # bo'sh Filial 2 ham me'yordan kam
    assert (await hr.get(f"{P}/overview", params={"q": "chilon"})).json()["total"] == 1
    assert (await hr.get(f"{P}/overview", params={"district": "Yunusobod"})).json()["total"] == 1
    assert mudir


async def test_visibility_scopes(new_client, clock):
    ctx = await setup(new_client)
    mine = (await ctx["coord"].get(f"{P}/overview")).json()
    assert [i["id"] for i in mine["items"]] == [ctx["a"]]
    assert (await ctx["coord"].get(f"{P}/branches/{ctx['a']}")).status_code == 200
    assert (await ctx["coord"].get(f"{P}/branches/{ctx['b']}")).status_code == 404
    assert [i["id"] for i in (await ctx["coord2"].get(f"{P}/overview")).json()["items"]] == [ctx["b"]]
    assert [m["id"] for m in (await ctx["coord"].get(f"{P}/map")).json()] == [ctx["a"]]  # faqat koordinatasi bor va o'zinikilari
    far, _ = await as_user(new_client, "ali", "farmasevt")
    assert (await far.get(f"{P}/overview")).status_code == 403
    assert (await ctx["coord"].put(f"{P}/branches/{ctx['a']}/profile", json={"staff_norm": {}, "is_24h": True})).status_code == 403
    assert (await ctx["coord"].get(f"{P}/quality")).status_code == 403
    mgr, _ = await as_user(new_client, "m", "hr_menejer")
    assert (await mgr.get(f"{P}/overview")).json()["kpis"]["branches"] == 2


async def test_card_team_and_week_coverage(new_client, clock):
    ctx = await setup(new_client)
    await profile(ctx["hr"], ctx["a"])
    await mk_employee("Mudirov", ctx["a"], ctx["pos"]["Mudir"])
    await mk_employee("Stajyorov", ctx["a"], ctx["pos"]["Stajyor"])
    await mk_employee("Haydov", ctx["a"], ctx["pos"]["Haydovchi"])
    card = (await ctx["coord"].get(f"{P}/branches/{ctx['a']}")).json()
    assert [t["role"] for t in card["team"]] == ["manager", "intern", "other"]
    assert card["team"][0]["status"] == "pending" and card["team"][0]["shift"] == "09:00–21:00"
    assert card["counts"] == {"manager": 1, "pharmacist": 0, "intern": 1, "other": 1}
    # 7 kun: du-sh mudir ishlaydi, yakshanba dam -> yopiq/ishsiz kun "qamrovsiz"
    assert [w["uncovered"] for w in card["week"]] == [False, False, False, False, False, False, True]
    assert card["week"][0]["by_role"]["manager"] == 1 and card["week"][6]["scheduled"] == 0
    assert card["can_manage"] is False and card["can_request"] is True
    assert card["hours"] == {"is_24h": False, "open": "09:00", "close": "21:00"}


async def test_profile_validation_and_bulk(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    bad = {"staff_norm": {"manager": 1, "pharmacist": 2, "intern": 0}, "is_24h": False, "open_time": "09:00"}
    assert (await hr.put(f"{P}/branches/{ctx['a']}/profile", json=bad)).status_code == 422
    assert (await hr.put(f"{P}/branches/{ctx['a']}/profile", json={**bad, "close_time": "09:00"})).status_code == 422
    await profile(hr, ctx["a"], is_24h=True)
    card = (await hr.get(f"{P}/branches/{ctx['a']}")).json()
    assert card["hours"] == {"is_24h": True, "open": None, "close": None}

    r = await hr.post(f"{P}/norms/bulk", json={"staff_norm": {"manager": 1, "pharmacist": 3, "intern": 1}, "hours": True, "is_24h": False, "open_time": "08:00", "close_time": "22:00"})
    assert r.json() == {"branches": 2, "applied": False}  # dry run hech narsani o'zgartirmaydi
    assert (await hr.get(f"{P}/branches/{ctx['b']}")).json()["norm"] == {"manager": 1, "pharmacist": 2, "intern": 0}
    r = await hr.post(f"{P}/norms/bulk", json={"branch_ids": [ctx["b"]], "staff_norm": {"manager": 1, "pharmacist": 3, "intern": 1}, "hours": True, "open_time": "08:00", "close_time": "22:00", "dry_run": False})
    assert r.json() == {"branches": 1, "applied": True}
    b = (await hr.get(f"{P}/branches/{ctx['b']}")).json()
    assert b["norm"]["pharmacist"] == 3 and b["hours"]["open"] == "08:00"
    assert (await hr.get(f"{P}/branches/{ctx['a']}")).json()["norm"]["pharmacist"] == 2  # boshqa filial tegilmadi
    assert (await hr.post(f"{P}/norms/bulk", json={})).json()["detail"]["code"] == "nothing_to_apply"
    assert (await hr.get("/api/v1/audit", params={"action": "pharmacy.bulk_norms"})).json()["total"] == 1


async def test_needs_flow(new_client, clock):
    ctx = await setup(new_client)
    hr, coord = ctx["hr"], ctx["coord"]
    await profile(hr, ctx["a"])
    await mk_employee("Mudirov", ctx["a"], ctx["pos"]["Mudir"])

    sug = (await coord.get(f"{P}/needs/suggestions")).json()
    assert sug == [{"branch": {"id": ctx["a"], "number": 1, "name": "Filial 1"}, "role": "pharmacist", "gap": 2}]

    r = await coord.post(f"{P}/needs", json={"branch_id": ctx["a"], "role": "pharmacist", "count": 2, "urgency": "urgent", "reason": "Ikki farmasevt ketdi"})
    assert r.status_code == 201 and r.json()["status"] == "open"
    nid = r.json()["id"]
    assert (await coord.post(f"{P}/needs", json={"branch_id": ctx["b"], "role": "intern"})).status_code == 404  # o'ziniki emas
    assert (await coord.post(f"{P}/needs", json={"branch_id": ctx["a"], "role": "driver"})).status_code == 422
    assert (await coord.get(f"{P}/needs/suggestions")).json() == []  # so'rov bor: takror taklif qilinmaydi

    kinds = [n["kind"] for n in (await hr.get("/api/v1/notifications")).json()["items"]]
    assert "pharmacy.need" in kinds
    a = next(i for i in (await hr.get(f"{P}/overview")).json()["items"] if i["id"] == ctx["a"])
    assert "needs" in a["flags"] and a["open_needs"] == 2

    # tahrirlash (yaratuvchi), filialni almashtirib bo'lmaydi
    u = await coord.put(f"{P}/needs/{nid}", json={"branch_id": ctx["a"], "role": "pharmacist", "count": 1, "urgency": "normal"})
    assert u.json()["count"] == 1
    assert (await coord.put(f"{P}/needs/{nid}", json={"branch_id": ctx["b"], "role": "pharmacist"})).status_code in (400, 404)
    # yopish: koordinator "bajarildi" qila olmaydi; HR qiladi, yaratuvchiga xabar boradi
    assert (await coord.post(f"{P}/needs/{nid}/close", json={"status": "filled"})).status_code == 403
    r = await hr.post(f"{P}/needs/{nid}/close", json={"status": "filled", "note": "Yangi xodim olindi"})
    assert r.json()["status"] == "filled"
    assert "pharmacy.need_filled" in [n["kind"] for n in (await coord.get("/api/v1/notifications")).json()["items"]]
    assert (await hr.post(f"{P}/needs/{nid}/close", json={"status": "filled"})).json()["detail"]["code"] == "already_closed"
    assert (await coord.put(f"{P}/needs/{nid}", json={"branch_id": ctx["a"], "role": "pharmacist"})).status_code == 403  # yopilganini tahrirlab bo'lmaydi

    # yaratuvchi o'z so'rovini sabab bilan bekor qiladi
    n2 = (await coord.post(f"{P}/needs", json={"branch_id": ctx["a"], "role": "intern"})).json()["id"]
    assert (await coord.post(f"{P}/needs/{n2}/close", json={"status": "cancelled"})).json()["detail"]["code"] == "note_required"
    assert (await coord.post(f"{P}/needs/{n2}/close", json={"status": "cancelled", "note": "Kerak emas"})).json()["status"] == "cancelled"
    assert (await hr.get(f"{P}/needs", params={"status": "all"})).json()["total"] == 2
    assert (await hr.get(f"{P}/needs", params={"status": "filled"})).json()["total"] == 1
    assert (await ctx["coord2"].get(f"{P}/needs/{nid}")).status_code == 404
    assert [x["role"] for x in (await hr.get(f"{P}/branches/{ctx['a']}")).json()["closed_needs"]] == ["intern", "pharmacist"]


async def test_quality_and_map(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    q = (await hr.get(f"{P}/quality")).json()
    codes = {i["code"]: i["count"] for i in q["issues"]}
    assert q["branches"] == 2 and q["complete"] == 0
    assert codes["no_geo"] == 1 and codes["no_manager"] == 2 and codes["no_staff"] == 2 and codes["no_phone"] == 1 and codes["no_hours"] == 2
    await profile(hr, ctx["a"])
    await mk_employee("Mudirov", ctx["a"], ctx["pos"]["Mudir"])
    codes = {i["code"]: i["count"] for i in (await hr.get(f"{P}/quality")).json()["issues"]}
    assert codes["no_manager"] == 1 and "no_hours" in codes and codes["no_hours"] == 1 and codes.get("no_staff") == 1

    pts = (await hr.get(f"{P}/map")).json()
    assert [p["id"] for p in pts] == [ctx["a"]] and pts[0]["severity"] in ("uncovered", "short")
