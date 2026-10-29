"""HR hujjatlar kutubxonasi: tayyor kartochkalar, ko'rinish (rol bo'yicha), versiyalar va «tanishdim» tasdig'i."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.models.auth import Role, User
from app.models.hrdocs import HrDocument, HrDocumentAck
from app.rbac import matches
from app.services.notifications import register_template

CATEGORIES = ("strategy", "policy", "process", "system", "culture")
register_template("hrdoc.published", {"uz": "Yangi HR hujjat", "ru": "Новый HR-документ"}, {"uz": "«{title}» (v{version}) e'lon qilindi. Iltimos, tanishib chiqing.", "ru": "Опубликован «{title}» (v{version}). Пожалуйста, ознакомьтесь."}, "info")

# (kalit, kategoriya, sarlavha): mijoz ro'yxati bo'yicha bo'sh kartochkalar; mazmunini mijoz o'zi to'ldiradi
DEFAULT_DOCS: tuple[tuple[str, str, str], ...] = (
    ("mission", "strategy", "Kompaniya missiyasi (vazifasi)"),
    ("goal", "strategy", "Kompaniyaning oliy maqsadi"),
    ("smart", "strategy", "Kompaniyaning SMART maqsadlari"),
    ("strategies", "strategy", "Kompaniya strategiyalari (ketma-ketlikda)"),
    ("values", "strategy", "Kompaniya qadriyatlari"),
    ("slogan", "strategy", "Kompaniya shiori"),
    ("charter", "policy", "Kompaniya nizomi"),
    ("internal_rules", "policy", "Ichki tartib qoidalari"),
    ("hr_docflow", "policy", "HR hujjatlar nazorati"),
    ("job_duties", "policy", "Lavozim majburiyatlari"),
    ("recruiting", "process", "Recruiting jarayoni"),
    ("preboarding", "process", "Preboarding tizimi"),
    ("onboarding", "process", "Onboarding dasturi"),
    ("offboarding", "process", "Offboarding dasturi"),
    ("assessment", "process", "Xodimlarni baholash dasturi (onlayn kuzatuv xizmati)"),
    ("service", "process", "Servis (ish bajarish va muomila madaniyatini tuzish)"),
    ("training", "process", "Xodimlarni o'qitish va rivojlantirish"),
    ("grading", "system", "C&B (Grading) tizimi"),
    ("kaizen", "system", "Kayzen tizimi"),
    ("kpi", "system", "KPI"),
    ("motivation", "system", "Motivation"),
    ("social_climate", "culture", "Ijtimoiy muhit"),
    ("corp_culture", "culture", "Korporativ madaniyat"),
    ("gamification", "culture", "Gamifikatsiya"),
)


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def can_manage(auth: AuthContext) -> bool:
    return has(auth, "hrdocs.manage")


def visible_to(doc: HrDocument, auth: AuthContext) -> bool:
    if can_manage(auth):
        return True
    return doc.status == "published" and (not doc.roles or auth.user.role.key in doc.roles)


async def ensure_default_docs(db: AsyncSession) -> int:
    """Yo'q tayyor kartochkalarni (qoralama holatida, bo'sh) yaratadi. Mavjudlariga tegmaydi."""
    have = set((await db.scalars(select(HrDocument.key).where(HrDocument.key.is_not(None)))).all())
    added = 0
    for i, (key, cat, title) in enumerate(DEFAULT_DOCS, 1):
        if key not in have:
            db.add(HrDocument(key=key, category=cat, title=title, status="draft", version=0, sort_order=i, roles=[], requires_ack=False))
            added += 1
    await db.commit()
    return added


def needs_ack(doc: HrDocument, ack: HrDocumentAck | None) -> bool:
    return doc.status == "published" and doc.requires_ack and (ack is None or ack.version < doc.version)


def out(doc: HrDocument, ack: HrDocumentAck | None = None, *, with_body: bool = False) -> dict[str, Any]:
    d = {
        "id": doc.id, "key": doc.key, "category": doc.category, "title": doc.title, "summary": doc.summary, "status": doc.status, "version": doc.version,
        "requires_ack": doc.requires_ack, "roles": doc.roles or [], "has_file": bool(doc.file_key), "file_name": doc.file_name, "file_size": doc.file_size,
        "has_body": bool(doc.body and doc.body.strip()), "published_at": doc.published_at,
        "ack": {"version": ack.version, "at": ack.acknowledged_at} if ack else None, "needs_ack": needs_ack(doc, ack),
    }  # fmt: skip
    if with_body:
        d["body"] = doc.body or ""
    return d


async def audience(db: AsyncSession, doc: HrDocument) -> list[User]:
    """Hujjat ko'rinadigan faol foydalanuvchilar (rollar bo'sh bo'lsa hamma)."""
    stmt = select(User).where(User.is_active.is_(True))
    if doc.roles:
        stmt = stmt.join(Role, Role.id == User.role_id).where(Role.key.in_(doc.roles))
    return list((await db.scalars(stmt)).all())


async def ack_counts(db: AsyncSession, doc_ids: list[int]) -> dict[int, int]:
    if not doc_ids:
        return {}
    rows = (await db.execute(select(HrDocumentAck.document_id, func.count()).where(HrDocumentAck.document_id.in_(doc_ids)).group_by(HrDocumentAck.document_id))).all()
    return {r[0]: r[1] for r in rows}


def stamp(moment: datetime) -> datetime:
    return moment
