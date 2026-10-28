"""Javob olish bildirgisi: tasdiqlangan so'rov uchun raqamli hujjat (raqam, QR tekshiruv kodi, yaxlitlik xeshi, PDF)."""

import hashlib
import io
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answers import LeaveEvent, LeaveRequest
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch, Department, Position
from app.services import answers as svc
from app.services.attendance_pdf import _fonts
from app.services.letters_pdf import QRCode
from app.timeutil import tz

T = {
    "uz": {
        "title": "JAVOB OLISH BILDIRGISI", "employee": "Xodim", "position": "Lavozim", "department": "Bo'lim", "branch": "Filial",
        "kind": "Ruxsat turi", "period": "Sana / vaqt", "duration": "Davomiyligi", "reason": "Sabab", "note": "Izoh",
        "kinds": {"day": "Kunlik", "hourly": "Soatlik"},
        "reasons": {"sick": "Kasallik", "family": "Oilaviy", "personal": "Shaxsiy", "business": "Xizmat", "other": "Boshqa"},
        "units": {"day": "kun", "hour": "soat", "min": "daqiqa"},
        "decision": "Qaror", "approved_by": "Tasdiqladi", "levels": {"coordinator": "Koordinator", "hr": "HR"}, "at": "Sana",
        "events": {"submitted": "So'rov yuborildi", "escalated": "HR ga o'tdi", "approved": "Tasdiqladi", "rejected": "Rad etdi", "cancelled": "Bekor qilindi"},
        "esign": "Elektron tasdiq bilan rasmiylashtirilgan", "doc_no": "Hujjat raqami", "status": "Holat",
        "valid": "Amal qiladi", "cancelled": "Bekor qilingan", "verify": "Hujjat haqiqiyligini QR kod yoki {url} orqali tekshirish mumkin.", "code": "Kod",
    },
    "ru": {
        "title": "УВЕДОМЛЕНИЕ ОБ ОТСУТСТВИИ", "employee": "Сотрудник", "position": "Должность", "department": "Отдел", "branch": "Филиал",
        "kind": "Тип разрешения", "period": "Дата / время", "duration": "Длительность", "reason": "Причина", "note": "Комментарий",
        "kinds": {"day": "Дневное", "hourly": "Почасовое"},
        "reasons": {"sick": "Болезнь", "family": "Семейная", "personal": "Личная", "business": "Служебная", "other": "Другая"},
        "units": {"day": "дн.", "hour": "ч", "min": "мин"},
        "decision": "Решение", "approved_by": "Одобрил(а)", "levels": {"coordinator": "Координатор", "hr": "HR"}, "at": "Дата",
        "events": {"submitted": "Заявка отправлена", "escalated": "Передано HR", "approved": "Одобрил(а)", "rejected": "Отклонил(а)", "cancelled": "Отменено"},
        "esign": "Оформлено с электронным подтверждением", "doc_no": "Номер документа", "status": "Статус",
        "valid": "Действует", "cancelled": "Отменено", "verify": "Подлинность документа можно проверить по QR-коду или на {url}.", "code": "Код",
    },
}


def content_hash(req: LeaveRequest, emp: Employee) -> str:
    payload = {
        "number": req.statement_no, "code": req.statement_code, "employee_id": emp.id, "employee": emp.full_name, "kind": req.kind,
        "start": req.start_date, "end": req.end_date, "from": req.start_time, "to": req.end_time, "reason_type": req.reason_type,
        "decided_by": req.decided_by, "decided_at": req.decided_at.astimezone(UTC).isoformat() if req.decided_at else None, "level": req.decided_level,
    }  # fmt: skip
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


async def ensure(db: AsyncSession, req: LeaveRequest, emp: Employee, moment: datetime) -> bool:
    """Tasdiqlangan so'rovga bildirgi raqami/kodi/xeshini (bir marta) beradi. Yangi berilgan bo'lsa True."""
    if req.status != "approved" or req.statement_no:
        return False
    n = await db.scalar(text("SELECT nextval('leave_no_seq')"))
    req.statement_no = f"JO-{moment.astimezone(tz()).year}-{int(n):04d}"
    req.statement_code = secrets.token_urlsafe(12)
    req.statement_at = moment
    req.statement_hash = content_hash(req, emp)
    return True


def public_view(req: LeaveRequest, emp: Employee, provided_hash: str | None) -> dict[str, Any]:
    """Ochiq tekshiruv: sabab va shaxsiy ma'lumotsiz, faqat mavjudligi, holati va yaxlitligi."""
    parts = emp.full_name.split()
    short = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else (parts[0] if parts else "—")
    intact = bool(req.statement_hash) and content_hash(req, emp) == req.statement_hash
    h = (req.statement_hash or "")
    return {
        "valid": req.status == "approved", "intact": intact, "number": req.statement_no, "employee": short, "status": req.status, "kind": req.kind,
        "start_date": req.start_date, "end_date": req.end_date,
        "start_time": req.start_time.strftime("%H:%M") if req.start_time else None, "end_time": req.end_time.strftime("%H:%M") if req.end_time else None,
        "decided_level": req.decided_level, "decided_at": req.decided_at, "hash_prefix": h[:16],
        "hash_match": (provided_hash.strip().lower() == h[: len(provided_hash.strip())]) if provided_hash and provided_hash.strip() else None,
    }  # fmt: skip


def _dur(req: LeaveRequest, t: dict[str, Any]) -> str:
    u = t["units"]
    if req.kind == "hourly" and req.start_time and req.end_time:
        h, m = divmod(max(0, svc.minutes(req.end_time) - svc.minutes(req.start_time)), 60)
        return " ".join(p for p in (f"{h} {u['hour']}" if h else "", f"{m} {u['min']}" if m else "") if p)
    return f"{(req.end_date - req.start_date).days + 1} {u['day']}"


async def build_pdf(db: AsyncSession, req: LeaveRequest, emp: Employee, verify_url: str, company: str, lang: str = "uz") -> bytes:
    t = T["ru" if lang == "ru" else "uz"]
    pos = await db.get(Position, emp.position_id) if emp.position_id else None
    dept = await db.get(Department, emp.department_id) if emp.department_id else None
    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    decider = await db.get(User, req.decided_by) if req.decided_by else None
    events = list((await db.scalars(select(LeaveEvent).where(LeaveEvent.request_id == req.id).order_by(LeaveEvent.created_at, LeaveEvent.id))).all())
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({e.actor_id for e in events if e.actor_id})))).all()} if events else {}

    regular, bold = _fonts()
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontName=regular, fontSize=10.5, leading=15)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
    title = ParagraphStyle("title", parent=body, fontName=bold, fontSize=15, leading=20, alignment=1, spaceBefore=10, spaceAfter=10)
    lab = ParagraphStyle("lab", parent=body, textColor=colors.HexColor("#555555"))
    b = ParagraphStyle("b", parent=body, fontName=bold)

    def p(x: str, st: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(x).replace("\n", "<br/>"), st)

    when = req.start_date.strftime("%d.%m.%Y")
    if req.kind == "hourly" and req.start_time and req.end_time:
        when += f"  {req.start_time:%H:%M}–{req.end_time:%H:%M}"
    elif req.end_date != req.start_date:
        when += f" – {req.end_date.strftime('%d.%m.%Y')}"
    rows = [
        (t["employee"], emp.full_name), (t["position"], pos.name if pos else "—"), (t["department"], dept.name if dept else "—"), (t["branch"], branch.name if branch else "—"),
        (t["kind"], t["kinds"][req.kind]), (t["period"], when), (t["duration"], _dur(req, t)), (t["reason"], t["reasons"].get(req.reason_type, req.reason_type)),
    ]  # fmt: skip
    if req.reason:
        rows.append((t["note"], req.reason))
    info = Table([[p(a, lab), p(v, b)] for a, v in rows], colWidths=[42 * mm, 120 * mm])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))  # fmt: skip

    decided = req.decided_at.astimezone(tz()).strftime("%d.%m.%Y %H:%M") if req.decided_at else "—"
    level = t["levels"].get(req.decided_level or "", "")
    status_text = t["valid"] if req.status == "approved" else t["cancelled"]
    sign = [
        p(t["esign"], ParagraphStyle("sb", parent=body, fontName=bold, fontSize=10)),
        p(f"{t['approved_by']}: {level} {decider.full_name if decider else '—'}".strip(), small),
        p(f"{t['at']}: {decided}", small),
        p(f"{t['doc_no']}: {req.statement_no}", small),
        p(f"SHA-256: {(req.statement_hash or '')[:32]}…", small),
        p(f"{t['status']}: {status_text}", small),
    ]
    sig = Table([[sign, [QRCode(verify_url, 30 * mm), p(f"{t['code']}: {req.statement_code}", small)]]], colWidths=[118 * mm, 45 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9ca3af")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))  # fmt: skip
    hist = [p(f"{(e.created_at.astimezone(tz())).strftime('%d.%m.%Y %H:%M')} · {names.get(e.actor_id or 0, '—')} · {t['events'].get(e.action, e.action)}", small) for e in events]
    story = [
        p(company, ParagraphStyle("co", parent=body, fontName=bold, fontSize=12)),
        p(f"№ {req.statement_no}    {decided.split(' ')[0]}", small),
        p(t["title"], title),
        info,
        Spacer(1, 6 * mm),
        p(t["decision"], b),
        *hist,
        Spacer(1, 10 * mm),
        KeepTogether([sig, Spacer(1, 3 * mm), p(t["verify"].format(url=verify_url), small)]),
    ]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=18 * mm, title=str(req.statement_no)).build(story)
    return buf.getvalue()
