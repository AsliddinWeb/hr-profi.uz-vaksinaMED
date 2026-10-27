"""Integratsiyalar: API kalitlari, tashqi tizimlar uchun ochiq API (savdo/reja, xodimlar, filiallar), savdo hisoboti va filial reyestrini solishtirish."""

import hashlib
import hmac
import re
import secrets
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import plans
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.employees import Employee
from app.models.integrations import ApiKey, BranchDailyMetric
from app.models.org import Branch, Position
from app.rbac import matches
from app.services import pharmacy as ph
from app.services.audit import audit
from app.timeutil import now

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])
ext_router = APIRouter(prefix="/ext/v1", tags=["external-api"])

SCOPES = ("metrics:write", "employees:read", "branches:read")
KEY_RE = re.compile(r"^koshi_([a-z0-9]{8})_([A-Za-z0-9_-]{20,64})$")


def _need(auth: AuthContext, *perms: str) -> None:
    if not any(matches(auth.permissions, p) for p in perms):
        raise error(403, "forbidden")


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _key_out(k: ApiKey) -> dict[str, Any]:
    return {"id": k.id, "name": k.name, "prefix": k.prefix, "scopes": k.scopes or [], "is_active": k.is_active, "created_at": k.created_at, "last_used_at": k.last_used_at, "revoked_at": k.revoked_at}


# --- Kalitlarni boshqarish ----------------------------------------------------------------


@router.get("/keys")
async def list_keys(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "integrations.read", "integrations.manage")
    return [_key_out(k) for k in (await db.scalars(select(ApiKey).order_by(ApiKey.id.desc()))).all()]


class KeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(min_length=1, max_length=len(SCOPES))


@router.post("/keys", status_code=201)
async def create_key(body: KeyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Yangi API kaliti. To'liq kalit FAQAT shu javobda ko'rsatiladi (keyin faqat prefiks)."""
    _need(auth, "integrations.manage")
    plans.require_feature("integrations")  # PREMIUM
    if any(s not in SCOPES for s in body.scopes):
        raise error(400, "scope_invalid")
    prefix = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(8))
    secret = secrets.token_urlsafe(32)
    k = ApiKey(name=body.name.strip(), prefix=prefix, key_hash=_hash(secret), scopes=sorted(set(body.scopes)), created_by=auth.user.id)
    db.add(k)
    await db.flush()
    await audit(db, request, "integrations.key_create", actor=auth.user, entity="api_key", entity_id=k.id, data={"name": k.name, "scopes": k.scopes})
    await db.commit()
    return {**_key_out(k), "key": f"koshi_{prefix}_{secret}"}


@router.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need(auth, "integrations.manage")
    k = await db.get(ApiKey, key_id)
    if not k:
        raise error(404, "not_found")
    if k.is_active:
        k.is_active, k.revoked_at = False, now()
        await audit(db, request, "integrations.key_revoke", actor=auth.user, entity="api_key", entity_id=k.id)
        await db.commit()
    return _key_out(k)


# --- Ochiq (tashqi) API: kalit bilan ------------------------------------------------------


def api_key(scope: str):
    async def dep(x_api_key: str | None = Header(default=None), db: AsyncSession = Depends(get_session)) -> ApiKey:
        m = KEY_RE.match(x_api_key or "")
        k = await db.scalar(select(ApiKey).where(ApiKey.prefix == m.group(1))) if m else None
        if not m or k is None or not k.is_active or not hmac.compare_digest(k.key_hash, _hash(m.group(2))):
            raise error(401, "api_key_invalid")
        if scope not in (k.scopes or []):
            raise error(403, "scope_forbidden", scope=scope)
        moment = now()
        if k.last_used_at is None or moment - k.last_used_at > timedelta(minutes=1):
            k.last_used_at = moment
            await db.commit()
        return k

    return dep


class MetricItem(BaseModel):
    branch_number: int = Field(ge=1)
    date: date
    sales: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    plan: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    receipts: int | None = Field(default=None, ge=0)


class MetricsIn(BaseModel):
    items: list[MetricItem] = Field(min_length=1, max_length=2000)


@ext_router.post("/metrics/daily")
async def push_metrics(body: MetricsIn, db: AsyncSession = Depends(get_session), key: ApiKey = Depends(api_key("metrics:write"))):
    """Tashqi tizim (Dori/FOM) filialning kunlik savdosi va rejasini yuboradi; takror yuborilsa yangilanadi."""
    branches = {b.number: b.id for b in (await db.scalars(select(Branch).where(Branch.number.in_({i.branch_number for i in body.items})))).all()}
    unknown = sorted({i.branch_number for i in body.items if i.branch_number not in branches})
    saved = 0
    today = now().date()
    for it in body.items:
        bid = branches.get(it.branch_number)
        if bid is None:
            continue
        if it.date > today + timedelta(days=1):
            raise error(400, "date_future", date=str(it.date))
        row = await db.scalar(select(BranchDailyMetric).where(BranchDailyMetric.branch_id == bid, BranchDailyMetric.metric_date == it.date))
        if row is None:
            row = BranchDailyMetric(branch_id=bid, metric_date=it.date)
            db.add(row)
        row.sales, row.plan, row.receipts, row.source, row.updated_at = it.sales, it.plan, it.receipts, f"api:{key.prefix}", now()
        saved += 1
    await db.commit()
    return {"saved": saved, "unknown_branches": unknown}


@ext_router.get("/branches")
async def ext_branches(db: AsyncSession = Depends(get_session), _: ApiKey = Depends(api_key("branches:read"))):
    rows = (await db.scalars(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.number))).all()
    return [{"number": b.number, "name": b.name, "address": b.address, "district": b.district, "phone": b.phone} for b in rows]


@ext_router.get("/employees")
async def ext_employees(branch_number: int | None = None, page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_session), _: ApiKey = Depends(api_key("employees:read"))):
    """Minimal ma'lumot: shaxsiy hujjat, telefon va maosh chiqarilmaydi."""
    stmt = select(Employee, Branch.number, Position.name).join(Branch, Branch.id == Employee.branch_id, isouter=True).join(Position, Position.id == Employee.position_id, isouter=True).where(Employee.status == "active")
    if branch_number is not None:
        stmt = stmt.where(Branch.number == branch_number)
    rows = (await db.execute(stmt.order_by(Employee.id).offset((page - 1) * size).limit(size))).all()
    return {"page": page, "size": size, "items": [{"employee_no": e.employee_no, "full_name": e.full_name, "position": pos, "branch_number": num, "hire_date": e.hire_date} for e, num, pos in rows]}


# --- Savdo hisoboti (ichki) ---------------------------------------------------------------


@router.get("/metrics")
async def metrics_report(start: date, end: date, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Filial bo'yicha savdo va reja bajarilishi, xodim yetishmasligi bilan birga: reja past + xodim yetishmaydigan filiallar birinchi."""
    _need(auth, "integrations.read", "integrations.manage")
    if end < start or (end - start).days > 400:
        raise error(400, "range_invalid", max_days=400)
    agg = (await db.execute(
        select(BranchDailyMetric.branch_id, func.sum(BranchDailyMetric.sales), func.sum(BranchDailyMetric.plan), func.count(), func.max(BranchDailyMetric.metric_date))
        .where(BranchDailyMetric.metric_date >= start, BranchDailyMetric.metric_date <= end).group_by(BranchDailyMetric.branch_id)
    )).all()  # fmt: skip
    ids = [r[0] for r in agg]
    if not ids:
        return {"start": start, "end": end, "items": [], "totals": {"sales": 0, "plan": 0, "attainment": None}}
    branches = {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_(ids)))).all()}
    emps = (await db.scalars(select(Employee).where(Employee.status == "active", Employee.branch_id.in_(ids)))).all()
    pos_roles = {pid: ph.role_of(name) for pid, name in (await ph.positions_map(db)).items()}
    by_branch: dict[int, list[Employee]] = {}
    for e in emps:
        by_branch.setdefault(e.branch_id, []).append(e)  # type: ignore[arg-type]
    items = []
    for bid, sales, plan, days, last in agg:
        b = branches[bid]
        counts = ph.team_counts(b, by_branch.get(bid, []), pos_roles)
        gaps = ph.gaps(b, counts)
        att = round(float(sales) / float(plan) * 100, 1) if plan and float(plan) > 0 else None
        items.append({
            "branch": {"id": bid, "number": b.number, "name": b.name}, "sales": float(sales), "plan": float(plan) if plan is not None else None, "attainment": att, "days": days, "last_date": last,
            "staff_gaps": gaps, "at_risk": bool(gaps) and att is not None and att < 90,
        })  # fmt: skip
    items.sort(key=lambda x: (x["attainment"] is None, x["attainment"] if x["attainment"] is not None else 0))
    tp = sum(i["plan"] or 0 for i in items)
    ts = sum(i["sales"] for i in items)
    return {"start": start, "end": end, "items": items, "totals": {"sales": ts, "plan": tp, "attainment": round(ts / tp * 100, 1) if tp else None}}


# --- Filial reyestrini solishtirish -------------------------------------------------------


class ExtBranch(BaseModel):
    number: int | None = Field(default=None, ge=1, le=999_999)
    name: str = Field(min_length=1, max_length=160)
    address: str | None = Field(default=None, max_length=300)


class ReconcileIn(BaseModel):
    rows: list[ExtBranch] = Field(min_length=1, max_length=3000)


def _norm(s: str | None) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", (s or "").lower())


@router.post("/reconcile")
async def reconcile(body: ReconcileIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Tashqi ro'yxat (IT, FOM, ochilishlar ro'yxati) bilan tizimdagi faol filiallarni solishtiradi. Hech narsa o'zgartirilmaydi."""
    _need(auth, "integrations.read", "integrations.manage")
    system = list((await db.scalars(select(Branch).where(Branch.is_active.is_(True)))).all())
    by_num = {b.number: b for b in system if b.number}
    by_name = {_norm(b.name): b for b in system}
    seen_nums: dict[int, int] = {}
    matched: list[dict[str, Any]] = []
    only_ext, mismatch = [], []
    used: set[int] = set()
    for r in body.rows:
        if r.number is not None:
            seen_nums[r.number] = seen_nums.get(r.number, 0) + 1
        b = by_num.get(r.number) if r.number is not None else None
        how = "number"
        if b is None:
            b = by_name.get(_norm(r.name))
            how = "name"
        if b is None:
            only_ext.append({"number": r.number, "name": r.name, "address": r.address})
            continue
        used.add(b.id)
        entry = {"number": b.number, "system_name": b.name, "external_name": r.name, "by": how}
        if _norm(b.name) != _norm(r.name):
            mismatch.append({**entry, "kind": "name"})
        elif how == "name" and r.number is not None and b.number != r.number:
            mismatch.append({**entry, "kind": "number", "external_number": r.number})
        else:
            matched.append(entry)
    only_sys = [{"number": b.number, "name": b.name} for b in sorted(system, key=lambda x: (x.number or 10**9, x.name)) if b.id not in used]
    return {
        "external_total": len(body.rows), "system_total": len(system), "matched": len(matched), "mismatch": mismatch, "only_external": only_ext, "only_system": only_sys,
        "duplicates_external": sorted(n for n, c in seen_nums.items() if c > 1),
    }  # fmt: skip

