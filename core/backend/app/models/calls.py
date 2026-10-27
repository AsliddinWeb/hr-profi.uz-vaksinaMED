from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Call(Base):
    """Qo'ng'iroq / konferensiya (LiveKit xonasi).

    kind: direct | conference. status: ringing | scheduled | active | ended | declined | missed | cancelled.
    """

    __tablename__ = "calls"
    __table_args__ = (Index("ix_calls_status", "status"), Index("ix_calls_host", "host_id"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))
    media: Mapped[str] = mapped_column(String(5), default="video")  # audio | video
    title: Mapped[str | None] = mapped_column(String(200))
    room_name: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(10))
    host_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ring_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    end_reason: Mapped[str | None] = mapped_column(String(12))  # host | empty | stale | admin
    empty_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CallParticipant(Base):
    """status: invited | joined | left | declined | missed."""

    __tablename__ = "call_participants"
    __table_args__ = (UniqueConstraint("call_id", "user_id", name="uq_call_participant"), Index("ix_call_participants_user", "user_id"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(8), default="invitee")  # host | invitee
    status: Mapped[str] = mapped_column(String(8), default="invited")
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_seconds: Mapped[int] = mapped_column(Integer, default=0)
