from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.employees import Employee
from app.models.mobile import MobilePermit
from app.services import mobile as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

M = "/api/v1/mobile"


def at(h, m=0, s=0, day=10):
    return datetime(2026, 11, day, h, m, s, tzinfo=tz())


@pytest.fixture
def clock(monkeypatch):
    state = {"t": at(9, 10)}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.mobile", "app.api.attendance", "app.services.attendance"):
        monkeypatch.setattr(f"{mod}.now", fn)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    boss, _ = await as_user(new_client, "boss", "direktor")
    far, _ = await as_user(new_client, "far", "farmasevt")
    w, w_uid = await as_user(new_client, "kuryer", "koordinator")
    async with SessionLocal() as s:
        e = Employee(last_name="Kuryer", first_name="X", full_name="Kuryer X", user_id=w_uid, status="active")
        s.add(e)
        await s.commit()
        eid = e.id
    shift = (await hr.post("/api/v1/schedule/shifts", json={"name": "K", "start_time": "09:00", "end_time": "18:00", "late_grace_minutes": 5})).json()
    await hr.post("/api/v1/schedule/groups", json={"name": "Ofis", "default_shift_id": shift["id"], "weekly_off_days": [6], "is_default": True})
    return {"hr": hr, "boss": boss, "far": far, "w": w, "eid": eid}


async def grant(ctx, **kw):
    r = await ctx["hr"].put(f"{M}/permits/{ctx['eid']}", json={"enabled": True, "window_start": "08:00:00", "window_end": "20:00:00", **kw})
    assert r.status_code == 200, r.text
    return r.json()


def pts(clock_t, n, lat0=41.30, step=0.001, start_min=0, every_s=60, **kw):
    return [{"lat": lat0 + i * step, "lng": 69.28, "accuracy": 10, "speed": 5, "at": (clock_t + timedelta(minutes=start_min, seconds=i * every_s)).isoformat(), **kw} for i in range(n)]


def test_units():
    a = (41.30, 69.28, at(10))
    assert 111 < svc.segment_m(a, (41.301, 69.28, at(10, 1))) < 112
    assert svc.segment_m(a, (45.0, 69.28, at(10, 0, 10))) is None  # imkonsiz tezlik
    assert svc.segment_m(a, (41.301, 69.28, at(9, 59))) is None  # vaqt orqaga
    p = MobilePermit(window_start=time(8), window_end=time(20))
    assert svc.in_window(p, at(8)) and svc.in_window(p, at(20)) and not svc.in_window(p, at(20, 1)) and not svc.in_window(p, at(7, 59))
    with pytest.raises(Exception) as e:
        svc.check_ready(None, at(10))
    assert e.value.detail["code"] == "no_permit"


async def test_permit_consent_and_start_rules(new_client, clock):
    ctx = await setup(new_client)
    hr, boss, far, w = ctx["hr"], ctx["boss"], ctx["far"], ctx["w"]
    assert (await far.put(f"{M}/permits/{ctx['eid']}", json={})).status_code == 403
    assert (await boss.put(f"{M}/permits/{ctx['eid']}", json={})).status_code == 403
    assert (await hr.put(f"{M}/permits/{ctx['eid']}", json={"window_start": "20:00:00", "window_end": "08:00:00"})).json()["detail"]["code"] == "window_invalid"
    assert (await hr.put(f"{M}/permits/{ctx['eid']}", json={"interval_s": 5})).status_code == 422
    # ruxsatsiz
    assert (await w.get(f"{M}/my")).json()["reason"] == "no_permit"
    assert (await w.post(f"{M}/my/start", json={})).json()["detail"]["code"] == "no_permit"
    p = await grant(ctx, interval_s=30)
    assert p["interval_s"] == 30 and p["consent_at"] is None
    assert "mobile.granted" in [n["kind"] for n in (await w.get("/api/v1/notifications")).json()["items"]]
    # rozilik kerak
    me = (await w.get(f"{M}/my")).json()
    assert me["reason"] == "consent_required" and me["can_start"] is False and me["privacy"]["retention_days"] == 90
    assert (await w.post(f"{M}/my/start", json={})).json()["detail"]["code"] == "consent_required"
    assert (await far.post(f"{M}/my/consent")).json()["detail"]["code"] == "no_employee"
    assert (await w.post(f"{M}/my/consent")).json()["consent_at"]
    # vaqt oynasidan tashqari
    clock["t"] = at(21, 0)
    r = await w.post(f"{M}/my/start", json={"lat": 41.3, "lng": 69.28})
    assert r.json()["detail"]["code"] == "outside_hours" and r.json()["detail"]["start"] == "08:00"
    # geolokatsiya ruxsati yo'q
    clock["t"] = at(9, 10)
    assert (await w.post(f"{M}/my/start", json={"permission": "denied"})).json()["detail"]["code"] == "location_permission_required"
    r = await w.post(f"{M}/my/start", json={"lat": 41.3, "lng": 69.28, "battery": 80})
    assert r.status_code == 201 and r.json()["status"] == "active"
    assert (await w.post(f"{M}/my/start", json={})).json()["detail"]["code"] == "session_active"
    # davomat: "mobile" usulida, 10 daqiqa kechikish (5 daq imtiyoz)
    async with SessionLocal() as s:
        rec = (await s.scalars(select(AttendanceRecord).where(AttendanceRecord.employee_id == ctx["eid"]))).one()
        assert rec.in_method == "mobile" and rec.late_minutes == 10 and rec.check_out_at is None
    assert (await hr.get("/api/v1/audit", params={"action": "mobile.permit_save"})).json()["total"] >= 1


async def test_points_distance_events_and_live(new_client, clock):
    ctx = await setup(new_client)
    hr, boss, w = ctx["hr"], ctx["boss"], ctx["w"]
    await grant(ctx)
    await w.post(f"{M}/my/consent")
    assert (await w.post(f"{M}/my/points", json={"points": []})).json()["detail"]["code"] == "no_session"
    await w.post(f"{M}/my/start", json={"lat": 41.3, "lng": 69.28})
    clock["t"] = at(9, 30)
    batch = pts(at(9, 12), 4) + [{"lat": 41.31, "lng": 69.28, "accuracy": 900, "at": at(9, 20).isoformat()}] + [pts(at(9, 12), 1)[0]]  # yomon aniqlik + takror
    r = (await w.post(f"{M}/my/points", json={"points": batch, "device": {"battery": 80, "charging": False, "permission": "granted", "gps_enabled": True}})).json()
    assert r["saved"] == 4 and r["skipped"] == 2 and r["interval_s"] == 60
    # GPS sakrashi (10 soniyada 500 km) tashlanadi; 3 segment * 111.19 m = 0.334 km
    r = (await w.post(f"{M}/my/points", json={"points": [{"lat": 46.0, "lng": 69.28, "accuracy": 10, "at": at(9, 17, 10).isoformat()}]})).json()
    assert r["saved"] == 0 and r["skipped"] == 1
    assert r["session"]["distance_km"] == 0.334 and r["session"]["points_count"] == 4
    # keyingi nuqtalar oldingi zanjirni davom ettiradi (0.111 km qo'shiladi)
    r = (await w.post(f"{M}/my/points", json={"points": pts(at(9, 20), 1, lat0=41.303)})).json()
    assert r["session"]["distance_km"] == pytest.approx(0.334 + 0.0, abs=0.001)  # 41.303 -> oxirgi nuqta 41.303 (takror joy)
    live = (await boss.get(f"{M}/live")).json()
    assert len(live) == 1 and live[0]["employee"]["name"] == "Kuryer X" and live[0]["battery"] == 80 and live[0]["stale"] is False and live[0]["permission"] == "granted"
    assert (await ctx["far"].get(f"{M}/live")).status_code == 403

    # qurilma holati: batareya (bir marta), ruxsat, GPS
    async def dev(**d):
        r = await w.post(f"{M}/my/points", json={"points": [], "device": d})
        assert r.status_code == 200, r.text

    await dev(battery=12, charging=False)
    await dev(battery=10, charging=False)  # takror xabar yo'q
    await dev(battery=45, charging=False)  # tiklandi
    await dev(battery=9, charging=False)  # yana tushdi
    await dev(permission="denied")
    await dev(permission="denied")
    await dev(gps_enabled=False)
    ev = (await boss.get(f"{M}/events")).json()
    kinds = sorted(e["kind"] for e in ev["items"])
    assert kinds == ["gps_off", "low_battery", "low_battery", "permission_lost"]
    kinds_n = [n["kind"] for n in (await hr.get("/api/v1/notifications")).json()["items"]]
    assert kinds_n.count("mobile.event") == 4
    assert (await boss.get(f"{M}/events", params={"kind": "gps_off"})).json()["total"] == 1


async def test_sos_ack_stop_and_attendance(new_client, clock):
    ctx = await setup(new_client)
    hr, boss, w = ctx["hr"], ctx["boss"], ctx["w"]
    await grant(ctx)
    await w.post(f"{M}/my/consent")
    # SOS sessiyasiz ham ishlaydi
    r = await w.post(f"{M}/my/sos", json={"lat": 41.3, "lng": 69.28, "note": "Yordam kerak", "battery": 50})
    assert r.status_code == 201
    ev = (await hr.get(f"{M}/events", params={"open_only": "true"})).json()["items"][0]
    assert ev["kind"] == "sos" and ev["severity"] == "critical" and ev["data"]["note"] == "Yordam kerak" and ev["lat"] == 41.3
    assert "mobile.sos" in [n["kind"] for n in (await hr.get("/api/v1/notifications")).json()["items"]]
    assert (await boss.post(f"{M}/events/{ev['id']}/ack", json={})).status_code == 403
    r = await hr.post(f"{M}/events/{ev['id']}/ack", json={"note": "Bog'lanildi"})
    assert r.json()["acknowledged_at"] and r.json()["ack_note"] == "Bog'lanildi"
    assert (await hr.post(f"{M}/events/{ev['id']}/ack", json={})).status_code == 409
    assert (await hr.get(f"{M}/events", params={"open_only": "true"})).json()["total"] == 0

    sid = (await w.post(f"{M}/my/start", json={"lat": 41.3, "lng": 69.28})).json()["id"]
    clock["t"] = at(17, 45)
    r = (await w.post(f"{M}/my/stop", json={"lat": 41.31, "lng": 69.28})).json()
    assert r["status"] == "ended" and r["end_reason"] == "user"
    assert (await w.post(f"{M}/my/stop", json={})).json()["detail"]["code"] == "no_session"
    async with SessionLocal() as s:
        rec = (await s.scalars(select(AttendanceRecord).where(AttendanceRecord.employee_id == ctx["eid"]))).one()
        assert rec.out_method == "mobile" and rec.check_out_at is not None and rec.worked_minutes == 8 * 60 + 35 and rec.early_leave_minutes == 15
    # trek tarixini ko'rish auditga yoziladi
    assert (await boss.get(f"{M}/sessions/{sid}/track")).status_code == 200
    assert (await hr.get("/api/v1/audit", params={"action": "mobile.view_track"})).json()["total"] == 1
    assert (await ctx["far"].get(f"{M}/sessions/{sid}")).status_code == 403
    sess = (await boss.get(f"{M}/sessions", params={"employee_id": ctx["eid"]})).json()
    assert sess["total"] == 1 and sess["items"][0]["employee"]["name"] == "Kuryer X"
    for a in ("start", "stop", "sos", "ack", "consent"):
        assert (await hr.get("/api/v1/audit", params={"action": f"mobile.{a}"})).json()["total"] >= 1, a


async def test_watch_signal_window_and_revocation(new_client, clock):
    ctx = await setup(new_client)
    hr, w = ctx["hr"], ctx["w"]
    await grant(ctx)
    await w.post(f"{M}/my/consent")
    await w.post(f"{M}/my/start", json={"lat": 41.3, "lng": 69.28})
    clock["t"] = at(9, 20)
    await w.post(f"{M}/my/points", json={"points": pts(at(9, 12), 3)})

    async def tick(moment):
        async with SessionLocal() as db:
            n, _ = await svc.watch(db, moment)
            await db.commit()
            return n

    assert await tick(at(9, 22)) == 0  # signal bor (oxirgi nuqta 9:14)
    assert await tick(at(9, 30)) == 1  # 10 daqiqadan oshdi
    assert await tick(at(9, 40)) == 0  # takror yo'q
    assert (await hr.get(f"{M}/events", params={"kind": "signal_lost"})).json()["total"] == 1
    clock["t"] = at(9, 45)
    await w.post(f"{M}/my/points", json={"points": pts(at(9, 44), 1)})
    assert (await hr.get(f"{M}/events", params={"kind": "signal_back"})).json()["total"] == 1
    # oyna tugagach avtomatik yopiladi, davomatga ketish oyna oxirida yoziladi
    assert await tick(at(20, 20)) == 1  # 9:44 dan beri signal yo'q: yangi uzilish
    assert await tick(at(20, 40)) == 1
    async with SessionLocal() as s:
        rec = (await s.scalars(select(AttendanceRecord).where(AttendanceRecord.employee_id == ctx["eid"]))).one()
        assert rec.check_out_at == at(20, 0)
    assert (await hr.get(f"{M}/events", params={"kind": "auto_closed"})).json()["total"] == 1
    clock["t"] = at(20, 41)
    assert (await w.post(f"{M}/my/points", json={"points": []})).json()["detail"]["code"] == "no_session"

    # rozilikni qaytarish va ruxsatni bekor qilish sessiyani tugatadi
    clock["t"] = at(9, 5, day=11)
    await w.post(f"{M}/my/start", json={})
    assert (await w.delete(f"{M}/my/consent")).status_code == 204
    s1 = (await hr.get(f"{M}/sessions", params={"status": "ended"})).json()["items"][0]
    assert s1["end_reason"] == "consent_revoked"
    assert (await w.post(f"{M}/my/start", json={})).json()["detail"]["code"] == "consent_required"
    await w.post(f"{M}/my/consent")
    await w.post(f"{M}/my/start", json={})
    assert (await hr.delete(f"{M}/permits/{ctx['eid']}")).status_code == 204
    assert (await hr.get(f"{M}/sessions", params={"status": "ended"})).json()["items"][0]["end_reason"] == "permit_revoked"
    assert (await w.post(f"{M}/my/start", json={})).json()["detail"]["code"] == "no_permit"
