"""Koordinator checklist: shablonlar, filialga borish (GPS), to'ldirish, qamrov, reyting, trend."""

from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.checklists import ChecklistFile, ChecklistTemplate, ChecklistVisit
from app.models.org import Branch
from app.services import checklists as svc
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/checklists", tags=["checklists"])
MAX_FILES = 40


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Access = require_any("checklists.own", "checklists.read", "checklists.manage")
Manager = require_any("checklists.manage")


# --- Shablonlar -------------------------------------------------------------------------


class ItemIn(BaseModel):
    id: str | None = Field(default=None, max_length=16)
    section: str | None = Field(default=None, max_length=80)
    text: str = Field(min_length=1, max_length=300)
    kind: str = Field(default="yesno", pattern="^(yesno|score)$")
    weight: int = Field(default=1, ge=1, le=10)
    required: bool = True
    critical: bool = False


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=300)
    items: list[ItemIn]
    is_active: bool = True


def _tpl_out(t: ChecklistTemplate, used: int = 0, with_items: bool = True) -> dict[str, Any]:
    out = {"id": t.id, "name": t.name, "description": t.description, "is_active": t.is_active, "item_count": len(t.items or []), "used": used}
    if with_items:
        out["items"] = t.items
    return out


@router.get("/templates")
async def templates(all: bool = False, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    stmt = select(ChecklistTemplate).order_by(ChecklistTemplate.name)
    if not (all and svc.can_manage(auth)):
        stmt = stmt.where(ChecklistTemplate.is_active.is_(True))
    rows = (await db.scalars(stmt)).all()
    used = dict((await db.execute(select(ChecklistVisit.template_id, func.count()).group_by(ChecklistVisit.template_id))).all())
    return [_tpl_out(t, used.get(t.id, 0), with_items=False) for t in rows]


@router.get("/templates/{tpl_id}")
async def template(tpl_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    t = await db.get(ChecklistTemplate, tpl_id)
    if not t or (not t.is_active and not svc.can_manage(auth)):
        raise error(404, "not_found")
    return _tpl_out(t)


@router.post("/templates", status_code=201)
async def create_template(body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    t = ChecklistTemplate(name=body.name.strip(), description=(body.description or "").strip() or None, items=svc.clean_items([i.model_dump() for i in body.items]), is_active=body.is_active)
    db.add(t)
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "template_exists") from None
    await audit(db, request, "checklists.template_create", actor=auth.user, entity="checklist_template", entity_id=t.id, data={"name": t.name, "items": len(t.items)})
    await db.commit()
    return _tpl_out(t)


@router.put("/templates/{tpl_id}")
async def update_template(tpl_id: int, body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    t = await db.get(ChecklistTemplate, tpl_id)
    if not t:
        raise error(404, "not_found")
    t.name, t.description, t.is_active = body.name.strip(), (body.description or "").strip() or None, body.is_active
    t.items = svc.clean_items([i.model_dump() for i in body.items])  # eski tekshiruvlar o'z nusxasini saqlaydi
    try:
        await db.flush()
    except IntegrityError:
        raise error(409, "template_exists") from None
    await audit(db, request, "checklists.template_update", actor=auth.user, entity="checklist_template", entity_id=t.id, data={"name": t.name, "items": len(t.items)})
    await db.commit()
    return _tpl_out(t)


@router.delete("/templates/{tpl_id}", status_code=204)
async def delete_template(tpl_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    t = await db.get(ChecklistTemplate, tpl_id)
    if not t:
        raise error(404, "not_found")
    if await db.scalar(select(func.count()).select_from(ChecklistVisit).where(ChecklistVisit.template_id == t.id)):
        raise error(409, "template_in_use")
    await audit(db, request, "checklists.template_delete", actor=auth.user, entity="checklist_template", entity_id=t.id, data={"name": t.name})
    await db.delete(t)
    await db.commit()


# --- Tekshiruvlar (filialga borish) -----------------------------------------------------


async def _visit(db: AsyncSession, visit_id: int, auth: AuthContext, *, lock: bool = False) -> ChecklistVisit:
    stmt = select(ChecklistVisit).where(ChecklistVisit.id == visit_id)
    v = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not v:
        raise error(404, "not_found")
    if v.coordinator_id == auth.user.id or svc.sees_all(auth):
        return v
    b = await db.get(Branch, v.branch_id) if v.branch_id else None
    if b and b.manager_user_id == auth.user.id and v.status == "submitted":
        return v
    raise error(404, "not_found")


def _owner_draft(auth: AuthContext, v: ChecklistVisit) -> None:
    if v.coordinator_id != auth.user.id and not svc.can_manage(auth):
        raise error(403, "forbidden")
    if v.status != "draft":
        raise error(409, "already_submitted")


@router.get("/branches")
async def my_branches(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Borish mumkin bo'lgan filiallar: o'ziniki (koordinator) yoki hammasi (boshqaruvchi)."""
    stmt = select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.number, Branch.name)
    if not svc.can_manage(auth):
        stmt = stmt.where(Branch.coordinator_user_id == auth.user.id)
    rows = (await db.scalars(stmt)).all()
    return [{"id": b.id, "name": b.name, "number": b.number, "has_geo": b.latitude is not None, "radius": b.geofence_radius_m} for b in rows]


class StartIn(BaseModel):
    branch_id: int
    template_id: int
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    reason: str | None = Field(default=None, max_length=300)


@router.post("/visits", status_code=201)
async def start_visit(body: StartIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    if not (svc.has(auth, "checklists.own") or svc.can_manage(auth)):
        raise error(403, "forbidden")
    b = await db.get(Branch, body.branch_id)
    if not b or not b.is_active:
        raise error(400, "unknown_branch")
    if not (svc.my_branch(auth, b) or svc.can_manage(auth)):
        raise error(403, "not_your_branch")
    tpl = await db.get(ChecklistTemplate, body.template_id)
    if not tpl or not tpl.is_active:
        raise error(400, "unknown_template")
    existing = await db.scalar(select(ChecklistVisit.id).where(ChecklistVisit.coordinator_id == auth.user.id, ChecklistVisit.branch_id == b.id, ChecklistVisit.status == "draft"))
    if existing:
        raise error(409, "draft_exists", id=existing)
    dist, inside = svc.check_geo(b, body.latitude, body.longitude)
    reason = (body.reason or "").strip() or None
    if not inside and not reason:
        raise error(400, "outside_geofence", distance=dist, radius=b.geofence_radius_m)
    v = ChecklistVisit(
        template_id=tpl.id, template_name=tpl.name, branch_id=b.id, coordinator_id=auth.user.id, status="draft", started_at=now(),
        latitude=body.latitude, longitude=body.longitude, distance_m=dist, geo_ok=inside, geo_reason=None if inside else reason, answers=svc.fresh_answers(tpl.items),
    )  # fmt: skip
    db.add(v)
    await db.flush()
    await audit(db, request, "checklists.start", actor=auth.user, entity="checklist_visit", entity_id=v.id, data={"branch_id": b.id, "distance_m": dist, "geo_ok": inside})
    await db.commit()
    return await _detail(db, v, auth)


@router.get("/visits")
async def visits(
    scope: str = Query(default="mine", pattern="^(mine|all|branch)$"),
    status: str | None = Query(default=None, pattern="^(draft|submitted)$"),
    branch_id: int | None = None,
    coordinator_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Access),
):
    V = ChecklistVisit
    conds: list = []
    if scope == "mine":
        conds.append(V.coordinator_id == auth.user.id)
    elif scope == "branch":
        ids = select(Branch.id).where(Branch.manager_user_id == auth.user.id)
        conds += [V.branch_id.in_(ids), V.status == "submitted"]
    elif not svc.sees_all(auth):
        raise error(403, "forbidden")
    if status:
        conds.append(V.status == status)
    if branch_id:
        conds.append(V.branch_id == branch_id)
    if coordinator_id:
        conds.append(V.coordinator_id == coordinator_id)
    if start or end:
        s_dt, e_dt = svc.range_dt(start or date(2000, 1, 1), end or date(2100, 1, 1))
        conds += [V.started_at >= s_dt, V.started_at < e_dt]
    total = await db.scalar(select(func.count()).select_from(V).where(*conds)) or 0
    rows = (await db.scalars(select(V).where(*conds).order_by(V.started_at.desc(), V.id.desc()).offset((page - 1) * size).limit(size))).all()
    unames = await svc.names(db, {r.coordinator_id for r in rows})
    bnames = await svc.branch_names(db)
    return {"total": total, "page": page, "size": size, "items": [svc.visit_out(v, unames, bnames) for v in rows]}


async def _detail(db: AsyncSession, v: ChecklistVisit, auth: AuthContext) -> dict[str, Any]:
    out = svc.visit_out(v, await svc.names(db, {v.coordinator_id}), await svc.branch_names(db))
    files = (await db.scalars(select(ChecklistFile).where(ChecklistFile.visit_id == v.id).order_by(ChecklistFile.id))).all()
    editable = v.status == "draft" and (v.coordinator_id == auth.user.id or svc.can_manage(auth))
    return {
        **out, "answers": v.answers, "note": v.note, "geo_reason": v.geo_reason, "can": {"edit": editable, "delete": editable},
        "files": [{"id": f.id, "item_id": f.item_id, "filename": f.filename, "mime": f.mime, "size": f.size, "created_at": f.created_at} for f in files],
    }  # fmt: skip


@router.get("/visits/{visit_id}")
async def visit(visit_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    return await _detail(db, await _visit(db, visit_id, auth), auth)


class AnswerIn(BaseModel):
    id: str
    value: int | None = Field(default=None, ge=0, le=5)
    na: bool = False
    comment: str | None = Field(default=None, max_length=500)


class AnswersIn(BaseModel):
    answers: list[AnswerIn] = []
    note: str | None = Field(default=None, max_length=5000)


@router.put("/visits/{visit_id}/answers")
async def save_answers(visit_id: int, body: AnswersIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v = await _visit(db, visit_id, auth, lock=True)
    _owner_draft(auth, v)
    v.answers = svc.apply_answers([dict(a) for a in v.answers], [a.model_dump() for a in body.answers])
    v.note = (body.note or "").strip() or None
    v.score, v.critical_fails = svc.compute(v.answers)  # qoralama bahosi (oldindan ko'rish)
    await db.commit()
    return await _detail(db, v, auth)


@router.post("/visits/{visit_id}/submit")
async def submit(visit_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v = await _visit(db, visit_id, auth, lock=True)
    _owner_draft(auth, v)
    missing = svc.unanswered(v.answers)
    if missing:
        raise error(400, "unanswered", count=len(missing), items=missing)
    v.score, v.critical_fails = svc.compute(v.answers)
    v.status, v.submitted_at = "submitted", now()
    await audit(db, request, "checklists.submit", actor=auth.user, entity="checklist_visit", entity_id=v.id, data={"branch_id": v.branch_id, "score": v.score, "critical_fails": v.critical_fails, "geo_ok": v.geo_ok})
    notes = await svc.notify_submitted(db, v, auth.user, await users_with_permission(db, "checklists.read"))
    await db.commit()
    await deliver(request.app, notes)
    return await _detail(db, v, auth)


@router.delete("/visits/{visit_id}", status_code=204)
async def delete_draft(visit_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v = await _visit(db, visit_id, auth, lock=True)
    _owner_draft(auth, v)
    keys = [f.key for f in (await db.scalars(select(ChecklistFile).where(ChecklistFile.visit_id == v.id))).all()]
    await audit(db, request, "checklists.discard", actor=auth.user, entity="checklist_visit", entity_id=v.id, data={"branch_id": v.branch_id})
    await db.delete(v)
    await db.commit()
    for k in keys:
        await request.app.state.storage.delete(k)


# --- Rasm/fayllar -----------------------------------------------------------------------


@router.post("/visits/{visit_id}/files", status_code=201)
async def upload_file(visit_id: int, request: Request, item_id: str | None = Query(default=None, max_length=16), file: UploadFile = File(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v = await _visit(db, visit_id, auth)
    _owner_draft(auth, v)
    if item_id and item_id not in {a["id"] for a in v.answers}:
        raise error(400, "unknown_item")
    if (await db.scalar(select(func.count()).select_from(ChecklistFile).where(ChecklistFile.visit_id == v.id)) or 0) >= MAX_FILES:
        raise error(409, "too_many_files", max=MAX_FILES)
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"checklists/{v.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    f = ChecklistFile(visit_id=v.id, item_id=item_id, uploaded_by=auth.user.id, key=key, filename=up.filename, mime=up.mime, size=len(up.data))
    db.add(f)
    await db.flush()
    out = {"id": f.id, "item_id": f.item_id, "filename": f.filename, "mime": f.mime, "size": f.size, "created_at": f.created_at}
    await db.commit()
    return out


async def _file(db: AsyncSession, visit_id: int, file_id: int, auth: AuthContext) -> tuple[ChecklistVisit, ChecklistFile]:
    v = await _visit(db, visit_id, auth)
    f = await db.get(ChecklistFile, file_id)
    if not f or f.visit_id != v.id:
        raise error(404, "not_found")
    return v, f


@router.get("/visits/{visit_id}/files/{file_id}")
async def download_file(visit_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    _, f = await _file(db, visit_id, file_id, auth)
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": f"inline; filename*=UTF-8''{quote(f.filename)}"}
    return StreamingResponse(request.app.state.storage.stream(f.key), media_type=f.mime, headers=headers)


@router.delete("/visits/{visit_id}/files/{file_id}", status_code=204)
async def delete_file(visit_id: int, file_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    v, f = await _file(db, visit_id, file_id, auth)
    _owner_draft(auth, v)
    key = f.key
    await db.delete(f)
    await db.commit()
    await request.app.state.storage.delete(key)


# --- Hisobotlar -------------------------------------------------------------------------


def _range(start: date, end: date, max_days: int = 400) -> None:
    if end < start or (end - start).days > max_days:
        raise error(400, "range_invalid", max_days=max_days)


@router.get("/coverage")
async def coverage(start: date, end: date, days: int = Query(default=svc.COVERAGE_DAYS, ge=1, le=90), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    _range(start, end)
    return {"days": days, "items": await svc.coverage(db, auth, start, end, now(), days)}


@router.get("/ranking")
async def ranking(start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    _range(start, end)
    return await svc.ranking(db, auth, start, end)


@router.get("/trend")
async def trend(start: date, end: date, branch_id: int | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    _range(start, end)
    return await svc.trend(db, auth, start, end, branch_id)
