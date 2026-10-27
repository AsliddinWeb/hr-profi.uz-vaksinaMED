"""Face ID: rozilik, ro'yxatga olish (liveness bilan), yuz orqali keldi/ketdi, boshqaruv va sifat o'lchovi."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import record_out
from app.api.employees import get_employee
from app.config import get_settings
from app.db import get_session
from app.deps import AuthContext, error, require
from app.face.crypto import encrypt_vector
from app.face.engine import MAX_IMAGE_BYTES, get_engine
from app.face.liveness import MAX_FRAMES, MIN_VALID_FRAMES, verify_liveness
from app.models.employees import Employee
from app.models.face import FaceAttempt, FaceConsent, FaceTemplate
from app.models.schedule import ShiftTemplate
from app.services import attendance as att
from app.services import face as svc
from app.services.audit import audit

router = APIRouter(prefix="/v1/face", tags=["face"])


async def _read_frames(files: list[UploadFile]) -> list[bytes]:
    if not files or len(files) > MAX_FRAMES:
        raise error(400, "frames_invalid", max=MAX_FRAMES)
    out = []
    for f in files:
        data = await f.read(MAX_IMAGE_BYTES + 1)
        out.append(data)
    return out


# --- Xodimning o'zi ---------------------------------------------------------------------


@router.get("/status")
async def my_status(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require("face.enroll"))):
    emp = await att.current_employee(db, auth.user.id)
    s = get_settings()
    consent = await svc.get_consent(db, emp.id)
    templates = await svc.templates_of(db, emp.id)
    return {
        "employee": {"id": emp.id, "full_name": emp.full_name},
        "consent": {
            "given": svc.consent_active(consent),
            "given_at": consent.given_at if consent else None,
            "version": consent.version if consent else None,
            "revoked_at": consent.revoked_at if consent else None,
            "outdated": bool(consent and consent.revoked_at is None and consent.version != s.face_consent_version),
        },
        "current_version": s.face_consent_version,
        "enrolled": len(templates) > 0,
        "enrolled_at": templates[0].created_at if templates else None,
        "last_verified_at": max((t.last_verified_at for t in templates if t.last_verified_at), default=None),
        "retention_days": s.face_retention_days,
    }


class ConsentIn(BaseModel):
    version: str = Field(max_length=30)


@router.post("/consent")
async def give_consent(
    body: ConsentIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("face.enroll")),
):
    """Xodim o'z biometrik ma'lumotiga rozilik beradi (faqat joriy matn versiyasiga)."""
    emp = await att.current_employee(db, auth.user.id)
    version = get_settings().face_consent_version
    if body.version != version:
        raise error(409, "consent_version_mismatch", current=version)
    c = await svc.get_consent(db, emp.id)
    now = datetime.now(UTC)
    if c is None:
        c = FaceConsent(employee_id=emp.id, version=version, given_at=now)
        db.add(c)
    else:
        c.version, c.given_at, c.revoked_at = version, now, None
    c.ip = request.client.host if request.client else None
    await audit(db, request, "face.consent", actor=auth.user, entity="employee", entity_id=emp.id, data={"version": version})
    await db.commit()
    return {"given": True, "version": version}


@router.delete("/consent", status_code=204)
async def revoke_consent(
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("face.enroll")),
):
    """Rozilikni qaytarib olish: yuz shablonlari DARHOL o'chadi."""
    emp = await att.current_employee(db, auth.user.id)
    c = await svc.get_consent(db, emp.id)
    n = await svc.delete_templates(db, emp.id)
    if c:
        c.revoked_at = datetime.now(UTC)
    await audit(db, request, "face.revoke", actor=auth.user, entity="employee", entity_id=emp.id, data={"templates_deleted": n})
    await db.commit()


class ChallengeIn(BaseModel):
    purpose: str = Field(pattern="^(enroll|verify)$")


@router.post("/challenge")
async def challenge(
    body: ChallengeIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("face.enroll")),
):
    emp = await att.current_employee(db, auth.user.id)
    consent = await svc.get_consent(db, emp.id)
    if not svc.consent_active(consent):
        raise error(409, "consent_required")
    if body.purpose == "verify":
        if not await svc.templates_of(db, emp.id):
            raise error(409, "face_not_enrolled")
        await svc.check_lock(request.app.state.redis, emp.id)
    ch = await svc.create_challenge(request.app.state.redis, emp.id, body.purpose)
    return {**ch, "min_frames": MIN_VALID_FRAMES}


@router.post("/enroll")
async def enroll(
    request: Request,
    challenge_id: str = Form(max_length=60),
    frames: list[UploadFile] = File(),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("face.enroll")),
):
    emp = await att.current_employee(db, auth.user.id)
    if not svc.consent_active(await svc.get_consent(db, emp.id)):
        raise error(409, "consent_required")
    redis = request.app.state.redis
    steps = await svc.consume_challenge(redis, emp.id, challenge_id, "enroll")
    engine = get_engine(request.app.state)
    results = await svc.analyze_frames(engine, await _read_frames(frames))
    live, why = verify_liveness(steps, results)
    if not live:
        await svc.log_attempt(db, emp.id, "enroll", success=False, score=None, liveness_ok=False, reason=why, frames=len(results))
        await db.commit()
        raise error(400, "liveness_failed", reason=why, hint=svc.frame_reasons(results))
    best = svc.pick_templates(results)
    if "center" not in best:
        raise error(400, "liveness_failed", reason="no_center")

    # Boshqa xodimga tegishli yuz bo'lmasligi kerak (do'stining nomidan belgilashga qarshi)
    ids, mat = await svc.load_matrix(db, exclude_employee=emp.id)
    thr = get_settings().face_duplicate_threshold
    for r in best.values():
        sims = (mat @ r.embedding) if mat.shape[0] else []  # type: ignore[operator]
        if len(sims) and float(max(sims)) >= thr:
            other = ids[int(sims.argmax())]
            await svc.log_attempt(db, emp.id, "enroll", success=False, score=float(max(sims)), liveness_ok=True, reason="duplicate", frames=len(results))
            await audit(db, request, "face.duplicate", actor=auth.user, entity="employee", entity_id=emp.id, data={"matched_employee_id": other})
            await db.commit()
            raise error(409, "face_already_enrolled")

    await svc.delete_templates(db, emp.id)
    for pose, r in best.items():
        db.add(FaceTemplate(employee_id=emp.id, pose=pose, vector_enc=encrypt_vector(r.embedding, emp.id), model=engine.model_name, quality=r.quality))  # type: ignore[arg-type]
    await svc.log_attempt(db, emp.id, "enroll", success=True, score=None, liveness_ok=True, reason=None, frames=len(results))
    await audit(db, request, "face.enroll", actor=auth.user, entity="employee", entity_id=emp.id, data={"poses": sorted(best)})
    await db.commit()
    return {"enrolled": True, "poses": sorted(best)}


@router.post("/punch")
async def face_punch(
    request: Request,
    challenge_id: str = Form(max_length=60),
    lat: float | None = Form(default=None),
    lng: float | None = Form(default=None),
    accuracy: float | None = Form(default=None, ge=0),
    frames: list[UploadFile] = File(),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("face.enroll")),
):
    """Yuz orqali keldi/ketdi: liveness + o'z shabloniga 1:1 solishtirish, keyin oddiy davomat qoidalari (geofence va h.k.)."""
    emp = await att.current_employee(db, auth.user.id)
    if not svc.consent_active(await svc.get_consent(db, emp.id)):
        raise error(409, "consent_required")
    redis = request.app.state.redis
    await svc.check_lock(redis, emp.id)
    steps = await svc.consume_challenge(redis, emp.id, challenge_id, "verify")
    engine = get_engine(request.app.state)
    results = await svc.analyze_frames(engine, await _read_frames(frames))
    live, why = verify_liveness(steps, results)
    if not live:
        await svc.register_fail(redis, emp.id)
        await svc.log_attempt(db, emp.id, "verify", success=False, score=None, liveness_ok=False, reason=why, frames=len(results))
        await db.commit()
        raise error(400, "liveness_failed", reason=why, hint=svc.frame_reasons(results))

    _, mat = await svc.load_matrix(db, only_employee=emp.id)
    if mat.shape[0] == 0:
        raise error(409, "face_not_enrolled")
    score = svc.match_score(svc.verification_embeddings(results), mat)
    ok = score >= get_settings().face_match_threshold
    await svc.log_attempt(db, emp.id, "verify", success=ok, score=score, liveness_ok=True, reason=None if ok else "mismatch", frames=len(results))
    if not ok:
        await svc.register_fail(redis, emp.id)
        await db.commit()
        raise error(400, "face_mismatch")
    await redis.delete(svc._fkey(emp.id))
    for t in await svc.templates_of(db, emp.id):
        t.last_verified_at = datetime.now(UTC)
    await db.commit()  # tekshiruv natijasi davomat xatosida ham saqlansin

    try:
        action, rec = await att.punch(db, emp, method="face", token=None, lat=lat, lng=lng, accuracy=accuracy)
    except Exception:
        await db.rollback()
        raise
    await db.commit()
    shift = await db.get(ShiftTemplate, rec.shift_id) if rec.shift_id else None
    return {"action": action, "record": record_out(rec, shift), "score": round(score, 3)}


# --- Boshqaruv --------------------------------------------------------------------------


@router.get("/employees")
async def employees(
    q: str | None = None,
    state: str | None = Query(default=None, pattern="^(enrolled|consent_only|none|revoked)$"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("face.read")),
):
    """Xodimlarning Face ID holati. Shablon/rasm KO'RSATILMAYDI, faqat holat."""
    tmpl = (
        select(FaceTemplate.employee_id, func.count().label("n"), func.max(FaceTemplate.last_verified_at).label("verified"), func.min(FaceTemplate.created_at).label("enrolled"))
        .group_by(FaceTemplate.employee_id)
        .subquery()
    )
    stmt = (
        select(Employee, FaceConsent, tmpl.c.n, tmpl.c.verified, tmpl.c.enrolled)
        .outerjoin(FaceConsent, FaceConsent.employee_id == Employee.id)
        .outerjoin(tmpl, tmpl.c.employee_id == Employee.id)
        .where(Employee.status == "active")
    )
    if q and q.strip():
        stmt = stmt.where(Employee.full_name.ilike(f"%{q.strip()}%"))
    if state == "enrolled":
        stmt = stmt.where(tmpl.c.n.is_not(None))
    elif state == "consent_only":
        stmt = stmt.where(tmpl.c.n.is_(None), FaceConsent.id.is_not(None), FaceConsent.revoked_at.is_(None))
    elif state == "revoked":
        stmt = stmt.where(FaceConsent.revoked_at.is_not(None))
    elif state == "none":
        stmt = stmt.where(FaceConsent.id.is_(None))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.order_by(Employee.full_name).offset((page - 1) * size).limit(size))).all()
    summary = {
        "enrolled": await db.scalar(select(func.count(func.distinct(FaceTemplate.employee_id)))) or 0,
        "active": await db.scalar(select(func.count()).select_from(Employee).where(Employee.status == "active")) or 0,
    }
    return {
        "total": total or 0, "page": page, "size": size, "summary": summary,
        "items": [
            {"employee": {"id": e.id, "employee_no": e.employee_no, "full_name": e.full_name},
             "state": _state(c, n), "consent_version": c.version if c else None,
             "given_at": c.given_at if c else None, "templates": n or 0, "enrolled_at": enrolled, "last_verified_at": verified}
            for e, c, n, verified, enrolled in rows
        ],
    }  # fmt: skip


def _state(c: FaceConsent | None, n: int | None) -> str:
    if n:
        return "enrolled"
    if c and c.revoked_at:
        return "revoked"
    return "consent_only" if c else "none"


@router.get("/employees/{employee_id}")
async def employee_detail(
    employee_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("face.read")),
):
    """Bitta xodimning Face ID holati va urinishlari. Biometrik ma'lumotga kirish auditga yoziladi."""
    emp = await get_employee(db, employee_id)
    consent = await svc.get_consent(db, emp.id)
    templates = await svc.templates_of(db, emp.id)
    attempts = (await db.scalars(select(FaceAttempt).where(FaceAttempt.employee_id == emp.id).order_by(FaceAttempt.id.desc()).limit(30))).all()
    totals = (
        await db.execute(
            select(FaceAttempt.success, func.count()).where(FaceAttempt.employee_id == emp.id, FaceAttempt.purpose == "verify").group_by(FaceAttempt.success)
        )
    ).all()
    await audit(db, request, "face.view", actor=auth.user, entity="employee", entity_id=emp.id)
    await db.commit()
    return {
        "employee": {"id": emp.id, "full_name": emp.full_name, "status": emp.status},
        "state": _state(consent, len(templates)),
        "consent": {"version": consent.version, "given_at": consent.given_at, "revoked_at": consent.revoked_at} if consent else None,
        "templates": [{"id": t.id, "pose": t.pose, "model": t.model, "quality": round(t.quality, 2), "created_at": t.created_at, "last_verified_at": t.last_verified_at} for t in templates],
        "verify_ok": next((n for ok, n in totals if ok), 0),
        "verify_fail": next((n for ok, n in totals if not ok), 0),
        "attempts": [{"id": a.id, "purpose": a.purpose, "success": a.success, "liveness_ok": a.liveness_ok, "reason": a.reason, "created_at": a.created_at} for a in attempts],
    }  # fmt: skip


@router.delete("/employees/{employee_id}/templates", status_code=204)
async def delete_employee_templates(
    employee_id: int,
    request: Request,
    reason: str = Query(min_length=3, max_length=300),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("face.manage")),
):
    """HR xodimning yuz shablonini o'chiradi (masalan, ishdan ketgan yoki shubha bor). Rozilik qoladi: xodim qayta ro'yxatdan o'tishi mumkin."""
    emp = await get_employee(db, employee_id)
    n = await svc.delete_templates(db, emp.id)
    await audit(db, request, "face.delete", actor=auth.user, entity="employee", entity_id=emp.id, data={"templates_deleted": n}, note=reason.strip())
    await db.commit()


@router.get("/evaluation")
async def evaluation(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("face.evaluate"))) -> dict[str, Any]:
    return await svc.evaluation(db)
