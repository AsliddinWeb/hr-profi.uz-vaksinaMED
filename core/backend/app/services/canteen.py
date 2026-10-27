"""Abet: menyu, baholash oynasi, QR token va tahlil yordamchilari."""

import hashlib
import hmac
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import AuthContext, error
from app.models.canteen import CanteenSettings
from app.models.employees import Employee
from app.rbac import matches
from app.services.notifications import register_template

KINDS = ("soup", "main", "salad", "side", "drink", "dessert", "other")
LOW_STARS = 2

register_template("canteen.low_rating", {"uz": "Abetga past baho", "ru": "Низкая оценка столовой"}, {"uz": "{date}: {stars}★ {comment}", "ru": "{date}: {stars}★ {comment}"}, "warning")
register_template("canteen.reply", {"uz": "Izohingizga javob berildi", "ru": "На ваш комментарий ответили"}, {"uz": "{date}: {reply}", "ru": "{date}: {reply}"}, "info")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def can_read(auth: AuthContext) -> bool:
    return has(auth, "canteen.read") or has(auth, "canteen.manage")


def qr_sig(epoch: int) -> str:
    return hmac.new(get_settings().secret_key.encode(), f"canteen-qr:{epoch}".encode(), hashlib.sha256).hexdigest()[:20]


def make_qr_token(epoch: int) -> str:
    return f"{epoch}.{qr_sig(epoch)}"


def qr_valid(token: str | None, epoch: int) -> bool:
    if not token:
        return False
    try:
        e, sig = token.strip().split(".")
        return int(e) == epoch and hmac.compare_digest(sig, qr_sig(epoch))
    except ValueError:
        return False


async def get_settings_row(db: AsyncSession) -> CanteenSettings:
    s = await db.get(CanteenSettings, 1)
    if s is None:
        s = CanteenSettings(id=1, qr_epoch=0, require_qr=False, rating_days=1)
        db.add(s)
        await db.flush()
    return s


def rating_open(menu_date: date, today: date, rating_days: int) -> bool:
    """Menyu kunidan oldin baholab bo'lmaydi; kundan keyin `rating_days` kun ichida mumkin."""
    return menu_date <= today and (today - menu_date).days <= rating_days


async def my_employee(db: AsyncSession, auth: AuthContext) -> Employee:
    e = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id, Employee.status == "active"))
    if not e:
        raise error(403, "no_employee")
    return e
