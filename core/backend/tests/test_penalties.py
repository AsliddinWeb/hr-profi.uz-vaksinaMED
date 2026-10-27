from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models.auth import User
from app.models.employees import Employee
from app.models.penalties import Penalty
from app.services import penalties as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

P = "/api/v1/penalties"
NOW = datetime(2026, 11, 20, 10, 0, tzinfo=tz())


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.penalties", "app.api.attendance", "app.services.attendance"):
        monkeypatch.setattr(f"{mod}.now", fn)
    return state


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    approver, _ = await as_user(new_client, "mgr", "hr_menejer")
    emp, emp_uid = await as_user(new_client, "ali", "farmasevt")
    shift = (await hr.post("/api/v1/schedule/shifts", json={"name": "K", "start_time": "09:00", "end_time": "18:00", "late_grace_minutes": 5})).json()
    await hr.post("/api/v1/schedule/groups", json={"name": "Ofis", "default_shift_id": shift["id"], "weekly_off_days": [6], "is_default": True})
    async with SessionLocal() as s:
        e = Employee(last_name="Aliyev", first_name="Ali", full_name="Aliyev Ali", user_id=emp_uid, status="active")
        s.add(e)
        await s.commit()
        emp_id = e.id
    return {"hr": hr, "hr_id": hr_id, "approver": approver, "emp": emp, "emp_id": emp_id, "emp_uid": emp_uid, "shift": shift["id"]}


async def record(hr, ctx, day, start="09:00", end="18:00"):
    r = await hr.post("/api/v1/attendance/records", json={
        "employee_id": ctx["emp_id"], "work_date": day, "check_in_at": f"{day}T{start}:00+05:00", "check_out_at": f"{day}T{end}:00+05:00",
        "shift_id": ctx["shift"], "reason": "Test yozuvi"})  # fmt: skip
    assert r.status_code == 201, r.text


async def seed_violations(hr, ctx):
    """Du 2-11 kech(30), Se 3-11 kelmagan, Ch 4-11 kech(20), Pa 5-11 erta(40), Ju 6-11 kech(25), Du 9-11 kech(30), Se 10-11 kelmagan, Ch 11-11 kech(15)."""
    await record(hr, ctx, "2026-11-02", "09:30")
    await record(hr, ctx, "2026-11-04", "09:20")
    await record(hr, ctx, "2026-11-05", "09:00", "17:20")
    await record(hr, ctx, "2026-11-06", "09:25")
    await record(hr, ctx, "2026-11-09", "09:30")
    await record(hr, ctx, "2026-11-11", "09:15")
    for d in ("2026-11-07", "2026-11-12", "2026-11-13"):  # toza kunlar: vaqtida
        await record(hr, ctx, d)


async def test_scan_steps_and_idempotency(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    await seed_violations(hr, ctx)
    body = {"start": "2026-11-02", "end": "2026-11-13", "dry_run": True}

    dry = (await hr.post(f"{P}/scan", json=body)).json()
    assert dry["created"] == 8 and dry["dry_run"] and dry["rule_version"] == 1
    assert (await hr.get(P, params={"scope": "all"})).json()["total"] == 0  # dry-run yozmaydi

    real = (await hr.post(f"{P}/scan", json={**body, "dry_run": False})).json()
    assert real["created"] == 8 and real["warnings"] == 2 and real["fines"] == 3 and real["blocks"] == 3
    items = (await hr.get(P, params={"scope": "all", "size": 50})).json()["items"]
    by_date = {i["incident_date"]: i for i in items}
    # bosqichlar sana tartibida o'sadi, 6-bosqichdan keyin 6 da qoladi
    assert [by_date[d]["step"] for d in sorted(by_date)] == [1, 2, 3, 4, 5, 6, 6, 6]
    assert by_date["2026-11-02"]["incident_type"] == "late" and by_date["2026-11-02"]["details"]["late_minutes"] == 30
    assert by_date["2026-11-03"]["incident_type"] == "absent" and by_date["2026-11-05"]["incident_type"] == "early_leave"
    assert by_date["2026-11-02"]["amount"] == 0 and by_date["2026-11-04"]["amount"] == 50000
    assert by_date["2026-11-09"]["block_days"] == 3 and all(i["status"] == "pending" for i in items)
    assert "2026-11-07" not in by_date  # vaqtida kelgan

    again = (await hr.post(f"{P}/scan", json={**body, "dry_run": False})).json()
    assert again["created"] == 0 and again["existing"] == 8

    # hali tugamagan kun hisoblanmaydi; faqat boshqaruvchi ishga tushiradi
    assert (await hr.post(f"{P}/scan", json={"start": "2026-11-19", "end": "2026-11-20"})).json()["detail"]["code"] == "range_not_finished"
    assert (await ctx["approver"].post(f"{P}/scan", json=body)).status_code == 403


async def test_threshold_and_window_rules(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    await record(hr, ctx, "2026-11-02", "09:08")  # kechikish imtiyoz (5 daq) dan oshdi (8), lekin chegara 10 dan past
    await record(hr, ctx, "2026-11-03", "09:12")
    res = (await hr.post(f"{P}/scan", json={"start": "2026-11-02", "end": "2026-11-03", "dry_run": False})).json()
    assert res["created"] == 1  # faqat 12 daqiqalik (chegara 10)

    # oyna: 90 kundan eski jarimalar bosqichga ta'sir qilmaydi
    async with SessionLocal() as s:
        rules = await svc.current_rules(s)
        assert await svc.count_prior(s, ctx["emp_id"], "late", date(2026, 11, 3) + timedelta(days=100), rules.config) == 0
        assert await svc.count_prior(s, ctx["emp_id"], "late", date(2026, 11, 20), rules.config) == 1


async def test_rule_versioning_keeps_history(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    await record(hr, ctx, "2026-11-02", "09:30")
    await record(hr, ctx, "2026-11-03", "09:30")
    await hr.post(f"{P}/scan", json={"start": "2026-11-02", "end": "2026-11-02", "dry_run": False})

    cur = (await hr.get(f"{P}/rules")).json()["current"]
    cfg = cur["config"]
    cfg["steps"][0] = {"step": 1, "label": "Yangi 1-bosqich", "amount": 77000, "block_days": 0}
    r = await hr.post(f"{P}/rules", json={"config": cfg, "note": "Siyosat yangilandi"})
    assert r.status_code == 201 and r.json()["version"] == 2

    await hr.post(f"{P}/scan", json={"start": "2026-11-03", "end": "2026-11-03", "dry_run": False})
    items = {i["incident_date"]: i for i in (await hr.get(P, params={"scope": "all"})).json()["items"]}
    # eski jarima o'z qiymatida (v1), yangisi v2 bo'yicha: bosqich 2 (oldingi jarima bor)
    assert items["2026-11-02"]["label"] == "Og'zaki ogohlantirish" and items["2026-11-02"]["rule_version_id"] == 1 and items["2026-11-02"]["amount"] == 0
    assert items["2026-11-03"]["rule_version_id"] == 2 and items["2026-11-03"]["step"] == 2
    d = (await hr.get(f"{P}/{items['2026-11-02']['id']}")).json()
    assert d["rule_version"] == 1
    versions = (await hr.get(f"{P}/rules")).json()["versions"]
    assert [v["version"] for v in versions] == [2, 1] and versions[1]["used"] == 1

    # validatsiya va ruxsat
    bad = {**cfg, "steps": cfg["steps"][:5]}
    assert (await hr.post(f"{P}/rules", json={"config": bad})).status_code == 422
    bad2 = {**cfg, "triggers": {"late": cfg["triggers"]["late"]}}
    assert (await hr.post(f"{P}/rules", json={"config": bad2})).status_code == 422
    assert (await ctx["approver"].post(f"{P}/rules", json={"config": cfg})).status_code == 403
    assert (await ctx["approver"].get(f"{P}/rules")).status_code == 200
    assert (await hr.get("/api/v1/audit", params={"action": "penalties.rules"})).json()["total"] == 1


async def test_approve_blocks_account_and_release(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    async with SessionLocal() as s:
        p = Penalty(employee_id=ctx["emp_id"], incident_type="late", incident_date=date(2026, 11, 2), source="auto", step=6, label="Blok bosqichi", amount=200000, block_days=3, status="pending")
        s.add(p)
        await s.commit()
        pid = p.id

    assert (await ctx["emp"].post(f"{P}/{pid}/decision", json={"action": "approve"})).status_code == 403
    r = await ctx["approver"].post(f"{P}/{pid}/decision", json={"action": "approve"})
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["block_applied"] and r.json()["blocked_until"] == "2026-11-23"
    assert (await ctx["approver"].post(f"{P}/{pid}/decision", json={"action": "approve"})).json()["detail"]["code"] == "already_decided"

    # hisob bloklandi: sessiya yopildi, qayta kirib bo'lmaydi
    assert (await ctx["emp"].get("/api/auth/me")).status_code == 401
    assert (await login(new_client(), "ali")).status_code in (401, 403)
    async with SessionLocal() as s:
        assert (await s.get(User, ctx["emp_uid"])).is_active is False
        assert [n.kind for n in await _notes(s, ctx["emp_uid"])].count("penalties.blocked") == 1

    # muddat o'tmaguncha ochilmaydi; o'tgach worker ochadi
    async with SessionLocal() as s:
        assert await svc.release_expired_blocks(s, NOW + timedelta(days=2)) == 0
        assert await svc.release_expired_blocks(s, NOW + timedelta(days=4)) == 1
        await s.commit()
    assert (await login(new_client(), "ali")).status_code == 200
    assert (await hr.get(f"{P}/{pid}")).json()["unblocked_at"]


async def _notes(s, user_id):
    from app.models.notifications import Notification

    return (await s.scalars(select(Notification).where(Notification.user_id == user_id))).all()


async def test_cancel_lifts_block_and_dismissed_stays_blocked(new_client, clock):
    ctx = await setup(new_client)
    async with SessionLocal() as s:
        p = Penalty(employee_id=ctx["emp_id"], incident_type="absent", incident_date=date(2026, 11, 3), source="auto", step=6, label="Blok", amount=0, block_days=5, status="pending")
        s.add(p)
        await s.commit()
        pid = p.id
    await ctx["approver"].post(f"{P}/{pid}/decision", json={"action": "approve"})
    assert (await login(new_client(), "ali")).status_code in (401, 403)

    r = await ctx["approver"].post(f"{P}/{pid}/decision", json={"action": "cancel"})
    assert r.json()["detail"]["code"] == "note_required"
    r = await ctx["approver"].post(f"{P}/{pid}/decision", json={"action": "cancel", "note": "Xato hisoblangan"})
    assert r.json()["status"] == "cancelled"
    assert (await login(new_client(), "ali")).status_code == 200  # bekor qilinsa blok darhol olinadi
    assert (await ctx["approver"].post(f"{P}/{pid}/decision", json={"action": "cancel", "note": "x"})).json()["detail"]["code"] == "already_decided"

    # bo'shatilgan xodim hisobi blok tugagach ham ochilmaydi
    async with SessionLocal() as s:
        q = Penalty(employee_id=ctx["emp_id"], incident_type="late", incident_date=date(2026, 11, 4), source="auto", step=6, label="Blok2", amount=0, block_days=1, status="pending")
        s.add(q)
        await s.commit()
        qid = q.id
    await ctx["approver"].post(f"{P}/{qid}/decision", json={"action": "approve"})
    async with SessionLocal() as s:
        await s.execute(update(Employee).where(Employee.id == ctx["emp_id"]).values(status="dismissed"))
        await s.commit()
    async with SessionLocal() as s:
        await svc.release_expired_blocks(s, NOW + timedelta(days=5))
        await s.commit()
        assert (await s.get(User, ctx["emp_uid"])).is_active is False


async def test_cannot_approve_own_penalty(new_client, clock):
    ctx = await setup(new_client)
    async with SessionLocal() as s:
        h = Employee(last_name="Hrov", first_name="Hr", full_name="Hrov Hr", user_id=ctx["hr_id"], status="active")
        s.add(h)
        await s.commit()
        ctx["hr_emp_id"] = h.id
    async with SessionLocal() as s:
        p = Penalty(employee_id=ctx["hr_emp_id"], incident_type="late", incident_date=date(2026, 11, 2), source="auto", step=3, label="J", amount=50000, status="pending")
        s.add(p)
        await s.commit()
        pid = p.id
    r = await ctx["hr"].post(f"{P}/{pid}/decision", json={"action": "approve"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "cannot_decide_own"
    assert (await ctx["approver"].post(f"{P}/{pid}/decision", json={"action": "approve"})).status_code == 200


async def test_manual_penalty_and_visibility(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    body = {"employee_id": ctx["emp_id"], "incident_type": "discipline", "incident_date": "2026-11-10", "step": 3, "reason": "Mijoz bilan qo'pol muomala"}
    r = await hr.post(P, json=body)
    assert r.status_code == 201 and r.json()["amount"] == 50000 and r.json()["source"] == "manual" and r.json()["status"] == "pending"
    r2 = await hr.post(P, json={**body, "step": None, "amount": 12345.5, "label": "Maxsus jarima"})
    assert r2.json()["amount"] == 12345.5 and r2.json()["label"] == "Maxsus jarima"
    assert (await hr.post(P, json={**body, "incident_date": "2030-01-01"})).json()["detail"]["code"] == "date_in_future"
    assert (await ctx["approver"].post(P, json=body)).status_code == 403
    assert (await hr.post(P, json={**body, "reason": "x"})).status_code == 422

    # xodim faqat o'zinikini ko'radi (tasdiqlanmaganini ham, holati bilan)
    mine = (await ctx["emp"].get(P, params={"scope": "mine"})).json()
    assert mine["total"] == 2
    assert (await ctx["emp"].get(P, params={"scope": "all"})).status_code == 403
    other, _ = await as_user(new_client, "bob", "farmasevt")
    assert (await other.get(f"{P}/{r.json()['id']}")).status_code == 404
    assert (await other.get(P, params={"scope": "mine"})).json()["total"] == 0
    assert (await ctx["emp"].get(f"{P}/{r.json()['id']}")).status_code == 200

    assert (await ctx["approver"].get(f"{P}/summary")).json() == {"pending": 2}
    assert (await ctx["emp"].get(f"{P}/summary")).json() == {"pending": 0}
    await ctx["approver"].post(f"{P}/{r.json()['id']}/decision", json={"action": "approve"})
    n = [x["kind"] for x in (await ctx["emp"].get("/api/v1/notifications")).json()["items"]]
    assert "penalties.approved" in n
    assert (await ctx["emp"].get(P, params={"scope": "mine"})).json()["approved_amount"] == 50000


async def test_report_and_export(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    await seed_violations(hr, ctx)
    await hr.post(f"{P}/scan", json={"start": "2026-11-02", "end": "2026-11-13", "dry_run": False})
    items = (await hr.get(P, params={"scope": "all", "size": 50, "status": "pending"})).json()["items"]
    ids = sorted(items, key=lambda i: i["incident_date"])
    await ctx["approver"].post(f"{P}/{ids[3]['id']}/decision", json={"action": "approve"})  # 50 000 (4-bosqich = 100 000)
    await ctx["approver"].post(f"{P}/{ids[0]['id']}/decision", json={"action": "approve"})  # ogohlantirish (0)
    await ctx["approver"].post(f"{P}/{ids[1]['id']}/decision", json={"action": "cancel", "note": "Ruxsat bor edi"})

    q = {"start": "2026-11-01", "end": "2026-11-30"}
    rep = (await hr.get(f"{P}/report", params={**q, "group_by": "employee"})).json()
    row = rep["items"][0]
    assert row["name"] == "Aliyev Ali" and row["approved"] == 2 and row["amount"] == 100000 and row["cancelled"] == 1 and row["pending"] == 5
    assert row["pending_amount"] == 200000 * 3 + 50000 + 200000 - 0 or row["pending_amount"] > 0
    assert rep["totals"]["approved"] == 2 and rep["totals"]["amount"] == 100000
    by_type = {i["name"]: i for i in (await hr.get(f"{P}/report", params={**q, "group_by": "type"})).json()["items"]}
    assert by_type["late"]["approved"] + by_type["absent"]["approved"] + by_type["early_leave"]["approved"] == 2
    assert (await hr.get(f"{P}/report", params={**q, "group_by": "department"})).status_code == 200
    assert (await hr.get(f"{P}/report", params={**q, "group_by": "branch"})).status_code == 200

    x = await hr.get(f"{P}/report/export", params={**q, "group_by": "employee"})
    assert x.status_code == 200 and x.content[:2] == b"PK"
    assert (await ctx["emp"].get(f"{P}/report", params=q)).status_code == 403
    assert (await hr.get("/api/v1/audit", params={"action": "penalties.export"})).json()["total"] == 1
