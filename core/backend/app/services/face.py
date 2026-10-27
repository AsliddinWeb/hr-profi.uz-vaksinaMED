"""Face ID: rozilik, ro'yxatga olish, tekshirish, saqlash muddati, sifat o'lchovi."""

import asyncio
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import error
from app.face.crypto import decrypt_vector
from app.face.engine import FaceEngine, FrameResult
from app.face.liveness import (
    CENTER_MAX,
    CHALLENGE_TTL,
    MAX_FRAMES,
    TURN_MIN,
    classify,
    new_steps,
    verify_liveness,
)
from app.models.auth import AuditLog
from app.models.employees import Employee
from app.models.face import FaceAttempt, FaceConsent, FaceTemplate

LOCK_FAILS = 8  # shuncha xato urinishdan keyin vaqtincha bloklanadi
LOCK_WINDOW_S = 600
SWEEP = [round(0.20 + 0.05 * i, 2) for i in range(13)]  # 0.20 .. 0.80


# --- Rozilik ----------------------------------------------------------------------------


async def get_consent(db: AsyncSession, employee_id: int) -> FaceConsent | None:
    return await db.scalar(select(FaceConsent).where(FaceConsent.employee_id == employee_id))


def consent_active(c: FaceConsent | None) -> bool:
    return bool(c and c.revoked_at is None and c.version == get_settings().face_consent_version)


async def templates_of(db: AsyncSession, employee_id: int) -> list[FaceTemplate]:
    return list(
        (await db.scalars(select(FaceTemplate).where(FaceTemplate.employee_id == employee_id).order_by(FaceTemplate.id))).all()
    )


async def delete_templates(db: AsyncSession, employee_id: int) -> int:
    res = await db.execute(delete(FaceTemplate).where(FaceTemplate.employee_id == employee_id))
    return res.rowcount or 0


# --- Challenge --------------------------------------------------------------------------


def _ckey(employee_id: int, cid: str) -> str:
    return f"face:chal:{employee_id}:{cid}"


async def create_challenge(redis, employee_id: int, purpose: str) -> dict[str, Any]:
    cid = secrets.token_urlsafe(16)
    steps = new_steps()
    await redis.set(_ckey(employee_id, cid), json.dumps({"steps": steps, "purpose": purpose}), ex=CHALLENGE_TTL)
    return {"id": cid, "steps": steps, "expires_in": CHALLENGE_TTL, "max_frames": MAX_FRAMES}


async def consume_challenge(redis, employee_id: int, cid: str, purpose: str) -> list[str]:
    """Bir martalik: ishlatilgach o'chadi (qayta yuborish/replay ishlamaydi)."""
    raw = await redis.getdel(_ckey(employee_id, cid))
    if not raw:
        raise error(400, "challenge_invalid")
    data = json.loads(raw)
    if data["purpose"] != purpose:
        raise error(400, "challenge_invalid")
    return data["steps"]


# --- Urinishlar va bloklash -------------------------------------------------------------


def _fkey(employee_id: int) -> str:
    return f"face:fails:{employee_id}"


async def check_lock(redis, employee_id: int) -> None:
    n = await redis.get(_fkey(employee_id))
    if n and int(n) >= LOCK_FAILS:
        raise error(429, "face_locked", retry_after=await redis.ttl(_fkey(employee_id)))


async def register_fail(redis, employee_id: int) -> None:
    key = _fkey(employee_id)
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, LOCK_WINDOW_S)


async def log_attempt(db: AsyncSession, employee_id: int | None, purpose: str, *, success: bool, score: float | None, liveness_ok: bool, reason: str | None, frames: int) -> None:
    db.add(FaceAttempt(employee_id=employee_id, purpose=purpose, success=success, score=score, liveness_ok=liveness_ok, reason=reason, frames=frames))


# --- Tahlil -----------------------------------------------------------------------------


async def analyze_frames(engine: FaceEngine, images: list[bytes]) -> list[FrameResult]:
    if not images or len(images) > MAX_FRAMES:
        raise error(400, "frames_invalid", max=MAX_FRAMES)
    return [await asyncio.to_thread(engine.analyze, img) for img in images]


def frame_reasons(results: list[FrameResult]) -> str | None:
    """Eng ko'p uchragan rad etish sababi (foydalanuvchiga maslahat uchun)."""
    reasons = [r.reason for r in results if not r.ok and r.reason]
    return max(set(reasons), key=reasons.count) if reasons else None


async def load_matrix(db: AsyncSession, *, exclude_employee: int | None = None, only_employee: int | None = None):
    """(employee_ids, matrix) — shifrlangan shablonlar ochilib, matritsaga yig'iladi."""
    stmt = select(FaceTemplate)
    if only_employee is not None:
        stmt = stmt.where(FaceTemplate.employee_id == only_employee)
    if exclude_employee is not None:
        stmt = stmt.where(FaceTemplate.employee_id != exclude_employee)
    rows = (await db.scalars(stmt)).all()
    if not rows:
        return [], np.zeros((0, 128), dtype=np.float32)
    ids = [r.employee_id for r in rows]
    mat = np.stack([decrypt_vector(r.vector_enc, r.employee_id) for r in rows])
    return ids, mat


def match_score(embeddings: list[np.ndarray], matrix: np.ndarray) -> float:
    if matrix.shape[0] == 0 or not embeddings:
        return -1.0
    return float(np.max(np.stack(embeddings) @ matrix.T))


def pick_templates(results: list[FrameResult]) -> dict[str, FrameResult]:
    """Har poza (center/left/right) uchun eng sifatli kadr."""
    best: dict[str, FrameResult] = {}
    for r in results:
        if not r.ok or r.yaw is None:
            continue
        pose = classify(r.yaw)
        if pose and (pose not in best or r.quality > best[pose].quality):
            best[pose] = r
    return best


def verification_embeddings(results: list[FrameResult]) -> list[np.ndarray]:
    """Tekshiruv uchun to'g'ri qaragan kadrlar (yo'q bo'lsa hammasi)."""
    ok = [r for r in results if r.ok and r.embedding is not None]
    center = [r.embedding for r in ok if abs(r.yaw or 0) <= CENTER_MAX]
    return center or [r.embedding for r in ok]  # type: ignore[misc]


async def purge_templates(db: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    """Saqlash muddati o'tgan shablonlarni o'chiradi (muddat: oxirgi tekshiruv/yaratilishdan; bo'shatilgan xodim: qisqa muddat)."""
    s = get_settings()
    now = now or datetime.now(UTC)
    stale = now - timedelta(days=s.face_retention_days)
    expired = (
        await db.scalars(
            select(FaceTemplate.employee_id).where(func.coalesce(FaceTemplate.last_verified_at, FaceTemplate.created_at) < stale)
        )
    ).all()
    dismissed_cut = (now - timedelta(days=s.face_dismissed_retention_days)).date()
    dismissed = (
        await db.scalars(
            select(FaceTemplate.employee_id)
            .join(Employee, Employee.id == FaceTemplate.employee_id)
            .where(Employee.status == "dismissed", Employee.dismissal_date <= dismissed_cut)
        )
    ).all()
    revoked = (
        await db.scalars(
            select(FaceTemplate.employee_id)
            .join(FaceConsent, FaceConsent.employee_id == FaceTemplate.employee_id)
            .where(FaceConsent.revoked_at.is_not(None))
        )
    ).all()
    result = {"expired": 0, "dismissed": 0, "revoked": 0}
    for reason, ids in (("expired", expired), ("dismissed", dismissed), ("revoked", revoked)):
        for emp_id in set(ids):
            n = await delete_templates(db, emp_id)
            result[reason] += n
            db.add(AuditLog(action="face.purge", entity="employee", entity_id=str(emp_id), data={"reason": reason, "templates": n}))
    await db.commit()
    return result


# --- Sifat o'lchovi (FAR/FRR) -----------------------------------------------------------


async def evaluation(db: AsyncSession) -> dict[str, Any]:
    """Yolg'on qabul (FAR) va yolg'on rad (FRR) chegara bo'yicha.

    Impostor: har xodim shabloni boshqa xodim shablonlari bilan solishtiriladi (ro'yxatdan o'tganlar orasida).
    Genuine: xodim o'z hisobi bilan o'tgan, liveness'dan o'tgan haqiqiy urinishlar ballari.
    """
    s = get_settings()
    ids, mat = await load_matrix(db)
    by_emp: dict[int, list[int]] = {}
    for i, e in enumerate(ids):
        by_emp.setdefault(e, []).append(i)
    impostor: list[float] = []
    emps = list(by_emp)
    for a in range(len(emps)):
        for b in range(a + 1, len(emps)):
            sub = mat[by_emp[emps[a]]] @ mat[by_emp[emps[b]]].T
            impostor.append(float(sub.max()))
    genuine = [
        r
        for r in (
            await db.scalars(
                select(FaceAttempt.score).where(FaceAttempt.purpose == "verify", FaceAttempt.liveness_ok.is_(True), FaceAttempt.score.is_not(None))
            )
        ).all()
    ]
    imp = np.array(impostor)
    gen = np.array(genuine)
    table = []
    for t in SWEEP:
        far = float((imp >= t).mean()) if imp.size else None
        frr = float((gen < t).mean()) if gen.size else None
        table.append({"threshold": t, "far": far, "frr": frr})
    eer = None
    if imp.size and gen.size:
        eer = min(table, key=lambda r: abs((r["far"] or 0) - (r["frr"] or 0)))["threshold"]
    recommended = None
    if imp.size >= 20 and gen.size >= 20:
        ok = [r for r in table if (r["far"] or 0) <= 0.001]
        recommended = min(ok, key=lambda r: r["frr"] or 0)["threshold"] if ok else None
    return {
        "threshold": s.face_match_threshold,
        "duplicate_threshold": s.face_duplicate_threshold,
        "enrolled_employees": len(emps),
        "impostor_pairs": int(imp.size),
        "genuine_attempts": int(gen.size),
        "table": table,
        "eer_threshold": eer,
        "recommended": recommended,
        "enough_data": bool(imp.size >= 20 and gen.size >= 20),
        "turn_min": TURN_MIN,
    }


__all__ = ["verify_liveness"]
