"""Eslatmalar: takrorlanish hisobi (Toshkent vaqti), ishga tushirish, kechiktirish."""

import calendar
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminders import Reminder, ReminderEvent
from app.services.notifications import notify, register_template
from app.timeutil import tz

REPEATS = ("once", "daily", "weekly", "monthly", "yearly")
MAX_ACTIVE = 200
MAX_PER_RUN = 500

register_template(
    "reminders.fire",
    {"uz": "Eslatma", "ru": "Напоминание"},
    {"uz": "{title}", "ru": "{title}"},
    "info",
)


def _at(day: date, anchor: datetime) -> datetime:
    """`day` sanasidagi tayanch vaqt (mahalliy soat/daqiqa) — tz-aware."""
    local = anchor.astimezone(tz())
    return datetime.combine(day, time(local.hour, local.minute), tzinfo=tz())


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def _clamp_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def compute_next(rem: Reminder, after: datetime) -> datetime | None:
    """`after` dan KEYINGI birinchi ishga tushish vaqti (qat'iy katta). Tugagan bo'lsa None."""
    anchor = rem.first_at.astimezone(tz())
    a_date = anchor.date()
    n = max(rem.interval or 1, 1)
    after_local = after.astimezone(tz())
    cand: datetime | None = None

    if rem.repeat == "once":
        cand = rem.first_at if rem.first_at > after else None
    elif rem.repeat == "daily":
        day = max(after_local.date(), a_date)
        k = -(-(day - a_date).days // n)  # ceil
        while True:
            c = _at(a_date + timedelta(days=k * n), anchor)
            if c > after:
                cand = c
                break
            k += 1
    elif rem.repeat == "weekly":
        days = sorted(set(rem.weekdays or [a_date.weekday()]))
        a_week = a_date - timedelta(days=a_date.weekday())
        d = max(after_local.date(), a_date)
        for _ in range(7 * n * 2 + 14):
            if d.weekday() in days and ((d - timedelta(days=d.weekday()) - a_week).days // 7) % n == 0:
                c = _at(d, anchor)
                if c > after and c >= rem.first_at:
                    cand = c
                    break
            d += timedelta(days=1)
    elif rem.repeat == "monthly":
        k = max(0, _months_between(a_date, after_local.date()))
        k = -(-k // n) * n
        while True:
            total = a_date.month - 1 + k
            c = _at(_clamp_day(a_date.year + total // 12, total % 12 + 1, a_date.day), anchor)
            if c > after:
                cand = c
                break
            k += n
    elif rem.repeat == "yearly":
        k = max(0, after_local.year - a_date.year)
        k = -(-k // n) * n
        while True:
            c = _at(_clamp_day(a_date.year + k, a_date.month, a_date.day), anchor)
            if c > after:
                cand = c
                break
            k += n
    if cand is not None and rem.until is not None and cand.astimezone(tz()).date() > rem.until:
        return None
    return cand


def upcoming(rem: Reminder, start: datetime, count: int) -> list[datetime]:
    out: list[datetime] = []
    cur = start
    while len(out) < count:
        nxt = compute_next(rem, cur)
        if nxt is None:
            break
        out.append(nxt)
        cur = nxt
    return out


def initial_next(rem: Reminder, moment: datetime) -> datetime | None:
    """Yaratilganda/tahrirlanganda: birinchi kelajakdagi vaqt (o'tmishda boshlangan bo'lsa keyingi takror)."""
    if rem.first_at > moment:
        return compute_next(rem, rem.first_at - timedelta(seconds=1)) if rem.repeat != "once" else rem.first_at
    return compute_next(rem, moment)


def log(db: AsyncSession, rem: Reminder, actor_id: int | None, action: str, data: dict[str, Any] | None = None) -> None:
    db.add(ReminderEvent(reminder_id=rem.id, actor_id=actor_id, action=action, data=data))


def audience(rem: Reminder) -> list[int]:
    return list(dict.fromkeys([rem.owner_id, *(rem.recipients or [])]))


async def fire_due(db: AsyncSession, moment: datetime):
    """Vaqti kelgan eslatmalarni yuboradi va keyingi vaqtni hisoblaydi. (soni, bildirishnomalar telegram bilan, telegramsiz)."""
    due = (
        await db.scalars(
            select(Reminder)
            .where(Reminder.is_active.is_(True), or_(Reminder.next_at <= moment, Reminder.snooze_at <= moment))
            .order_by(Reminder.next_at)
            .limit(MAX_PER_RUN)
            .with_for_update(skip_locked=True)
        )
    ).all()
    with_tg, without_tg = [], []
    for rem in due:
        snoozed = rem.snooze_at is not None and rem.snooze_at <= moment
        regular = rem.next_at is not None and rem.next_at <= moment
        notes = await notify(db, audience(rem), "reminders.fire", link=rem.link or f"/reminders/{rem.id}", params={"title": rem.title}, body={"uz": rem.note or "", "ru": rem.note or ""} if rem.note else None)
        (with_tg if rem.telegram else without_tg).extend(notes)
        rem.last_fired_at, rem.fire_count = moment, rem.fire_count + 1
        if snoozed:
            rem.snooze_at = None
        if regular:
            rem.next_at = compute_next(rem, moment)  # o'tkazib yuborilgan takrorlar yig'ilmaydi: bir marta yuboriladi
        log(db, rem, None, "fired", {"snoozed": snoozed and not regular})
        if rem.next_at is None and rem.snooze_at is None:
            rem.is_active = False  # tugadi (bir martalik yoki muddati o'tgan)
    return len(due), with_tg, without_tg


def is_finished(rem: Reminder) -> bool:
    return rem.next_at is None and rem.snooze_at is None


def reminder_out(rem: Reminder, names: dict[int, str] | None = None) -> dict[str, Any]:
    names = names or {}
    return {
        "id": rem.id, "title": rem.title, "note": rem.note, "link": rem.link, "owner_id": rem.owner_id,
        "recipients": [{"id": u, "name": names.get(u)} for u in (rem.recipients or [])],
        "repeat": rem.repeat, "interval": rem.interval, "weekdays": rem.weekdays or [], "first_at": rem.first_at,
        "until": rem.until, "telegram": rem.telegram, "is_active": rem.is_active, "next_at": rem.next_at, "snooze_at": rem.snooze_at,
        "last_fired_at": rem.last_fired_at, "last_ack_at": rem.last_ack_at, "fire_count": rem.fire_count,
        "finished": is_finished(rem),
    }  # fmt: skip
