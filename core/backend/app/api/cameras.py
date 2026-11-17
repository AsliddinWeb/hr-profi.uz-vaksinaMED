"""Kameralar paneli: reyestr (IP kamera, kompyuter, telefon), holat nazorati, Excel import va kamera stansiyasi."""

import base64
import io
import secrets
from collections import defaultdict
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require_any
from app.models.cameras import Camera, CameraEvent
from app.models.org import Branch
from app.services import cameras as svc
from app.services.audit import audit
from app.services.notifications import deliver
from app.timeutil import now

router = APIRouter(prefix="/v1/cameras", tags=["cameras"])
public_router = APIRouter(prefix="/v1/public/camera", tags=["public"])
can_read = require_any("cameras.read", "cameras.manage")
can_manage = require_any("cameras.manage")

KINDS = ("ip", "webcam", "phone")
SNAP_TTL = 15 * 60
MAX_SNAP = 400_000
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="ip", pattern="^(ip|webcam|phone)$")
    branch_id: int | None = None
    location: str | None = Field(default=None, max_length=120)
    brand: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=80)
    host: str | None = Field(default=None, max_length=200, pattern=r"^[A-Za-z0-9.\-:\[\]]*$")
    port: int | None = Field(default=None, ge=1, le=65535)
    is_active: bool = True
    note: str | None = Field(default=None, max_length=1000)


def _out(c: Camera, branches: dict[int, Branch]) -> dict[str, Any]:
    b = branches.get(c.branch_id or 0)
    return {
        "id": c.id, "name": c.name, "kind": c.kind, "location": c.location, "brand": c.brand, "model": c.model,
        "host": c.host, "port": c.port, "is_active": c.is_active, "status": c.status if c.is_active else "disabled",
        "branch": {"id": b.id, "name": b.name, "number": b.number} if b else None,
        "last_check_at": c.last_check_at, "last_online_at": c.last_online_at, "offline_since": c.offline_since,
        "last_error": c.last_error, "device_info": c.device_info, "note": c.note,
        "station_url": f"/camera-station/{c.station_token}" if c.station_token else None,
    }  # fmt: skip


async def _branches(db: AsyncSession, ids: set[int]) -> dict[int, Branch]:
    ids.discard(0)
    return {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_(ids)))).all()} if ids else {}


async def _get(db: AsyncSession, cid: int) -> Camera:
    c = await db.get(Camera, cid)
    if not c:
        raise error(404, "not_found")
    return c


def _validate(body: CameraIn) -> None:
    if body.kind == "ip" and not (body.host or "").strip():
        raise error(400, "host_required")


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):
    cams = list((await db.scalars(select(Camera))).all())
    act = [c for c in cams if c.is_active]
    by_status: dict[str, int] = defaultdict(int)
    by_kind: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_branch: dict[int, dict[str, int]] = defaultdict(lambda: {"total": 0, "online": 0, "offline": 0})
    for c in act:
        by_status[c.status] += 1
        by_kind[c.kind][c.status] += 1
        if c.branch_id:
            pb = per_branch[c.branch_id]
            pb["total"] += 1
            if c.status in ("online", "offline"):
                pb[c.status] += 1
    branches_total = await db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))) or 0
    names = await _branches(db, set(per_branch))
    bad = sorted(((bid, v) for bid, v in per_branch.items() if v["offline"]), key=lambda x: -x[1]["offline"])[:15]
    since = now() - timedelta(hours=24)
    events = (await db.execute(
        select(CameraEvent, Camera.name).join(Camera, Camera.id == CameraEvent.camera_id).where(CameraEvent.created_at >= since).order_by(CameraEvent.id.desc()).limit(30)
    )).all()  # fmt: skip
    return {
        "total": len(act), "disabled": len(cams) - len(act),
        "online": by_status["online"], "offline": by_status["offline"], "unknown": by_status["unknown"],
        "by_kind": {k: dict(v) for k, v in by_kind.items()},
        "branches_total": branches_total, "branches_covered": len(per_branch),
        "branches_with_offline": sum(1 for v in per_branch.values() if v["offline"]),
        "worst_branches": [{"id": bid, "name": names[bid].name if bid in names else f"#{bid}", "number": names[bid].number if bid in names else None, **v} for bid, v in bad],
        "events": [{"at": e.created_at, "camera_id": e.camera_id, "camera": n, "status": e.status, "message": e.message} for e, n in events],
    }  # fmt: skip


@router.get("")
async def list_cameras(
    q: str | None = None,
    status: str | None = Query(default=None, pattern="^(online|offline|unknown|disabled)$"),
    kind: str | None = Query(default=None, pattern="^(ip|webcam|phone)$"),
    branch_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(can_read),
):
    stmt = select(Camera)
    if q:
        like = f"%{q.strip()}%"
        bids = select(Branch.id).where(Branch.name.ilike(like))
        stmt = stmt.where(or_(Camera.name.ilike(like), Camera.host.ilike(like), Camera.location.ilike(like), Camera.branch_id.in_(bids)))
    if status == "disabled":
        stmt = stmt.where(Camera.is_active.is_(False))
    elif status:
        stmt = stmt.where(Camera.is_active.is_(True), Camera.status == status)
    if kind:
        stmt = stmt.where(Camera.kind == kind)
    if branch_id:
        stmt = stmt.where(Camera.branch_id == branch_id)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list((await db.scalars(stmt.order_by(case((Camera.status == "offline", 0), (Camera.status == "unknown", 1), else_=2), Camera.branch_id, Camera.name).offset((page - 1) * size).limit(size))).all())
    br = await _branches(db, {c.branch_id or 0 for c in rows})
    return {"items": [_out(c, br) for c in rows], "total": total, "page": page, "size": size}


@router.post("", status_code=201)
async def create_camera(body: CameraIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    _validate(body)
    c = Camera(**body.model_dump(), created_by=auth.user.id)
    if c.kind == "ip":
        c.port = c.port or 554
    else:
        c.station_token = secrets.token_urlsafe(18)
    db.add(c)
    await db.flush()
    await audit(db, request, "camera.create", actor=auth.user, entity="camera", entity_id=c.id, data={"name": c.name, "kind": c.kind})
    await db.commit()
    return _out(c, await _branches(db, {c.branch_id or 0}))


@router.put("/{cid}")
async def update_camera(cid: int, body: CameraIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    _validate(body)
    c = await _get(db, cid)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    if c.kind != "ip" and not c.station_token:
        c.station_token = secrets.token_urlsafe(18)
    await audit(db, request, "camera.update", actor=auth.user, entity="camera", entity_id=c.id)
    await db.commit()
    return _out(c, await _branches(db, {c.branch_id or 0}))


@router.delete("/{cid}", status_code=204)
async def delete_camera(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    c = await _get(db, cid)
    await audit(db, request, "camera.delete", actor=auth.user, entity="camera", entity_id=c.id, data={"name": c.name})
    await db.delete(c)
    await db.commit()


@router.post("/{cid}/check")
async def check_now(cid: int, request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_manage)):
    c = await _get(db, cid)
    if c.kind != "ip" or not c.host:
        raise error(400, "not_ip_camera")
    err = await svc.probe(c.host, c.port or 554)
    c.fail_count = max(c.fail_count, svc.FAILS_TO_OFFLINE - 1)  # qo'lda tekshiruv natijasi darhol ko'rinsin
    svc.apply_result(db, c, err is None, err, now())
    await db.commit()
    return _out(c, await _branches(db, {c.branch_id or 0}))


@router.post("/{cid}/station-token")
async def new_station_token(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    """Stansiya havolasini yangilash (eski havola ishlamay qoladi)."""
    c = await _get(db, cid)
    if c.kind == "ip":
        raise error(400, "not_station")
    c.station_token = secrets.token_urlsafe(18)
    await audit(db, request, "camera.token", actor=auth.user, entity="camera", entity_id=c.id)
    await db.commit()
    return {"station_url": f"/camera-station/{c.station_token}"}


@router.get("/{cid}/snapshot")
async def snapshot(cid: int, request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):
    await _get(db, cid)
    data = await request.app.state.redis.get(f"cam:snap:{cid}")
    if not data:
        raise error(404, "no_snapshot")
    raw = base64.b64decode(data)
    return Response(raw, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/{cid}/events")
async def camera_events(cid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_read)):
    await _get(db, cid)
    rows = (await db.scalars(select(CameraEvent).where(CameraEvent.camera_id == cid).order_by(CameraEvent.id.desc()).limit(100))).all()
    return [{"at": e.created_at, "status": e.status, "message": e.message} for e in rows]


@router.get("/import/template.xlsx")
async def import_template(_: AuthContext = Depends(can_manage)):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Kameralar"
    ws.append(["Filial raqami", "Filial nomi", "Kamera nomi", "Joyi", "IP yoki domen", "Port", "Brend", "Model"])
    ws.append([1, "", "Kirish", "Kirish eshigi", "192.168.1.64", 554, "Hikvision", "DS-2CD1023"])
    for col, w in zip("ABCDEFGH", (14, 30, 22, 20, 22, 8, 14, 16), strict=True):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="kameralar-shablon.xlsx"'})


@router.post("/import")
async def import_cameras(request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(can_manage)):
    """Excel'dan ommaviy qo'shish (1000+ filial): filial raqami yoki nomi bo'yicha bog'lanadi; bir xil IP:port qayta qo'shilmaydi."""
    from openpyxl import load_workbook

    raw = await file.read(5_000_001)
    if len(raw) > 5_000_000:
        raise error(413, "file_too_large")
    try:
        ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
    except Exception:  # noqa: BLE001
        raise error(400, "bad_file") from None
    branches = list((await db.scalars(select(Branch))).all())
    by_num = {b.number: b.id for b in branches if b.number is not None}
    by_name = {b.name.strip().lower(): b.id for b in branches}
    seen = {(c.host, c.port) for c in (await db.scalars(select(Camera).where(Camera.kind == "ip"))).all()}
    added, skipped, errors = 0, 0, []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not any(row):
            continue
        num, bname, name, loc, host, port, brand, model = (list(row) + [None] * 8)[:8]
        host = str(host or "").strip()
        if not host:
            errors.append({"row": i, "error": "host_required"})
            continue
        try:
            port = int(port or 554)
        except (TypeError, ValueError):
            errors.append({"row": i, "error": "bad_port"})
            continue
        bid = None
        if num not in (None, ""):
            try:
                bid = by_num.get(int(num))
            except (TypeError, ValueError):
                bid = None
        if bid is None and bname:
            bid = by_name.get(str(bname).strip().lower())
        if bid is None and (num or bname):
            errors.append({"row": i, "error": "branch_not_found"})
            continue
        if (host, port) in seen:
            skipped += 1
            continue
        seen.add((host, port))
        db.add(Camera(branch_id=bid, name=str(name or host)[:120], location=(str(loc)[:120] if loc else None), host=host[:200], port=port,
                      brand=(str(brand)[:40] if brand else None), model=(str(model)[:80] if model else None), kind="ip", created_by=auth.user.id))  # fmt: skip
        added += 1
    await audit(db, request, "camera.import", actor=auth.user, entity="camera", data={"added": added, "skipped": skipped, "errors": len(errors)})
    await db.commit()
    return {"added": added, "skipped": skipped, "errors": errors[:200]}


@router.post("/scan")
async def scan_now(request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(can_manage)):
    """Barcha kameralarni hozir tekshirish (odatda server buni har 5 daqiqada o'zi qiladi)."""
    notes = await svc.scan(db, now())
    await db.commit()
    await deliver(request.app, notes)
    return await summary(db, _)


# --- Kamera stansiyasi (kompyuter / telefon): qurilmada havola ochiladi, foydalanuvchi o'zi yoqadi ---


async def _station(db: AsyncSession, token: str) -> Camera:
    c = await db.scalar(select(Camera).where(Camera.station_token == token))
    if not c or not c.is_active:
        raise error(404, "not_found")
    return c


@public_router.get("/{token}")
async def station_info(token: str, db: AsyncSession = Depends(get_session)):
    c = await _station(db, token)
    b = await db.get(Branch, c.branch_id) if c.branch_id else None
    return {"name": c.name, "kind": c.kind, "branch": b.name if b else None, "location": c.location, "interval": 60}


class BeatIn(BaseModel):
    device: str | None = Field(default=None, max_length=200)
    snapshot: str | None = Field(default=None, max_length=MAX_SNAP * 2)  # base64 JPEG (kichik kadr)


@public_router.post("/{token}/beat")
async def station_beat(token: str, body: BeatIn, request: Request, db: AsyncSession = Depends(get_session)):
    redis = request.app.state.redis
    key = f"rl:cambeat:{token}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, 60)
    if n > 6:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(key), 1))
    c = await _station(db, token)
    moment = now()
    changed = svc.apply_result(db, c, True, None, moment)
    if body.device:
        c.device_info = body.device[:200]
    if body.snapshot:
        try:
            raw = base64.b64decode(body.snapshot.split(",", 1)[-1], validate=True)
        except ValueError:
            raise error(400, "bad_snapshot") from None
        if len(raw) > MAX_SNAP or not raw.startswith(b"\xff\xd8"):
            raise error(400, "bad_snapshot")
        await redis.set(f"cam:snap:{c.id}", base64.b64encode(raw), ex=SNAP_TTL)
    notes = await svc.notes_for(db, {"online": [c]}) if changed == "online" else []
    await db.commit()
    await deliver(request.app, notes)
    return {"ok": True, "status": c.status}


@public_router.post("/{token}/stop")
async def station_stop(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    """Foydalanuvchi stansiyani o'zi to'xtatdi: oflayn deb belgilanadi, kadr o'chiriladi."""
    c = await _station(db, token)
    if c.status != "offline":
        c.status, c.offline_since, c.last_error, c.last_check_at = "offline", now(), "stopped", now()
        db.add(CameraEvent(camera_id=c.id, status="offline", message="stopped"))
    await request.app.state.redis.delete(f"cam:snap:{c.id}")
    await db.commit()
    return {"ok": True}
