"""Kompaniyaga moslanadigan sozlamalar: xodim segmentlari (Ofis, Dorixona, ... — har kompaniya o'zi qo'shadi) va kalit-qiymat sozlamalari."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EmployeeSegment(Base):
    """Xodimlar guruhi (dashboard, davomat, jarima va xatlarda filtr sifatida).
    scope: all | office (filialga biriktirilmagan) | branch (filial xodimlari); ixtiyoriy qo'shimcha filtr: bo'limlar va lavozimlar (VA sharti)."""

    __tablename__ = "employee_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(200))
    scope: Mapped[str] = mapped_column(String(8), default="all")
    department_ids: Mapped[list] = mapped_column(JSON, default=list)
    position_ids: Mapped[list] = mapped_column(JSON, default=list)
    color: Mapped[str | None] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanySetting(Base):
    """Kalit-qiymat sozlamasi (masalan `checklists.month_limit` = 4, `revisions.cycle_days` = 90)."""

    __tablename__ = "company_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | int | str | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
