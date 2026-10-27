from datetime import date, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.employees import Employee
from app.models.growth import Promotion
from app.models.org import Position
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

AT = "/api/v1/attestation"
GR = "/api/v1/growth"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


async def setup(new_client):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    hr, _ = await as_user(new_client, "hrm", "hr_menejer")
    mudir, mudir_id = await as_user(new_client, "mudir", "mudir")
    coord, coord_id = await as_user(new_client, "coord", "koordinator")
    far, far_uid = await as_user(new_client, "far", "farmasevt")
    other, other_uid = await as_user(new_client, "other", "farmasevt")
    branch = (await hrd.post("/api/v1/branches", json={"number": 51, "name": "F51", "manager_user_id": mudir_id, "coordinator_user_id": coord_id})).json()
    async with SessionLocal() as s:
        p1, p2 = Position(name="Stajyor-F"), Position(name="Farmatsevt-F")
        s.add_all([p1, p2])
        await s.flush()
        e = Employee(last_name="Far", first_name="X", full_name="Far X", user_id=far_uid, status="active", branch_id=branch["id"], position_id=p1.id, hire_date=date(2026, 1, 1))
        o = Employee(last_name="Other", first_name="X", full_name="Other X", user_id=other_uid, status="active", branch_id=None, position_id=p1.id, hire_date=date(2026, 1, 1))
        s.add_all([e, o])
        await s.commit()
        ids = {"p1": p1.id, "p2": p2.id, "emp": e.id, "other": o.id}
    lv = (await hrd.put(f"{GR}/levels", json={"levels": [{"name": "Stajyor", "position_id": ids["p1"]}, {"name": "Farmatsevt", "position_id": ids["p2"], "salary_min": 3_000_000}]})).json()
    return {"hrd": hrd, "hr": hr, "mudir": mudir, "coord": coord, "far": far, "other": other, "lv": lv, **ids}


async def test_levels_and_permissions(new_client):
    ctx = await setup(new_client)
    assert [x["name"] for x in ctx["lv"]] == ["Stajyor", "Farmatsevt"] and ctx["lv"][1]["salary_min"] == 3_000_000
    assert (await ctx["hr"].put(f"{GR}/levels", json={"levels": []})).status_code == 403  # faqat HRD
    r = await ctx["hrd"].put(f"{GR}/levels", json={"levels": [{"name": "A", "position_id": ctx["p1"]}, {"name": "B", "position_id": ctx["p1"]}]})
    assert r.json()["detail"]["code"] == "position_duplicate"
    assert (await ctx["far"].get(f"{GR}/levels")).status_code == 403


async def test_attestation_cycle_scores_decision_and_auto_promotion(new_client):
    ctx = await setup(new_client)
    assert (await ctx["far"].post(f"{AT}/cycles")).status_code == 403
    r = await ctx["hr"].post(f"{AT}/cycles", params={"month": "2026-09"})
    assert r.status_code == 201 and r.json()["created"] == 2  # ikkala xodim ham zinapoyadagi lavozimda
    assert (await ctx["hr"].post(f"{AT}/cycles", params={"month": "2026-09"})).json()["created"] == 0
    assert any(n["kind"] == "attestation.opened" for n in await notes(ctx["far"]))
    assert any(n["kind"] == "attestation.summary" for n in await notes(ctx["mudir"]))

    mine = (await ctx["far"].get(AT, params={"scope": "mine"})).json()
    assert len(mine) == 1 and mine[0]["level"] == "Stajyor" and not mine[0]["can"]["score"]
    aid = mine[0]["id"]
    # begona xodim va oddiy farmatsevt boshqa attestatsiyani ko'rmaydi; mudir ko'radi
    other_id = next(a["id"] for a in (await ctx["hr"].get(AT, params={"month": "2026-09"})).json() if a["employee"]["name"] == "Other X")
    assert (await ctx["far"].get(f"{AT}/{other_id}")).status_code == 404
    assert (await ctx["mudir"].get(f"{AT}/{aid}")).status_code == 200
    assert (await ctx["mudir"].get(f"{AT}/{other_id}")).status_code == 404  # boshqa filial

    # ball va fidbek
    assert (await ctx["mudir"].post(f"{AT}/{aid}/scores", json={"test_score": 90})).status_code == 403
    assert (await ctx["hr"].post(f"{AT}/{aid}/scores", json={})).json()["detail"]["code"] == "scores_required"
    r = await ctx["hr"].post(f"{AT}/{aid}/scores", json={"test_score": 80, "practical_score": 60})
    assert r.json()["total"] == 70.0 and r.json()["status"] == "scored" and r.json()["passes"]
    assert (await ctx["mudir"].post(f"{AT}/{aid}/feedback", json={"text": "Yaxshi"})).json()["role"] == "zav"
    assert (await ctx["coord"].post(f"{AT}/{aid}/feedback", json={"text": "Mos"})).json()["role"] == "coordinator"
    assert (await ctx["far"].post(f"{AT}/{aid}/feedback", json={"text": "Men"})).status_code == 403

    # qaror: faqat HR; mezondan past "o'tdi" uchun sabab shart
    assert (await ctx["mudir"].post(f"{AT}/{aid}/decide", json={"decision": "passed"})).status_code == 403
    await ctx["hr"].post(f"{AT}/{aid}/scores", json={"test_score": 50, "practical_score": 50})
    assert (await ctx["hr"].post(f"{AT}/{aid}/decide", json={"decision": "passed"})).json()["detail"]["code"] == "note_required"
    await ctx["hr"].post(f"{AT}/{aid}/scores", json={"test_score": 90, "practical_score": 80})
    r = await ctx["hr"].post(f"{AT}/{aid}/decide", json={"decision": "passed"})
    assert r.status_code == 200 and r.json()["status"] == "decided"
    assert any(n["kind"] == "attestation.decided" and "o'tdi" in n["body"]["uz"] for n in await notes(ctx["far"]))
    assert (await ctx["hr"].post(f"{AT}/{aid}/decide", json={"decision": "retake"})).json()["detail"]["code"] == "already_decided"

    # bitta o'tish yetmaydi (standart 2 ta); ikkinchi oy ham o'tsa o'sish taklifi paydo bo'ladi
    assert (await ctx["hrd"].get(f"{GR}/promotions")).json()["items"] == []
    await ctx["hr"].post(f"{AT}/cycles", params={"month": "2026-10"})
    aid2 = next(a["id"] for a in (await ctx["far"].get(AT, params={"scope": "mine", "month": "2026-10"})).json())
    await ctx["hr"].post(f"{AT}/{aid2}/scores", json={"test_score": 85, "practical_score": 85})
    await ctx["hr"].post(f"{AT}/{aid2}/decide", json={"decision": "passed"})
    items = (await ctx["hrd"].get(f"{GR}/promotions", params={"status": "proposed"})).json()["items"]
    assert len(items) == 1 and items[0]["source"] == "auto" and items[0]["from"] == "Stajyor" and items[0]["to"] == "Farmatsevt"
    assert any(n["kind"] == "career.proposed" for n in await notes(ctx["hrd"]))

    rep = (await ctx["hrd"].get(f"{AT}/report", params={"month": "2026-10"})).json()
    assert rep["levels"][0]["passed"] == 1 and rep["levels"][0]["open"] == 1
    assert (await ctx["far"].get(f"{AT}/report", params={"month": "2026-10"})).status_code == 403


async def test_promotion_approval_changes_position(new_client):
    ctx = await setup(new_client)
    to_id = ctx["lv"][1]["id"]
    r = await ctx["coord"].post(f"{GR}/promotions", json={"employee_id": ctx["emp"], "to_level_id": to_id, "basis": "Yaxshi ishlaydi"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert (await ctx["coord"].post(f"{GR}/promotions", json={"employee_id": ctx["emp"], "to_level_id": to_id})).json()["detail"]["code"] == "promotion_exists"
    assert (await ctx["coord"].post(f"{GR}/promotions/{pid}/decide", json={"action": "approve"})).status_code == 403
    assert (await ctx["hrd"].post(f"{GR}/promotions/{pid}/decide", json={"action": "reject"})).json()["detail"]["code"] == "note_required"
    r = await ctx["hrd"].post(f"{GR}/promotions/{pid}/decide", json={"action": "approve", "note": "OK"})
    assert r.status_code == 200 and r.json()["status"] == "applied"
    async with SessionLocal() as s:
        assert (await s.get(Employee, ctx["emp"])).position_id == ctx["p2"]
        assert (await s.get(Promotion, pid)).status == "applied"
    assert any(n["kind"] == "employee.transferred" for n in await notes(ctx["far"]))
    # pastga "o'sish" mumkin emas
    stj = ctx["lv"][0]["id"]
    assert (await ctx["coord"].post(f"{GR}/promotions", json={"employee_id": ctx["emp"], "to_level_id": stj})).json()["detail"]["code"] == "level_not_higher"


async def test_settings_and_performance_score(new_client):
    ctx = await setup(new_client)
    assert (await ctx["hr"].put(f"{GR}/settings/attestation", json={"value": {"pass_score": 60}})).status_code == 403
    r = await ctx["hrd"].put(f"{GR}/settings/attestation", json={"value": {"pass_score": 60, "test_weight": 100, "practical_weight": 0, "promote_after": 1}})
    assert r.json()["pass_score"] == 60
    assert (await ctx["hrd"].put(f"{GR}/settings/attestation", json={"value": {"pass_score": 150}})).json()["detail"]["code"] == "value_invalid"
    assert (await ctx["hrd"].put(f"{GR}/settings/nope", json={"value": {}})).status_code == 404

    # davomat: o'tgan 30 kunda 3 kun keldi, 1 kun kelmadi (grafik kunlari)
    async with SessionLocal() as s:
        today = datetime.now(tz()).date()
        for d in range(2, 5):
            day = today - timedelta(days=d)
            s.add(AttendanceRecord(employee_id=ctx["emp"], work_date=day, check_in_at=datetime.combine(day, datetime.min.time(), tzinfo=tz()) + timedelta(hours=9), check_out_at=datetime.combine(day, datetime.min.time(), tzinfo=tz()) + timedelta(hours=18), in_method="qr", out_method="qr", worked_minutes=540))
        await s.commit()
    me = (await ctx["far"].get(f"{GR}/performance/{ctx['emp']}")).json()
    comps = {c["key"]: c for c in me["components"]}
    assert comps["attendance"]["available"] and comps["attendance"]["value"] <= 100
    assert not comps["attestation"]["available"] and not comps["learning"]["available"]
    assert me["score"] is not None
    assert (await ctx["far"].get(f"{GR}/performance/{ctx['other']}")).status_code == 404

    # ro'yxat: HR hammasini, mudir faqat o'z filialini, farmasevt hech narsa
    assert len((await ctx["hr"].get(f"{GR}/performance")).json()["items"]) == 2
    mud = (await ctx["mudir"].get(f"{GR}/performance")).json()["items"]
    assert [x["employee"]["name"] for x in mud] == ["Far X"]
    assert (await ctx["far"].get(f"{GR}/performance")).status_code == 403
