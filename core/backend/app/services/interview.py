"""AI suhbat: lavozim kompetensiyasidan hard/soft savollar, javoblarni AI baholash (0-10), umumiy foiz va xulosa.

AI o'chiq bo'lsa savollar kompetensiya kartochkasidan shablon bilan tuziladi, baholashni HR qo'lda qiladi.
"""

import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Position
from app.models.recruit import Application, PositionRequirement
from app.models.smart import AiInterview
from app.services import ai
from app.timeutil import now

LANG_NAME = {"uz": "o'zbek (lotin)", "ru": "русский"}
GENERIC_HARD = ["Oldingi ish joyingizda qanday vazifalarni bajargansiz? Aniq misol keltiring.", "Kasbingizdagi eng murakkab holatni va uni qanday hal qilganingizni aytib bering.", "Ishingizda qaysi dastur va vositalardan foydalanasiz?"]
GENERIC_SOFT = ["Norozi mijoz bilan qanday gaplashasiz? Misol keltiring.", "Jamoada kelishmovchilik bo'lsa, nima qilasiz?", "Nima uchun aynan shu lavozimda ishlamoqchisiz?"]


def new_token() -> str:
    return secrets.token_urlsafe(16)[:22]


async def _card(db: AsyncSession, position_id: int | None) -> tuple[str, dict[str, Any]]:
    if not position_id:
        return "Xodim", {}
    pos = await db.get(Position, position_id)
    req = await db.scalar(select(PositionRequirement).where(PositionRequirement.position_id == position_id))
    prof = dict(req.profile or {}) if req else {}
    if req and req.requirements:
        prof["requirements"] = req.requirements
    return (pos.name if pos else "Xodim"), prof


def template_questions(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """AI bo'lmaganda: kartochkadagi har bir ko'nikma bo'yicha savol (3 hard + 3 soft)."""
    hard = [str(x) for x in (profile.get("hard_skills") or [])][:3]
    soft = [str(x) for x in (profile.get("soft_skills") or [])][:3]
    qs = [{"kind": "hard", "skill": s, "text": f"«{s}» bo'yicha tajribangizni aniq misol bilan aytib bering."} for s in hard]
    qs += [{"kind": "hard", "skill": None, "text": t} for t in GENERIC_HARD[: 3 - len(hard)]]
    qs += [{"kind": "soft", "skill": s, "text": f"«{s}» sifatingiz namoyon bo'lgan vaziyatni aytib bering."} for s in soft]
    qs += [{"kind": "soft", "skill": None, "text": t} for t in GENERIC_SOFT[: 3 - len(soft)]]
    return [{"id": f"q{i + 1}", **q} for i, q in enumerate(qs)]


async def build_questions(db: AsyncSession, user_id: int, position_id: int | None, lang: str) -> tuple[str, list[dict[str, Any]]]:
    title, profile = await _card(db, position_id)
    cfg = await ai.get_cfg(db)
    if not ai.feature_on(cfg, "interview"):
        return title, template_questions(profile)
    system = (
        f"{ai.SYSTEM_RULES}\nVazifa: '{title}' lavozimiga nomzod uchun {LANG_NAME.get(lang, LANG_NAME['uz'])} tilida suhbat savollarini tuzing: "
        "3 ta hard skill (kasbiy bilim, amaliy vaziyat) va 3 ta soft skill (muloqot, mas'uliyat, jamoa) savoli. Savollar qisqa, aniq va ochiq bo'lsin. "
        'FAQAT bitta JSON qaytaring: {"questions": [{"kind": "hard"|"soft", "skill": str|null, "text": str}]}.'
    )
    try:
        raw, _ = await ai.run_for(db, user_id, "interview", system, f"<data>\nLavozim: {title}\nKompetensiya kartochkasi: {profile}\n</data>", max_tokens=1200)
        items = ai.extract_json(raw).get("questions") or []
    except Exception:  # noqa: BLE001 — AI xatosida shablon savollar bilan davom etamiz
        return title, template_questions(profile)
    qs = [
        {"kind": q["kind"], "skill": (str(q.get("skill"))[:80] if q.get("skill") else None), "text": str(q["text"]).strip()[:500]}
        for q in items
        if isinstance(q, dict) and q.get("kind") in ("hard", "soft") and str(q.get("text") or "").strip()
    ][:8]
    if len(qs) < 4:
        return title, template_questions(profile)
    return title, [{"id": f"q{i + 1}", **q} for i, q in enumerate(qs)]


async def grade(db: AsyncSession, iv: AiInterview, user_id: int) -> bool:
    """Javoblarni AI baholaydi. AI o'chiq yoki xato bo'lsa False (HR qo'lda baholaydi)."""
    cfg = await ai.get_cfg(db)
    if not ai.feature_on(cfg, "interview"):
        return False
    lines = []
    for q in iv.questions:
        a = (iv.answers or {}).get(q["id"]) or {}
        lines.append(f"[{q['id']}] ({q['kind']}) Savol: {q['text']}\nJavob: {(a.get('text') or a.get('transcript') or '—')[:2000]}")
    system = (
        f"{ai.SYSTEM_RULES}\nVazifa: '{iv.title}' lavozimi bo'yicha nomzod javoblarini adolatli baholang. Har javobga 0-10 ball va 1 jumlali izoh "
        f"({LANG_NAME.get(iv.lang, LANG_NAME['uz'])} tilida). Bo'sh yoki savolga aloqasiz javob 0. Keyin hard va soft bo'yicha umumiy foiz (0-100) va 2-3 jumlali xulosa. "
        'FAQAT bitta JSON: {"scores": [{"id": str, "score": int, "feedback": str}], "hard": int, "soft": int, "summary": str}.'
    )
    try:
        raw, _ = await ai.run_for(db, user_id, "interview", system, "<data>\n" + "\n\n".join(lines) + "\n</data>", max_tokens=1500, entity="ai_interview", entity_id=iv.id)
        d = ai.extract_json(raw)
    except Exception:  # noqa: BLE001
        return False
    ids = {q["id"] for q in iv.questions}
    scores = {}
    for s in d.get("scores") or []:
        if isinstance(s, dict) and s.get("id") in ids:
            try:
                scores[s["id"]] = {"score": max(0, min(10, int(s.get("score", 0)))), "feedback": str(s.get("feedback") or "")[:300]}
            except (TypeError, ValueError):
                continue

    def pct(kind: str, given: Any) -> int | None:
        vals = [scores[q["id"]]["score"] for q in iv.questions if q["kind"] == kind and q["id"] in scores]
        if vals:
            return round(sum(vals) / len(vals) * 10)
        try:
            return max(0, min(100, int(given)))
        except (TypeError, ValueError):
            return None

    iv.scores, iv.hard_pct, iv.soft_pct = scores, pct("hard", d.get("hard")), pct("soft", d.get("soft"))
    iv.summary, iv.status, iv.graded_at = str(d.get("summary") or "")[:1500] or None, "graded", now()
    if iv.application_id:
        a = await db.get(Application, iv.application_id)
        if a:  # inson bahosi bo'lmasa, 1-5 shkalaga o'tkazib yozamiz
            to5 = lambda p: None if p is None else max(1, min(5, round(p / 20)))  # noqa: E731
            a.hard_skill = a.hard_skill or to5(iv.hard_pct)
            a.soft_skill = a.soft_skill or to5(iv.soft_pct)
    return True


def out(iv: AiInterview, *, public: bool = False) -> dict[str, Any]:
    base = {"id": iv.id, "title": iv.title, "status": iv.status, "lang": iv.lang, "questions": iv.questions,
            "answers": {k: {"text": v.get("text"), "transcript": v.get("transcript")} for k, v in (iv.answers or {}).items()}}  # fmt: skip
    if public:
        return base
    return {**base, "token": iv.token, "url": f"/interview/{iv.token}", "application_id": iv.application_id, "employee_id": iv.employee_id,
            "scores": iv.scores, "hard_pct": iv.hard_pct, "soft_pct": iv.soft_pct, "summary": iv.summary,
            "created_at": iv.created_at, "submitted_at": iv.submitted_at, "graded_at": iv.graded_at}  # fmt: skip
