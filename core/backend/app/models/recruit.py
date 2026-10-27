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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Vacancy(Base, TimestampMixin):
    """Ish o'rni (vakansiya). Holat: draft | open | paused | closed."""

    __tablename__ = "vacancies"
    __table_args__ = (Index("ix_vacancies_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))
    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    openings: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(8), default="draft")
    recruiter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deadline: Mapped[date | None] = mapped_column(Date)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(250), index=True)
    phone: Mapped[str | None] = mapped_column(String(13), index=True)
    email: Mapped[str | None] = mapped_column(String(120))
    birth_date: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str | None] = mapped_column(String(40))
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    resume_text: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)  # bot orqali kelgan nomzod: unga xabar yuborish uchun
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Application(Base, TimestampMixin):
    """Ariza: nomzodning vakansiyadagi pipeline holati. Bosqich: new | screening | interview | offer | hired | rejected."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("vacancy_id", "candidate_id", name="uq_application"), Index("ix_applications_stage", "vacancy_id", "stage"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(10), default="new")
    rating: Mapped[int | None] = mapped_column(Integer)
    reject_reason: Mapped[str | None] = mapped_column(String(300))
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recruiter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stage_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    hired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_link_id: Mapped[int | None] = mapped_column(ForeignKey("source_links.id", ondelete="SET NULL"), index=True)
    # Suhbat natijasi: tajriba darajasi ochiladigan bosqichlarni belgilaydi (high: 3, mid: 2, none: 1)
    experience_level: Mapped[str | None] = mapped_column(String(8))  # high | mid | none
    hard_skill: Mapped[int | None] = mapped_column(Integer)
    soft_skill: Mapped[int | None] = mapped_column(Integer)
    interview_notes: Mapped[str | None] = mapped_column(Text)
    interviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    interviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bg_status: Mapped[str | None] = mapped_column(String(8))  # pending | passed | failed
    bg_note: Mapped[str | None] = mapped_column(Text)
    bg_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    bg_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_scan: Mapped[dict | None] = mapped_column(JSONB)
    ai_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Job offer: HR taklif qiladi -> HRD tasdiqlaydi -> nomzodga yuboriladi
    offer_status: Mapped[str | None] = mapped_column(String(12))  # pending_hrd | approved | rejected
    offer_level: Mapped[str | None] = mapped_column(String(10))  # intern | pharmacist | senior
    offer_salary: Mapped[int | None] = mapped_column(Integer)
    offer_start: Mapped[date | None] = mapped_column(Date)
    offer_note: Mapped[str | None] = mapped_column(Text)
    offer_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    offer_decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    offer_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offer_decision_note: Mapped[str | None] = mapped_column(Text)
    offer_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApplicationEvent(Base):
    """Tarix: bosqich o'zgarishi (`stage`), rad etish, izoh (`comment`), xodimga aylantirish."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(12))  # applied | stage | rejected | reopened | comment | hired | rating
    from_stage: Mapped[str | None] = mapped_column(String(10))
    to_stage: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateFile(Base):
    __tablename__ = "candidate_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PositionRequirement(Base, TimestampMixin):
    """Lavozim bo'yicha talablar va e'lon shabloni: vakansiya ochilganda avtomatik to'ldiriladi."""

    __tablename__ = "position_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), unique=True)
    requirements: Mapped[str | None] = mapped_column(Text)
    competencies: Mapped[list] = mapped_column(JSONB, default=list)
    ad_template: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class VacancyChannel(Base):
    """Vakansiya e'lon qilingan joy: hh.uz, OLX, Telegram, sayt, Instagram, billboard, tanish-bilish..."""

    __tablename__ = "vacancy_channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(12))
    url: Mapped[str | None] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(String(300))
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceLink(Base):
    """Shaxsiy/kanal linki: nomzod shu link orqali ariza topshirsa, manba (kanal va egasi) avtomatik yoziladi."""

    __tablename__ = "source_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(12))
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    label: Mapped[str | None] = mapped_column(String(120))
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecruitCall(Base):
    """Rekruter qo'ng'iroqlari jurnali (qo'ng'iroq, mos / mos emas): rekruter paneli hisoboti uchun."""

    __tablename__ = "recruit_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str | None] = mapped_column(String(13))
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id", ondelete="SET NULL"))
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"))
    outcome: Mapped[str] = mapped_column(String(10))  # suitable | unsuitable | no_answer | callback
    note: Mapped[str | None] = mapped_column(String(300))
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
