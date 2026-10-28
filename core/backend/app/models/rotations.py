from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Rotation(Base, TimestampMixin):
    """Rotatsiya: xodimni filialdan filialga vaqtincha (sana dan-gacha) o'tkazish. Tasdiqlangach start sanasida xodimning
    filiali `to_branch` ga almashadi (davomat, grafik, geofence shunga bog'lanadi), end sanasidan keyin `from_branch` ga qaytadi."""

    __tablename__ = "rotations"
    __table_args__ = (Index("ix_rotations_status", "status"), Index("ix_rotations_employee", "employee_id", "status"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    from_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    to_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | approved | active | completed | rejected | cancelled
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
