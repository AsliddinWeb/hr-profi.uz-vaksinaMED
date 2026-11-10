"""AI suhbat (hard/soft skill), ovoz chiqarib o'qish urinishlari va 100 kishilik onlayn konferensiyalar."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AiInterview(Base):
    """AI suhbat: lavozim kompetensiyasidan savollar (hard/soft), nomzod/xodim yozma yoki ovozli javob beradi,
    AI har javobni baholaydi. Nomzod uchun ochiq havola (`token`), xodim uchun tizim ichida."""

    __tablename__ = "ai_interviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    token: Mapped[str] = mapped_column(String(24), unique=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(10), default="sent")  # sent | answering | submitted | graded
    questions: Mapped[list] = mapped_column(JSONB, default=list)  # [{id, kind: hard|soft, skill, text}]
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)  # {qid: {text, transcript, audio_key, at}}
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)  # {qid: {score 0-10, feedback}}
    hard_pct: Mapped[int | None] = mapped_column(Integer)
    soft_pct: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReadAloudAttempt(Base):
    """Prebording: stajyor slayd/matnni ovoz chiqarib o'qiydi; Whisper matnga aylantiradi va aniqlik hisoblanadi."""

    __tablename__ = "read_aloud_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("internship_enrollments.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("internship_steps.id", ondelete="CASCADE"))
    transcript: Mapped[str] = mapped_column(Text)
    accuracy: Mapped[int] = mapped_column(Integer)  # 0-100
    missed: Mapped[list] = mapped_column(JSONB, default=list)  # o'qilmagan so'zlar (ko'pi bilan 30)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conference(Base):
    """Onlayn konferensiya/dars (100 kishigacha): LiveKit xonasi, qatnashuv, oxirida vazifalar va hisobot."""

    __tablename__ = "conferences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    room: Mapped[str] = mapped_column(String(64), unique=True)
    host_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    capacity: Mapped[int] = mapped_column(Integer, default=100)
    audience: Mapped[dict] = mapped_column(JSONB, default=dict)  # {all: bool, position_ids: [], branch_ids: [], department_ids: []}
    status: Mapped[str] = mapped_column(String(10), default="scheduled")  # scheduled | live | ended | cancelled
    tasks: Mapped[list] = mapped_column(JSONB, default=list)  # [{title, description, due_days}] — tugagach qatnashchilarga topshiriq
    auto_tasks_for_absent: Mapped[bool] = mapped_column(Boolean, default=True)  # kelmaganlarga yozuvni ko'rish topshirig'i
    recording_url: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConferenceAttendee(Base):
    """Qatnashuv: kim qachon kirdi/chiqdi, jami necha soniya (yurak urishi bilan hisoblanadi)."""

    __tablename__ = "conference_attendees"
    __table_args__ = (UniqueConstraint("conference_id", "user_id", name="uq_conference_attendee"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conference_id: Mapped[int] = mapped_column(ForeignKey("conferences.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    first_join_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    joins: Mapped[int] = mapped_column(Integer, default=1)
