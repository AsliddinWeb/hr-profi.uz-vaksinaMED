"""Prebording: lavozim yo'nalishlari va dars bosqichlari (admin), stajyor paneli, ko'rish nazorati, kamera/mikrofon kuzatuvi."""

from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee
from app.models.internship import (
    InternshipEnrollment,
    InternshipMonitor,
    InternshipProgram,
    InternshipStep,
    InternshipVideoEvent,
)
from app.models.org import Position
from app.services import calls as calls_svc
from app.services import internship as isvc
from app.services import preboarding as svc
from app.services.audit import audit
from app.services.notifications import deliver
from app.services.uploads import storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/preboarding", tags=["preboarding"])


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(isvc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Manager = require_any("internship.manage")
Viewer = require_any("internship.read", "internship.manage")


# --- Admin: yo'nalishlar (lavozimlar) ---------------------------------------------------


class MonitoringIn(BaseModel):
    camera: bool = True
    live: bool = True
    record: bool = True
    snapshots: bool = True


class TrackIn(BaseModel):
    position_id: int
    pass_score: int = Field(default=50, ge=1, le=100)
    monitoring: MonitoringIn = MonitoringIn()


async def _track(db: AsyncSession, pid: int) -> InternshipProgram:
    p = await db.get(InternshipProgram, pid)
    if not p or p.phase != "preboarding" or not p.is_active:
        raise error(404, "not_found")
    return p


async def _position(db: AsyncSession, position_id: int) -> Position:
    pos = await db.get(Position, position_id)
    if not pos:
        raise error(400, "unknown_position")
    return pos


def _stage_out(s: InternshipStep) -> dict[str, Any]:
    return {**isvc.step_out(s, reveal=True), "media": svc.media_out(s)}


async def _track_out(db: AsyncSession, p: InternshipProgram) -> dict[str, Any]:
    pos = await db.get(Position, p.position_id) if p.position_id else None
    steps = await isvc.steps_of(db, p.id)
    enrolled = await db.scalar(select(func.count()).select_from(InternshipEnrollment).where(InternshipEnrollment.program_id == p.id)) or 0
    return {
        "id": p.id, "name": p.name, "description": p.description, "pass_score": p.pass_score, "position": {"id": pos.id, "name": pos.name} if pos else None,
        "monitoring": svc.monitoring_of(p), "enrolled": enrolled, "stages": [_stage_out(s) for s in steps],
    }  # fmt: skip


@router.get("/tracks")
async def list_tracks(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    return {"items": [await _track_out(db, p) for p in await svc.tracks(db)], "livekit": calls_svc.enabled()}


@router.post("/tracks", status_code=201)
async def create_track(body: TrackIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    pos = await _position(db, body.position_id)
    p = await svc.ensure_track(db, pos)
    p.pass_score, p.monitoring = body.pass_score, body.monitoring.model_dump()
    await audit(db, request, "preboarding.track_create", actor=auth.user, entity="internship_program", entity_id=p.id, data={"position": pos.name})
    await db.commit()
    return await _track_out(db, p)


@router.put("/tracks/{pid}")
async def update_track(pid: int, body: TrackIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    """Lavozimni almashtirish, o'tish bali va kuzatuv sozlamalari."""
    p = await _track(db, pid)
    pos = await _position(db, body.position_id)
    if pos.id != p.position_id:
        other = await db.scalar(select(InternshipProgram.id).where(InternshipProgram.phase == "preboarding", InternshipProgram.position_id == pos.id, InternshipProgram.is_active.is_(True), InternshipProgram.id != p.id))
        if other:
            raise error(409, "track_exists")
        p.position_id, p.name = pos.id, f"{pos.name}: prebording"
    p.pass_score, p.monitoring = body.pass_score, body.monitoring.model_dump()
    await audit(db, request, "preboarding.track_update", actor=auth.user, entity="internship_program", entity_id=p.id, data={"position": pos.name, "monitoring": p.monitoring})
    await db.commit()
    return await _track_out(db, p)


@router.delete("/tracks/{pid}", status_code=204)
async def delete_track(pid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    """Stajyori bor yo'nalish o'chirilmaydi, nofaol qilinadi (tarix saqlanadi)."""
    p = await _track(db, pid)
    used = await db.scalar(select(func.count()).select_from(InternshipEnrollment).where(InternshipEnrollment.program_id == p.id))
    await audit(db, request, "preboarding.track_delete", actor=auth.user, entity="internship_program", entity_id=p.id, data={"name": p.name})
    if used:
        p.is_active = False
    else:
        await db.delete(p)
    await db.commit()


# --- Admin: bosqichlar --------------------------------------------------------------------


class QuestionIn(BaseModel):
    id: str | None = Field(default=None, max_length=16)
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    correct: list[int] = Field(min_length=1)


class StageIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    audience: str = Field(default="all", pattern="^(all|students|staff)$")
    url: str | None = Field(default=None, max_length=500)
    slides_url: str | None = Field(default=None, max_length=500)
    questions: list[QuestionIn] = []
    pass_score: int | None = Field(default=None, ge=1, le=100)
    max_attempts: int = Field(default=3, ge=0, le=20)
    published: bool = True
    min_video_seconds: int | None = Field(default=None, ge=10, le=36000)
    min_slides_seconds: int | None = Field(default=None, ge=10, le=36000)


def _apply(s: InternshipStep, b: StageIn) -> None:
    url, slides = (b.url or "").strip() or None, (b.slides_url or "").strip() or None
    svc.check_urls(url, slides)
    s.kind, s.title, s.description = "lesson", b.title.strip(), (b.description or "").strip() or None
    s.audience, s.url, s.slides_url, s.published = b.audience, url, slides, b.published
    s.questions = isvc.clean_questions([q.model_dump() for q in b.questions]) if b.questions else []
    s.pass_score, s.max_attempts, s.required = b.pass_score, b.max_attempts, True
    s.min_video_seconds, s.min_slides_seconds = b.min_video_seconds, b.min_slides_seconds


async def _stage(db: AsyncSession, sid: int) -> tuple[InternshipStep, InternshipProgram]:
    s = await db.get(InternshipStep, sid)
    if not s:
        raise error(404, "not_found")
    return s, await _track(db, s.program_id)


@router.post("/tracks/{pid}/stages", status_code=201)
async def create_stage(pid: int, body: StageIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    p = await _track(db, pid)
    last = await db.scalar(select(func.max(InternshipStep.position)).where(InternshipStep.program_id == p.id))
    s = InternshipStep(program_id=p.id, position=(last if last is not None else -1) + 1, questions=[])
    _apply(s, body)
    db.add(s)
    await db.flush()
    await audit(db, request, "preboarding.stage_create", actor=auth.user, entity="internship_step", entity_id=s.id, data={"program_id": p.id, "title": s.title})
    await db.commit()
    return _stage_out(s)


@router.put("/stages/{sid}")
async def update_stage(sid: int, body: StageIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    s, _ = await _stage(db, sid)
    _apply(s, body)
    await audit(db, request, "preboarding.stage_update", actor=auth.user, entity="internship_step", entity_id=s.id, data={"title": s.title, "published": s.published})
    await db.commit()
    return _stage_out(s)


@router.delete("/stages/{sid}", status_code=204)
async def delete_stage(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    s, _ = await _stage(db, sid)
    await audit(db, request, "preboarding.stage_delete", actor=auth.user, entity="internship_step", entity_id=s.id, data={"title": s.title})
    await db.delete(s)
    await db.commit()


# --- Admin: natijalar va kuzatuv ---------------------------------------------------------


@router.get("/tracks/{pid}/results")
async def results(pid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    p = await _track(db, pid)
    steps = await isvc.steps_of(db, p.id)
    titles = {s.id: s.title for s in steps}
    moment = now()
    rows = []
    for e in (await db.scalars(select(InternshipEnrollment).where(InternshipEnrollment.program_id == p.id).order_by(InternshipEnrollment.id.desc()).limit(200))).all():
        emp = await db.get(Employee, e.employee_id)
        prog = await isvc.progress_of(db, e.id)
        views = await svc.views_of(db, e.id)
        sessions = (await db.scalars(select(InternshipMonitor).where(InternshipMonitor.enrollment_id == e.id).order_by(InternshipMonitor.id.desc()).limit(20))).all()
        rows.append({
            "id": e.id, "employee": {"id": emp.id, "full_name": emp.full_name} if emp else None, "status": e.status, "started_at": e.started_at,
            "consent": e.monitor_consent_at, "summary": isvc.summarize(steps, prog),
            "stages": [{"id": x["step"].id, "title": x["step"].title, "state": x["state"], "req": svc.requirements(x["step"], views, prog.get(x["step"].id), isvc.threshold(x["step"], p))} for x in isvc.step_states(p, steps, prog)],
            "sessions": [svc.monitor_out(m, moment, titles) for m in sessions], "live": any(svc.is_live(m, moment) for m in sessions),
        })  # fmt: skip
    return {"items": rows}


async def _session(db: AsyncSession, mid: int) -> InternshipMonitor:
    m = await db.get(InternshipMonitor, mid)
    if not m:
        raise error(404, "not_found")
    return m


@router.get("/monitor/{mid}")
async def monitor_detail(mid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    m = await _session(db, mid)
    return {**svc.monitor_out(m, now()), "clip_list": [{"i": i, "at": c["at"], "size": c.get("size")} for i, c in enumerate(m.clips or [])], "snapshot_list": [{"i": i, "at": x["at"]} for i, x in enumerate(m.snapshots or [])]}


@router.get("/monitor/{mid}/clip/{i}")
async def monitor_clip(mid: int, i: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    m = await _session(db, mid)
    if not 0 <= i < len(m.clips or []):
        raise error(404, "not_found")
    c = m.clips[i]
    await audit(db, request, "preboarding.view_recording", actor=auth.user, entity="internship_monitor", entity_id=m.id, data={"clip": i})
    await db.commit()
    return StreamingResponse(request.app.state.storage.stream(c["key"]), media_type=c.get("mime") or "video/webm", headers={"Cache-Control": "private, no-store"})


@router.get("/monitor/{mid}/snapshot/{i}")
async def monitor_snapshot(mid: int, i: int, request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    m = await _session(db, mid)
    if not 0 <= i < len(m.snapshots or []):
        raise error(404, "not_found")
    return StreamingResponse(request.app.state.storage.stream(m.snapshots[i]["key"]), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/monitor/{mid}/watch")
async def monitor_watch(mid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    """Jonli ko'rish va eshitish (yashirin tomoshabin). Har kirish auditga yoziladi."""
    m = await _session(db, mid)
    if not calls_svc.enabled():
        raise error(409, "calls_disabled")
    if not svc.is_live(m, now()):
        raise error(409, "not_live")
    await audit(db, request, "preboarding.watch_live", actor=auth.user, entity="internship_monitor", entity_id=m.id)
    await db.commit()
    return {"token": svc.viewer_token(m.room, auth.user.id, auth.user.full_name), "url": get_settings().livekit_public_url or None, "room": m.room}


# --- Stajyor paneli ---------------------------------------------------------------------


async def _me(db: AsyncSession, auth: AuthContext) -> Employee:
    emp = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id))
    if not emp:
        raise error(409, "no_employee_profile")
    return emp


async def _my(db: AsyncSession, auth: AuthContext, *, lock: bool = False) -> tuple[InternshipEnrollment, InternshipProgram, Employee]:
    emp = await _me(db, auth)
    e = await svc.my_enrollment(db, emp, now())
    if not e:
        raise error(404, "no_preboarding")
    if lock:
        await db.refresh(e, with_for_update=True)
    return e, await db.get(InternshipProgram, e.program_id), emp


async def _my_stage(db: AsyncSession, auth: AuthContext, sid: int):
    e, p, emp = await _my(db, auth, lock=True)
    if e.status != "active":
        raise error(409, "invalid_transition")
    steps = await isvc.steps_of(db, p.id)
    x = next((x for x in isvc.step_states(p, steps, await isvc.progress_of(db, e.id)) if x["step"].id == sid), None)
    if x is None:
        raise error(404, "not_found")
    if x["state"] == "locked":
        raise error(409, "step_locked")
    return e, p, emp, x["step"], x


async def _my_out(db: AsyncSession, e: InternshipEnrollment, p: InternshipProgram, emp: Employee) -> dict[str, Any]:
    steps = await isvc.steps_of(db, p.id)
    prog = await isvc.progress_of(db, e.id)
    views = await svc.views_of(db, e.id)
    pos = await db.get(Position, p.position_id) if p.position_id else None
    from app.models.auth import User  # noqa: PLC0415
    from app.models.org import Branch  # noqa: PLC0415

    branch = await db.get(Branch, emp.branch_id) if emp.branch_id else None
    mentor = await db.get(User, e.mentor_id) if e.mentor_id else None
    return {
        "me": {
            "full_name": emp.full_name, "phone": emp.phone, "position": pos.name if pos else None, "branch": branch.name if branch else None,
            "branch_address": branch.address if branch else None, "mentor": mentor.full_name if mentor else None, "mentor_phone": mentor.phone if mentor else None,
            "hire_date": emp.hire_date, "photo": bool(emp.photo_key), "employee_id": emp.id,
        },
        "enrollment": {"id": e.id, "status": e.status, "started_at": e.started_at, "due_date": e.due_date, "consent": e.monitor_consent_at},
        "program": {"id": p.id, "name": p.name, "description": p.description, "position": pos.name if pos else None, "pass_score": p.pass_score},
        "monitoring": svc.monitoring_of(p), "livekit": calls_svc.enabled(), "summary": isvc.summarize(steps, prog),
        "stages": [
            {**isvc.step_out(x["step"], reveal=False), "media": svc.media_out(x["step"]), "state": x["state"], "score": x["score"], "attempts": x["attempts"],
             "req": svc.requirements(x["step"], views, prog.get(x["step"].id), isvc.threshold(x["step"], p))}
            for x in isvc.step_states(p, steps, prog)
        ],
    }  # fmt: skip


@router.get("/my")
async def my(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Stajyorning prebordingi. Lavozimida dastur bo'lsa birinchi kirishda o'zi biriktiriladi; yo'q bo'lsa null."""
    emp = await db.scalar(select(Employee).where(Employee.user_id == auth.user.id))
    if not emp:
        return None
    e = await svc.my_enrollment(db, emp, now())
    if not e:
        return None
    await db.commit()
    return await _my_out(db, e, await db.get(InternshipProgram, e.program_id), emp)


@router.post("/my/consent")
async def consent(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    e, p, emp = await _my(db, auth, lock=True)
    if not e.monitor_consent_at:
        e.monitor_consent_at = now()
        await audit(db, request, "preboarding.consent", actor=auth.user, entity="internship_enrollment", entity_id=e.id)
        await db.commit()
    return await _my_out(db, e, p, emp)


@router.post("/my/stages/{sid}/start")
async def start(sid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Darsni boshlash: kuzatuv sessiyasi va (jonli yoqilgan bo'lsa) kamera/mikrofonni nashr qilish tokeni."""
    e, p, emp, s, _ = await _my_stage(db, auth, sid)
    mon = svc.monitoring_of(p)
    if mon["camera"] and not e.monitor_consent_at:
        raise error(409, "consent_required")
    m = await svc.start_session(db, e, s, now()) if mon["camera"] else None
    await db.commit()
    live = bool(m and mon["live"] and calls_svc.enabled())
    return {
        "monitor_id": m.id if m else None, "monitoring": mon,
        "live": {"token": svc.publisher_token(m.room, auth.user.id, emp.full_name), "url": get_settings().livekit_public_url or None, "room": m.room} if live and m else None,
    }  # fmt: skip


class TickIn(BaseModel):
    kind: str = Field(pattern="^(video|slides)$")
    delta: int = Field(ge=0, le=60)
    pos: int | None = Field(default=None, ge=0, le=360000)
    duration: int | None = Field(default=None, ge=1, le=360000)
    monitor_id: int | None = None
    camera_ok: bool = True
    event: str | None = Field(default=None, max_length=40)  # camera_off | hidden | ...


@router.post("/my/stages/{sid}/tick")
async def tick(sid: int, body: TickIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Har ~10 s: video/slayd ko'rilgan vaqt. Kamera shart bo'lsa va o'chiq bo'lsa vaqt hisoblanmaydi."""
    e, p, emp, s, _ = await _my_stage(db, auth, sid)
    moment = now()
    mon = svc.monitoring_of(p)
    m = await db.get(InternshipMonitor, body.monitor_id) if body.monitor_id else None
    if m and m.enrollment_id == e.id:
        m.last_seen_at = moment
        if body.event:
            m.events = [*(m.events or [])[-199:], {"at": moment.isoformat(), "kind": body.event}]
    counted = body.camera_ok or not mon["camera"]
    if counted and ((body.kind == "video" and s.url) or (body.kind == "slides" and s.slides_url)):
        await svc.record_view(db, e, s, body.kind, body.delta, body.pos, body.duration)
    done = await svc.try_complete(db, e, s, p, moment)
    notes = await isvc.check_ready(db, e, p, emp.full_name, moment) if done else []
    await db.commit()
    await deliver(request.app, notes)
    return {"counted": counted, **(await _my_out(db, e, p, emp))}


class SubmitIn(BaseModel):
    answers: dict[str, list[int]]


@router.post("/my/stages/{sid}/submit")
async def submit(sid: int, body: SubmitIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    e, p, emp, s, x = await _my_stage(db, auth, sid)
    if not s.questions:
        raise error(400, "not_a_test")
    req = svc.requirements(s, await svc.views_of(db, e.id), (await isvc.progress_of(db, e.id)).get(s.id), isvc.threshold(s, p))
    if not svc.media_ready(req):
        raise error(409, "media_not_watched")
    if req["test"]["done"]:
        raise error(409, "already_done")
    if s.max_attempts and x["attempts"] >= s.max_attempts:
        raise error(409, "attempts_exhausted", max=s.max_attempts)
    score, wrong = isvc.grade(s, body.answers)
    th = isvc.threshold(s, p)
    moment = now()
    prog = await isvc.complete_step(db, e, s, moment, score=score, done=False)
    prog.attempts += 1
    done = await svc.try_complete(db, e, s, p, moment)
    notes = await isvc.check_ready(db, e, p, emp.full_name, moment) if done else []
    await audit(db, request, "preboarding.test", actor=auth.user, entity="internship_enrollment", entity_id=e.id, data={"step_id": s.id, "score": score, "passed": score >= th, "attempt": prog.attempts})
    await db.commit()
    await deliver(request.app, notes)
    return {"score": score, "passed": score >= th, "wrong": [] if score >= th else wrong, "threshold": th, **(await _my_out(db, e, p, emp))}


@router.post("/my/stages/{sid}/done")
async def mark_read(sid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Video, slayd va testi yo'q (faqat matnli) bosqich: «Tanishdim»."""
    e, p, emp, s, _ = await _my_stage(db, auth, sid)
    if s.url or s.slides_url or s.questions:
        raise error(400, "requirements_pending")
    moment = now()
    await isvc.complete_step(db, e, s, moment)
    notes = await isvc.check_ready(db, e, p, emp.full_name, moment)
    await db.commit()
    await deliver(request.app, notes)
    return await _my_out(db, e, p, emp)


async def _my_monitor(db: AsyncSession, auth: AuthContext, mid: int) -> InternshipMonitor:
    e, _, _ = await _my(db, auth)
    m = await db.get(InternshipMonitor, mid)
    if not m or m.enrollment_id != e.id or m.ended_at is not None:
        raise error(404, "not_found")
    return m


@router.post("/my/monitor/{mid}/clip", status_code=201)
async def upload_clip(mid: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Kamera+mikrofon yozuvining ~60 s lik bo'lagi (webm/mp4)."""
    m = await _my_monitor(db, auth, mid)
    data = await file.read(svc.MAX_CLIP_BYTES + 1)
    if not data or len(data) > svc.MAX_CLIP_BYTES:
        raise error(413, "file_too_large")
    mime = "video/webm" if data[:4] == b"\x1a\x45\xdf\xa3" else "video/mp4" if data[4:8] == b"ftyp" else None
    if not mime:
        raise error(415, "unsupported_type")
    moment = now()
    key = storage_key(f"preboarding/{m.enrollment_id}/{m.id}", f"clip-{len(m.clips or [])}.{'webm' if mime == 'video/webm' else 'mp4'}")
    await request.app.state.storage.put(key, data, mime)
    m.clips = [*(m.clips or []), {"key": key, "at": moment.isoformat(), "size": len(data), "mime": mime}]
    m.last_seen_at = moment
    await db.commit()
    return {"clips": len(m.clips)}


@router.post("/my/monitor/{mid}/snapshot", status_code=201)
async def upload_snapshot(mid: int, request: Request, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    m = await _my_monitor(db, auth, mid)
    data = await file.read(svc.MAX_SNAPSHOT_BYTES + 1)
    if not data or len(data) > svc.MAX_SNAPSHOT_BYTES or not data.startswith(b"\xff\xd8\xff"):
        raise error(415, "unsupported_type")
    moment = now()
    key = storage_key(f"preboarding/{m.enrollment_id}/{m.id}", f"snap-{len(m.snapshots or [])}.jpg")
    await request.app.state.storage.put(key, data, "image/jpeg")
    m.snapshots = [*(m.snapshots or []), {"key": key, "at": moment.isoformat()}]
    m.last_seen_at = moment
    await db.commit()
    return {"snapshots": len(m.snapshots)}


@router.post("/my/monitor/{mid}/end", status_code=204)
async def end_session(mid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    m = await _my_monitor(db, auth, mid)
    m.ended_at = now()
    await db.commit()


# --- Video hodisalari, statistika va hisobot ------------------------------------------


class EventIn(BaseModel):
    kind: str = Field(pattern="^(pause|rewind|confused)$")
    pos: int = Field(ge=0, le=360000)
    to_pos: int | None = Field(default=None, ge=0, le=360000)
    note: str | None = Field(default=None, max_length=1000)


async def _event_quota(db: AsyncSession, e: InternshipEnrollment, s: InternshipStep) -> None:
    n = await db.scalar(select(func.count()).select_from(InternshipVideoEvent).where(InternshipVideoEvent.enrollment_id == e.id, InternshipVideoEvent.step_id == s.id))
    if (n or 0) >= svc.MAX_EVENTS_PER_STAGE:
        raise error(429, "too_many_events")


@router.post("/my/stages/{sid}/event", status_code=201)
async def video_event(sid: int, body: EventIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Pauza, orqaga qaytish yoki «tushunmadim» (ixtiyoriy matn bilan)."""
    e, _, _, s, _ = await _my_stage(db, auth, sid)
    await _event_quota(db, e, s)
    if body.kind == "rewind" and (body.to_pos is None or body.to_pos >= body.pos):
        raise error(400, "rewind_invalid")
    db.add(InternshipVideoEvent(enrollment_id=e.id, step_id=s.id, kind=body.kind, pos=body.pos, to_pos=body.to_pos if body.kind == "rewind" else None, note=(body.note or "").strip() or None))
    await db.commit()
    return {"ok": True}


@router.post("/my/stages/{sid}/voice", status_code=201)
async def voice_note(sid: int, request: Request, pos: int = 0, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Ovozli izoh: «shu joyini tushunmadim» (video qaysi joyda to'xtatilgani bilan)."""
    e, _, _, s, _ = await _my_stage(db, auth, sid)
    await _event_quota(db, e, s)
    data = await file.read(svc.MAX_VOICE_BYTES + 1)
    if not data or len(data) > svc.MAX_VOICE_BYTES:
        raise error(413, "file_too_large")
    mime = svc.audio_mime(data)
    if not mime:
        raise error(415, "unsupported_type")
    ev = InternshipVideoEvent(enrollment_id=e.id, step_id=s.id, kind="voice", pos=max(0, min(pos, 360000)))
    db.add(ev)
    await db.flush()
    key = storage_key(f"preboarding/{e.id}/voice", f"v{ev.id}.{mime.split('/')[1]}")
    await request.app.state.storage.put(key, data, mime)
    ev.audio_key, ev.audio_mime = key, mime
    await db.commit()
    return {"id": ev.id}


@router.get("/events/{eid}/audio")
async def event_audio(eid: int, request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    ev = await db.get(InternshipVideoEvent, eid)
    if not ev or not ev.audio_key:
        raise error(404, "not_found")
    return StreamingResponse(request.app.state.storage.stream(ev.audio_key), media_type=ev.audio_mime or "audio/webm", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/tracks/{pid}/stats")
async def stats(pid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    """Har bosqich videosi: qayerda ko'p to'xtashgan, orqaga qaytishgan va tushunmaganlar (izohlar bilan)."""
    p = await _track(db, pid)
    return {"items": [await svc.stage_stats(db, s) for s in await isvc.steps_of(db, p.id) if s.url]}


@router.get("/tracks/{pid}/report")
async def report(pid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    p = await _track(db, pid)
    return {"items": await svc.report_rows(db, p)}


@router.get("/tracks/{pid}/report.xlsx")
async def report_xlsx(pid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    import io  # noqa: PLC0415

    from openpyxl import Workbook  # noqa: PLC0415

    from app.services.xlsx_safe import harden  # noqa: PLC0415

    p = await _track(db, pid)
    rows = await svc.report_rows(db, p)
    wb = Workbook()
    ws = wb.active
    ws.title = "Prebording"
    ws.append(["Xodim", "Holat", "Boshlagan", "Bosqich", "Jami", "%", "O'rtacha ball", "Urinishlar", "Video (daq)", "Slayd (daq)", "Pauza", "Orqaga", "Tushunmadim"])
    for r in rows:
        ws.append([r["employee"], r["status"], r["started_at"].strftime("%d.%m.%Y") if r["started_at"] else "", r["done"], r["required"], r["percent"], r["avg_score"], r["attempts"], r["video_min"], r["slides_min"], r["pauses"], r["rewinds"], r["confused"]])
    harden(wb)
    buf = io.BytesIO()
    wb.save(buf)
    await audit(db, request, "preboarding.report_export", actor=auth.user, entity="internship_program", entity_id=p.id)
    await db.commit()
    from fastapi.responses import Response  # noqa: PLC0415

    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="preboarding-{p.id}.xlsx"'})


@router.get("/my/photo")
async def my_photo(request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Stajyorning o'z rasmi (xodimlar ro'yxatini ko'rish huquqisiz)."""
    emp = await _me(db, auth)
    if not emp.photo_key:
        raise error(404, "not_found")
    return StreamingResponse(request.app.state.storage.stream(emp.photo_key), media_type=emp.photo_mime or "image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


# --- Ovoz chiqarib o'qish (Whisper): bosqich matnini o'qiydi, aniqlik foizi ---------------------------


@router.post("/my/stages/{sid}/read-aloud", status_code=201)
async def read_aloud(sid: int, request: Request, seconds: int = 0, file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Stajyor bosqich matnini (tavsif) ovoz chiqarib o'qiydi; Whisper matnga aylantiradi, mos kelish foizi va o'qilmagan so'zlar qaytadi."""
    from app.models.smart import ReadAloudAttempt  # noqa: PLC0415
    from app.services import speech  # noqa: PLC0415

    e, _, _, s, _ = await _my_stage(db, auth, sid)
    expected = (s.description or "").strip()
    if len(expected.split()) < 5:
        raise error(409, "no_reading_text")
    n = await db.scalar(select(func.count()).select_from(ReadAloudAttempt).where(ReadAloudAttempt.enrollment_id == e.id, ReadAloudAttempt.step_id == s.id)) or 0
    if n >= 20:
        raise error(429, "too_many_attempts")
    data = await file.read(speech.MAX_AUDIO_BYTES + 1)
    mime = svc.audio_mime(data) if data else None
    if not mime:
        raise error(415, "unsupported_type")
    text = await speech.transcribe(data, mime, "uz")
    acc, missed = speech.reading_score(expected, text)
    db.add(ReadAloudAttempt(enrollment_id=e.id, step_id=s.id, transcript=text[:20000], accuracy=acc, missed=missed, duration_s=max(0, min(seconds, 3600)) or None))
    await db.commit()
    return {"accuracy": acc, "missed": missed, "transcript": text, "attempts": n + 1}


@router.get("/tracks/{pid}/read-aloud")
async def read_aloud_results(pid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Viewer)):
    """Yo'nalish bo'yicha o'qish natijalari: har stajyor va bosqich uchun eng yaxshi aniqlik va urinishlar soni."""
    from app.models.smart import ReadAloudAttempt  # noqa: PLC0415

    rows = (await db.execute(
        select(Employee.full_name, InternshipStep.title, func.max(ReadAloudAttempt.accuracy), func.count(), func.max(ReadAloudAttempt.created_at))
        .join(InternshipEnrollment, InternshipEnrollment.id == ReadAloudAttempt.enrollment_id)
        .join(Employee, Employee.id == InternshipEnrollment.employee_id)
        .join(InternshipStep, InternshipStep.id == ReadAloudAttempt.step_id)
        .where(InternshipEnrollment.program_id == pid)
        .group_by(Employee.full_name, InternshipStep.title).order_by(Employee.full_name)
    )).all()  # fmt: skip
    return {"items": [{"employee": n, "stage": t, "best": b, "attempts": c, "last_at": at} for n, t, b, c, at in rows]}
