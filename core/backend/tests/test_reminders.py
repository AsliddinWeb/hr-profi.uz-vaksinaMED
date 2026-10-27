from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.notifications import Notification
from app.models.reminders import Reminder
from app.services import reminders as svc
from app.timeutil import tz
from tests.conftest import login, make_user

R = "/api/v1/reminders"
NOW = datetime(2026, 11, 2, 8, 0, tzinfo=tz())  # dushanba 08:00


def at(y, m, d, h=9, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=tz())


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def rem(first, repeat="once", **kw):
    return Reminder(owner_id=1, title="x", first_at=first, repeat=repeat, interval=kw.pop("interval", 1), weekdays=kw.pop("weekdays", []), **kw)


# --- Takrorlanish hisobi (DB siz) -------------------------------------------------------


def test_once():
    r = rem(at(2026, 11, 5))
    assert svc.compute_next(r, at(2026, 11, 4)) == at(2026, 11, 5)
    assert svc.compute_next(r, at(2026, 11, 5)) is None  # qat'iy "keyin"
    assert svc.compute_next(r, at(2026, 11, 6)) is None


def test_daily_interval_and_time_of_day():
    r = rem(at(2026, 11, 1, 9, 30), "daily", interval=2)
    assert svc.compute_next(r, at(2026, 11, 1, 9, 30)) == at(2026, 11, 3, 9, 30)
    assert svc.compute_next(r, at(2026, 11, 2)) == at(2026, 11, 3, 9, 30)
    assert svc.compute_next(r, at(2026, 11, 3, 9, 30)) == at(2026, 11, 5, 9, 30)
    assert svc.compute_next(r, at(2026, 11, 3, 9, 30)).utcoffset() == timedelta(hours=5)
    assert svc.compute_next(r, at(2026, 11, 3, 9, 30)).astimezone().astimezone(tz()).hour == 9


def test_weekly_weekdays_and_interval():
    r = rem(at(2026, 11, 2, 10), "weekly", weekdays=[0, 2, 4])  # Du/Ch/Ju
    assert svc.compute_next(r, at(2026, 11, 2, 10)) == at(2026, 11, 4, 10)
    assert svc.compute_next(r, at(2026, 11, 6, 10)) == at(2026, 11, 9, 10)
    biweekly = rem(at(2026, 11, 2, 10), "weekly", weekdays=[0], interval=2)
    assert svc.compute_next(biweekly, at(2026, 11, 2, 10)) == at(2026, 11, 16, 10)
    assert svc.compute_next(biweekly, at(2026, 11, 9)) == at(2026, 11, 16, 10)
    # boshlanish haftaning belgilangan kuniga to'g'ri kelmasa
    odd = rem(at(2026, 11, 3, 10), "weekly", weekdays=[0, 4])  # seshanba boshlangan
    assert svc.compute_next(odd, at(2026, 11, 3, 9)) == at(2026, 11, 6, 10)


def test_monthly_clamps_end_of_month():
    r = rem(at(2026, 1, 31, 10), "monthly")
    assert svc.compute_next(r, at(2026, 1, 31, 10)) == at(2026, 2, 28, 10)
    assert svc.compute_next(r, at(2026, 2, 28, 10)) == at(2026, 3, 31, 10)
    assert svc.compute_next(r, at(2026, 3, 31, 10)) == at(2026, 4, 30, 10)
    every2 = rem(at(2026, 1, 15, 8), "monthly", interval=2)
    assert svc.compute_next(every2, at(2026, 1, 15, 8)) == at(2026, 3, 15, 8)
    assert svc.compute_next(every2, at(2026, 3, 16)) == at(2026, 5, 15, 8)


def test_yearly_leap_day():
    r = rem(at(2028, 2, 29, 9), "yearly")
    assert svc.compute_next(r, at(2028, 2, 29, 9)) == at(2029, 2, 28, 9)
    assert svc.compute_next(r, at(2031, 3, 1)) == at(2032, 2, 29, 9)


def test_until_inclusive():
    r = rem(at(2026, 11, 1), "daily", until=date(2026, 11, 5))
    assert svc.compute_next(r, at(2026, 11, 4, 9)) == at(2026, 11, 5, 9)
    assert svc.compute_next(r, at(2026, 11, 5, 9)) is None
    assert svc.upcoming(rem(at(2026, 11, 1), "daily", until=date(2026, 11, 3)), at(2026, 10, 31), 10) == [at(2026, 11, d) for d in (1, 2, 3)]


# --- API va ishga tushirish -------------------------------------------------------------

pytestmark_db = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    monkeypatch.setattr("app.api.reminders.now", fn)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


def body(first="2026-11-02T10:00:00+05:00", **kw):
    return {"title": "Hisobotni yuborish", "first_at": first, **kw}


async def fire(moment):
    async with SessionLocal() as s:
        n, with_tg, without_tg = await svc.fire_due(s, moment)
        await s.commit()
        return n, with_tg, without_tg


@pytestmark_db
async def test_create_validation_and_preview(new_client, clock):
    c, _ = await as_user(new_client, "ali", "farmasevt")
    r = await c.post(R, json=body())
    assert r.status_code == 201 and iso(r.json()["next_at"]) == at(2026, 11, 2, 10)
    assert (await c.post(R, json=body("2026-11-01T10:00:00+05:00"))).json()["detail"]["code"] == "no_future_occurrence"
    # o'tmishda boshlangan takrorlanuvchi: keyingi takrorga o'tadi
    d = await c.post(R, json=body("2026-10-30T09:00:00+05:00", repeat="daily"))
    assert d.status_code == 201 and iso(d.json()["next_at"]) == at(2026, 11, 2, 9)
    assert (await c.post(R, json=body(link="https://evil.example"))).status_code == 422
    assert (await c.post(R, json=body(link="//evil.example"))).status_code == 422
    assert (await c.post(R, json=body(first_at="2026-11-05T10:00:00"))).status_code in (422,)  # tz yo'q
    assert (await c.post(R, json=body(repeat="weekly", weekdays=[9]))).status_code == 422
    assert (await c.post(R, json=body(repeat="daily", until="2026-10-01"))).status_code == 422
    p = (await c.post(f"{R}/preview", json=body(repeat="weekly", weekdays=[0, 3]))).json()["next"]
    assert [x[:10] for x in p] == ["2026-11-02", "2026-11-05", "2026-11-09", "2026-11-12", "2026-11-16"]


@pytestmark_db
async def test_fire_once_timing_and_idempotency(new_client, clock):
    c, uid = await as_user(new_client, "ali", "farmasevt")
    rid = (await c.post(R, json=body(note="Hujjatlarni tekshirish", link="/tasks/5"))).json()["id"]
    due = at(2026, 11, 2, 10)

    assert (await fire(due - timedelta(seconds=1)))[0] == 0  # vaqtidan oldin yuborilmaydi
    n, with_tg, _ = await fire(due)
    assert n == 1 and len(with_tg) == 1 and with_tg[0].user_id == uid and with_tg[0].link == "/tasks/5"
    assert with_tg[0].body_uz == "Hujjatlarni tekshirish" and with_tg[0].title_uz == "Eslatma"
    assert (await fire(due + timedelta(minutes=5)))[0] == 0  # takrorlanmaydi

    d = (await c.get(f"{R}/{rid}")).json()
    assert d["fire_count"] == 1 and d["finished"] and d["is_active"] is False and d["next_at"] is None
    assert [e["action"] for e in d["events"]] == ["fired", "created"]
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Notification).where(Notification.kind == "reminders.fire"))).all()) == 1


@pytestmark_db
async def test_recurring_after_downtime_fires_once_then_advances(new_client, clock):
    c, _ = await as_user(new_client, "ali", "farmasevt")
    rid = (await c.post(R, json=body("2026-11-02T10:00:00+05:00", repeat="daily"))).json()["id"]
    n, with_tg, _ = await fire(at(2026, 11, 5, 12))  # worker 3 kun ishlamadi
    assert n == 1 and len(with_tg) == 1  # o'tkazib yuborilganlar yig'ilmaydi
    d = (await c.get(f"{R}/{rid}")).json()
    assert iso(d["next_at"]) == at(2026, 11, 6, 10) and d["is_active"] and not d["finished"]
    assert (await fire(at(2026, 11, 5, 13)))[0] == 0
    assert (await fire(at(2026, 11, 6, 10)))[0] == 1


@pytestmark_db
async def test_recipients_telegram_flag_and_sharing(new_client, clock):
    owner, oid = await as_user(new_client, "boss", "koordinator")
    a, aid = await as_user(new_client, "ali", "farmasevt")
    r = await owner.post(R, json=body(recipients=[aid, oid], telegram=False))
    assert r.status_code == 201 and [x["id"] for x in r.json()["recipients"]] == [aid]  # egasi ro'yxatdan chiqariladi
    rid = r.json()["id"]
    n, with_tg, without_tg = await fire(at(2026, 11, 2, 10))
    assert n == 1 and with_tg == [] and sorted(x.user_id for x in without_tg) == sorted([oid, aid])

    # oluvchi ko'radi, kechiktiradi, belgilaydi; tahrirlay/o'chira olmaydi
    assert (await a.get(R, params={"scope": "shared", "state": "all"})).json()["total"] == 1
    assert (await a.get(R, params={"scope": "mine", "state": "all"})).json()["total"] == 0
    assert (await a.get(f"{R}/{rid}")).json()["is_owner"] is False
    assert (await a.put(f"{R}/{rid}", json=body())).status_code == 404
    assert (await a.delete(f"{R}/{rid}")).status_code == 404
    # huquqsiz xodim boshqalarga yubora olmaydi, noma'lum foydalanuvchi rad etiladi
    assert (await a.post(R, json=body(recipients=[oid]))).json()["detail"]["code"] == "cannot_assign_others"
    assert (await owner.post(R, json=body(recipients=[99999]))).json()["detail"]["code"] == "unknown_user"
    stranger, _ = await as_user(new_client, "eve", "farmasevt")
    assert (await stranger.get(f"{R}/{rid}")).status_code == 404


@pytestmark_db
async def test_snooze_ack_pause_resume(new_client, clock):
    c, _ = await as_user(new_client, "ali", "farmasevt")
    rid = (await c.post(R, json=body("2026-11-02T10:00:00+05:00", repeat="daily"))).json()["id"]
    await fire(at(2026, 11, 2, 10))

    clock["t"] = at(2026, 11, 2, 10, 1)
    s = (await c.post(f"{R}/{rid}/snooze", json={"minutes": 10})).json()
    assert iso(s["snooze_at"]) == at(2026, 11, 2, 10, 11)
    assert (await fire(at(2026, 11, 2, 10, 10)))[0] == 0
    n, with_tg, _ = await fire(at(2026, 11, 2, 10, 11))
    assert n == 1 and len(with_tg) == 1  # kechiktirilgan yana yuborildi
    d = (await c.get(f"{R}/{rid}")).json()
    assert d["snooze_at"] is None and iso(d["next_at"]) == at(2026, 11, 3, 10)  # asosiy jadval o'zgarmadi

    t = (await c.post(f"{R}/{rid}/snooze", json={"tomorrow": True})).json()
    assert iso(t["snooze_at"]) == at(2026, 11, 3, 9)  # ertaga 09:00 Toshkent
    assert (await c.post(f"{R}/{rid}/snooze", json={})).json()["detail"]["code"] == "snooze_required"
    a = (await c.post(f"{R}/{rid}/ack")).json()
    assert a["snooze_at"] is None and a["last_ack_at"] and a["is_active"]  # takrorlanuvchi davom etadi

    assert (await c.post(f"{R}/{rid}/pause")).json()["is_active"] is False
    assert (await fire(at(2026, 11, 3, 10)))[0] == 0  # to'xtatilgan yuborilmaydi
    clock["t"] = at(2026, 11, 5, 12)
    r = (await c.post(f"{R}/{rid}/resume")).json()
    assert r["is_active"] and iso(r["next_at"]) == at(2026, 11, 6, 10)  # o'tkazib yuborilganlar yo'q
    ev = [e["action"] for e in (await c.get(f"{R}/{rid}")).json()["events"]]
    assert ev[:3] == ["resumed", "paused", "done"]


@pytestmark_db
async def test_update_delete_limits_and_upcoming(new_client, clock, monkeypatch):
    c, _ = await as_user(new_client, "ali", "farmasevt")
    rid = (await c.post(R, json=body(repeat="daily", first="2026-11-02T10:00:00+05:00"))).json()["id"]
    up = (await c.get(f"{R}/upcoming", params={"days": 3})).json()
    assert [x["at"][:10] for x in up] == ["2026-11-02", "2026-11-03", "2026-11-04"]
    u = await c.put(f"{R}/{rid}", json=body(title="Yangi nom", repeat="weekly", weekdays=[2], first="2026-11-02T09:00:00+05:00"))
    assert u.json()["title"] == "Yangi nom" and iso(u.json()["next_at"]) == at(2026, 11, 4, 9)
    assert (await c.put(f"{R}/{rid}", json=body(first="2026-10-01T10:00:00+05:00"))).json()["detail"]["code"] == "no_future_occurrence"
    assert (await c.delete(f"{R}/{rid}")).status_code == 204
    assert (await c.get(f"{R}/{rid}")).status_code == 404

    monkeypatch.setattr("app.services.reminders.MAX_ACTIVE", 2)
    for _ in range(2):
        assert (await c.post(R, json=body())).status_code == 201
    assert (await c.post(R, json=body())).json()["detail"]["code"] == "too_many_reminders"
    assert (await c.get(R, params={"state": "finished"})).json()["total"] == 0
    assert (await c.get(R, params={"q": "Hisobot"})).json()["total"] == 2
