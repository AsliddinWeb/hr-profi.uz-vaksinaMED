"""Tushuntirish xatining PDF ko'rinishi: elektron imzo bloki va tekshirish QR kodi bilan."""

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.letters import ExplanationLetter
from app.services.attendance_pdf import _fonts

STATUS_LABEL = {"submitted": "Topshirilgan", "accepted": "Qabul qilingan", "returned": "Qaytarilgan"}


class QRCode(Flowable):
    def __init__(self, data: str, size: float):
        super().__init__()
        self.size = size
        widget = qr.QrCodeWidget(data, barLevel="M")
        x0, y0, x1, y1 = widget.getBounds()
        self.drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
        self.drawing.add(widget)
        self.width = self.height = size

    def draw(self) -> None:
        renderPDF.draw(self.drawing, self.canv, 0, 0)


def build_letter_pdf(letter: ExplanationLetter, verify_url: str) -> bytes:
    regular, bold = _fonts()
    snap = letter.snapshot or {}
    sig = letter.signature or {}
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontName=regular, fontSize=11, leading=16)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
    title = ParagraphStyle("title", parent=body, fontName=bold, fontSize=15, leading=20, alignment=1, spaceBefore=14, spaceAfter=12)
    right = ParagraphStyle("right", parent=body, alignment=2)

    def para(text: str, style=body) -> Paragraph:
        return Paragraph(escape(text).replace("\n", "<br/>"), style)

    signed_at = datetime.fromisoformat(sig["at"]).strftime("%d.%m.%Y %H:%M") if sig.get("at") else "—"
    sign_info = [
        para("Elektron imzo bilan imzolangan", ParagraphStyle("sb", parent=body, fontName=bold, fontSize=10)),
        para(f"{sig.get('name', '')}", small),
        para(f"Sana: {signed_at}", small),
        para(f"Hujjat raqami: {letter.number}", small),
        para(f"SHA-256: {(letter.content_hash or '')[:32]}…", small),
        para(f"Holat: {STATUS_LABEL.get(letter.status, letter.status)}", small),
    ]
    sig_table = Table([[sign_info, [QRCode(verify_url, 30 * mm), para(f"Kod: {letter.code}", small)]]], colWidths=[118 * mm, 45 * mm])
    sig_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9ca3af")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))

    story = [
        para(snap.get("company", ""), ParagraphStyle("co", parent=body, fontName=bold, fontSize=12)),
        para(f"№ {letter.number}    {snap.get('date', '')}", small),
        Spacer(1, 6 * mm),
        para(snap.get("recipient", ""), right),
        para(f"{snap.get('employee_name', '')}", right),
        para(snap.get("title", "TUSHUNTIRISH XATI"), title),
        para(snap.get("body", letter.explanation or "")),
        Spacer(1, 12 * mm),
        KeepTogether([sig_table, Spacer(1, 3 * mm), para(f"Hujjat haqiqiyligini QR kod yoki {verify_url} orqali tekshirish mumkin.", small)]),
    ]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=18 * mm, title=f"{letter.number}").build(story)
    return buf.getvalue()
