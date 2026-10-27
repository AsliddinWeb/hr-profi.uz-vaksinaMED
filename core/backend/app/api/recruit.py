"""Nomzodlar va ish o'rinlari: vakansiyalar, nomzodlar, arizalar (pipeline), xodimga aylantirish, tahlil."""

from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.employees import _snapshot
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.internship import HireDocs
from app.models.org import Branch
from app.models.recruit import Application, ApplicationEvent, Candidate, CandidateFile, Vacancy
from app.rbac import matches
from app.services import employees as emp_svc
from app.services import onboarding as _onboarding  # noqa: F401  (xabar shablonlarini ro'yxatdan o'tkazadi)
from app.services import recruit as svc
from app.services import recruit_pipeline as psvc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/recruit", tags=["recruit"])
MAX_FILES = 10


def require(perm: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not svc.has(auth, perm):
            raise error(403, "forbidden")
        return auth

    return dep


Read = require("recruit.read")
Manage = require("recruit.manage")


def _phone(raw: str | None) -> str | None:
    try:
        return emp_svc.normalize_phone(raw)
    except ValueError:
        raise error(400, "phone_invalid") from None


def _email(raw: str | None) -> str | None:
    try:
        return emp_svc.normalize_email(raw)
    except ValueError:
        raise error(400, "email_invalid") from None


async def _lookups(db: AsyncSession) -> dict[str, dict[int, str]]:
    from app.models.org import Department, Position

    return {
        "branch": {b.id: b.name for b in (await db.scalars(select(Branch))).all()},
        "department": {d.id: d.name for d in (await db.scalars(select(Department))).all()},
        "position": {p.id: p.name for p in (await db.scalars(select(Position))).all()},
    }


async def _check_refs(db: AsyncSession, branch_id, department_id, position_id, recruiter_id=None) -> None:
    try:
        await emp_svc.validate_assignment(db, department_id, position_id, branch_id)
    except Exception as exc:  # noqa: BLE001
        raise error(400, "unknown_reference") from exc
    if recruiter_id is not None and recruiter_id not in set(await users_with_permission(db, "recruit.manage")):
        raise error(400, "unknown_recruiter")


# --- Yordamchi ----------------------------------------------------------------------------


@router.get("/recruiters")
async def recruiters(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    ids = await users_with_permission(db, "recruit.manage")
    if not ids:
        return []
    rows = (await db.execute(select(User.id, User.full_name).where(User.is_active.is_(True), User.id.in_(ids)).order_by(User.full_name))).all()
    return [{"id": r.id, "name": r.full_name} for r in rows]


# --- Vakansiyalar -------------------------------------------------------------------------


class VacancyIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    branch_id: int | None = None
    department_id: int | None = None
    position_id: int | None = None
    description: str | None = Field(default=None, max_length=10000)
    requirements: str | None = Field(default=None, max_length=10000)
    salary_from: int | None = Field(default=None, ge=0, le=1_000_000_000)
    salary_to: int | None = Field(default=None, ge=0, le=1_000_000_000)
    openings: int = Field(default=1, ge=1, le=500)
    recruiter_id: int | None = None
    deadline: date | None = None


def _vacancy_out(v: Vacancy, lk: dict, unames: dict[int, str], funnel: dict[str, int] | None = None) -> dict[str, Any]:
    hired = (funnel or {}).get("hired", 0)
    return {
        "id": v.id, "title": v.title, "status": v.status, "openings": v.openings, "hired": hired, "filled": hired >= v.openings,
        "branch": {"id": v.branch_id, "name": lk["branch"].get(v.branch_id or 0)} if v.branch_id else None,
        "department": {"id": v.department_id, "name": lk["department"].get(v.department_id or 0)} if v.department_id else None,
        "position": {"id": v.position_id, "name": lk["position"].get(v.position_id or 0)} if v.position_id else None,
        "description": v.description, "requirements": v.requirements, "salary_from": v.salary_from, "salary_to": v.salary_to, "deadline": v.deadline,
        "recruiter": {"id": v.recruiter_id, "name": unames.get(v.recruiter_id or 0)} if v.recruiter_id else None,
        "opened_at": v.opened_at, "closed_at": v.closed_at, "created_at": v.created_at, "funnel": funnel,
    }  # fmt: skip


def _salary_ok(b: VacancyIn) -> None:
    if b.salary_from is not None and b.salary_to is not None and b.salary_to < b.salary_from:
        raise error(400, "salary_range_invalid")


@router.get("/vacancies")
async def vacancies(
    status: str | None = Query(default=None, pattern="^(draft|open|paused|closed|active)$"),
    q: str | None = None,
    recruiter_id: int | None = None,
    branch_id: int | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Read),
):
    V = Vacancy
    conds: list = []
    if status == "active":
        conds.append(V.status.in_(("open", "paused")))
    elif status:
        conds.append(V.status == status)
    if q and q.strip():
        conds.append(V.title.ilike(f"%{q.strip()}%"))
    if recruiter_id:
        conds.append(V.recruiter_id == recruiter_id)
    if branch_id:
        conds.append(V.branch_id == branch_id)
    total = await db.scalar(select(func.count()).select_from(V).where(*conds)) or 0
    rows = (await db.scalars(select(V).where(*conds).order_by(V.created_at.desc(), V.id.desc()).offset((page - 1) * size).limit(size))).all()
    ids = [v.id for v in rows]
    counts: dict[int, dict[str, int]] = {i: {s: 0 for s in svc.STAGES} for i in ids}
    if ids:
        for vid, st, n in (await db.execute(select(Application.vacancy_id, Application.stage, func.count()).where(Application.vacancy_id.in_(ids)).group_by(Application.vacancy_id, Application.stage))).all():
            counts[vid][st] = n
    lk, un = await _lookups(db), await svc.names(db, {v.recruiter_id for v in rows})
    return {"total": total, "page": page, "size": size, "items": [_vacancy_out(v, lk, un, counts[v.id]) for v in rows]}


@router.post("/vacancies", status_code=201)
async def create_vacancy(body: VacancyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    _salary_ok(body)
    await _check_refs(db, body.branch_id, body.department_id, body.position_id, body.recruiter_id)
    v = Vacancy(**{**body.model_dump(), "title": body.title.strip()}, status="draft", created_by=auth.user.id)
    db.add(v)
    await db.flush()
    await audit(db, request, "recruit.vacancy_create", actor=auth.user, entity="vacancy", entity_id=v.id, data={"title": v.title})
    await db.commit()
    return await _vacancy_detail(db, v)


async def _vacancy(db: AsyncSession, vid: int, *, lock: bool = False) -> Vacancy:
    stmt = select(Vacancy).where(Vacancy.id == vid)
    v = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not v:
        raise error(404, "not_found")
    return v


async def _vacancy_detail(db: AsyncSession, v: Vacancy) -> dict[str, Any]:
    return _vacancy_out(v, await _lookups(db), await svc.names(db, {v.recruiter_id}), await svc.funnel(db, v.id))


@router.get("/vacancies/{vid}")
async def vacancy(vid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    return await _vacancy_detail(db, await _vacancy(db, vid))


@router.put("/vacancies/{vid}")
async def update_vacancy(vid: int, body: VacancyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    v = await _vacancy(db, vid, lock=True)
    _salary_ok(body)
    await _check_refs(db, body.branch_id, body.department_id, body.position_id, body.recruiter_id)
    notes = []
    if body.recruiter_id and body.recruiter_id != v.recruiter_id and body.recruiter_id != auth.user.id:
        notes = await notify(db, [body.recruiter_id], "recruit.assigned", link=f"/recruit/vacancies/{v.id}", params={"vacancy": body.title})
    for k, val in {**body.model_dump(), "title": body.title.strip()}.items():
        setattr(v, k, val)
    await audit(db, request, "recruit.vacancy_update", actor=auth.user, entity="vacancy", entity_id=v.id, data={"title": v.title})
    await db.commit()
    await deliver(request.app, notes)
    return await _vacancy_detail(db, v)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(open|paused|closed)$")


@router.post("/vacancies/{vid}/status")
async def vacancy_status(vid: int, body: StatusIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    v = await _vacancy(db, vid, lock=True)
    if v.status == body.status:
        raise error(409, "invalid_transition")
    moment = now()
    if body.status == "open":
        v.opened_at = v.opened_at or moment
        v.closed_at = None
    elif body.status == "closed":
        v.closed_at = moment
    v.status = body.status
    await audit(db, request, "recruit.vacancy_status", actor=auth.user, entity="vacancy", entity_id=v.id, data={"status": v.status})
    await db.commit()
    return await _vacancy_detail(db, v)


@router.delete("/vacancies/{vid}", status_code=204)
async def delete_vacancy(vid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    v = await _vacancy(db, vid, lock=True)
    if await db.scalar(select(func.count()).select_from(Application).where(Application.vacancy_id == v.id)):
        raise error(409, "vacancy_in_use")
    await audit(db, request, "recruit.vacancy_delete", actor=auth.user, entity="vacancy", entity_id=v.id, data={"title": v.title})
    await db.delete(v)
    await db.commit()


# --- Nomzodlar ----------------------------------------------------------------------------


class CandidateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=250)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    address: str | None = Field(default=None, max_length=300)
    source: str | None = Field(default=None, pattern="^(walk_in|referral|telegram|olx|hh|social|other)$")
    skills: list[str] = Field(default=[], max_length=30)
    resume_text: str | None = Field(default=None, max_length=50000)
    note: str | None = Field(default=None, max_length=5000)


class ParseIn(BaseModel):
    text: str = Field(min_length=10, max_length=50000)


@router.post("/candidates/parse")
async def parse(body: ParseIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Rezyume matnidan maydonlarni ajratib beradi (saqlamaydi). AI yoqilgan bo'lsa Claude, bo'lmasa (yoki xato bo'lsa) qoidalar asosida."""
    from app.services import ai

    rules = svc.parse_resume(body.text)
    cfg = await ai.get_cfg(db)
    if ai.feature_on(cfg, "resume") and matches(auth.permissions, "ai.use"):
        try:
            found = {**rules, **await ai.parse_resume(db, auth, body.text)}  # AI qoidalardagi bo'sh joylarni to'ldiradi va ustun turadi
            return {"fields": found, "engine": "ai", "found": sorted(found)}
        except HTTPException:
            pass  # limit/xato: qoidalar natijasi bilan davom etamiz
    return {"fields": rules, "engine": "rules", "found": sorted(rules)}


def _cand_values(body: CandidateIn) -> dict[str, Any]:
    return {
        "full_name": " ".join(body.full_name.split()), "phone": _phone(body.phone), "email": _email(body.email), "birth_date": body.birth_date,
        "address": (body.address or "").strip() or None, "source": body.source, "skills": list(dict.fromkeys(s.strip()[:40] for s in body.skills if s.strip())),
        "resume_text": (body.resume_text or "").strip() or None, "note": (body.note or "").strip() or None,
    }  # fmt: skip


@router.get("/candidates")
async def candidates(
    q: str | None = None,
    source: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Read),
):
    C = Candidate
    conds: list = []
    if q and q.strip():
        like = f"%{q.strip()}%"
        digits = "".join(ch for ch in q if ch.isdigit())
        conds.append(or_(C.full_name.ilike(like), C.phone.ilike(f"%{digits}%") if len(digits) >= 3 else C.full_name.ilike(like), C.email.ilike(like)))
    if source:
        conds.append(C.source == source)
    total = await db.scalar(select(func.count()).select_from(C).where(*conds)) or 0
    rows = (await db.scalars(select(C).where(*conds).order_by(C.created_at.desc(), C.id.desc()).offset((page - 1) * size).limit(size))).all()
    apps = dict((await db.execute(select(Application.candidate_id, func.count()).where(Application.candidate_id.in_([c.id for c in rows])).group_by(Application.candidate_id))).all()) if rows else {}
    return {"total": total, "page": page, "size": size, "items": [{**svc.candidate_out(c), "applications": apps.get(c.id, 0), "created_at": c.created_at} for c in rows]}


@router.post("/candidates", status_code=201)
async def create_candidate(body: CandidateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    vals = _cand_values(body)
    if vals["phone"]:
        existing = await db.scalar(select(Candidate.id).where(Candidate.phone == vals["phone"]))
        if existing:
            raise error(409, "candidate_exists", id=existing)
    c = Candidate(**vals, created_by=auth.user.id)
    db.add(c)
    await db.flush()
    await audit(db, request, "recruit.candidate_create", actor=auth.user, entity="candidate", entity_id=c.id, data={"name": c.full_name})
    await db.commit()
    return await _candidate_detail(db, c)


async def _candidate(db: AsyncSession, cid: int) -> Candidate:
    c = await db.get(Candidate, cid)
    if not c:
        raise error(404, "not_found")
    return c


async def _candidate_detail(db: AsyncSession, c: Candidate) -> dict[str, Any]:
    apps = (await db.scalars(select(Application).where(Application.candidate_id == c.id).order_by(Application.applied_at.desc()))).all()
    titles = {v.id: v.title for v in (await db.scalars(select(Vacancy).where(Vacancy.id.in_([a.vacancy_id for a in apps])))).all()} if apps else {}
    files = (await db.scalars(select(CandidateFile).where(CandidateFile.candidate_id == c.id).order_by(CandidateFile.id))).all()
    return {
        **svc.candidate_out(c), "resume_text": c.resume_text, "created_at": c.created_at,
        "applications": [{"id": a.id, "vacancy": {"id": a.vacancy_id, "title": titles.get(a.vacancy_id)}, "stage": a.stage, "applied_at": a.applied_at} for a in apps],
        "files": [{"id": f.id, "filename": f.filename, "mime": f.mime, "size": f.size, "created_at": f.created_at} for f in files],
    }  # fmt: skip


@router.get("/candidates/{cid}")
async def candidate(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    return await _candidate_detail(db, await _candidate(db, cid))


@router.put("/candidates/{cid}")
async def update_candidate(cid: int, body: CandidateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    c = await _candidate(db, cid)
    vals = _cand_values(body)
    if vals["phone"]:
        other = await db.scalar(select(Candidate.id).where(Candidate.phone == vals["phone"], Candidate.id != c.id))
        if other:
            raise error(409, "candidate_exists", id=other)
    for k, v in vals.items():
        setattr(c, k, v)
    await audit(db, request, "recruit.candidate_update", actor=auth.user, entity="candidate", entity_id=c.id, data={"name": c.full_name})
    await db.commit()
    return await _candidate_detail(db, c)


@router.delete("/candidates/{cid}", status_code=204)
async def delete_candidate(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    c = await _candidate(db, cid)
    if await db.scalar(select(func.count()).select_from(Application).where(Application.candidate_id == c.id)):
        raise error(409, "candidate_in_use")
    keys = [f.key for f in (await db.scalars(select(CandidateFile).where(CandidateFile.candidate_id == c.id))).all()]
    await audit(db, request, "recruit.candidate_delete", actor=auth.user, entity="candidate", entity_id=c.id, data={"name": c.full_name})
    await db.delete(c)
    await db.commit()
    for k in keys:
        await request.app.state.storage.delete(k)


@router.post("/candidates/{cid}/files", status_code=201)
async def upload_file(cid: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    c = await _candidate(db, cid)
    if (await db.scalar(select(func.count()).select_from(CandidateFile).where(CandidateFile.candidate_id == c.id)) or 0) >= MAX_FILES:
        raise error(409, "too_many_files", max=MAX_FILES)
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"recruit/{c.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    f = CandidateFile(candidate_id=c.id, uploaded_by=auth.user.id, key=key, filename=up.filename, mime=up.mime, size=len(up.data))
    db.add(f)
    await db.flush()
    out = {"id": f.id, "filename": f.filename, "mime": f.mime, "size": f.size, "created_at": f.created_at}
    await db.commit()
    return out


async def _file(db: AsyncSession, cid: int, fid: int) -> CandidateFile:
    f = await db.get(CandidateFile, fid)
    if not f or f.candidate_id != cid:
        raise error(404, "not_found")
    return f


@router.get("/candidates/{cid}/files/{fid}")
async def download_file(cid: int, fid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    f = await _file(db, cid, fid)
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.filename)}"}
    return StreamingResponse(request.app.state.storage.stream(f.key), media_type=f.mime, headers=headers)


@router.delete("/candidates/{cid}/files/{fid}", status_code=204)
async def delete_file(cid: int, fid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    f = await _file(db, cid, fid)
    key = f.key
    await db.delete(f)
    await db.commit()
    await request.app.state.storage.delete(key)


# --- Arizalar (pipeline) ------------------------------------------------------------------


def _app_out(a: Application, cands: dict[int, Candidate], vac: dict[int, Vacancy], unames: dict[int, str]) -> dict[str, Any]:
    c, v = cands.get(a.candidate_id), vac.get(a.vacancy_id)
    return {
        "id": a.id, "stage": a.stage, "rating": a.rating, "reject_reason": a.reject_reason, "interview_at": a.interview_at, "applied_at": a.applied_at, "stage_changed_at": a.stage_changed_at,
        "candidate": {"id": a.candidate_id, "full_name": c.full_name if c else None, "phone": c.phone if c else None, "source": c.source if c else None, "skills": (c.skills if c else []) or []},
        "vacancy": {"id": a.vacancy_id, "title": v.title if v else None},
        "recruiter": {"id": a.recruiter_id, "name": unames.get(a.recruiter_id or 0)} if a.recruiter_id else None,
        "employee_id": a.employee_id, "hired_at": a.hired_at,
        "experience_level": a.experience_level, "stages_unlocked": psvc.STAGES_BY_LEVEL.get(a.experience_level or "", []), "hard_skill": a.hard_skill, "soft_skill": a.soft_skill,
        "interview_notes": a.interview_notes, "interviewed_at": a.interviewed_at, "bg_status": a.bg_status, "bg_note": a.bg_note, "ai_scan": a.ai_scan, "ai_scan_at": a.ai_scan_at,
        "offer": {"status": a.offer_status, "level": a.offer_level, "salary": a.offer_salary, "start": a.offer_start, "note": a.offer_note, "decision_note": a.offer_decision_note, "sent_at": a.offer_sent_at} if a.offer_status else None,
        "has_telegram": bool(c and c.telegram_chat_id),
    }  # fmt: skip


async def _out_many(db: AsyncSession, rows: list[Application]) -> list[dict[str, Any]]:
    if not rows:
        return []
    cands = {c.id: c for c in (await db.scalars(select(Candidate).where(Candidate.id.in_({a.candidate_id for a in rows})))).all()}
    vac = {v.id: v for v in (await db.scalars(select(Vacancy).where(Vacancy.id.in_({a.vacancy_id for a in rows})))).all()}
    un = await svc.names(db, {a.recruiter_id for a in rows})
    return [_app_out(a, cands, vac, un) for a in rows]


async def _application(db: AsyncSession, aid: int, *, lock: bool = False) -> Application:
    stmt = select(Application).where(Application.id == aid)
    a = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not a:
        raise error(404, "not_found")
    return a


class ApplyIn(BaseModel):
    vacancy_id: int
    candidate_id: int
    note: str | None = Field(default=None, max_length=2000)


@router.post("/applications", status_code=201)
async def apply(body: ApplyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    v = await _vacancy(db, body.vacancy_id)
    if v.status != "open":
        raise error(409, "vacancy_not_open")
    c = await _candidate(db, body.candidate_id)
    if await db.scalar(select(Application.id).where(Application.vacancy_id == v.id, Application.candidate_id == c.id)):
        raise error(409, "already_applied")
    moment = now()
    a = Application(vacancy_id=v.id, candidate_id=c.id, stage="new", recruiter_id=v.recruiter_id or auth.user.id, applied_at=moment, stage_changed_at=moment)
    db.add(a)
    await db.flush()
    svc.log(db, a, auth.user.id, "applied", to="new", note=(body.note or "").strip() or None)
    await audit(db, request, "recruit.apply", actor=auth.user, entity="application", entity_id=a.id, data={"vacancy_id": v.id, "candidate_id": c.id})
    notes = await svc.notify_new(db, v, c, auth.user.id)
    await db.commit()
    await deliver(request.app, notes)
    return (await _out_many(db, [a]))[0]


@router.get("/applications")
async def applications(
    vacancy_id: int | None = None,
    candidate_id: int | None = None,
    stage: str | None = Query(default=None, pattern="^(new|screening|interview|offer|hired|rejected|open)$"),
    recruiter_id: int | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Read),
):
    A = Application
    conds: list = []
    if vacancy_id:
        conds.append(A.vacancy_id == vacancy_id)
    if candidate_id:
        conds.append(A.candidate_id == candidate_id)
    if stage == "open":
        conds.append(A.stage.in_(svc.OPEN_STAGES))
    elif stage:
        conds.append(A.stage == stage)
    if recruiter_id:
        conds.append(A.recruiter_id == recruiter_id)
    stmt = select(A)
    if q and q.strip():
        stmt = stmt.join(Candidate, Candidate.id == A.candidate_id)
        conds.append(Candidate.full_name.ilike(f"%{q.strip()}%"))
    total = await db.scalar(select(func.count()).select_from(stmt.where(*conds).subquery())) or 0
    rows = (await db.scalars(stmt.where(*conds).order_by(A.stage_changed_at.desc(), A.id.desc()).offset((page - 1) * size).limit(size))).all()
    return {"total": total, "page": page, "size": size, "items": await _out_many(db, list(rows))}


@router.get("/board")
async def board(vacancy_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    """Bitta vakansiya bo'yicha ustunlar (bosqichlar); har ustunda 200 tagacha ariza."""
    await _vacancy(db, vacancy_id)
    out: dict[str, Any] = {}
    for st in svc.STAGES:
        rows = (await db.scalars(select(Application).where(Application.vacancy_id == vacancy_id, Application.stage == st).order_by(Application.stage_changed_at.desc()).limit(200))).all()
        total = await db.scalar(select(func.count()).select_from(Application).where(Application.vacancy_id == vacancy_id, Application.stage == st)) or 0
        out[st] = {"total": total, "items": await _out_many(db, list(rows))}
    return out


@router.get("/applications/{aid}")
async def application(aid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    a = await _application(db, aid)
    out = (await _out_many(db, [a]))[0]
    events = (await db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == a.id).order_by(ApplicationEvent.id))).all()
    un = await svc.names(db, {e.actor_id for e in events})
    v = await _vacancy(db, a.vacancy_id)
    return {
        **out, "vacancy": {"id": v.id, "title": v.title, "status": v.status, "branch_id": v.branch_id, "department_id": v.department_id, "position_id": v.position_id},
        "can": {"approve": svc.has(auth, "recruit.approve"), "manage": svc.has(auth, "recruit.manage"), "hire": a.stage == "offer" and svc.has(auth, "recruit.manage") and svc.has(auth, "employees.create")},
        "events": [{"id": e.id, "action": e.action, "from": e.from_stage, "to": e.to_stage, "note": e.note, "data": e.data, "actor": un.get(e.actor_id or 0), "created_at": e.created_at} for e in events],
    }  # fmt: skip


class StageIn(BaseModel):
    stage: str = Field(pattern="^(new|screening|interview|offer)$")
    note: str | None = Field(default=None, max_length=2000)
    interview_at: datetime | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


@router.post("/applications/{aid}/stage")
async def set_stage(aid: int, body: StageIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid, lock=True)
    before = a.stage
    await svc.move(db, a, auth, body.stage, body.note, now(), interview_at=body.interview_at, rating=body.rating)
    await audit(db, request, "recruit.stage", actor=auth.user, entity="application", entity_id=a.id, data={"from": before, "to": a.stage})
    await db.commit()
    return (await _out_many(db, [a]))[0]


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/applications/{aid}/reject")
async def reject(aid: int, body: ReasonIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid, lock=True)
    before = a.stage
    await svc.reject(db, a, auth, body.reason, now())
    await audit(db, request, "recruit.reject", actor=auth.user, entity="application", entity_id=a.id, data={"from": before, "reason": a.reject_reason})
    await db.commit()
    return (await _out_many(db, [a]))[0]


@router.post("/applications/{aid}/reopen")
async def reopen(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid, lock=True)
    await svc.reopen(db, a, auth, now())
    await audit(db, request, "recruit.reopen", actor=auth.user, entity="application", entity_id=a.id)
    await db.commit()
    return (await _out_many(db, [a]))[0]


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


@router.post("/applications/{aid}/comments", status_code=201)
async def comment(aid: int, body: CommentIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await _application(db, aid)
    svc.log(db, a, auth.user.id, "comment", note=body.body.strip())
    await db.commit()
    return {"ok": True}


class HireIn(BaseModel):
    last_name: str | None = Field(default=None, max_length=80)
    first_name: str | None = Field(default=None, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    hire_date: date | None = None
    branch_id: int | None = None
    department_id: int | None = None
    position_id: int | None = None
    confirm_duplicate: bool = False


@router.post("/applications/{aid}/hire")
async def hire(aid: int, body: HireIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Nomzodni xodimga aylantiradi: karta, "ishga olindi" tarixi, vakansiya to'lganda yopiladi."""
    if not svc.has(auth, "employees.create"):
        raise error(403, "forbidden")
    a = await _application(db, aid, lock=True)
    if a.stage != "offer":
        raise error(409, "invalid_transition")
    if a.offer_status in ("pending_hrd", "rejected"):
        raise error(409, "offer_not_approved")
    v = await _vacancy(db, a.vacancy_id, lock=True)
    c = await _candidate(db, a.candidate_id)
    last, first, middle = svc.split_name(c.full_name)
    last, first = (body.last_name or last).strip(), (body.first_name or first).strip()
    middle = (body.middle_name if body.middle_name is not None else middle) or None
    if not last or not first:
        raise error(400, "name_incomplete")
    branch_id = body.branch_id if body.branch_id is not None else v.branch_id
    department_id = body.department_id if body.department_id is not None else v.department_id
    position_id = body.position_id if body.position_id is not None else v.position_id
    await emp_svc.validate_assignment(db, department_id, position_id, branch_id)
    full_name = emp_svc.build_full_name(last, first, middle)
    dups = await emp_svc.find_duplicates(db, pinfl=None, passport_no=None, phone=c.phone, full_name=full_name, birth_date=c.birth_date)
    if dups and not body.confirm_duplicate:
        raise error(409, "possible_duplicate", matches=[emp_svc.match_out(m) for m in dups])
    moment = now()
    hire_date = body.hire_date or local_date(moment)
    emp = Employee(
        last_name=last, first_name=first, middle_name=middle, full_name=full_name, birth_date=c.birth_date, phone=c.phone, email=c.email, address=c.address,
        department_id=department_id, position_id=position_id, branch_id=branch_id, status="active", hire_date=hire_date,
    )  # fmt: skip
    db.add(emp)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "possible_duplicate", matches=[]) from None
    await db.refresh(emp)
    snap = await _snapshot(db, emp.department_id, emp.position_id, emp.branch_id)
    emp_svc.add_event(db, emp.id, "hired", hire_date, data={**snap, "source": "recruit", "vacancy_id": v.id}, actor_id=auth.user.id)
    svc.log(db, a, auth.user.id, "hired", frm=a.stage, to="hired", data={"employee_id": emp.id, "employee_no": emp.employee_no})
    a.stage, a.stage_changed_at, a.employee_id, a.hired_at = "hired", moment, emp.id, moment
    hired = (await db.scalar(select(func.count()).select_from(Application).where(Application.vacancy_id == v.id, Application.stage == "hired"))) or 0
    closed = False
    if hired >= v.openings and v.status != "closed":
        v.status, v.closed_at, closed = "closed", moment, True
    await audit(db, request, "recruit.hire", actor=auth.user, entity="application", entity_id=a.id, data={"employee_id": emp.id, "vacancy_id": v.id, "vacancy_closed": closed})
    await audit(db, request, "employee.create", actor=auth.user, entity="employee", entity_id=emp.id, data={"name": emp.full_name, "employee_no": emp.employee_no, "source": "recruit"})
    db.add(HireDocs(employee_id=emp.id))
    notes = await notify(db, await users_with_permission(db, "employees.documents"), "kadr.arrived", link="/kadr", params={"employee": emp.full_name})
    notes += await notify(db, [u for u in {v.recruiter_id, a.recruiter_id} if u and u != auth.user.id], "recruit.hired", link=f"/employees/{emp.id}", params={"candidate": c.full_name, "vacancy": v.title})
    await db.commit()
    await deliver(request.app, notes)
    await request.app.state.events.emit("employee.created", employee_id=emp.id, employee_no=emp.employee_no, full_name=emp.full_name)
    return {"application": (await _out_many(db, [a]))[0], "employee_id": emp.id, "employee_no": emp.employee_no, "vacancy_closed": closed}


# --- Tahlil -------------------------------------------------------------------------------


@router.get("/summary")
async def summary(start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Read)):
    if end < start or (end - start).days > 400:
        raise error(400, "range_invalid", max_days=400)
    s_dt = datetime.combine(start, datetime.min.time(), tzinfo=tz())
    e_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz())
    A = Application
    in_range = (A.applied_at >= s_dt, A.applied_at < e_dt)
    applied = await db.scalar(select(func.count()).select_from(A).where(*in_range)) or 0
    hired = await db.scalar(select(func.count()).select_from(A).where(A.hired_at >= s_dt, A.hired_at < e_dt)) or 0
    rejected = await db.scalar(select(func.count()).select_from(A).where(*in_range, A.stage == "rejected")) or 0
    avg_s = await db.scalar(select(func.avg(func.extract("epoch", A.hired_at - A.applied_at))).where(A.hired_at >= s_dt, A.hired_at < e_dt))
    stages = dict((await db.execute(select(A.stage, func.count()).where(*in_range).group_by(A.stage))).all())
    src = (await db.execute(select(Candidate.source, func.count(), func.count().filter(A.stage == "hired")).join(Candidate, Candidate.id == A.candidate_id).where(*in_range).group_by(Candidate.source))).all()
    open_vac = await db.scalar(select(func.count()).select_from(Vacancy).where(Vacancy.status == "open")) or 0
    return {
        "start": start, "end": end, "applied": applied, "hired": hired, "rejected": rejected, "open_vacancies": open_vac,
        "avg_days_to_hire": round(avg_s / 86400, 1) if avg_s else None, "stages": {s: stages.get(s, 0) for s in svc.STAGES},
        "sources": sorted([{"source": r[0], "applied": r[1], "hired": r[2]} for r in src], key=lambda x: -x["applied"]),
    }  # fmt: skip
