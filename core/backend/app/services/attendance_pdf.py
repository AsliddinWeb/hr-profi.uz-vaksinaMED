"""Davomat dashboardining PDF ko'rinishi (reportlab, DejaVu shrifti: kirill va o'zbek harflari)."""

import io
from datetime import date
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from app.config import get_settings

L = {
    "uz": {
        "title": "Davomat hisoboti", "period": "Davr", "filters": "Filtr", "kpi": "Asosiy ko'rsatkichlar",
        "employees": "Xodimlar", "attended": "Ishga kelgan kunlar", "absent": "Kelmagan kunlar", "rate": "Davomat foizi",
        "late": "Kechikish (marta)", "late_min": "Kechikish (daqiqa)", "early": "Erta ketish (marta)",
        "punctuality": "O'z vaqtida kelish", "hours": "Ishlagan soat", "dept": "Bo'limlar kesimida",
        "branch": "Filiallar kesimida", "top_late": "Ko'p kechikkanlar", "top_absent": "Ko'p kelmaganlar",
        "name": "Nomi", "person": "Xodim", "times": "Marta", "minutes": "Daqiqa", "days": "Kun", "none": "Bo'limsiz / filialsiz",
        "generated": "Tayyorlandi",
    },
    "ru": {
        "title": "Отчёт по посещаемости", "period": "Период", "filters": "Фильтр", "kpi": "Основные показатели",
        "employees": "Сотрудники", "attended": "Отработанные дни", "absent": "Дни неявок", "rate": "Посещаемость",
        "late": "Опоздания (раз)", "late_min": "Опоздания (мин)", "early": "Ранний уход (раз)",
        "punctuality": "Приход вовремя", "hours": "Отработано часов", "dept": "По отделам",
        "branch": "По филиалам", "top_late": "Чаще всего опаздывают", "top_absent": "Чаще всего не выходят",
        "name": "Название", "person": "Сотрудник", "times": "Раз", "minutes": "Минут", "days": "Дней", "none": "Без отдела / филиала",
        "generated": "Сформировано",
    },
}


def _fonts() -> tuple[str, str]:
    d = Path(get_settings().font_dir)
    if "DejaVu" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("DejaVu", str(d / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(d / "DejaVuSans-Bold.ttf")))
    return "DejaVu", "DejaVu-Bold"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def _d(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def build_pdf(data: dict[str, Any], lang: str, filters_text: str, generated: str) -> bytes:
    t = L["ru" if lang == "ru" else "uz"]
    regular, bold = _fonts()
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontName=regular, fontSize=9, leading=12)
    h1 = ParagraphStyle("h1", parent=body, fontName=bold, fontSize=16, leading=20, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=body, fontName=bold, fontSize=11, leading=14, spaceBefore=12, spaceAfter=4)
    muted = ParagraphStyle("muted", parent=body, textColor=colors.HexColor("#6b7280"))

    def table(rows: list[list[Any]], widths: list[float], numeric_from: int = 1) -> Table:
        tb = Table(rows, colWidths=widths, repeatRows=1)
        tb.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), regular), ("FONTNAME", (0, 0), (-1, 0), bold),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef0fb")),
            ("ALIGN", (numeric_from, 0), (-1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))  # fmt: skip
        return tb

    k = data["kpis"]
    story: list[Any] = [
        Paragraph(t["title"], h1),
        Paragraph(f"{t['period']}: {_d(data['start'])} – {_d(data['end'])}", body),
        Paragraph(f"{t['filters']}: {filters_text}", muted),
        Paragraph(f"{t['generated']}: {generated}", muted),
        Paragraph(t["kpi"], h2),
        table(
            [
                [t["employees"], k["employees"]], [t["attended"], k["attended"]], [t["absent"], k["absent"]],
                [t["rate"], _pct(k["rate"])], [t["punctuality"], _pct(k["punctuality"])],
                [t["late"], k["late_count"]], [t["late_min"], k["late_minutes"]], [t["early"], k["early_count"]],
                [t["hours"], f"{k['worked_minutes'] / 60:.1f}"],
            ],
            [110 * mm, 40 * mm],
        ),
    ]  # fmt: skip
    for key, title in (("by_department", t["dept"]), ("by_branch", t["branch"])):
        rows = [[t["name"], t["employees"], t["absent"], t["late"], t["rate"]]]
        for r in data[key]:
            rows.append([r["name"] or t["none"], r["employees"], r["absent"], r["late_count"], _pct(r["rate"])])
        story += [Paragraph(title, h2), table(rows, [70 * mm, 25 * mm, 25 * mm, 30 * mm, 25 * mm])]
    for key, title, col, head in (("top_late", t["top_late"], "late_count", t["times"]), ("top_absent", t["top_absent"], "absent", t["days"])):
        if data[key]:
            rows = [[t["person"], head] + ([t["minutes"]] if key == "top_late" else [])]
            for p in data[key]:
                rows.append([p["employee"]["full_name"], p[col]] + ([p["late_minutes"]] if key == "top_late" else []))
            story += [Paragraph(title, h2), table(rows, [100 * mm, 25 * mm] + ([25 * mm] if key == "top_late" else []))]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=t["title"]).build(story)
    return buf.getvalue()
