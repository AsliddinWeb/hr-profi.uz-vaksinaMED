"""Rekruting 2 (F49): suhbat kartochkasi, test banki va nomzod testi, fon tekshiruvi (rozilik bilan), yakuniy xulosa, offer javobi."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import _base_url
from app.api.recruit import Manage, Read, _application
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.recruit import (
    Application,
    BackgroundCheck,
    Candidate,
    CandidateTest,
    InterviewScore,
    TestBank,
    Vacancy,
)
from app.rbac import matches
from app.services import recruit as rsvc
from app.services import recruit_eval as ev
from app.services import recruit_pipeline as psvc
from app.services.answers import users_with_permission
from app.services.audit import audit, client_ip
from app.services.notifications import deliver, notify
from app.timeutil import now

router = APIRouter(prefix="/v1/recruit", tags=["recruit-eval"])
public_router = APIRouter(prefix="/v1/public", tags=["public"])


def _can(auth: AuthContext, *perms: str) -> bool:
    return any(matches(auth.permissions, p) for p in perms)


def _need(auth: AuthContext, *perms: str) -> None:
    if not _can(auth, *perms):
        raise error(403, "forbidden")


async def _rate(request: Request, kind: str, limit: int, window: int) -> None:
    redis = request.app.state.redis
    key = f"rl:{kind}:{client_ip(request)}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, window)
    if n > limit:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(key), 1))


async def _tell(request: Request, c: Candidate | None, text: str) -> bool:
    if c and c.telegram_chat_id:
        await request.app.state.queue.enqueue("deliver_candidate_telegram", c.telegram_chat_id, text)  # type: ignore[union-attr]
        return True
    return False


async def _recruiter_ids(db: AsyncSession, a: Application, *extra: int | None) -> list[int]:
    return [u for u in dict.fromkeys([a.recruiter_id, *extra]) if u]


# --- Suhbat kartochkasi (kompetensiya ballari) ------------------------------------------


class ScoreIn(BaseModel):
    scores: dict[str, int] = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/applications/{aid}/scorecard")
async def scorecard(aid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Intervyu kartochkasi: kompetensiyalar va savollar, mening ballarim; HR hamma suhbatdosh ballari va o'rtachani ko'radi."""
    _need(auth, "recruit.manage", "recruit.interview")
    a = await _application(db, aid)
    card = await ev.card_for(db, a)
    comps = ev.competencies(card)
    rows = list((await db.scalars(select(InterviewScore).where(InterviewScore.application_id == aid))).all())
    mine = next((r for r in rows if r.interviewer_id == auth.user.id), None)
    manage = _can(auth, "recruit.manage")
    c, v = await db.get(Candidate, a.candidate_id), await db.get(Vacancy, a.vacancy_id)
    out: dict[str, Any] = {
        "application": {"id": a.id, "candidate": c.full_name if c else None, "vacancy": v.title if v else None}, "competencies": comps, "questions": card.get("questions") or [],
        "mine": {"scores": mine.scores, "notes": mine.notes} if mine else None, "summary": ev.summarize_scores(rows, comps) if manage else None,
    }  # fmt: skip
    if manage:
        names = await rsvc.names(db, {r.interviewer_id for r in rows})
        out["interviewers"] = [{"name": names.get(r.interviewer_id), "scores": r.scores, "notes": r.notes, "avg": round(sum(r.scores.values()) / len(r.scores), 2) if r.scores else None} for r in rows]
    return out


@router.put("/applications/{aid}/scorecard")
async def save_scorecard(aid: int, body: ScoreIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "recruit.manage", "recruit.interview")
    a = await _application(db, aid, lock=True)
    if a.stage in ("hired", "rejected"):
        raise error(409, "invalid_transition")
    comps = ev.competencies(await ev.card_for(db, a))
    scores = ev.clean_scores(body.scores, comps)
    row = await db.scalar(select(InterviewScore).where(InterviewScore.application_id == aid, InterviewScore.interviewer_id == auth.user.id))
    if row is None:
        row = InterviewScore(application_id=aid, interviewer_id=auth.user.id)
        db.add(row)
    row.scores, row.notes = scores, (body.notes or "").strip() or None
    rsvc.log(db, a, auth.user.id, "comment", note="Suhbat bahosi kiritildi", data={"scorecard": True})
    await audit(db, request, "recruit.scorecard", actor=auth.user, entity="application", entity_id=a.id)
    await db.commit()
    return {"saved": True, "scores": scores}


# --- Test banki ---------------------------------------------------------------------------


class QuestionIn(BaseModel):
    id: str | None = Field(default=None, max_length=12)
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    correct: list[int] = Field(min_length=1, max_length=6)


class BankIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    kind: str = Field(pattern="^(iq|logic|position)$")
    position_id: int | None = None
    time_limit_min: int = Field(default=20, ge=1, le=240)
    pass_score: int = Field(default=60, ge=1, le=100)
    questions: list[QuestionIn] = Field(min_length=1, max_length=100)
    is_active: bool = True


def _bank_out(b: TestBank, *, answers: bool) -> dict[str, Any]:
    qs = b.questions or []
    return {"id": b.id, "name": b.name, "kind": b.kind, "position_id": b.position_id, "time_limit_min": b.time_limit_min, "pass_score": b.pass_score, "is_active": b.is_active, "question_count": len(qs),
            "questions": qs if answers else None}  # fmt: skip


@router.get("/tests")
async def list_banks(position_id: int | None = None, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    stmt = select(TestBank).order_by(TestBank.kind, TestBank.name)
    if position_id:
        stmt = stmt.where((TestBank.position_id == position_id) | TestBank.position_id.is_(None))
    return [_bank_out(b, answers=False) for b in (await db.scalars(stmt)).all()]


@router.post("/tests", status_code=201)
async def create_bank(body: BankIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    b = TestBank(name=body.name.strip(), kind=body.kind, position_id=body.position_id, time_limit_min=body.time_limit_min, pass_score=body.pass_score, questions=ev.clean_questions([q.model_dump() for q in body.questions]), is_active=body.is_active, created_by=auth.user.id)
    db.add(b)
    await db.flush()
    await audit(db, request, "recruit.test_create", actor=auth.user, entity="test_bank", entity_id=b.id)
    await db.commit()
    return _bank_out(b, answers=True)


@router.get("/tests/{bid}")
async def get_bank(bid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Manage)):
    b = await db.get(TestBank, bid)
    if not b:
        raise error(404, "not_found")
    return _bank_out(b, answers=True)


@router.put("/tests/{bid}")
async def update_bank(bid: int, body: BankIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    b = await db.get(TestBank, bid)
    if not b:
        raise error(404, "not_found")
    b.name, b.kind, b.position_id, b.time_limit_min, b.pass_score, b.is_active = body.name.strip(), body.kind, body.position_id, body.time_limit_min, body.pass_score, body.is_active
    b.questions = ev.clean_questions([q.model_dump() for q in body.questions])
    await audit(db, request, "recruit.test_update", actor=auth.user, entity="test_bank", entity_id=b.id)
    await db.commit()
    return _bank_out(b, answers=True)


@router.delete("/tests/{bid}", status_code=204)
async def delete_bank(bid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    b = await db.get(TestBank, bid)
    if not b:
        raise error(404, "not_found")
    if await db.scalar(select(func.count()).select_from(CandidateTest).where(CandidateTest.bank_id == bid)):
        raise error(409, "in_use")  # natijalari bor: nofaol qiling
    await audit(db, request, "recruit.test_delete", actor=auth.user, entity="test_bank", entity_id=bid)
    await db.delete(b)
    await db.commit()


class AssignIn(BaseModel):
    bank_id: int


@router.post("/applications/{aid}/tests", status_code=201)
async def assign_test(aid: int, body: AssignIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid, lock=True)
    if a.stage in ("hired", "rejected"):
        raise error(409, "invalid_transition")
    bank = await db.get(TestBank, body.bank_id)
    if not bank or not bank.is_active:
        raise error(400, "unknown_test")
    t = CandidateTest(application_id=a.id, bank_id=bank.id, token=ev.new_token(), created_by=auth.user.id)
    db.add(t)
    await db.flush()
    url = f"{_base_url(request)}/test/{t.token}"
    c = await db.get(Candidate, a.candidate_id)
    sent = await _tell(request, c, f"📝 «{bank.name}» testi: {bank.time_limit_min} daqiqa, {len(bank.questions or [])} savol. Boshlash: {url}")
    rsvc.log(db, a, auth.user.id, "comment", note=f"Test berildi: {bank.name}", data={"test": bank.id})
    await audit(db, request, "recruit.test_assign", actor=auth.user, entity="application", entity_id=a.id, data={"bank": bank.id, "telegram": sent})
    await db.commit()
    return {**ev.test_out(t, bank, now(), url), "telegram_sent": sent}


@router.get("/applications/{aid}/tests")
async def application_tests(aid: int, request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    await _application(db, aid)
    rows = list((await db.scalars(select(CandidateTest).where(CandidateTest.application_id == aid).order_by(CandidateTest.id.desc()))).all())
    banks = {b.id: b for b in (await db.scalars(select(TestBank).where(TestBank.id.in_([t.bank_id for t in rows])))).all()} if rows else {}
    base, moment = _base_url(request), now()
    return [ev.test_out(t, banks.get(t.bank_id), moment, f"{base}/test/{t.token}" if ev.test_status(t, moment) in ("assigned", "started") else None) for t in rows]


async def _test_ctx(db: AsyncSession, token: str, *, lock: bool = False) -> tuple[CandidateTest, TestBank, Application]:
    stmt = select(CandidateTest).where(CandidateTest.token == token[:24])
    t = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not t:
        raise error(404, "not_found")
    return t, await db.get(TestBank, t.bank_id), await db.get(Application, t.application_id)  # type: ignore[return-value]


def _public_test(t: CandidateTest, b: TestBank, moment: datetime, *, with_questions: bool) -> dict[str, Any]:
    st = ev.test_status(t, moment)
    out = {"name": b.name, "kind": b.kind, "time_limit_min": b.time_limit_min, "question_count": len(b.questions or []), "status": st, "deadline_at": t.deadline_at}
    if with_questions and st == "started":
        out["questions"] = ev.public_questions(b)
    return out


@public_router.get("/test/{token}")
async def public_test(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "test_view", 120, 60)
    t, b, _ = await _test_ctx(db, token)
    return _public_test(t, b, now(), with_questions=True)


@public_router.post("/test/{token}/start")
async def public_test_start(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    """Testni boshlaydi: vaqt hisobi shu paytdan (server tomonida). Qayta bosilsa vaqt yangilanmaydi."""
    await _rate(request, "test_write", 30, 60)
    t, b, _ = await _test_ctx(db, token, lock=True)
    moment = now()
    if t.status == "assigned":
        t.status, t.started_at, t.deadline_at = "started", moment, moment + timedelta(minutes=b.time_limit_min)
        await db.commit()
    return _public_test(t, b, moment, with_questions=True)


class SubmitIn(BaseModel):
    answers: dict[str, list[int]] = Field(default_factory=dict)


@public_router.post("/test/{token}/submit")
async def public_test_submit(token: str, body: SubmitIn, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "test_write", 30, 60)
    t, b, a = await _test_ctx(db, token, lock=True)
    moment = now()
    if t.status != "started":
        raise error(409, "test_closed")
    if ev.test_status(t, moment) == "expired":
        t.status = "expired"
        t.passed = False
        await db.commit()
        raise error(409, "test_expired")
    t.answers, t.submitted_at, t.status = {k: v for k, v in body.answers.items() if len(v) <= 6}, moment, "submitted"
    t.score_pct = ev.score_answers(b, t.answers)
    t.passed = t.score_pct >= b.pass_score
    c = await db.get(Candidate, a.candidate_id)
    notes = await notify(db, await _recruiter_ids(db, a), "recruit.test_done", params={"candidate": c.full_name if c else "", "test": b.name, "score": t.score_pct, "result": "o'tdi" if t.passed else "o'tmadi"}, link=f"/recruit/applications/{a.id}")
    await db.commit()
    await deliver(request.app, notes)
    return {"status": "submitted"}  # natija nomzodga ko'rsatilmaydi


# --- Fon tekshiruvi (rozilik bilan) --------------------------------------------------------


class ItemsIn(BaseModel):
    items: list[dict[str, Any]] = Field(max_length=10)


class FinishIn(BaseModel):
    decision: str = Field(pattern="^(passed|failed)$")
    note: str | None = Field(default=None, max_length=2000)


def _bg_out(bg: BackgroundCheck | None, url: str | None = None) -> dict[str, Any] | None:
    if bg is None:
        return None
    return {"id": bg.id, "status": bg.status, "consent_at": bg.consent_at, "items": bg.items or [], "decision": bg.decision, "decision_note": bg.decision_note, "finished_at": bg.finished_at, "consent_url": url}


@router.post("/applications/{aid}/background-check", status_code=201)
async def start_background(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "recruit.manage", "recruit.background")
    a = await _application(db, aid, lock=True)
    bg = await db.scalar(select(BackgroundCheck).where(BackgroundCheck.application_id == aid))
    if bg is None:
        bg = BackgroundCheck(application_id=aid, consent_token=ev.new_token(), items=ev.default_items(), created_by=auth.user.id)
        db.add(bg)
        a.bg_status = a.bg_status or "pending"
        await db.flush()
    url = f"{_base_url(request)}/consent/{bg.consent_token}"
    sent = False
    if bg.consent_at is None:
        sent = await _tell(request, await db.get(Candidate, a.candidate_id), f"🔒 Fon tekshiruviga rozilik berish uchun havola: {url}")
    await audit(db, request, "recruit.bg_start", actor=auth.user, entity="application", entity_id=a.id, data={"telegram": sent})
    await db.commit()
    return {**_bg_out(bg, url if bg.consent_at is None else None), "telegram_sent": sent}  # type: ignore[dict-item]


@router.get("/applications/{aid}/background-check")
async def get_background(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "recruit.manage", "recruit.background")
    await _application(db, aid)
    bg = await db.scalar(select(BackgroundCheck).where(BackgroundCheck.application_id == aid))
    return _bg_out(bg, f"{_base_url(request)}/consent/{bg.consent_token}" if bg and bg.consent_at is None else None)


@router.put("/applications/{aid}/background-check/items")
async def background_items(aid: int, body: ItemsIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "recruit.manage", "recruit.background")
    await _application(db, aid, lock=True)
    bg = await db.scalar(select(BackgroundCheck).where(BackgroundCheck.application_id == aid).with_for_update())
    if not bg:
        raise error(404, "not_found")
    if bg.consent_at is None:
        raise error(409, "consent_required")
    if bg.status == "done":
        raise error(409, "already_finished")
    items = []
    for it in body.items:
        key, res = str(it.get("key") or ""), it.get("result")
        if key not in ev.BG_ITEMS or (res is not None and res not in ev.BG_RESULTS):
            raise error(400, "items_invalid")
        items.append({"key": key, "result": res, "note": (str(it.get("note") or "").strip()[:500]) or None})
    bg.items = items
    await db.commit()
    return _bg_out(bg)


@router.post("/applications/{aid}/background-check/finish")
async def finish_background(aid: int, body: FinishIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "recruit.manage", "recruit.background")
    a = await _application(db, aid, lock=True)
    bg = await db.scalar(select(BackgroundCheck).where(BackgroundCheck.application_id == aid).with_for_update())
    if not bg:
        raise error(404, "not_found")
    if bg.consent_at is None:
        raise error(409, "consent_required")
    note = (body.note or "").strip() or None
    if body.decision == "failed" and not note:
        raise error(400, "note_required")
    moment = now()
    bg.status, bg.decision, bg.decision_note, bg.checked_by, bg.finished_at = "done", body.decision, note, auth.user.id, moment
    a.bg_status, a.bg_note, a.bg_by, a.bg_at = body.decision, note, auth.user.id, moment  # eski «fon tekshiruv» maydonlari bilan sinxron (offer shunga tayanadi)
    rsvc.log(db, a, auth.user.id, "comment", note=f"Fon tekshiruvi: {body.decision}" + (f" — {note}" if note else ""), data={"background": body.decision})
    c = await db.get(Candidate, a.candidate_id)
    hr = await users_with_permission(db, "recruit.approve")
    notes = await notify(db, [u for u in dict.fromkeys([*(await _recruiter_ids(db, a)), *hr]) if u != auth.user.id], "recruit.bg_done", params={"candidate": c.full_name if c else "", "result": "o'tdi" if body.decision == "passed" else "o'tmadi"}, link=f"/recruit/applications/{a.id}")
    await audit(db, request, "recruit.bg_finish", actor=auth.user, entity="application", entity_id=a.id, data={"decision": body.decision})
    await db.commit()
    await deliver(request.app, notes)
    return _bg_out(bg)


@public_router.get("/consent/{token}")
async def public_consent(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "consent_view", 60, 60)
    bg = await db.scalar(select(BackgroundCheck).where(BackgroundCheck.consent_token == token[:24]))
    if not bg:
        raise error(404, "not_found")
    a = await db.get(Application, bg.application_id)
    c = await db.get(Candidate, a.candidate_id)  # type: ignore[union-attr]
    return {"name": c.full_name if c else None, "consent_at": bg.consent_at}


@public_router.post("/consent/{token}/agree")
async def public_consent_agree(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "consent_write", 20, 600)
    bg = await db.scalar(select(BackgroundCheck).where(BackgroundCheck.consent_token == token[:24]).with_for_update())
    if not bg:
        raise error(404, "not_found")
    if bg.consent_at is None:
        bg.consent_at, bg.consent_ip, bg.status = now(), client_ip(request), "in_progress"
        a = await db.get(Application, bg.application_id)
        c = await db.get(Candidate, a.candidate_id)  # type: ignore[union-attr]
        sec = await users_with_permission(db, "recruit.background")
        notes = await notify(db, [u for u in dict.fromkeys([*(await _recruiter_ids(db, a)), *sec])], "recruit.consent_given", params={"candidate": c.full_name if c else ""}, link=f"/recruit/applications/{a.id}")  # type: ignore[union-attr]
        await db.commit()
        await deliver(request.app, notes)
    return {"consent_at": bg.consent_at}


# --- Yakuniy xulosa ----------------------------------------------------------------------


class ConclusionIn(BaseModel):
    text: str = Field(min_length=10, max_length=6000)
    recommendation: str = Field(pattern="^(hire|reserve|reject)$")


@router.post("/applications/{aid}/conclusion/draft")
async def conclusion_draft(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Intervyu, test, moslik va fon tekshiruvidan xulosa loyihasini yaratadi (tasdiqlangan bo'lsa qayta yozilmaydi)."""
    a = await _application(db, aid, lock=True)
    if a.conclusion and a.conclusion.get("status") == "approved":
        raise error(409, "already_approved")
    a.conclusion = await ev.build_conclusion(db, a)
    await audit(db, request, "recruit.conclusion_draft", actor=auth.user, entity="application", entity_id=a.id)
    await db.commit()
    return a.conclusion


@router.put("/applications/{aid}/conclusion")
async def conclusion_edit(aid: int, body: ConclusionIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid, lock=True)
    if not a.conclusion:
        raise error(409, "no_draft")
    if a.conclusion.get("status") == "approved":
        raise error(409, "already_approved")
    a.conclusion = {**a.conclusion, "text": body.text.strip(), "recommendation": body.recommendation, "edited_by": auth.user.id}
    await db.commit()
    return a.conclusion


@router.post("/applications/{aid}/conclusion/approve")
async def conclusion_approve(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "recruit.approve")
    a = await _application(db, aid, lock=True)
    if not a.conclusion:
        raise error(409, "no_draft")
    if a.conclusion.get("status") == "approved":
        raise error(409, "already_approved")
    a.conclusion = {**a.conclusion, "status": "approved", "approved_by": auth.user.id, "approved_by_name": auth.user.full_name, "approved_at": now().isoformat()}
    c = await db.get(Candidate, a.candidate_id)
    notes = await notify(db, [u for u in await _recruiter_ids(db, a, a.offer_by) if u != auth.user.id], "recruit.conclusion_approved", params={"candidate": c.full_name if c else "", "rec": ev.REC_UZ[a.conclusion["recommendation"]]}, link=f"/recruit/applications/{a.id}")
    rsvc.log(db, a, auth.user.id, "comment", note=f"Yakuniy xulosa tasdiqlandi: {ev.REC_UZ[a.conclusion['recommendation']]}", data={"conclusion": a.conclusion["recommendation"]})
    await audit(db, request, "recruit.conclusion_approve", actor=auth.user, entity="application", entity_id=a.id, data={"rec": a.conclusion["recommendation"]})
    await db.commit()
    await deliver(request.app, notes)
    return a.conclusion


# --- Offer: havola, PDF, nomzod javobi ----------------------------------------------------


@router.post("/applications/{aid}/offer/link")
async def offer_link(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Tasdiqlangan offer uchun nomzodga havola (Telegram bo'lmasa rekruter o'zi ulashadi)."""
    a = await _application(db, aid, lock=True)
    if a.offer_status != "approved":
        raise error(409, "offer_not_approved")
    if not a.offer_token:
        a.offer_token = ev.new_token()
    await db.commit()
    return {"url": f"{_base_url(request)}/offer/{a.offer_token}"}


@router.get("/applications/{aid}/offer/pdf")
async def offer_pdf(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid)
    if not a.offer_status or a.offer_status == "rejected":
        raise error(409, "offer_not_approved")
    if not a.offer_token and a.offer_status == "approved":
        a = await _application(db, aid, lock=True)
        a.offer_token = ev.new_token()
        await db.commit()
    cfg = getattr(request.app.state, "client_config", None)
    company = (cfg.brand.get("name") if cfg else None) or "HR-Profi"
    url = f"{_base_url(request)}/offer/{a.offer_token}" if a.offer_token else _base_url(request)
    content = await ev.build_offer_pdf(db, a, url, company)
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="offer-{a.id}.pdf"'})


async def _offer_ctx(db: AsyncSession, token: str, *, lock: bool = False) -> tuple[Application, Candidate | None, Vacancy | None]:
    stmt = select(Application).where(Application.offer_token == token[:24])
    a = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not a or a.offer_status != "approved":
        raise error(404, "not_found")
    return a, await db.get(Candidate, a.candidate_id), await db.get(Vacancy, a.vacancy_id)


def _public_offer(a: Application, v: Vacancy | None) -> dict[str, Any]:
    return {"vacancy": v.title if v else None, "level": psvc.LEVEL_UZ.get(a.offer_level or ""), "salary": a.offer_salary, "start": a.offer_start, "schedule": a.offer_schedule, "probation_days": a.offer_probation_days, "note": a.offer_note, "response": a.offer_response, "response_at": a.offer_response_at}


@public_router.get("/offer/{token}")
async def public_offer(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "offer_view", 120, 60)
    a, _, v = await _offer_ctx(db, token)
    return _public_offer(a, v)


class OfferReplyIn(BaseModel):
    answer: str = Field(pattern="^(accepted|declined)$")
    reason: str | None = Field(default=None, max_length=300)


@public_router.post("/offer/{token}/respond")
async def public_offer_respond(token: str, body: OfferReplyIn, request: Request, db: AsyncSession = Depends(get_session)):
    """Nomzod offerni qabul qiladi yoki sabab ko'rsatib rad etadi (rad etilsa ariza avtomatik yopiladi)."""
    await _rate(request, "offer_write", 20, 600)
    a, c, v = await _offer_ctx(db, token, lock=True)
    if a.offer_response:
        raise error(409, "already_answered")
    reason = (body.reason or "").strip()
    if body.answer == "declined" and len(reason) < 3:
        raise error(400, "reason_required")
    moment = now()
    a.offer_response, a.offer_response_at, a.offer_decline_reason = body.answer, moment, reason or None
    if body.answer == "declined" and a.stage not in ("hired", "rejected"):
        rsvc.log(db, a, None, "rejected", frm=a.stage, to="rejected", note=f"Nomzod offerni rad etdi: {reason}")
        a.stage, a.reject_reason, a.reject_code, a.stage_changed_at = "rejected", f"Offer rad etildi: {reason}"[:300], "declined", moment
    else:
        rsvc.log(db, a, None, "comment", note="Nomzod offerni qabul qildi", data={"offer_response": "accepted"})
    targets = list(dict.fromkeys([u for u in (a.recruiter_id, a.offer_by, a.offer_decided_by) if u]))
    notes = await notify(db, targets, "recruit.offer_response", params={"candidate": c.full_name if c else "", "answer": "qabul qildi" if body.answer == "accepted" else f"rad etdi ({reason})"}, link=f"/recruit/applications/{a.id}")
    await db.commit()
    await deliver(request.app, notes)
    return _public_offer(a, v)

