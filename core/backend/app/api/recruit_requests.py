"""Rekruting: bo'lim zayafkalari (bo'lim boshlig'i -> HR tasdig'i -> vakansiya), vakansiya paneli (nomzodlar, kunlik
qo'ng'iroqlar, saralash) va 2-10 nomzodni yonma-yon solishtirish."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.org import Branch, Department, Position
from app.models.recruit import (
    Application,
    Candidate,
    CandidateFile,
    HireRequest,
    PositionRequirement,
    RecruitCall,
    SourceLink,
    Vacancy,
)
from app.rbac import matches
from app.services import growth
from app.services import recruit_sources as src
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify, register_template
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/recruit", tags=["recruit"])

register_template("recruit.request_new", {"uz": "Yangi zayafka", "ru": "Новая заявка"}, {"uz": "{number}: {position} × {count} ({unit})", "ru": "{number}: {position} × {count} ({unit})"}, "info")
register_template("recruit.request_approved", {"uz": "Zayafka tasdiqlandi", "ru": "Заявка одобрена"}, {"uz": "{number}: vakansiya ochildi — {position}", "ru": "{number}: вакансия открыта — {position}"}, "success")
register_template("recruit.request_rejected", {"uz": "Zayafka rad etildi", "ru": "Заявка отклонена"}, {"uz": "{number}: {note}", "ru": "{number}: {note}"}, "danger")

STAGES = ("new", "screening", "interview", "offer", "hired", "rejected")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def can_manage(auth: AuthContext) -> bool:
    return has(auth, "recruit.manage")


def sees_all_units(auth: AuthContext) -> bool:
    """HR (HRD, HR menejer), rekruter, direktor va o'rinbosarlari: hamma bo'lim/filial uchun zayavka ocha oladi."""
    return any(has(auth, x) for x in ("recruit.manage", "recruit.approve", "recruit.read", "org.manage"))


def can_decide(auth: AuthContext) -> bool:
    return has(auth, "recruit.manage") or has(auth, "recruit.approve")


async def _my_units(db: AsyncSession, auth: AuthContext) -> tuple[list[Department], list[Branch]]:
    """Zayafka bera oladigan bo'limlar (boshlig'i) va filiallar (mudiri/koordinatori). HR hammasiga."""
    if sees_all_units(auth):
        return list((await db.scalars(select(Department).order_by(Department.name))).all()), list((await db.scalars(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.number, Branch.name))).all())
    uid = auth.user.id
    deps = list((await db.scalars(select(Department).where(Department.head_user_id == uid).order_by(Department.name))).all())
    brs = list((await db.scalars(select(Branch).where(Branch.is_active.is_(True), or_(Branch.manager_user_id == uid, Branch.coordinator_user_id == uid)).order_by(Branch.name))).all())
    return deps, brs


async def _number(db: AsyncSession, moment: datetime) -> str:
    n = await db.scalar(text("SELECT nextval('hire_request_no_seq')"))
    return f"ZY-{local_date(moment).year}-{int(n):04d}"


async def _out(db: AsyncSession, r: HireRequest, auth: AuthContext) -> dict[str, Any]:
    dep = await db.get(Department, r.department_id) if r.department_id else None
    br = await db.get(Branch, r.branch_id) if r.branch_id else None
    pos = await db.get(Position, r.position_id) if r.position_id else None
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_([x for x in (r.created_by, r.decided_by) if x])))).all()} if (r.created_by or r.decided_by) else {}
    return {
        "id": r.id, "number": r.number, "department": {"id": dep.id, "name": dep.name} if dep else None, "branch": {"id": br.id, "name": br.name} if br else None,
        "position": {"id": pos.id, "name": pos.name} if pos else None, "count": r.count, "urgency": r.urgency, "needed_from": r.needed_from, "reason": r.reason,
        "requirements": r.requirements, "salary_from": r.salary_from, "salary_to": r.salary_to, "status": r.status, "created_at": r.created_at,
        "created_by": names.get(r.created_by or 0), "decided_by": names.get(r.decided_by or 0), "decided_at": r.decided_at, "decision_note": r.decision_note,
        "vacancy_id": r.vacancy_id, "can": {"decide": r.status == "pending" and can_decide(auth), "cancel": r.status == "pending" and (r.created_by == auth.user.id or can_manage(auth))},
    }  # fmt: skip


@router.get("/requests/meta")
async def requests_meta(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Forma uchun: foydalanuvchi zayafka bera oladigan bo'lim/filiallar va lavozimlar."""
    from app.models.competency import PositionProfile

    deps, brs = await _my_units(db, auth)
    positions = (await db.scalars(select(Position).where(Position.is_active.is_(True)).order_by(Position.name))).all()
    # har lavozimning profil holati: tasdiqlangan versiya bo'lsa "approved", aks holda oxirgi versiya holati, umuman yo'q bo'lsa "none"
    prof: dict[int, dict[str, Any]] = {}
    for pr in (await db.scalars(select(PositionProfile).where(PositionProfile.status != "archived").order_by(PositionProfile.position_id, PositionProfile.version))).all():
        cur = prof.get(pr.position_id)
        if cur is None or cur["status"] != "approved" or pr.status == "approved":
            prof[pr.position_id] = {"status": pr.status, "version": pr.version, "id": pr.id}
    scope = "all" if sees_all_units(auth) else "own"
    return {
        "departments": [{"id": d.id, "name": d.name} for d in deps], "branches": [{"id": b.id, "name": b.name} for b in brs],
        "positions": [{"id": p.id, "name": p.name, "department_id": p.department_id, "profile": prof.get(p.id) or {"status": "none", "version": None, "id": None}} for p in positions],
        "can_request": bool(deps or brs), "can_decide": can_decide(auth), "scope": scope, "can_create_position": has(auth, "org.manage"),
    }  # fmt: skip


@router.get("/requests/requirements/{position_id}")
async def requirements_for(position_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(get_auth)):
    """Lavozim kompetensiya kartochkasidan zayafka talablarini avto-to'ldirish."""
    req = await db.scalar(select(PositionRequirement).where(PositionRequirement.position_id == position_id))
    return {"requirements": req.requirements if req else None, "card": bool(req)}


class RequestIn(BaseModel):
    department_id: int | None = None
    branch_id: int | None = None
    position_id: int
    count: int = Field(default=1, ge=1, le=100)
    urgency: str = Field(default="normal", pattern="^(low|normal|urgent)$")
    needed_from: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    requirements: str | None = Field(default=None, max_length=10000)
    salary_from: int | None = Field(default=None, ge=0, le=1_000_000_000)
    salary_to: int | None = Field(default=None, ge=0, le=1_000_000_000)


@router.post("/requests", status_code=201)
async def create_request(body: RequestIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if bool(body.department_id) == bool(body.branch_id):
        raise error(400, "unit_required")
    deps, brs = await _my_units(db, auth)
    if body.department_id and body.department_id not in {d.id for d in deps}:
        raise error(403, "forbidden")
    if body.branch_id and body.branch_id not in {b.id for b in brs}:
        raise error(403, "forbidden")
    pos = await db.get(Position, body.position_id)
    if not pos or not pos.is_active:
        raise error(400, "unknown_position")
    if body.department_id and pos.department_id not in (None, body.department_id):
        raise error(400, "position_department_mismatch")
    if body.salary_from is not None and body.salary_to is not None and body.salary_from > body.salary_to:
        raise error(400, "salary_range_invalid")
    from app.models.competency import PositionProfile
    from app.services.company import get_setting

    profile = await db.scalar(select(PositionProfile).where(PositionProfile.position_id == pos.id, PositionProfile.status == "approved").order_by(PositionProfile.version.desc()).limit(1))
    if profile is None and await get_setting(db, "recruit.require_profile"):
        raise error(400, "profile_not_approved")
    reqs = (body.requirements or "").strip() or None
    if reqs is None:
        card = await db.scalar(select(PositionRequirement).where(PositionRequirement.position_id == pos.id))
        reqs = card.requirements if card else None
    moment = now()
    r = HireRequest(
        number=await _number(db, moment), department_id=body.department_id, branch_id=body.branch_id, position_id=pos.id, count=body.count, urgency=body.urgency,
        needed_from=body.needed_from, reason=(body.reason or "").strip() or None, requirements=reqs, salary_from=body.salary_from, salary_to=body.salary_to,
        status="pending", created_by=auth.user.id, profile_id=profile.id if profile else None,
    )  # fmt: skip
    db.add(r)
    await db.flush()
    unit = next((d.name for d in deps if d.id == body.department_id), None) or next((b.name for b in brs if b.id == body.branch_id), "—")
    targets = set(await users_with_permission(db, "recruit.manage")) | set(await users_with_permission(db, "recruit.approve"))
    notes = await notify(db, [u for u in targets if u != auth.user.id], "recruit.request_new", link=f"/recruit/requests/{r.id}", params={"number": r.number, "position": pos.name, "count": r.count, "unit": unit})
    await audit(db, request, "recruit.request_create", actor=auth.user, entity="hire_request", entity_id=r.id, data={"position": pos.name, "count": r.count})
    await db.commit()
    await deliver(request.app, notes)
    return await _out(db, r, auth)


@router.get("/requests")
async def list_requests(status: str | None = Query(default=None, pattern="^(pending|approved|rejected|cancelled)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    stmt = select(HireRequest).order_by(HireRequest.id.desc()).limit(300)
    if status:
        stmt = stmt.where(HireRequest.status == status)
    if not (can_manage(auth) or can_decide(auth) or has(auth, "recruit.read")):
        stmt = stmt.where(HireRequest.created_by == auth.user.id)
    return {"items": [await _out(db, r, auth) for r in (await db.scalars(stmt)).all()]}


async def _request(db: AsyncSession, rid: int, auth: AuthContext, *, lock: bool = False) -> HireRequest:
    stmt = select(HireRequest).where(HireRequest.id == rid)
    r = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not r or not (r.created_by == auth.user.id or can_manage(auth) or can_decide(auth) or has(auth, "recruit.read")):
        raise error(404, "not_found")
    return r


@router.get("/requests/{rid}")
async def get_request(rid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    return await _out(db, await _request(db, rid, auth), auth)


class DecideIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)
    recruiter_id: int | None = None


@router.post("/requests/{rid}/decide")
async def decide(rid: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """HR: tasdiqlash (vakansiya avtomatik ochiladi, talablar zayafkadan) yoki rad etish (sabab bilan)."""
    r = await _request(db, rid, auth, lock=True)
    if not can_decide(auth):
        raise error(403, "forbidden")
    if r.status != "pending":
        raise error(409, "already_decided")
    note = (body.note or "").strip() or None
    if body.action == "reject" and not note:
        raise error(400, "note_required")
    if body.action == "approve" and body.recruiter_id is not None:
        recruiters = set(await users_with_permission(db, "recruit.manage"))
        active = await db.scalar(select(User.id).where(User.id == body.recruiter_id, User.is_active.is_(True)))
        if body.recruiter_id not in recruiters or active is None:
            raise error(400, "unknown_recruiter")
    moment = now()
    pos = await db.get(Position, r.position_id)
    r.decided_by, r.decided_at, r.decision_note = auth.user.id, moment, note
    notes: list = []
    post: tuple[int, str] | None = None
    if body.action == "approve":
        dep = await db.get(Department, r.department_id) if r.department_id else None
        br = await db.get(Branch, r.branch_id) if r.branch_id else None
        sla = (await growth.get_setting(db, "recruit"))["sla_days"]
        v = Vacancy(
            title=f"{pos.name if pos else 'Xodim'} — {(dep.name if dep else None) or (br.name if br else '')}".rstrip(" —"), department_id=r.department_id, branch_id=r.branch_id,
            position_id=r.position_id, requirements=r.requirements, salary_from=r.salary_from, salary_to=r.salary_to, openings=r.count, status="open",
            recruiter_id=body.recruiter_id, deadline=r.needed_from or (local_date(moment) + timedelta(days=sla)), opened_at=moment, created_by=auth.user.id,
            description=r.reason,
        )  # fmt: skip
        db.add(v)
        await db.flush()
        r.status, r.vacancy_id = "approved", v.id
        # Avtomatik nomzod havolalari (Telegram + sayt) va kanal sozlangan bo'lsa e'lon
        post = await src.auto_publish(db, v, br, body.recruiter_id or auth.user.id, auth.user.id)
        notes += await notify(db, [r.created_by] if r.created_by else [], "recruit.request_approved", link=f"/recruit/requests/{r.id}", params={"number": r.number, "position": pos.name if pos else ""})
        targets = [body.recruiter_id] if body.recruiter_id else await users_with_permission(db, "recruit.manage")
        notes += await notify(db, [t for t in targets if t and t != auth.user.id], "need.vacancy", params={"title": v.title}, link=f"/recruit/vacancies/{v.id}/promo")
    else:
        r.status = "rejected"
        notes += await notify(db, [r.created_by] if r.created_by else [], "recruit.request_rejected", link=f"/recruit/requests/{r.id}", params={"number": r.number, "note": note or ""})
    await audit(db, request, f"recruit.request_{r.status}", actor=auth.user, entity="hire_request", entity_id=r.id, data={"vacancy_id": r.vacancy_id, "auto_post": bool(post)})
    await db.commit()
    await deliver(request.app, notes)
    await src.send_post(request.app, post)
    return await _out(db, r, auth)


@router.post("/requests/{rid}/cancel")
async def cancel(rid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    r = await _request(db, rid, auth, lock=True)
    if r.status != "pending" or not (r.created_by == auth.user.id or can_manage(auth)):
        raise error(409, "invalid_transition")
    r.status = "cancelled"
    await audit(db, request, "recruit.request_cancel", actor=auth.user, entity="hire_request", entity_id=r.id)
    await db.commit()
    return await _out(db, r, auth)


# --- Vakansiya paneli ------------------------------------------------------------------


@router.get("/vacancies/{vid}/dashboard")
async def vacancy_dashboard(vid: int, days: int = Query(default=14, ge=1, le=90), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Zayafka/vakansiya bo'yicha: nechta nomzod, bosqichlar, kunlik kiruvchi/chiquvchi qo'ng'iroqlar, telefon suhbatda
    saralangan va mos kelganlar, manba havolalari."""
    if not (has(auth, "recruit.read") or can_manage(auth)):
        raise error(403, "forbidden")
    v = await db.get(Vacancy, vid)
    if not v:
        raise error(404, "not_found")
    stages = dict((await db.execute(select(Application.stage, func.count()).where(Application.vacancy_id == v.id).group_by(Application.stage))).all())
    today = local_date(now())
    start = today - timedelta(days=days - 1)
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    calls = (await db.scalars(select(RecruitCall).where(RecruitCall.vacancy_id == v.id, RecruitCall.called_at >= s_dt))).all()
    per_day = {start + timedelta(days=i): {"in": 0, "out": 0, "screened": 0, "suitable": 0} for i in range(days)}
    for c in calls:
        d = local_date(c.called_at)
        if d in per_day:
            per_day[d][c.direction or "out"] += 1
            if c.outcome in ("suitable", "unsuitable"):
                per_day[d]["screened"] += 1
            if c.outcome == "suitable":
                per_day[d]["suitable"] += 1
    all_calls = (await db.execute(select(RecruitCall.direction, RecruitCall.outcome, func.count()).where(RecruitCall.vacancy_id == v.id).group_by(RecruitCall.direction, RecruitCall.outcome))).all()
    tot = {"in": 0, "out": 0, "screened": 0, "suitable": 0, "no_answer": 0}
    for direction, outcome, n in all_calls:
        tot[direction or "out"] += n
        if outcome in ("suitable", "unsuitable"):
            tot["screened"] += n
        if outcome == "suitable":
            tot["suitable"] += n
        if outcome == "no_answer":
            tot["no_answer"] += n
    links = (await db.scalars(select(SourceLink).where(SourceLink.vacancy_id == v.id, SourceLink.is_active.is_(True)))).all()
    from app.services.recruit_sources import apply_url  # noqa: PLC0415

    total = sum(stages.values())
    return {
        "vacancy": {"id": v.id, "title": v.title, "status": v.status, "openings": v.openings, "deadline": v.deadline, "opened_at": v.opened_at},
        "applications": total, "stages": {k: stages.get(k, 0) for k in STAGES}, "calls": tot,
        "days": [{"date": d, **x} for d, x in per_day.items()],
        "links": [{"id": lk.id, "code": lk.code, "url": apply_url(lk.code), "label": lk.label, "channel": lk.channel, "clicks": lk.clicks} for lk in links],
        "request": await _request_for_vacancy(db, v.id),
    }  # fmt: skip


async def _request_for_vacancy(db: AsyncSession, vid: int) -> dict[str, Any] | None:
    r = await db.scalar(select(HireRequest).where(HireRequest.vacancy_id == vid))
    return {"id": r.id, "number": r.number} if r else None


# --- Nomzodlarni solishtirish ----------------------------------------------------------


@router.get("/compare")
async def compare(ids: str = Query(min_length=1, max_length=200), vacancy_id: int | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """2-10 nomzodni yonma-yon: anketa, tajriba, ko'nikmalar, moslik bali, suhbat (hard/soft), test, fon tekshiruvi, bosqich, rezyume fayllari."""
    if not (has(auth, "recruit.read") or can_manage(auth)):
        raise error(403, "forbidden")
    try:
        cids = list(dict.fromkeys(int(x) for x in ids.split(",") if x.strip()))
    except ValueError:
        raise error(400, "ids_invalid") from None
    if not 2 <= len(cids) <= 10:
        raise error(400, "compare_count", min=2, max=10)
    from app.models.recruit import CandidateTest  # noqa: PLC0415

    out = []
    for cid in cids:
        c = await db.get(Candidate, cid)
        if not c:
            continue
        stmt = select(Application).where(Application.candidate_id == c.id).order_by(Application.id.desc())
        if vacancy_id:
            stmt = stmt.where(Application.vacancy_id == vacancy_id)
        a = await db.scalar(stmt.limit(1))
        tests = (await db.scalars(select(CandidateTest).where(CandidateTest.application_id == a.id))).all() if a else []
        files = (await db.scalars(select(CandidateFile).where(CandidateFile.candidate_id == c.id))).all()
        age = None
        if c.birth_date:
            t = local_date(now())
            age = t.year - c.birth_date.year - ((t.month, t.day) < (c.birth_date.month, c.birth_date.day))
        prof = c.profile or {}
        out.append({
            "id": c.id, "full_name": c.full_name, "phone": c.phone, "age": age, "address": c.address, "source": c.source, "skills": c.skills or [],
            "experience": prof.get("experience") or prof.get("experience_years"), "expected_salary": prof.get("expected_salary"), "languages": prof.get("languages"),
            "education": prof.get("education"), "profile_confirmed": bool(c.profile_confirmed_at), "resume_excerpt": (c.resume_text or "")[:600] or None,
            "files": [{"id": f.id, "name": f.filename} for f in files],
            "application": {
                "id": a.id, "vacancy_id": a.vacancy_id, "stage": a.stage, "rating": a.rating, "match_score": a.match_score, "experience_level": a.experience_level,
                "hard_skill": a.hard_skill, "soft_skill": a.soft_skill, "bg_status": a.bg_status, "interview_at": a.interview_at, "offer_status": a.offer_status,
                "ai": (a.ai_scan or {}).get("summary") if a.ai_scan else None,
            } if a else None,
            "tests": [{"score": x.score_pct, "status": x.status} for x in tests],
        })  # fmt: skip
    return {"items": out}


# --- Ochiq vakansiyalar (veb-sayt) ------------------------------------------------------

public_router = APIRouter(prefix="/v1/public", tags=["public"])


@public_router.get("/jobs")
async def public_jobs(db: AsyncSession = Depends(get_session)):
    """Saytdagi ochiq vakansiyalar: har biri "site" havolasi orqali ariza qabul qiladi (manba hisobi uchun)."""
    rows = (await db.execute(
        select(Vacancy, SourceLink.code, Branch.name)
        .join(SourceLink, (SourceLink.vacancy_id == Vacancy.id) & (SourceLink.channel == "site") & SourceLink.is_active.is_(True))
        .outerjoin(Branch, Branch.id == Vacancy.branch_id)
        .where(Vacancy.status == "open").order_by(Vacancy.opened_at.desc().nullslast(), Vacancy.id.desc()).limit(200)
    )).all()  # fmt: skip
    seen: set[int] = set()
    items = []
    for v, code, branch in rows:
        if v.id in seen:
            continue
        seen.add(v.id)
        items.append({"id": v.id, "title": v.title, "branch": branch, "salary_from": v.salary_from, "salary_to": v.salary_to, "requirements": (v.requirements or "")[:600] or None, "code": code, "opened_at": v.opened_at})
    return {"items": items}


# --- Rekruter kunlik nazorati -------------------------------------------------------------


@router.get("/daily")
async def daily(
    start: date = Query(), end: date = Query(), recruiter_id: int | None = None, vacancy_id: int | None = None,
    db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth),
):  # fmt: skip
    """Kunma-kun: nechta rezyume keldi (havola/bot orqali), nechtasi qo'lda biriktirildi, nechta qo'ng'iroq,
    nechtasi suhbatga chaqirildi va nechtasi keldi; qaysi e'lon (manba) orqali kelgani."""
    if not (has(auth, "recruit.read") or can_manage(auth)):
        raise error(403, "forbidden")
    if end < start or (end - start).days > 92:
        raise error(400, "range_invalid")
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz())
    days = {start + timedelta(days=i): {"received": 0, "attached": 0, "calls": 0, "invited": 0, "came": 0, "hired": 0} for i in range((end - start).days + 1)}
    by_source: dict[str, int] = {}
    stmt = select(Application, SourceLink.channel, SourceLink.label).outerjoin(SourceLink, SourceLink.id == Application.source_link_id).where(Application.applied_at >= s_dt, Application.applied_at < e_dt)
    if recruiter_id:
        stmt = stmt.where(Application.recruiter_id == recruiter_id)
    if vacancy_id:
        stmt = stmt.where(Application.vacancy_id == vacancy_id)
    for a, channel, label in (await db.execute(stmt)).all():
        d = local_date(a.applied_at)
        if d not in days:
            continue
        if a.source_link_id:
            days[d]["received"] += 1
            key = label or channel or "link"
        else:
            days[d]["attached"] += 1
            key = "qo'lda"
        by_source[key] = by_source.get(key, 0) + 1
    cstmt = select(RecruitCall.called_at).where(RecruitCall.called_at >= s_dt, RecruitCall.called_at < e_dt)
    if recruiter_id:
        cstmt = cstmt.where(RecruitCall.recruiter_id == recruiter_id)
    if vacancy_id:
        cstmt = cstmt.where(RecruitCall.vacancy_id == vacancy_id)
    for (at,) in (await db.execute(cstmt)).all():
        d = local_date(at)
        if d in days:
            days[d]["calls"] += 1
    istmt = select(Application.interview_at, Application.stage, Application.hired_at).where(
        or_(Application.interview_at.between(s_dt, e_dt), Application.hired_at.between(s_dt, e_dt))
    )  # fmt: skip
    if recruiter_id:
        istmt = istmt.where(Application.recruiter_id == recruiter_id)
    if vacancy_id:
        istmt = istmt.where(Application.vacancy_id == vacancy_id)
    for at, stage, hired_at in (await db.execute(istmt)).all():
        if at and s_dt <= at < e_dt and local_date(at) in days:
            d = local_date(at)
            days[d]["invited"] += 1
            if stage in ("interview", "offer", "hired") or hired_at:
                days[d]["came"] += 1  # suhbat bosqichidan o'tgan yoki undan ilgarilagan = kelgan
        if hired_at and s_dt <= hired_at < e_dt and local_date(hired_at) in days:
            days[local_date(hired_at)]["hired"] += 1
    rows = [{"date": d, **x} for d, x in days.items()]
    total = {k: sum(r[k] for r in rows) for k in ("received", "attached", "calls", "invited", "came", "hired")}
    recruiters = (await db.execute(select(User.id, User.full_name).where(User.id.in_(select(Application.recruiter_id).where(Application.recruiter_id.is_not(None)).distinct())))).all()
    return {"days": rows, "total": total, "by_source": sorted(({"source": k, "count": n} for k, n in by_source.items()), key=lambda x: -x["count"]), "recruiters": [{"id": i, "name": n} for i, n in recruiters]}
