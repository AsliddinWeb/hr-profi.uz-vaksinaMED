"""Apteka tarmog'i: umumiy ko'rinish, filial kartasi, xarita, «xodim kerak», me'yorlar, ma'lumot sifati."""

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch, Position
from app.models.pharmacy import StaffNeed
from app.services import pharmacy as svc
from app.services import recruit_sources as rsvc
from app.services import schedule as sched
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/pharmacy", tags=["pharmacy"])


def require_any(*perms: str):
    async def dep(auth: AuthContext = Depends(get_auth)) -> AuthContext:
        if not any(svc.has(auth, p) for p in perms):
            raise error(403, "forbidden")
        return auth

    return dep


Viewer = require_any("pharmacy.read", "pharmacy.own", "pharmacy.manage")
Manager = require_any("pharmacy.manage")


async def _network(db: AsyncSession, auth: AuthContext, moment: datetime, *, with_today: bool = True, only_active: bool = True, branch_ids: list[int] | None = None):
    """Ko'rinadigan filiallar + jamoa + bugungi holat + so'rovlar: har filial uchun yig'ma."""
    stmt = select(Branch)
    clause = svc.visible_clause(auth)
    if clause is not None:
        stmt = stmt.where(clause)
    if only_active:
        stmt = stmt.where(Branch.is_active.is_(True))
    if branch_ids is not None:
        stmt = stmt.where(Branch.id.in_(branch_ids))
    branches = list((await db.scalars(stmt.order_by(Branch.number.asc().nulls_last(), Branch.name))).all())
    ids = [b.id for b in branches]
    members: dict[int, list[Employee]] = {i: [] for i in ids}
    if ids:
        for e in (await db.scalars(select(Employee).where(Employee.branch_id.in_(ids), Employee.status == "active").order_by(Employee.full_name))).all():
            members[e.branch_id].append(e)  # type: ignore[index]
    pos_roles = await svc.positions_map(db)
    states: dict[int, dict[str, Any]] = {}
    if with_today:
        everyone = [e for lst in members.values() for e in lst]
        states = await svc.today_states(db, everyone, moment) if everyone else {}
    needs = await svc.open_needs(db, ids)
    rows = []
    for b in branches:
        team = members[b.id]
        counts = svc.team_counts(b, team, pos_roles)
        today = svc.summarize_today([states[e.id] for e in team]) if with_today else {}
        flags = svc.branch_flags(b, counts, today, moment, needs.get(b.id, [])) if with_today else []
        rows.append({"branch": b, "team": team, "counts": counts, "today": today, "flags": flags, "needs": needs.get(b.id, []), "gaps": svc.gaps(b, counts)})
    return rows, states, pos_roles


def _branch_brief(b: Branch, names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": b.id, "number": b.number, "name": b.name, "district": b.district, "address": b.address, "phone": b.phone,
        "manager": {"id": b.manager_user_id, "name": names.get(b.manager_user_id or 0)} if b.manager_user_id else None,
        "coordinator": {"id": b.coordinator_user_id, "name": names.get(b.coordinator_user_id or 0)} if b.coordinator_user_id else None,
        "has_geo": b.latitude is not None, "is_active": b.is_active,
    }  # fmt: skip


async def _user_names(db: AsyncSession, branches: list[Branch]) -> dict[int, str]:
    ids = {u for b in branches for u in (b.manager_user_id, b.coordinator_user_id) if u}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}


def _row_out(r: dict[str, Any], names: dict[int, str]) -> dict[str, Any]:
    b: Branch = r["branch"]
    return {
        **_branch_brief(b, names), "norm": svc.norm_of(b), "counts": r["counts"], "gaps": r["gaps"], "headcount": len(r["team"]),
        "today": r["today"], "flags": r["flags"], "severity": svc.severity(r["flags"]),
        "open_needs": sum(n.count for n in r["needs"]), "open_needs_list": [{"id": n.id, "role": n.role, "count": n.count, "urgency": n.urgency} for n in r["needs"]],
        "hours": {"is_24h": b.is_24h, "open": svc.fmt_time(b.open_time), "close": svc.fmt_time(b.close_time)},
    }  # fmt: skip


@router.get("/overview")
async def overview(
    q: str | None = None,
    coordinator_id: int | None = None,
    district: str | None = None,
    only: str | None = Query(default=None, pattern="^(uncovered|short|needs|ok)$"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Viewer),
):
    moment = now()
    rows, _, _ = await _network(db, auth, moment)
    names = await _user_names(db, [r["branch"] for r in rows])
    ql = (q or "").strip().lower()
    base = [
        r for r in rows
        if (not ql or ql in (r["branch"].name or "").lower() or ql == str(r["branch"].number) or ql in (r["branch"].district or "").lower())
        and (not coordinator_id or r["branch"].coordinator_user_id == coordinator_id)
        and (not district or r["branch"].district == district)
    ]  # fmt: skip
    sev = [svc.severity(r["flags"]) for r in base]
    kpis = {
        "branches": len(base),
        "uncovered": sev.count("uncovered"),
        "short": sev.count("short"),
        "ok": sev.count("ok"),
        "with_needs": sum(1 for r in base if r["needs"]),
        "open_needs": sum(n.count for r in base for n in r["needs"]),
        "expected": sum(r["today"]["expected"] for r in base),
        "attended": sum(r["today"]["attended"] for r in base),
        "absent": sum(r["today"]["absent"] for r in base),
        "late": sum(r["today"]["late"] for r in base),
        "headcount": sum(len(r["team"]) for r in base),
    }
    if only:
        base = [r for r in base if (only in r["flags"] if only in ("uncovered", "short", "needs") else svc.severity(r["flags"]) == "ok")]
    order = {"uncovered": 0, "short": 1, "ok": 2}
    base.sort(key=lambda r: (order[svc.severity(r["flags"])], -len(r["gaps"]), r["branch"].number or 10**9))
    total = len(base)
    districts = sorted({r["branch"].district for r in rows if r["branch"].district})
    return {
        "kpis": kpis, "total": total, "page": page, "size": size, "districts": districts,
        "items": [_row_out(r, names) for r in base[(page - 1) * size : page * size]],
    }  # fmt: skip


@router.get("/map")
async def map_points(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    """Ommaviy xarita: koordinatasi bor filiallar, holat rangi bilan."""
    rows, _, _ = await _network(db, auth, now())
    out = []
    for r in rows:
        b: Branch = r["branch"]
        if b.latitude is None or b.longitude is None:
            continue
        out.append({
            "id": b.id, "number": b.number, "name": b.name, "lat": float(b.latitude), "lng": float(b.longitude),
            "severity": svc.severity(r["flags"]), "flags": r["flags"], "headcount": len(r["team"]), "gaps": r["gaps"],
            "here_now": r["today"]["here_now"], "open_needs": sum(n.count for n in r["needs"]),
        })  # fmt: skip
    return out


@router.get("/branches/{branch_id}")
async def card(branch_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    """Filial kartasi: ma'lumot, jamoa (bugungi holat bilan), me'yor, so'rovlar va 7 kunlik qamrov."""
    b = await db.get(Branch, branch_id)
    if not b or not svc.can_see_branch(auth, b):
        raise error(404, "not_found")
    moment = now()
    rows, states, pos_roles = await _network(db, auth, moment, only_active=False, branch_ids=[b.id])
    r = rows[0]
    names = await _user_names(db, [b])
    pos_names = {p.id: p.name for p in (await db.scalars(select(Position))).all()}
    team = []
    for e in r["team"]:
        st = states[e.id]
        role = pos_roles.get(e.position_id or 0, "other")
        if role == "other" and b.manager_user_id and e.user_id == b.manager_user_id:
            role = "manager"
        team.append({
            "employee": {"id": e.id, "employee_no": e.employee_no, "full_name": e.full_name, "phone": e.phone, "has_photo": e.photo_key is not None},
            "position": pos_names.get(e.position_id or 0), "role": role, "status": st["status"], "expected": st["expected"],
            "check_in_at": st["check_in_at"], "check_out_at": st["check_out_at"], "late_minutes": st["late_minutes"],
            "shift": f"{st['shift'].start_time:%H:%M}–{st['shift'].end_time:%H:%M}" if st["shift"] else None,
        })  # fmt: skip
    team.sort(key=lambda t: (["manager", "pharmacist", "intern", "other"].index(t["role"]), t["employee"]["full_name"]))

    # Keyingi 7 kun: har kuni grafik bo'yicha qancha va qaysi lavozimdan ishlaydi
    today = local_date(moment)
    week = []
    if r["team"]:
        resolved = await sched.resolve_range(db, r["team"], today, today + timedelta(days=6))
        for i in range(7):
            d = today + timedelta(days=i)
            c = dict.fromkeys(svc.ALL_ROLES, 0)
            for e in r["team"]:
                if resolved[e.id][i].working and resolved[e.id][i].shift_id is not None:
                    role = pos_roles.get(e.position_id or 0, "other")
                    c["manager" if role == "other" and b.manager_user_id and e.user_id == b.manager_user_id else role] += 1
            week.append({"date": d, "scheduled": sum(c.values()), "by_role": c, "uncovered": b.is_active and c["manager"] + c["pharmacist"] == 0})
    else:
        week = [{"date": today + timedelta(days=i), "scheduled": 0, "by_role": dict.fromkeys(svc.ALL_ROLES, 0), "uncovered": b.is_active} for i in range(7)]

    closed = (await db.scalars(select(StaffNeed).where(StaffNeed.branch_id == b.id, StaffNeed.status != "open").order_by(StaffNeed.id.desc()).limit(5))).all()
    out = _row_out(r, names)
    out |= {
        "team": team, "week": week, "note": b.pharmacy_note, "latitude": float(b.latitude) if b.latitude is not None else None,
        "longitude": float(b.longitude) if b.longitude is not None else None, "geofence_radius_m": b.geofence_radius_m,
        "needs": [_need_out(n, b, {}) for n in r["needs"]], "closed_needs": [_need_out(n, b, {}) for n in closed],
        "can_manage": svc.has(auth, "pharmacy.manage"), "can_request": svc.has(auth, "pharmacy.request") or svc.has(auth, "pharmacy.manage"),
    }  # fmt: skip
    return out


# --- Profil va me'yorlar ----------------------------------------------------------------


class NormIn(BaseModel):
    manager: int = Field(default=1, ge=0, le=20)
    pharmacist: int = Field(default=2, ge=0, le=50)
    intern: int = Field(default=0, ge=0, le=50)


class ProfileIn(BaseModel):
    staff_norm: NormIn
    is_24h: bool = False
    open_time: time | None = None
    close_time: time | None = None
    pharmacy_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _hours(self):
        if not self.is_24h and (self.open_time is None) != (self.close_time is None):
            raise ValueError("hours_pair")
        if self.open_time and self.close_time and self.open_time == self.close_time and not self.is_24h:
            raise ValueError("hours_equal")
        return self


def _apply_profile(b: Branch, p: ProfileIn) -> None:
    b.staff_norm = p.staff_norm.model_dump()
    b.is_24h = p.is_24h
    b.open_time, b.close_time = (None, None) if p.is_24h else (p.open_time, p.close_time)
    b.pharmacy_note = (p.pharmacy_note or "").strip() or None


@router.put("/branches/{branch_id}/profile")
async def update_profile(branch_id: int, body: ProfileIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    b = await db.get(Branch, branch_id)
    if not b:
        raise error(404, "not_found")
    _apply_profile(b, body)
    await audit(db, request, "pharmacy.profile", actor=auth.user, entity="branch", entity_id=b.id, data={"norm": b.staff_norm, "is_24h": b.is_24h})
    await db.commit()
    return {"ok": True}


class BulkIn(BaseModel):
    branch_ids: list[int] | None = None  # None = barcha faol filiallar
    staff_norm: NormIn | None = None
    hours: bool = False  # ish vaqtini ham qo'llash
    is_24h: bool = False
    open_time: time | None = None
    close_time: time | None = None
    only_unset: bool = False  # faqat me'yori hali belgilanmaganlarga
    dry_run: bool = True


@router.post("/norms/bulk")
async def bulk_norms(body: BulkIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manager)):
    """Ko'p filialga bir xil me'yor/ish vaqtini qo'llash (142 ta filialni bir-bir kiritmaslik uchun)."""
    if not body.staff_norm and not body.hours:
        raise error(400, "nothing_to_apply")
    if body.hours:
        ProfileIn(staff_norm=NormIn(), is_24h=body.is_24h, open_time=body.open_time, close_time=body.close_time)  # validatsiya
    stmt = select(Branch).where(Branch.is_active.is_(True))
    if body.branch_ids:
        stmt = stmt.where(Branch.id.in_(body.branch_ids))
    branches = list((await db.scalars(stmt)).all())
    if body.only_unset:
        branches = [b for b in branches if not any(svc.norm_of(b).values())]
    if not body.dry_run:
        for b in branches:
            if body.staff_norm:
                b.staff_norm = body.staff_norm.model_dump()
            if body.hours:
                b.is_24h = body.is_24h
                b.open_time, b.close_time = (None, None) if body.is_24h else (body.open_time, body.close_time)
        await audit(db, request, "pharmacy.bulk_norms", actor=auth.user, entity="branch", data={"count": len(branches), "norm": body.staff_norm.model_dump() if body.staff_norm else None, "hours": body.hours})
        await db.commit()
    return {"branches": len(branches), "applied": not body.dry_run}


# --- «Xodim kerak» ----------------------------------------------------------------------


class NeedIn(BaseModel):
    branch_id: int
    role: str = Field(pattern="^(manager|pharmacist|intern|other)$")
    count: int = Field(default=1, ge=1, le=50)
    urgency: str = Field(default="normal", pattern="^(low|normal|urgent)$")
    needed_from: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    reason_type: str | None = Field(default=None, pattern=f"^({rsvc.REASONS})$")
    shift_note: str | None = Field(default=None, max_length=120)
    position_id: int | None = None


def _need_out(n: StaffNeed, b: Branch | None, names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": n.id, "branch": {"id": b.id, "number": b.number, "name": b.name} if b else None, "role": n.role, "count": n.count,
        "urgency": n.urgency, "needed_from": n.needed_from, "reason": n.reason, "status": n.status, "created_at": n.created_at,
        "created_by": names.get(n.created_by or 0), "closed_at": n.closed_at, "close_note": n.close_note,
        "approval": n.approval, "reason_type": n.reason_type, "shift_note": n.shift_note, "position_id": n.position_id,
        "vacancy_id": n.vacancy_id, "decision_note": n.decision_note,
    }  # fmt: skip


async def _need_branch(db: AsyncSession, auth: AuthContext, branch_id: int, *, for_request: bool) -> Branch:
    b = await db.get(Branch, branch_id)
    if not b or not (svc.sees_all(auth) or svc.can_see_branch(auth, b)):
        raise error(404, "not_found")
    if for_request and not (svc.has(auth, "pharmacy.manage") or (svc.has(auth, "pharmacy.request") and svc.can_see_branch(auth, b))):
        raise error(403, "forbidden")
    return b


@router.get("/needs")
async def list_needs(
    status: str | None = Query(default="open", pattern="^(open|filled|cancelled|all)$"),
    branch_id: int | None = None,
    role: str | None = Query(default=None, pattern="^(manager|pharmacist|intern|other)$"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Viewer),
):
    stmt = select(StaffNeed, Branch).join(Branch, Branch.id == StaffNeed.branch_id)
    clause = svc.visible_clause(auth)
    if clause is not None:
        stmt = stmt.where(clause)
    if status and status != "all":
        stmt = stmt.where(StaffNeed.status == status)
    if branch_id:
        stmt = stmt.where(StaffNeed.branch_id == branch_id)
    if role:
        stmt = stmt.where(StaffNeed.role == role)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await db.execute(stmt.order_by(StaffNeed.status.desc(), StaffNeed.id.desc()).offset((page - 1) * size).limit(size))).all()
    ids = {n.created_by for n, _ in rows if n.created_by}
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}
    return {"total": total, "page": page, "size": size, "items": [_need_out(n, b, names) for n, b in rows]}


@router.get("/needs/suggestions")
async def suggestions(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require_any("pharmacy.request", "pharmacy.manage"))):
    """Me'yordan kam, lekin ochiq so'rovi yo'q filiallar: «xodim kerak»ni bir bosishda yaratish uchun."""
    rows, _, _ = await _network(db, auth, now(), with_today=False)
    out = []
    for r in rows:
        b: Branch = r["branch"]
        requested = {n.role: 0 for n in r["needs"]}
        for n in r["needs"]:
            requested[n.role] += n.count
        for role, gap in r["gaps"].items():
            left = gap - requested.get(role, 0)
            if left > 0:
                out.append({"branch": {"id": b.id, "number": b.number, "name": b.name}, "role": role, "gap": left})
    return out


@router.post("/needs", status_code=201)
async def create_need(body: NeedIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(require_any("pharmacy.request", "pharmacy.manage"))):
    b = await _need_branch(db, auth, body.branch_id, for_request=True)
    if not b.is_active:
        raise error(409, "branch_inactive")
    if body.position_id and not await db.get(Position, body.position_id):
        raise error(400, "unknown_reference")
    # Tasdiq zanjiri: zaveduyushiy/koordinator -> HR menejer -> HRD. Yuqori huquqli yaratuvchi oldingi bosqichlarni o'tkazib yuboradi.
    approval = "approved" if svc.has(auth, "pharmacy.approve") else "pending_hrd" if svc.has(auth, "pharmacy.manage") else "pending_hr"
    n = StaffNeed(
        branch_id=b.id, role=body.role, count=body.count, urgency=body.urgency, needed_from=body.needed_from, reason=(body.reason or "").strip() or None,
        created_by=auth.user.id, status="open", approval=approval, reason_type=body.reason_type, shift_note=(body.shift_note or "").strip() or None, position_id=body.position_id,
    )  # fmt: skip
    db.add(n)
    await db.flush()
    label = f"№{b.number} {b.name}" if b.number else b.name
    targets = set(await users_with_permission(db, "pharmacy.manage")) | ({b.coordinator_user_id} if b.coordinator_user_id else set())
    notes = await notify(
        db, [u for u in targets if u != auth.user.id], "pharmacy.need", link=f"/pharmacy/needs/{n.id}",
        params={"branch": label, "role": body.role, "count": body.count, "urgency": body.urgency},
    )  # fmt: skip
    if approval == "pending_hrd":  # HR yaratgan: HRD tasdig'i kerak
        hrd = [u for u in await users_with_permission(db, "pharmacy.approve") if u != auth.user.id]
        notes += await notify(db, hrd, "need.review", link=f"/pharmacy/needs/{n.id}", params={"branch": label, "role": body.role, "count": body.count})
    if approval == "approved":
        _, vnotes = await rsvc.vacancy_from_need(db, n, b, auth.user.id, now())
        notes += vnotes
    await audit(db, request, "pharmacy.need_create", actor=auth.user, entity="staff_need", entity_id=n.id, data={"branch_id": b.id, "role": n.role, "count": n.count})
    await db.commit()
    await deliver(request.app, notes)
    return _need_out(n, b, {auth.user.id: auth.user.full_name})


async def _need(db: AsyncSession, need_id: int, auth: AuthContext) -> tuple[StaffNeed, Branch]:
    n = await db.get(StaffNeed, need_id)
    b = await db.get(Branch, n.branch_id) if n else None
    if not n or not b or not (svc.sees_all(auth) or svc.can_see_branch(auth, b)):
        raise error(404, "not_found")
    return n, b


def _can_edit_need(auth: AuthContext, n: StaffNeed) -> bool:
    return n.status == "open" and (svc.has(auth, "pharmacy.manage") or n.created_by == auth.user.id)


@router.get("/needs/{need_id}")
async def get_need(need_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    n, b = await _need(db, need_id, auth)
    users = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({x for x in (n.created_by, n.closed_by) if x})))).all()}
    out = _need_out(n, b, users)
    out["closed_by"] = users.get(n.closed_by or 0)
    out["can_edit"] = _can_edit_need(auth, n)
    out["can_close"] = n.status == "open" and svc.has(auth, "pharmacy.manage")
    pending = n.status == "open" and n.approval in ("pending_hr", "pending_hrd")
    out["can_forward"] = pending and n.approval == "pending_hr" and svc.has(auth, "pharmacy.manage")
    out["can_approve"] = pending and svc.has(auth, "pharmacy.approve")
    out["can_reject"] = pending and (svc.has(auth, "pharmacy.approve") or (n.approval == "pending_hr" and svc.has(auth, "pharmacy.manage")))
    return out


@router.put("/needs/{need_id}")
async def update_need(need_id: int, body: NeedIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    n, b = await _need(db, need_id, auth)
    if not _can_edit_need(auth, n):
        raise error(403, "forbidden")
    if body.branch_id != n.branch_id:
        raise error(400, "branch_locked")
    n.role, n.count, n.urgency, n.needed_from, n.reason = body.role, body.count, body.urgency, body.needed_from, (body.reason or "").strip() or None
    n.reason_type, n.shift_note, n.position_id = body.reason_type, (body.shift_note or "").strip() or None, body.position_id
    await audit(db, request, "pharmacy.need_update", actor=auth.user, entity="staff_need", entity_id=n.id)
    await db.commit()
    return _need_out(n, b, {})


class DecideIn(BaseModel):
    action: str = Field(pattern="^(forward|approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)
    recruiter_id: int | None = None


@router.post("/needs/{need_id}/decide")
async def decide_need(need_id: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    """Zayafka tasdig'i. HR menejer: forward/reject (pending_hr). HRD: approve/reject (pending_hr yoki pending_hrd)."""
    n, b = await _need(db, need_id, auth)
    note = (body.note or "").strip() or None
    is_hrd, is_hr = svc.has(auth, "pharmacy.approve"), svc.has(auth, "pharmacy.manage")
    if n.status != "open" or n.approval not in ("pending_hr", "pending_hrd"):
        raise error(409, "already_decided")
    if body.action == "forward" and not (is_hr and n.approval == "pending_hr"):
        raise error(403, "forbidden")
    if body.action == "approve" and not is_hrd:
        raise error(403, "forbidden")
    if body.action == "reject" and not (is_hrd or (is_hr and n.approval == "pending_hr")):
        raise error(403, "forbidden")
    if body.action == "reject" and not note:
        raise error(400, "note_required")
    moment, label, notes = now(), rsvc.branch_label(b), []
    params = {"branch": label, "role": n.role, "count": n.count}
    if body.action == "forward":
        n.approval, n.reviewed_by, n.reviewed_at = "pending_hrd", auth.user.id, moment
        notes = await notify(db, [u for u in await users_with_permission(db, "pharmacy.approve") if u != auth.user.id], "need.review", link=f"/pharmacy/needs/{n.id}", params=params)
    elif body.action == "approve":
        if body.recruiter_id is not None and body.recruiter_id not in set(await users_with_permission(db, "recruit.manage")):
            raise error(400, "unknown_recruiter")
        n.approval, n.approved_by, n.approved_at, n.decision_note = "approved", auth.user.id, moment, note
        _, notes = await rsvc.vacancy_from_need(db, n, b, auth.user.id, moment, body.recruiter_id)
        if n.created_by and n.created_by != auth.user.id:
            notes += await notify(db, [n.created_by], "need.decided", link=f"/pharmacy/needs/{n.id}", params={**params, "result": "tasdiqlandi", "note": note or ""})
    else:
        n.approval, n.approved_by, n.approved_at, n.decision_note = "rejected", auth.user.id, moment, note
        n.status, n.closed_by, n.closed_at, n.close_note = "cancelled", auth.user.id, moment, note
        if n.created_by and n.created_by != auth.user.id:
            notes = await notify(db, [n.created_by], "need.decided", link=f"/pharmacy/needs/{n.id}", params={**params, "result": "rad etildi", "note": note or ""}, severity="danger")
    await audit(db, request, f"pharmacy.need_{body.action}", actor=auth.user, entity="staff_need", entity_id=n.id, data={"vacancy_id": n.vacancy_id}, note=note)
    await db.commit()
    await deliver(request.app, notes)
    return _need_out(n, b, {})


class CloseIn(BaseModel):
    status: str = Field(pattern="^(filled|cancelled)$")
    note: str | None = Field(default=None, max_length=1000)


@router.post("/needs/{need_id}/close")
async def close_need(need_id: int, body: CloseIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Viewer)):
    n, b = await _need(db, need_id, auth)
    if n.status != "open":
        raise error(409, "already_closed")
    owner_cancel = body.status == "cancelled" and n.created_by == auth.user.id
    if not (svc.has(auth, "pharmacy.manage") or owner_cancel):
        raise error(403, "forbidden")
    if body.status == "cancelled" and not (body.note or "").strip():
        raise error(400, "note_required")
    n.status, n.closed_by, n.closed_at, n.close_note = body.status, auth.user.id, now(), (body.note or "").strip() or None
    notes = []
    if body.status == "filled" and n.created_by and n.created_by != auth.user.id:
        notes = await notify(db, [n.created_by], "pharmacy.need_filled", link=f"/pharmacy/needs/{n.id}", params={"branch": f"№{b.number} {b.name}" if b.number else b.name, "role": n.role, "count": n.count})
    await audit(db, request, f"pharmacy.need_{body.status}", actor=auth.user, entity="staff_need", entity_id=n.id, note=n.close_note)
    await db.commit()
    await deliver(request.app, notes)
    return _need_out(n, b, {})


# --- Ma'lumot sifati --------------------------------------------------------------------


@router.get("/quality")
async def quality(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require_any("pharmacy.manage", "pharmacy.read"))):
    """Tarmoq ma'lumotlari to'liqligi: har turdagi muammo soni va filiallar ro'yxati (142 ta filialni tekshirish uchun)."""
    moment = now()
    auth_all = _AllAuth()
    rows, _, _ = await _network(db, auth_all, moment, with_today=False, only_active=False)  # type: ignore[arg-type]
    issues: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        b: Branch = r["branch"]
        for code in svc.quality_issues(b, r["counts"], len(r["team"])):
            issues.setdefault(code, []).append({"id": b.id, "number": b.number, "name": b.name})
    total = len(rows)
    return {
        "branches": total, "active": sum(1 for r in rows if r["branch"].is_active),
        "complete": sum(1 for r in rows if not svc.quality_issues(r["branch"], r["counts"], len(r["team"]))),
        "issues": [{"code": k, "count": len(v), "branches": v[:200]} for k, v in sorted(issues.items(), key=lambda kv: -len(kv[1]))],
    }  # fmt: skip


class _AllAuth:
    """Ma'lumot sifati hisobi hamma filialni qamraydi (ko'rish huquqi tekshiruvi marshrutda)."""

    permissions = frozenset({"pharmacy.read"})
