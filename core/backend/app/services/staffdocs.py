"""Xodim elektron hujjatlari: ariza (xodim yozadi, HR ko'rib chiqadi) va buyruq (HR tayyorlaydi, imzolaydi, xodim tanishadi)."""

import hashlib
import io
import json
import secrets
from datetime import UTC, date, datetime
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.models.auth import User
from app.models.employees import Employee
from app.models.hrdocs import StaffDocument
from app.models.org import Branch, Department, Position
from app.rbac import matches
from app.services.attendance_pdf import _fonts
from app.services.letters_pdf import QRCode
from app.services.notifications import register_template
from app.timeutil import tz

APP_TYPES = ("vacation", "unpaid", "resign", "transfer", "other")
ORDER_TYPES = ("hire", "transfer", "vacation", "dismiss", "other")
NEEDS_DATES = ("vacation", "unpaid")

register_template("staff.application_new", {"uz": "Yangi ariza", "ru": "Новое заявление"}, {"uz": "{employee}: {title} ({number})", "ru": "{employee}: {title} ({number})"}, "info")
register_template("staff.application_decided", {"uz": "Arizangiz ko'rib chiqildi", "ru": "Ваше заявление рассмотрено"}, {"uz": "{title} ({number}): {result}", "ru": "{title} ({number}): {result}"}, "info")
register_template("staff.order_issued", {"uz": "Sizga buyruq chiqarildi", "ru": "На вас издан приказ"}, {"uz": "{title} ({number}). Iltimos, tanishib chiqing.", "ru": "{title} ({number}). Пожалуйста, ознакомьтесь."}, "info")

L: dict[str, dict[str, Any]] = {
    "uz": {
        "titles": {"vacation": "Mehnat ta'tili berish to'g'risida", "unpaid": "O'z hisobidan ta'til berish to'g'risida", "resign": "Ishdan bo'shash to'g'risida", "transfer": "Boshqa joyga o'tkazish to'g'risida", "other": "Boshqa masala bo'yicha", "hire": "Ishga qabul qilish to'g'risida", "dismiss": "Mehnat shartnomasini bekor qilish to'g'risida"},
        "app": "ARIZA", "order": "BUYRUQ", "to": "HR direktoriga", "from": "Ariza beruvchi", "decide": "Qaror", "approved": "Qabul qilindi", "rejected": "Rad etildi", "submitted": "Ko'rib chiqilmoqda", "cancelled": "Bekor qilingan",
        "order_word": "BUYURAMAN:", "esign": "Elektron imzo bilan tasdiqlangan", "signer": "Imzolagan", "at": "Sana", "doc_no": "Hujjat raqami", "status": "Holat", "ack": "Xodim tanishgan", "not_ack": "Xodim hali tanishmagan",
        "issued": "Amal qiladi", "verify": "Hujjat haqiqiyligini QR kod yoki {url} orqali tekshirish mumkin.", "code": "Kod", "period": "Muddat", "position": "Lavozim", "department": "Bo'lim", "branch": "Filial",
        "basis": "Asos", "status_h": {"submitted": "Ko'rib chiqilmoqda", "approved": "Qabul qilindi", "rejected": "Rad etildi", "cancelled": "Bekor qilingan", "draft": "Qoralama", "issued": "Amal qiladi"},
    },
    "ru": {
        "titles": {"vacation": "О предоставлении трудового отпуска", "unpaid": "О предоставлении отпуска за свой счёт", "resign": "Об увольнении", "transfer": "О переводе", "other": "По другому вопросу", "hire": "О приёме на работу", "dismiss": "О расторжении трудового договора"},
        "app": "ЗАЯВЛЕНИЕ", "order": "ПРИКАЗ", "to": "HR-директору", "from": "Заявитель", "decide": "Решение", "approved": "Принято", "rejected": "Отклонено", "submitted": "На рассмотрении", "cancelled": "Отменено",
        "order_word": "ПРИКАЗЫВАЮ:", "esign": "Подтверждено электронной подписью", "signer": "Подписал(а)", "at": "Дата", "doc_no": "Номер документа", "status": "Статус", "ack": "Сотрудник ознакомлен", "not_ack": "Сотрудник ещё не ознакомлен",
        "issued": "Действует", "verify": "Подлинность документа можно проверить по QR-коду или на {url}.", "code": "Код", "period": "Срок", "position": "Должность", "department": "Отдел", "branch": "Филиал",
        "basis": "Основание", "status_h": {"submitted": "На рассмотрении", "approved": "Принято", "rejected": "Отклонено", "cancelled": "Отменено", "draft": "Черновик", "issued": "Действует"},
    },
}


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def title_for(subtype: str, lang: str = "uz") -> str:
    return L["ru" if lang == "ru" else "uz"]["titles"].get(subtype, subtype)


def period_text(start: date | None, end: date | None) -> str:
    if not start:
        return ""
    return start.strftime("%d.%m.%Y") + (f" – {end.strftime('%d.%m.%Y')}" if end and end != start else "")


async def default_order_body(db: AsyncSession, emp: Employee, subtype: str, start: date | None, end: date | None) -> str:
    pos = await db.get(Position, emp.position_id) if emp.position_id else None
    dept = await db.get(Department, emp.department_id) if emp.department_id else None
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    who = f"{emp.full_name}" + (f", {pos.name}" if pos else "")
    when = period_text(start, end)
    place = ", ".join(x for x in (dept.name if dept else None, branch.name if branch else None) if x)
    if subtype == "hire":
        return f"1. {who} {start.strftime('%d.%m.%Y') if start else ''} dan boshlab {place or 'kompaniya'} ga ishga qabul qilinsin.\n2. Sinov muddati belgilansin."
    if subtype == "transfer":
        return f"1. {who} {start.strftime('%d.%m.%Y') if start else ''} dan boshlab boshqa lavozim/filialga o'tkazilsin.\n2. Yangi ish joyi va shartlar xodim bilan kelishilsin."
    if subtype == "vacation":
        return f"1. {who} ga {when} muddatga mehnat ta'tili berilsin.\n2. Ta'til davri uchun ish haqi qonunchilikka muvofiq to'lansin."
    if subtype == "dismiss":
        return f"1. {who} bilan tuzilgan mehnat shartnomasi {start.strftime('%d.%m.%Y') if start else ''} dan boshlab bekor qilinsin.\n2. Hisob-kitob qonunchilik muddatlarida amalga oshirilsin."
    return f"{who} bo'yicha: "


def content_hash(doc: StaffDocument, emp: Employee) -> str:
    payload = {
        "number": doc.number, "code": doc.code, "kind": doc.kind, "subtype": doc.subtype, "employee_id": emp.id, "employee": emp.full_name, "title": doc.title, "body": doc.body,
        "start": doc.start_date, "end": doc.end_date, "signed_by": doc.signed_by, "signed_at": doc.signed_at.astimezone(UTC).isoformat() if doc.signed_at else None,
    }  # fmt: skip
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


async def assign_number(db: AsyncSession, doc: StaffDocument, moment: datetime) -> None:
    seq, prefix = ("staff_app_no_seq", "AR") if doc.kind == "application" else ("staff_order_no_seq", "BY")
    n = await db.scalar(text(f"SELECT nextval('{seq}')"))
    doc.number = f"{prefix}-{moment.astimezone(tz()).year}-{int(n):04d}"
    doc.code = secrets.token_urlsafe(12)


def public_view(doc: StaffDocument, emp: Employee, provided_hash: str | None) -> dict[str, Any]:
    parts = emp.full_name.split()
    short = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else (parts[0] if parts else "—")
    h = doc.content_hash or ""
    intact = bool(h) and content_hash(doc, emp) == h
    return {
        "valid": doc.status in ("issued", "approved", "submitted"), "intact": intact, "number": doc.number, "kind": doc.kind, "subtype": doc.subtype, "title": doc.title, "employee": short, "status": doc.status,
        "signed_at": doc.signed_at, "hash_prefix": h[:16], "hash_match": (provided_hash.strip().lower() == h[: len(provided_hash.strip())]) if provided_hash and provided_hash.strip() else None,
    }  # fmt: skip


async def build_pdf(db: AsyncSession, doc: StaffDocument, emp: Employee, verify_url: str, company: str, lang: str = "uz") -> bytes:
    t = L["ru" if lang == "ru" else "uz"]
    pos = await db.get(Position, emp.position_id) if emp.position_id else None
    dept = await db.get(Department, emp.department_id) if emp.department_id else None
    signer = await db.get(User, doc.signed_by) if doc.signed_by else None
    decider = await db.get(User, doc.decided_by) if doc.decided_by else None
    regular, bold = _fonts()
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontName=regular, fontSize=11, leading=16)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
    title_st = ParagraphStyle("title", parent=body, fontName=bold, fontSize=15, leading=20, alignment=1, spaceBefore=10, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=body, fontName=bold, alignment=1, spaceAfter=10)
    right = ParagraphStyle("right", parent=body, alignment=2)
    b = ParagraphStyle("b", parent=body, fontName=bold)

    def p(x: str, st: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(x).replace("\n", "<br/>"), st)

    created = doc.created_at.astimezone(tz()).strftime("%d.%m.%Y") if doc.created_at else ""
    story: list[Any] = [p(company, ParagraphStyle("co", parent=body, fontName=bold, fontSize=12)), p(f"№ {doc.number or '—'}    {created}", small), Spacer(1, 5 * mm)]
    if doc.kind == "application":
        story += [p(t["to"], right), p(f"{t['from']}: {emp.full_name}", right), p(f"{pos.name if pos else ''}{', ' + dept.name if dept else ''}".strip(", "), right),
                  p(t["app"], title_st), p(doc.title, sub), p(doc.body)]  # fmt: skip
        if doc.start_date:
            story += [Spacer(1, 3 * mm), p(f"{t['period']}: {period_text(doc.start_date, doc.end_date)}", b)]
        story += [Spacer(1, 8 * mm), p(f"{emp.full_name}    {created}", small)]
        if doc.decided_at:
            res = t["approved"] if doc.status == "approved" else t["rejected"] if doc.status == "rejected" else t["cancelled"]
            story += [Spacer(1, 6 * mm), p(f"{t['decide']}: {res}" + (f" — {doc.decision_note}" if doc.decision_note else ""), b), p(f"{decider.full_name if decider else ''} · {doc.decided_at.astimezone(tz()).strftime('%d.%m.%Y %H:%M')}", small)]
        sign_lines = [p(t["esign"], ParagraphStyle("sb", parent=body, fontName=bold, fontSize=10)), p(f"{t['from']}: {emp.full_name}", small), p(f"{t['at']}: {created}", small), p(f"{t['doc_no']}: {doc.number}", small),
                      p(f"{t['status']}: {t['status_h'].get(doc.status, doc.status)}", small)]  # fmt: skip
    else:
        story += [p(t["order"], title_st), p(doc.title, sub), p(f"{t['basis']}: {emp.full_name}", small) if doc.related_id else Spacer(1, 0), Spacer(1, 3 * mm), p(t["order_word"], b), p(doc.body)]
        if doc.start_date:
            story += [Spacer(1, 3 * mm), p(f"{t['period']}: {period_text(doc.start_date, doc.end_date)}", b)]
        at = doc.signed_at.astimezone(tz()).strftime("%d.%m.%Y %H:%M") if doc.signed_at else "—"
        sign_lines = [p(t["esign"], ParagraphStyle("sb", parent=body, fontName=bold, fontSize=10)), p(f"{t['signer']}: {signer.full_name if signer else '—'}", small), p(f"{t['at']}: {at}", small), p(f"{t['doc_no']}: {doc.number}", small),
                      p(f"SHA-256: {(doc.content_hash or '')[:32]}…", small), p(f"{t['status']}: {t['status_h'].get(doc.status, doc.status)}", small),
                      p((t["ack"] + ": " + doc.acknowledged_at.astimezone(tz()).strftime("%d.%m.%Y %H:%M")) if doc.acknowledged_at else t["not_ack"], small)]  # fmt: skip
    sig = Table([[sign_lines, [QRCode(verify_url, 30 * mm), p(f"{t['code']}: {doc.code}", small)]]], colWidths=[118 * mm, 45 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9ca3af")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))  # fmt: skip
    story += [Spacer(1, 10 * mm), KeepTogether([sig, Spacer(1, 3 * mm), p(t["verify"].format(url=verify_url), small)])]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=18 * mm, title=str(doc.number or doc.title)).build(story)
    return buf.getvalue()
