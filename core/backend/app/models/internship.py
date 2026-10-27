from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class InternshipProgram(Base, TimestampMixin):
    """Stajirovka dasturi: tartiblangan bosqichlar (video, hujjat, matn, test)."""

    __tablename__ = "internship_programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(500))
    pass_score: Mapped[int] = mapped_column(Integer, default=70)  # testlar uchun standart o'tish bali (%)
    sequential: Mapped[bool] = mapped_column(Boolean, default=True)  # bosqichlar ketma-ket ochiladi
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    phase: Mapped[str] = mapped_column(String(12), default="preboarding", server_default="preboarding")  # preboarding (7 kun) | onboarding (90 kun)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))  # onboarding: lavozim bo'yicha dastur
    duration_days: Mapped[int | None] = mapped_column(Integer)


class InternshipStep(Base, TimestampMixin):
    """kind: video | document | text | test. `questions`: [{id, text, options[], correct[]}]."""

    __tablename__ = "internship_steps"
    __table_args__ = (Index("ix_internship_steps_program", "program_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("internship_programs.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    file_key: Mapped[str | None] = mapped_column(String(300))
    file_name: Mapped[str | None] = mapped_column(String(200))
    file_mime: Mapped[str | None] = mapped_column(String(80))
    file_size: Mapped[int | None] = mapped_column(Integer)
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    pass_score: Mapped[int | None] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)  # 0 = cheksiz
    required: Mapped[bool] = mapped_column(Boolean, default=True)


class InternshipEnrollment(Base, TimestampMixin):
    """Stajyorning dasturdagi yo'li. Holat: active | ready | completed | cancelled."""

    __tablename__ = "internship_enrollments"
    __table_args__ = (Index("ix_internship_enrollments_employee", "employee_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("internship_programs.id", ondelete="RESTRICT"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    mentor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column(Date)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    final_score: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    phase: Mapped[str] = mapped_column(String(12), default="preboarding", server_default="preboarding")
    day7_decision: Mapped[str | None] = mapped_column(String(8))  # fit | not_fit (7-kun qarori: HR menejer va trener)
    day7_note: Mapped[str | None] = mapped_column(Text)
    day7_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    day7_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_enrollment_id: Mapped[int | None] = mapped_column(BigInteger)  # qaror "mos" bo'lsa avtomatik ochilgan onboarding


class InternshipProgress(Base):
    __tablename__ = "internship_progress"
    __table_args__ = (UniqueConstraint("enrollment_id", "step_id", name="uq_internship_progress"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("internship_enrollments.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("internship_steps.id", ondelete="CASCADE"))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int | None] = mapped_column(Integer)  # testning eng yaxshi natijasi (%)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InternshipDaily(Base, TimestampMixin):
    """Kunlik hisobot (preboarding 7 kun): xodim nimani ko'rdi, tushundi va bajardi."""

    __tablename__ = "internship_daily"
    __table_args__ = (UniqueConstraint("enrollment_id", "day_no", name="uq_internship_daily"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("internship_enrollments.id", ondelete="CASCADE"), index=True)
    day_no: Mapped[int] = mapped_column(Integer)
    seen: Mapped[str | None] = mapped_column(Text)
    understood: Mapped[str | None] = mapped_column(Text)
    done: Mapped[str | None] = mapped_column(Text)


class InternshipFeedback(Base):
    """Kunlik fidbek: zaveduyushiy, trener, HR (va hamkasblar) yozadi."""

    __tablename__ = "internship_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("internship_enrollments.id", ondelete="CASCADE"), index=True)
    day_no: Mapped[int] = mapped_column(Integer)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(String(10))  # zav | trainer | hr
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClassSession(Base, TimestampMixin):
    """Oflayn dars yoki amaliyot (guruh): vaqt, joy, trener va qatnashuvchilar."""

    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10), default="lesson")  # lesson | practice
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    place: Mapped[str | None] = mapped_column(String(200))
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    attendance_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClassAttendee(Base):
    __tablename__ = "class_attendees"
    __table_args__ = (UniqueConstraint("session_id", "employee_id", name="uq_class_attendee"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    present: Mapped[bool | None] = mapped_column(Boolean)  # None = hali belgilanmagan


class HireDocs(Base, TimestampMixin):
    """Kadrovik: yangi xodimning hujjatlari qabul qilinishi va kadr buyrug'i holati."""

    __tablename__ = "hire_docs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), unique=True)
    docs_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    docs_received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    docs_note: Mapped[str | None] = mapped_column(Text)
    order_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_ready_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    order_no: Mapped[str | None] = mapped_column(String(40))
