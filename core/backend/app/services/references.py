"""Ish joyi ma'lumotnomasi: o'zgarmas mazmun, PDF va QR tekshiruv."""

import hashlib
import io
import json
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.references import EmploymentReference
from app.rbac import matches
from app.services.attendance_pdf import _fonts
from app.services.letters_pdf import QRCode
from app.timeutil import tz

TEXT: dict[str, dict[str, str]] = {
    "uz": {"title": "MA'LUMOTNOMA", "says": "Ushbu ma'lumotnoma", "works": "haqiqatan ham kompaniyada ishlashini tasdiqlash uchun berildi.", "position": "Lavozimi", "department": "Bo'lim", "branch": "Filial", "hired": "Ishga kirgan sana", "duties": "Bajaradigan vazifalari", "signer": "Ma'lumotnoma bergan", "date": "Berilgan sana", "verify": "Hujjat haqiqiyligini QR kod yoki {url} orqali tekshiring.", "code": "Tekshiruv kodi", "valid": "Amal qiladi", "cancelled": "Bekor qilingan"},
    "ru": {"title": "СПРАВКА", "says": "Настоящая справка выдана", "works": "для подтверждения работы в компании.", "position": "Должность", "department": "Отдел", "branch": "Филиал", "hired": "Дата приёма", "duties": "Должностные обязанности", "signer": "Выдал(а)", "date": "Дата выдачи", "verify": "Подлинность документа проверьте по QR-коду или на {url}.", "code": "Код проверки", "valid": "Действует", "cancelled": "Отменена"},
}


def has_permission(auth: Any, permission: str) -> bool:
    return matches(auth.permissions, permission)


def digest(snapshot: dict[str, Any]) -> str:
    packed = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def short_name(name: str) -> str:
    parts = name.split()
    return f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else (parts[0] if parts else "—")


def public_view(doc: EmploymentReference, provided_hash: str | None = None) -> dict[str, Any]:
    intact = digest(doc.snapshot) == doc.content_hash
    candidate = (provided_hash or "").strip().lower()
    return {
        "valid": doc.status == "issued", "intact": intact, "number": doc.number,
        "employee": short_name(str(doc.snapshot.get("employee_name") or "—")),
        "position": doc.snapshot.get("position") or "—", "status": doc.status,
        "issued_at": doc.issued_at, "hash_prefix": doc.content_hash[:16],
        "hash_match": candidate == doc.content_hash if candidate else None,
    }


def build_pdf(doc: EmploymentReference, verify_url: str, lang: str = "uz") -> bytes:
    data = doc.snapshot
    t = TEXT["ru" if lang == "ru" else "uz"]
    regular, bold = _fonts()
    ss = getSampleStyleSheet()
    base = ParagraphStyle("ref_base", parent=ss["Normal"], fontName=regular, fontSize=11, leading=16, textColor=colors.HexColor("#202938"))
    small = ParagraphStyle("ref_small", parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor("#555d6b"))
    title = ParagraphStyle("ref_title", parent=base, fontName=bold, fontSize=16, leading=22, alignment=1, spaceBefore=7 * mm, spaceAfter=7 * mm)
    label = ParagraphStyle("ref_label", parent=base, fontName=bold, spaceBefore=4 * mm, spaceAfter=2 * mm)
    company = ParagraphStyle("ref_company", parent=base, fontName=bold, fontSize=13, alignment=1, textColor=colors.HexColor("#132238"))

    def p(value: str, style: ParagraphStyle = base) -> Paragraph:
        return Paragraph(escape(value).replace("\n", "<br/>"), style)

    issued = doc.issued_at.astimezone(tz()).strftime("%d.%m.%Y")
    name = str(data.get("employee_name") or "—")
    story: list[Any] = [p(str(data.get("company") or "HR-Profi"), company), p(str(data.get("company_subtitle") or ""), small), Spacer(1, 2 * mm)]
    head = Table([[p(f"№ {doc.number}", small), p(issued, small)]], colWidths=[85 * mm, 85 * mm])
    head.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 1, colors.HexColor("#1596a8")), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [head, p(t["title"], title), p(f"{t['says']} {name} {t['works']}")]
    for key, label_text in (("position", t["position"]), ("department", t["department"]), ("branch", t["branch"]), ("hire_date", t["hired"])):
        value = data.get(key)
        if value:
            shown = value if key != "hire_date" else str(value)[8:10] + "." + str(value)[5:7] + "." + str(value)[:4]
            story.append(p(f"{label_text}: {shown}"))
    duties = [str(x) for x in data.get("duties", []) if str(x).strip()]
    if duties:
        story.append(p(t["duties"], label))
        story.append(p("\n".join(f"• {x}" for x in duties)))
    story += [Spacer(1, 12 * mm), p(f"{t['signer']}: {data.get('issued_by') or '—'}"), p(f"{t['date']}: {issued}", small)]
    sign = Table([[p(f"{t['code']}: {doc.code}", small), [QRCode(verify_url, 27 * mm), p(t["valid"] if doc.status == "issued" else t["cancelled"], small)]]], colWidths=[118 * mm, 45 * mm])
    sign.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9ca3af")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [Spacer(1, 14 * mm), KeepTogether([sign, Spacer(1, 3 * mm), p(t["verify"].format(url=verify_url), small)])]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=doc.number).build(story)
    return buf.getvalue()
