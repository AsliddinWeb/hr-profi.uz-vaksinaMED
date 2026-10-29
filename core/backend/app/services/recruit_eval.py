"""Rekruting 2 (F49): suhbat kartochkasi (kompetensiya ballari), test banki, fon tekshiruvi, yakuniy xulosa loyihasi va offer PDF."""

import io
import re
import secrets
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import error
from app.models.auth import User
from app.models.recruit import (
    Application,
    Candidate,
    CandidateTest,
    InterviewScore,
    PositionRequirement,
    TestBank,
    Vacancy,
)
from app.services import recruit_pipeline as psvc
from app.services.attendance_pdf import _fonts
from app.services.letters_pdf import QRCode
from app.services.notifications import register_template
from app.timeutil import tz

TEST_KINDS = ("iq", "logic", "position")
BG_ITEMS = ("reference", "documents", "social", "other")
BG_RESULTS = ("positive", "negative", "unknown")
DEFAULT_COMPETENCIES = ("Kasbiy bilim", "Muloqot", "Mas'uliyat", "Jamoada ishlash", "O'rganuvchanlik")
GRACE_SECONDS = 30
FAIR_NOTE = "Eslatma: jins, yosh, millat va din baholashda ishtirok etmaydi. Bu faqat loyiha: yakuniy qarorni HR rahbariyati qabul qiladi."

register_template("recruit.test_done", {"uz": "Nomzod testni topshirdi", "ru": "Кандидат сдал тест"}, {"uz": "{candidate}: {test} — {score}% ({result})", "ru": "{candidate}: {test} — {score}% ({result})"}, "info")
register_template("recruit.consent_given", {"uz": "Nomzod fon tekshiruviga rozilik berdi", "ru": "Кандидат дал согласие на проверку"}, {"uz": "{candidate}", "ru": "{candidate}"}, "info")
register_template("recruit.bg_done", {"uz": "Fon tekshiruvi tugadi", "ru": "Проверка завершена"}, {"uz": "{candidate}: {result}", "ru": "{candidate}: {result}"}, "info")
register_template("recruit.offer_response", {"uz": "Nomzod offerga javob berdi", "ru": "Кандидат ответил на оффер"}, {"uz": "{candidate}: {answer}", "ru": "{candidate}: {answer}"}, "info")
register_template("recruit.conclusion_approved", {"uz": "Yakuniy xulosa tasdiqlandi", "ru": "Итоговое заключение утверждено"}, {"uz": "{candidate}: {rec}", "ru": "{candidate}: {rec}"}, "success")


def new_token() -> str:
    return secrets.token_urlsafe(14)[:20]


# --- Suhbat kartochkasi ---------------------------------------------------------------


def competencies(card: dict[str, Any] | None) -> list[dict[str, str]]:
    """Baholanadigan kompetensiyalar: kartochkadagi hard/soft skill; bo'sh bo'lsa standart ro'yxat."""
    card = card or {}
    out = [{"key": s, "group": "hard"} for s in card.get("hard_skills") or []] + [{"key": s, "group": "soft"} for s in card.get("soft_skills") or []]
    return out or [{"key": s, "group": "soft"} for s in DEFAULT_COMPETENCIES]


async def card_for(db: AsyncSession, a: Application) -> dict[str, Any]:
    v = await db.get(Vacancy, a.vacancy_id)
    r = await db.scalar(select(PositionRequirement).where(PositionRequirement.position_id == v.position_id)) if v and v.position_id else None
    return (r.profile if r else None) or {}


def clean_scores(scores: dict[str, Any], comps: list[dict[str, str]]) -> dict[str, int]:
    keys = {c["key"] for c in comps}
    out: dict[str, int] = {}
    for k, v in scores.items():
        if k not in keys:
            raise error(400, "unknown_competency")
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
            raise error(400, "score_invalid")
        out[k] = v
    if not out:
        raise error(400, "scores_required")
    return out


def summarize_scores(rows: list[InterviewScore], comps: list[dict[str, str]]) -> dict[str, Any]:
    per: dict[str, list[int]] = {c["key"]: [] for c in comps}
    for r in rows:
        for k, v in (r.scores or {}).items():
            if k in per:
                per[k].append(v)
    avg = {k: round(sum(v) / len(v), 2) for k, v in per.items() if v}
    allv = [x for v in per.values() for x in v]
    return {"by_competency": avg, "overall": round(sum(allv) / len(allv), 2) if allv else None, "interviewers": len(rows)}


# --- Test banki ------------------------------------------------------------------------


def clean_questions(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw or len(raw) > 100:
        raise error(400, "questions_invalid")
    out, seen = [], set()
    for q in raw:
        text = str(q.get("text") or "").strip()
        opts = [str(o).strip() for o in (q.get("options") or [])]
        correct = sorted({int(i) for i in (q.get("correct") or []) if isinstance(i, int) and not isinstance(i, bool)})
        if not text or not 2 <= len(opts) <= 6 or any(not o for o in opts) or not correct or any(i < 0 or i >= len(opts) for i in correct):
            raise error(400, "questions_invalid")
        qid = str(q.get("id") or "") or secrets.token_hex(3)
        if qid in seen:
            raise error(400, "questions_invalid")
        seen.add(qid)
        out.append({"id": qid, "text": text[:500], "options": [o[:200] for o in opts], "correct": correct})
    return out


def public_questions(bank: TestBank) -> list[dict[str, Any]]:
    return [{"id": q["id"], "text": q["text"], "options": q["options"], "multiple": len(q["correct"]) > 1} for q in bank.questions or []]


def score_answers(bank: TestBank, answers: dict[str, Any]) -> int:
    qs = bank.questions or []
    right = 0
    for q in qs:
        given = answers.get(q["id"])
        if isinstance(given, list) and sorted({i for i in given if isinstance(i, int) and not isinstance(i, bool)}) == q["correct"]:
            right += 1
    return round(right / len(qs) * 100) if qs else 0


def test_status(t: CandidateTest, moment: datetime) -> str:
    """Muddati o'tib topshirilmagan test «expired» ko'rinadi."""
    if t.status == "started" and t.deadline_at and moment.timestamp() > t.deadline_at.timestamp() + GRACE_SECONDS:
        return "expired"
    return t.status


def test_out(t: CandidateTest, bank: TestBank | None, moment: datetime, url: str | None = None) -> dict[str, Any]:
    return {
        "id": t.id, "bank": {"id": t.bank_id, "name": bank.name if bank else None, "kind": bank.kind if bank else None, "pass_score": bank.pass_score if bank else None, "time_limit_min": bank.time_limit_min if bank else None},
        "status": test_status(t, moment), "started_at": t.started_at, "deadline_at": t.deadline_at, "submitted_at": t.submitted_at, "score_pct": t.score_pct, "passed": t.passed, "url": url,
    }  # fmt: skip


# --- Fon tekshiruvi ---------------------------------------------------------------------


def default_items() -> list[dict[str, Any]]:
    return [{"key": k, "result": None, "note": None} for k in BG_ITEMS]


# --- Yakuniy xulosa --------------------------------------------------------------------

REC_UZ = {"hire": "ishga olish", "reserve": "zaxiraga qo'yish", "reject": "olmaslik"}


async def build_conclusion(db: AsyncSession, a: Application) -> dict[str, Any]:
    """Intervyu, testlar, moslik va fon tekshiruvidan xulosa LOYIHASI (qoidalar asosida). Rekruter tahrirlaydi, HR rahbariyati tasdiqlaydi."""
    c = await db.get(Candidate, a.candidate_id)
    v = await db.get(Vacancy, a.vacancy_id)
    card = await card_for(db, a)
    comps = competencies(card)
    scores = list((await db.scalars(select(InterviewScore).where(InterviewScore.application_id == a.id))).all())
    sm = summarize_scores(scores, comps)
    tests = list((await db.scalars(select(CandidateTest).where(CandidateTest.application_id == a.id, CandidateTest.status == "submitted"))).all())
    banks = {b.id: b for b in (await db.scalars(select(TestBank).where(TestBank.id.in_([t.bank_id for t in tests])))).all()} if tests else {}
    lines = [f"Nomzod: {c.full_name if c else '—'}. Vakansiya: {v.title if v else '—'}."]
    parts: list[tuple[int, float]] = []
    if sm["overall"] is not None:
        pct = sm["overall"] / 5 * 100
        parts.append((50, pct))
        ranked = sorted(sm["by_competency"].items(), key=lambda kv: kv[1])
        strong = ", ".join(f"{k} ({v:g})" for k, v in ranked[::-1][:2])
        weak = ", ".join(f"{k} ({v:g})" for k, v in ranked[:2] if v < 3.5)
        lines.append(f"1) Suhbat: o'rtacha {sm['overall']:g}/5 ({sm['interviewers']} suhbatdosh). Kuchli tomonlari: {strong}." + (f" Rivojlantirish kerak: {weak}." if weak else ""))
    else:
        lines.append("1) Suhbat: kompetensiya baholari kiritilmagan.")
    if tests:
        avg = sum(t.score_pct or 0 for t in tests) / len(tests)
        parts.append((30, avg))
        def one(t: CandidateTest) -> str:
            name = banks[t.bank_id].name if t.bank_id in banks else "Test"
            return f"{name} — {t.score_pct}% ({passed_text if t.passed else failed_text})"

        passed_text, failed_text = "o'tdi", "o'tmadi"
        lines.append("2) Testlar: " + "; ".join(one(t) for t in tests) + ".")
    else:
        lines.append("2) Testlar: topshirilmagan.")
    if a.match_score is not None:
        parts.append((20, float(a.match_score)))
        lines.append(f"3) Kompetensiya kartochkasiga moslik: {a.match_score}%.")
    bg = a.bg_status
    lines.append("4) Fon tekshiruvi: " + {"passed": "o'tdi", "failed": "o'tmadi" + (f" ({a.bg_note})" if a.bg_note else ""), "pending": "jarayonda"}.get(bg or "", "o'tkazilmagan") + ".")
    if a.ai_scan and a.ai_scan.get("summary"):
        lines.append(f"5) AI skaner: {a.ai_scan.get('summary')}")
    total = round(sum(w * p for w, p in parts) / sum(w for w, _ in parts)) if parts else None
    if bg == "failed":
        rec = "reject"
    elif total is None:
        rec = "reserve"
    else:
        rec = "hire" if total >= 75 else "reserve" if total >= 55 else "reject"
    lines.append(f"Umumiy ball: {total if total is not None else '—'}/100. Tavsiya: {REC_UZ[rec]}.")
    lines.append(FAIR_NOTE)
    return {"draft": "\n".join(lines), "recommendation": rec, "score": total, "generated_at": datetime.now(tz()).isoformat(), "text": None, "status": "draft", "inputs": {"interview": sm["overall"], "tests": len(tests), "match": a.match_score, "background": bg}}


# --- Offer PDF -------------------------------------------------------------------------


async def build_offer_pdf(db: AsyncSession, a: Application, url: str, company: str) -> bytes:
    c = await db.get(Candidate, a.candidate_id)
    v = await db.get(Vacancy, a.vacancy_id)
    approver = await db.get(User, a.offer_decided_by) if a.offer_decided_by else None
    regular, bold = _fonts()
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontName=regular, fontSize=11, leading=16)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
    title = ParagraphStyle("title", parent=body, fontName=bold, fontSize=15, leading=20, alignment=1, spaceBefore=10, spaceAfter=10)
    b = ParagraphStyle("b", parent=body, fontName=bold)

    def p(x: str, st: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(x).replace("\n", "<br/>"), st)

    rows = [("Nomzod", c.full_name if c else "—"), ("Lavozim", v.title if v else "—"), ("Daraja", psvc.LEVEL_UZ.get(a.offer_level or "", "—")), ("Oylik (fiks)", f"{psvc.money(a.offer_salary)} so'm"),
            ("Ish grafigi", a.offer_schedule or "—"), ("Ishga chiqish sanasi", f"{a.offer_start:%d.%m.%Y}" if a.offer_start else "—"), ("Sinov muddati", f"{a.offer_probation_days} kun" if a.offer_probation_days is not None else "—")]  # fmt: skip
    info = Table([[p(k, small), p(val, b)] for k, val in rows], colWidths=[48 * mm, 115 * mm])
    info.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    resp = {"accepted": "Nomzod offerni qabul qilgan", "declined": "Nomzod offerni rad etgan"}.get(a.offer_response or "", "Nomzod javobi kutilmoqda")
    when = f" · {a.offer_response_at.astimezone(tz()):%d.%m.%Y %H:%M}" if a.offer_response_at else ""
    sign = [p("Elektron tasdiq", ParagraphStyle("sb", parent=body, fontName=bold, fontSize=10)), p(f"Tasdiqlagan: {approver.full_name if approver else '—'}" + (f" · {a.offer_decided_at.astimezone(tz()):%d.%m.%Y %H:%M}" if a.offer_decided_at else ""), small), p(resp + when, small)]
    sig = Table([[sign, [QRCode(url, 30 * mm)]]], colWidths=[118 * mm, 45 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9ca3af")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story = [p(company, ParagraphStyle("co", parent=body, fontName=bold, fontSize=12)), p("JOB OFFER (ISH TAKLIFI)", title), info]
    if a.offer_note:
        story += [Spacer(1, 4 * mm), p(a.offer_note)]
    story += [Spacer(1, 10 * mm), KeepTogether([sig, Spacer(1, 3 * mm), p(f"Offerga javob berish havolasi: {url}", small)])]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=18 * mm, title="Job offer").build(story)
    return buf.getvalue()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
