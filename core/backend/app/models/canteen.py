from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class CanteenSettings(Base):
    """Bitta qator (id=1): QR kodni bekor qilish uchun epoch, QR majburiyligi, baholash muddati."""

    __tablename__ = "canteen_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    qr_epoch: Mapped[int] = mapped_column(Integer, default=0)
    require_qr: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_days: Mapped[int] = mapped_column(Integer, default=1)  # menyu kunidan keyin necha kun baholash mumkin


class CanteenMenu(Base, TimestampMixin):
    __tablename__ = "canteen_menus"

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_date: Mapped[date] = mapped_column(Date, unique=True)
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CanteenDish(Base):
    """kind: soup | main | salad | side | drink | dessert | other"""

    __tablename__ = "canteen_dishes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("canteen_menus.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(10), default="main")
    description: Mapped[str | None] = mapped_column(String(300))


class CanteenRating(Base):
    """`dish_id` NULL = kunning umumiy bahosi. Bir xodim bir menyu/taomga bitta baho (qayta yuborsa yangilanadi)."""

    __tablename__ = "canteen_ratings"
    __table_args__ = (
        Index("uq_canteen_rating_overall", "menu_id", "employee_id", unique=True, postgresql_where=text("dish_id IS NULL")),
        Index("uq_canteen_rating_dish", "menu_id", "employee_id", "dish_id", unique=True, postgresql_where=text("dish_id IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("canteen_menus.id", ondelete="CASCADE"), index=True)
    dish_id: Mapped[int | None] = mapped_column(ForeignKey("canteen_dishes.id", ondelete="CASCADE"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    via_qr: Mapped[bool] = mapped_column(Boolean, default=False)
    reply: Mapped[str | None] = mapped_column(Text)
    replied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
