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
    sla_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # muddat yaqinlashgani haqida xabar berilgan payt
    sla_overdue_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # muddat o'tgani haqida xabar berilgan payt


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
    pinfl: Mapped[str | None] = mapped_column(String(14), index=True)  # JSHSHIR: takroriy nomzodlarni aniqlash
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)  # anketa javoblari (tajriba, kutilgan oylik, tillar...)
    profile_token: Mapped[str | None] = mapped_column(String(24), unique=True)  # nomzodning shaxsiy anketa havolasi
    profile_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    reject_code: Mapped[str | None] = mapped_column(String(16))  # rad etish sababi toifasi (voronka tahlili uchun)
    match_score: Mapped[int | None] = mapped_column(Integer)  # kompetensiya kartochkasiga moslik, 0-100
    match_detail: Mapped[dict | None] = mapped_column(JSONB)
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
    offer_schedule: Mapped[str | None] = mapped_column(String(200))  # ish grafigi (offer shabloni)
    offer_probation_days: Mapped[int | None] = mapped_column(Integer)  # sinov muddati (kun)
    offer_token: Mapped[str | None] = mapped_column(String(24), unique=True)  # nomzodga offer havolasi
    offer_response: Mapped[str | None] = mapped_column(String(10))  # accepted | declined
    offer_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offer_decline_reason: Mapped[str | None] = mapped_column(String(300))
    conclusion: Mapped[dict | None] = mapped_column(JSONB)  # yakuniy xulosa: qoralama, tahrir, tasdiq


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
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)  # tuzilgan kartochka: duties, hard_skills, soft_skills, languages, education, min_experience, exclusions
    version: Mapped[int] = mapped_column(Integer, default=1)
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
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # e'lon o'chirilgan/yopilgan payt


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
    callback_date: Mapped[date | None] = mapped_column(Date)  # «qayta qo'ng'iroq» natijasida: qachon qo'ng'iroq qilish kerak
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PositionRequirementVersion(Base):
    """Lavozim kartochkasining oldingi versiyalari (har o'zgarishda snapshot)."""

    __tablename__ = "position_requirement_versions"
    __table_args__ = (UniqueConstraint("position_id", "version", name="uq_position_requirement_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(String(300))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidatePhone(Base):
    """Telefon raqami egaligi tarixi: bir raqam turli vaqtda turli shaxsga tegishli bo'lishi mumkin."""

    __tablename__ = "candidate_phones"
    __table_args__ = (Index("ix_candidate_phones_phone", "phone"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str] = mapped_column(String(13))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InterviewInvite(Base, TimestampMixin):
    """Suhbatga taklif: nomzod havola orqali bo'sh vaqtlardan birini tanlaydi va «kelaman / kela olmayman» deb javob beradi."""

    __tablename__ = "interview_invites"
    __table_args__ = (Index("ix_interview_invites_app", "application_id", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(24), unique=True)
    slots: Mapped[list] = mapped_column(JSONB, default=list)  # ISO vaqtlar
    mode: Mapped[str] = mapped_column(String(8), default="offline")  # offline | online
    place: Mapped[str | None] = mapped_column(String(200))
    map_url: Mapped[str | None] = mapped_column(String(300))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    meeting_url: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="sent")  # sent | scheduled | declined | cancelled
    chosen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # nomzod tanlagan suhbat vaqti
    reply: Mapped[str | None] = mapped_column(String(12))  # coming | not_coming
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminded_day: Mapped[bool] = mapped_column(Boolean, default=False)
    reminded_2h: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class InterviewScore(Base, TimestampMixin):
    """Suhbatdosh bahosi: har bir kompetensiyaga 1-5 (`scores`: {kalit: ball}) va izoh."""

    __tablename__ = "interview_scores"
    __table_args__ = (UniqueConstraint("application_id", "interviewer_id", name="uq_interview_score"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    interviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)


class TestBank(Base, TimestampMixin):
    """Test banki (IQ, mantiq, lavozim bo'yicha bilim). `questions`: [{id, text, options[], correct[indeks]}]."""

    __tablename__ = "test_banks"
    __test__ = False  # pytest bu sinfni test deb yig'masin

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(10))  # iq | logic | position
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))
    time_limit_min: Mapped[int] = mapped_column(Integer, default=20)
    pass_score: Mapped[int] = mapped_column(Integer, default=60)
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CandidateTest(Base, TimestampMixin):
    """Nomzodga berilgan test: havola orqali topshiriladi, vaqt cheklovi bor, natija avtomatik hisoblanadi."""

    __tablename__ = "candidate_tests"
    __test__ = False
    __table_args__ = (Index("ix_candidate_tests_app", "application_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    bank_id: Mapped[int] = mapped_column(ForeignKey("test_banks.id", ondelete="RESTRICT"))
    token: Mapped[str] = mapped_column(String(24), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="assigned")  # assigned | started | submitted | expired
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    score_pct: Mapped[int | None] = mapped_column(Integer)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class BackgroundCheck(Base, TimestampMixin):
    """Fon tekshiruvi: avval nomzod roziligi (havola), keyin bandlar (tavsiya, hujjatlar, ijtimoiy tarmoq...) va qaror."""

    __tablename__ = "background_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True)
    consent_token: Mapped[str] = mapped_column(String(24), unique=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_ip: Mapped[str | None] = mapped_column(String(64))
    items: Mapped[list] = mapped_column(JSONB, default=list)  # [{key, result: positive|negative|unknown|None, note}]
    status: Mapped[str] = mapped_column(String(16), default="consent_pending")  # consent_pending | in_progress | done
    decision: Mapped[str | None] = mapped_column(String(8))  # passed | failed
    decision_note: Mapped[str | None] = mapped_column(Text)
    checked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

