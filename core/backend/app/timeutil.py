"""Ish vaqti mintaqasi: grafik sanalari va davomat shu mintaqada hisoblanadi (bazada UTC)."""

from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.config import get_settings


@lru_cache
def tz() -> tzinfo:
    try:
        return ZoneInfo(get_settings().timezone)
    except Exception:  # tzdata yo'q: O'zbekistonda DST yo'q, UTC+5
        return timezone(timedelta(hours=5))


def now() -> datetime:
    return datetime.now(UTC)


def local_date(moment: datetime) -> date:
    return moment.astimezone(tz()).date()


def localize(naive: datetime) -> datetime:
    """Mahalliy (naive) vaqtni tz-aware qiladi."""
    return naive.replace(tzinfo=tz())


def local_dt_fmt(moment: datetime) -> str:
    """Toshkent vaqtida: 05.11.2026 14:30."""
    return moment.astimezone(tz()).strftime("%d.%m.%Y %H:%M")
