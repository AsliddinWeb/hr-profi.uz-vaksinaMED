"""Eski tizimdan migratsiya: paketlar (yuklash, moslashtirish, dry-run, import, orqaga qaytarish), shablonlar, nazorat summalari."""

import asyncio
import csv
import io
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.migration import MigrationBatch, MigrationCheck, MigrationMapping
from app.models.org import Branch
from app.rbac import matches
from app.services import migration as svc
from app.services.audit import audit
from app.services.uploads import storage_key
from app.services.xlsx_safe import csv_safe
from app.timeutil import now

router = APIRouter(prefix="/v1/migration", tags=["migration"])


async def Manage(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not matches(auth.permissions, "migration.manage"):
        raise error(403, "forbidden")
    return auth


def _batch_out(b: MigrationBatch, users: dict[int, str] | None = None) -> dict[str, Any]:
    return {
        "id": b.id, "dataset": b.dataset, "filename": b.filename, "status": b.status, "headers": b.headers, "mapping": b.mapping, "options": b.options, "summary": b.summary,
        "issue_count": len(b.issues or []), "created_by": (users or {}).get(b.created_by or 0), "created_at": b.created_at, "applied_at": b.applied_at, "rolled_back_at": b.rolled_back_at,
    }  # fmt: skip


async def _users(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    from app.models.auth import User

    ids2 = {i for i in ids if i}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()} if ids2 else {}


async def _get(db: AsyncSession, bid: int, *, lock: bool = False) -> MigrationBatch:
    stmt = select(MigrationBatch).where(MigrationBatch.id == bid)
    b = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not b:
        raise error(404, "not_found")
    return b


async def _load(request: Request, b: MigrationBatch) -> tuple[list[str], list[list[Any]]]:
    data = b"".join([c async for c in request.app.state.storage.stream(b.file_key)])
    return await asyncio.to_thread(svc.read_table, b.filename, data)


@router.get("/datasets")
async def datasets(auth: AuthContext = Depends(Manage)):
    return {
        "datasets": {k: [{"key": f, "required": req} for f, req in v] for k, v in svc.FIELDS.items()},
        "match_by": ["legacy_id", "employee_no", "pinfl", "phone"],
        "metrics": list(svc.METRICS),
        "max_rows": svc.MAX_ROWS,
    }


# --- Paketlar ---------------------------------------------------------------------------


@router.get("/batches")
async def batches(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    rows = (await db.scalars(select(MigrationBatch).order_by(MigrationBatch.id.desc()).limit(200))).all()
    users = await _users(db, {b.created_by for b in rows})
    return [_batch_out(b, users) for b in rows]


@router.post("/batches", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), dataset: str = Form(...), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    who = {auth.user.id: auth.user.full_name}
    if dataset not in svc.FIELDS:
        raise error(400, "unknown_dataset")
    raw = await file.read(svc.MAX_BYTES + 1)
    if len(raw) > svc.MAX_BYTES:
        raise error(413, "file_too_large", max_mb=svc.MAX_BYTES // (1024 * 1024))
    name = (file.filename or "import.csv")[:200]
    try:
        headers, rows = await asyncio.to_thread(svc.read_table, name, raw)
    except ValueError:
        raise error(415, "file_format") from None
    except Exception:  # noqa: BLE001
        raise error(400, "file_unreadable") from None
    if not rows:
        raise error(400, "file_empty")
    if len(rows) > svc.MAX_ROWS[dataset]:
        raise error(400, "too_many_rows", max=svc.MAX_ROWS[dataset])
    b = MigrationBatch(dataset=dataset, filename=name, file_key="pending", status="draft", headers=headers, summary={"rows": len(rows)}, created_by=auth.user.id)
    db.add(b)
    await db.flush()
    b.file_key = storage_key(f"migration/{b.id}", name)
    await request.app.state.storage.put(b.file_key, raw, "application/octet-stream")
    b.mapping = svc.suggest_mapping(dataset, headers)
    await audit(db, request, "migration.upload", actor=auth.user, entity="migration_batch", entity_id=b.id, data={"dataset": dataset, "file": name, "rows": len(rows)})
    await db.commit()
    await db.refresh(b)
    return {**_batch_out(b, who), "sample": svc.sample(headers, rows), "suggested": b.mapping}


@router.get("/batches/{bid}")
async def batch(bid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    b = await _get(db, bid)
    out = _batch_out(b, await _users(db, {b.created_by}))
    if b.status in ("draft", "previewed"):
        headers, rows = await _load(request, b)
        out["sample"] = svc.sample(headers, rows)
    return out


class MappingIn(BaseModel):
    mapping: dict[str, str]
    options: dict[str, Any] = Field(default_factory=dict)


@router.put("/batches/{bid}/mapping")
async def set_mapping(bid: int, body: MappingIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Ustunlarni moslashtiradi va **dry-run** o'tkazadi (bazaga hech narsa yozilmaydi)."""
    who = {auth.user.id: auth.user.full_name}
    b = await _get(db, bid, lock=True)
    if b.status not in ("draft", "previewed"):
        raise error(409, "invalid_transition")
    headers, rows = await _load(request, b)
    svc.check_mapping(b.dataset, body.mapping, headers)
    b.mapping, b.options = body.mapping, {k: v for k, v in body.options.items() if k in ("create_missing", "match_by")}
    await db.commit()
    await db.refresh(b)
    res = await svc.run(db, b, headers, rows, commit=False, actor_id=auth.user.id)
    b.status, b.summary, b.issues = "previewed", res.summary(), res.issues
    await db.commit()
    await db.refresh(b)
    return _batch_out(b, who)


@router.post("/batches/{bid}/apply")
async def apply(bid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    who = {auth.user.id: auth.user.full_name}
    b = await _get(db, bid, lock=True)
    if b.status != "previewed":
        raise error(409, "invalid_transition")
    headers, rows = await _load(request, b)
    res = await svc.run(db, b, headers, rows, commit=True, actor_id=auth.user.id)
    b.status, b.summary, b.issues, b.applied_at = "applied", res.summary(), res.issues, now()
    await audit(db, request, "migration.apply", actor=auth.user, entity="migration_batch", entity_id=b.id, data={"dataset": b.dataset, **{k: v for k, v in res.summary().items() if isinstance(v, int)}})
    await db.commit()
    await db.refresh(b)
    return _batch_out(b, who)


@router.post("/batches/{bid}/rollback")
async def rollback(bid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    who = {auth.user.id: auth.user.full_name}
    b = await _get(db, bid, lock=True)
    if b.status != "applied":
        raise error(409, "invalid_transition")
    removed = await svc.rollback_batch(db, b)
    b.status, b.rolled_back_at = "rolled_back", now()
    b.summary = {**(b.summary or {}), "rolled_back": removed}
    await audit(db, request, "migration.rollback", actor=auth.user, entity="migration_batch", entity_id=b.id, data={"dataset": b.dataset, **removed})
    await db.commit()
    await db.refresh(b)
    return _batch_out(b, who)


@router.delete("/batches/{bid}", status_code=204)
async def delete_batch(bid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    b = await _get(db, bid, lock=True)
    if b.status not in ("draft", "previewed", "rolled_back"):
        raise error(409, "invalid_transition")
    key = b.file_key
    await audit(db, request, "migration.delete", actor=auth.user, entity="migration_batch", entity_id=b.id, data={"file": b.filename})
    await db.delete(b)
    await db.commit()
    await request.app.state.storage.delete(key)


@router.get("/batches/{bid}/issues.csv")
async def issues_csv(bid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    b = await _get(db, bid)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "status", "code", "field", "name"])
    for i in b.issues or []:
        w.writerow([i["row"], i["status"], i["code"], i.get("field") or "", csv_safe(i.get("name") or "")])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="migration-{b.id}-issues.csv"'})


@router.get("/batches/{bid}/issues")
async def issues(bid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    b = await _get(db, bid)
    return {"total": len(b.issues or []), "items": b.issues or []}


# --- Moslashtirish shablonlari -------------------------------------------------------------


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dataset: str = Field(pattern="^(employees|attendance)$")
    mapping: dict[str, str]
    options: dict[str, Any] = Field(default_factory=dict)


def _tpl_out(m: MigrationMapping) -> dict[str, Any]:
    return {"id": m.id, "name": m.name, "dataset": m.dataset, "mapping": m.mapping, "options": m.options, "updated_at": m.updated_at}


def _check_tpl(body: TemplateIn) -> None:
    allowed = {k for k, _ in svc.FIELDS[body.dataset]}
    bad = [k for k in body.mapping if k not in allowed]
    if bad:
        raise error(400, "unknown_field", field=bad[0])


@router.get("/templates")
async def templates(dataset: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    stmt = select(MigrationMapping).order_by(MigrationMapping.name)
    if dataset:
        stmt = stmt.where(MigrationMapping.dataset == dataset)
    return [_tpl_out(m) for m in (await db.scalars(stmt)).all()]


@router.get("/templates/{tid}")
async def template(tid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    m = await db.get(MigrationMapping, tid)
    if not m:
        raise error(404, "not_found")
    return _tpl_out(m)


@router.post("/templates", status_code=201)
async def create_template(body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    _check_tpl(body)
    m = MigrationMapping(name=body.name.strip(), dataset=body.dataset, mapping=body.mapping, options=body.options, created_by=auth.user.id)
    db.add(m)
    await db.flush()
    await audit(db, request, "migration.template_create", actor=auth.user, entity="migration_mapping", entity_id=m.id, data={"name": m.name})
    await db.commit()
    await db.refresh(m)
    return _tpl_out(m)


@router.put("/templates/{tid}")
async def update_template(tid: int, body: TemplateIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    m = await db.get(MigrationMapping, tid)
    if not m:
        raise error(404, "not_found")
    _check_tpl(body)
    m.name, m.dataset, m.mapping, m.options = body.name.strip(), body.dataset, body.mapping, body.options
    await audit(db, request, "migration.template_update", actor=auth.user, entity="migration_mapping", entity_id=m.id, data={"name": m.name})
    await db.commit()
    await db.refresh(m)
    return _tpl_out(m)


@router.delete("/templates/{tid}", status_code=204)
async def delete_template(tid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    m = await db.get(MigrationMapping, tid)
    if not m:
        raise error(404, "not_found")
    await audit(db, request, "migration.template_delete", actor=auth.user, entity="migration_mapping", entity_id=m.id, data={"name": m.name})
    await db.delete(m)
    await db.commit()


# --- Nazorat summalari va solishtirish -----------------------------------------------------


class CheckIn(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    metric: str = Field(pattern="^(employees_total|employees_active|employees_dismissed|attendance_records|attendance_hours)$")
    period: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    branch_id: int | None = None
    expected: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    tolerance: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)
    note: str | None = Field(default=None, max_length=1000)


async def _check_refs(db: AsyncSession, body: CheckIn) -> None:
    if body.metric.startswith("attendance") and not body.period:
        raise error(400, "period_required")
    if body.branch_id is not None and not await db.get(Branch, body.branch_id):
        raise error(400, "unknown_branch")


def _check_out(c: MigrationCheck) -> dict[str, Any]:
    return {"id": c.id, "label": c.label, "metric": c.metric, "period": c.period, "branch_id": c.branch_id, "expected": float(c.expected), "tolerance": float(c.tolerance), "note": c.note}


@router.get("/reconcile")
async def reconcile(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    return await svc.reconcile(db)


@router.get("/checks/{cid}")
async def get_check(cid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    c = await db.get(MigrationCheck, cid)
    if not c:
        raise error(404, "not_found")
    return _check_out(c)


@router.post("/checks", status_code=201)
async def create_check(body: CheckIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    await _check_refs(db, body)
    c = MigrationCheck(**body.model_dump(), created_by=auth.user.id)
    if not c.metric.startswith("attendance"):
        c.period = None
    db.add(c)
    await db.flush()
    await audit(db, request, "migration.check_create", actor=auth.user, entity="migration_check", entity_id=c.id, data={"label": c.label})
    await db.commit()
    return _check_out(c)


@router.put("/checks/{cid}")
async def update_check(cid: int, body: CheckIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    c = await db.get(MigrationCheck, cid)
    if not c:
        raise error(404, "not_found")
    await _check_refs(db, body)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    if not c.metric.startswith("attendance"):
        c.period = None
    await audit(db, request, "migration.check_update", actor=auth.user, entity="migration_check", entity_id=c.id, data={"label": c.label})
    await db.commit()
    return _check_out(c)


@router.delete("/checks/{cid}", status_code=204)
async def delete_check(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    c = await db.get(MigrationCheck, cid)
    if not c:
        raise error(404, "not_found")
    await audit(db, request, "migration.check_delete", actor=auth.user, entity="migration_check", entity_id=c.id, data={"label": c.label})
    await db.delete(c)
    await db.commit()


@router.post("/checks/import", status_code=201)
async def import_checks(request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """CSV/Excel: label, metric, period, branch (filial №), expected, tolerance."""
    raw = await file.read(2 * 1024 * 1024)
    try:
        items = await asyncio.to_thread(svc.parse_checks_csv, raw)
    except ValueError:
        raise error(415, "file_format") from None
    by_num = {b.number: b.id for b in (await db.scalars(select(Branch))).all() if b.number is not None}
    created = 0
    for it in items:
        bid = None
        if it["branch"]:
            num = it["branch"].lstrip("№# ")
            bid = by_num.get(int(num)) if num.isdigit() else None
            if bid is None:
                raise error(400, "unknown_branch", value=it["branch"])
        db.add(MigrationCheck(label=it["label"], metric=it["metric"], period=it["period"], branch_id=bid, expected=it["expected"], tolerance=it["tolerance"], created_by=auth.user.id))
        created += 1
    await audit(db, request, "migration.checks_import", actor=auth.user, entity="migration_check", data={"created": created})
    await db.commit()
    return {"created": created}


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    """Boshqaruv sahifasi uchun: paketlar soni va solishtirish holati."""
    n = await db.scalar(select(func.count()).select_from(MigrationBatch).where(MigrationBatch.status == "applied")) or 0
    rec = await svc.reconcile(db)
    return {"applied_batches": n, "checks": rec["total"], "matched": rec["matched"], "mismatched": rec["mismatched"]}
