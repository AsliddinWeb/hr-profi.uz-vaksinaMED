"""Kompetensiyalar bazasi, lavozim profillari (10 qadam), tasdiqlash markazi va kompetensiya dashboardi.

Rekruting zayafkasi faqat tasdiqlangan lavozim profili asosida yaratiladi (company setting `recruit.require_profile`).
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.competency import CATEGORIES, Competency, PositionProfile, ProfileCompetency
from app.models.org import Department, Position
from app.models.recruit import HireRequest, Vacancy
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.audit import audit
from app.services.notifications import deliver, notify, register_template
from app.timeutil import now

router = APIRouter(prefix="/v1/recruit", tags=["recruit"])

STEPS = ("general", "goal", "functions", "education", "hard", "soft", "management", "kpi", "portrait")
METHODS = ("practical", "test", "portfolio", "interview")

register_template("profile.submitted", {"uz": "Lavozim profili tasdiqlashga yuborildi", "ru": "Профиль должности отправлен на утверждение"}, {"uz": "{position} (v{version})", "ru": "{position} (v{version})"}, "info")
register_template("profile.decided", {"uz": "Lavozim profili bo'yicha qaror", "ru": "Решение по профилю должности"}, {"uz": "{position} (v{version}): {result}", "ru": "{position} (v{version}): {result}"}, "info")


def _has(auth: AuthContext, *perms: str) -> bool:
    return any(matches(auth.permissions, p) for p in perms)


def _reader(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not _has(auth, "recruit.read", "recruit.manage", "recruit.approve", "org.read", "org.manage"):
        raise error(403, "forbidden")
    return auth


def _editor(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not _has(auth, "recruit.manage", "org.manage"):
        raise error(403, "forbidden")
    return auth


def _approver(auth: AuthContext) -> bool:
    return _has(auth, "recruit.approve")


# --- Kompetensiyalar ----------------------------------------------------------------------


class CompetencyIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(pattern="^(hard|soft|management|knowledge|experience)$")
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


@router.get("/competencies")
async def list_competencies(
    category: str | None = Query(default=None, pattern="^(hard|soft|management|knowledge|experience)$"),
    q: str | None = None,
    active: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(_reader),
):
    cond = []
    if q:
        cond.append(Competency.name.ilike(f"%{q.strip()}%"))
    if active is not None:
        cond.append(Competency.is_active.is_(active))
    counts = dict((await db.execute(select(Competency.category, func.count()).where(*cond).group_by(Competency.category))).all())
    if category:
        cond.append(Competency.category == category)
    total = await db.scalar(select(func.count()).select_from(Competency).where(*cond)) or 0
    rows = (await db.scalars(select(Competency).where(*cond).order_by(Competency.name).offset((page - 1) * size).limit(size))).all()
    linked = dict((await db.execute(
        select(ProfileCompetency.competency_id, func.count(func.distinct(PositionProfile.position_id)))
        .join(PositionProfile, PositionProfile.id == ProfileCompetency.profile_id)
        .where(ProfileCompetency.competency_id.in_([c.id for c in rows]), PositionProfile.status != "archived")
        .group_by(ProfileCompetency.competency_id)
    )).all()) if rows else {}  # fmt: skip
    return {
        "total": total, "page": page, "size": size, "counts": {k: counts.get(k, 0) for k in CATEGORIES},
        "items": [{"id": c.id, "name": c.name, "category": c.category, "description": c.description, "is_active": c.is_active, "positions": linked.get(c.id, 0)} for c in rows],
    }  # fmt: skip


@router.post("/competencies", status_code=201)
async def create_competency(body: CompetencyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_editor)):
    if await db.scalar(select(Competency.id).where(func.lower(Competency.name) == body.name.strip().lower(), Competency.category == body.category)):
        raise error(409, "duplicate")
    c = Competency(name=body.name.strip(), category=body.category, description=(body.description or "").strip() or None, is_active=body.is_active)
    db.add(c)
    await db.flush()
    await audit(db, request, "competency.create", actor=auth.user, entity="competency", entity_id=c.id, data={"name": c.name})
    await db.commit()
    return {"id": c.id, "name": c.name, "category": c.category, "description": c.description, "is_active": c.is_active, "positions": 0}


@router.put("/competencies/{cid}")
async def update_competency(cid: int, body: CompetencyIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_editor)):
    c = await db.get(Competency, cid)
    if not c:
        raise error(404, "not_found")
    c.name, c.category, c.description, c.is_active = body.name.strip(), body.category, (body.description or "").strip() or None, body.is_active
    await audit(db, request, "competency.update", actor=auth.user, entity="competency", entity_id=c.id, data={"name": c.name})
    await db.commit()
    return {"id": c.id, "name": c.name, "category": c.category, "description": c.description, "is_active": c.is_active}


@router.delete("/competencies/{cid}", status_code=204)
async def delete_competency(cid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_editor)):
    c = await db.get(Competency, cid)
    if not c:
        raise error(404, "not_found")
    if await db.scalar(select(ProfileCompetency.id).where(ProfileCompetency.competency_id == cid).limit(1)):
        c.is_active = False  # profillarda ishlatilgan: o'chirilmaydi, nofaol qilinadi
    else:
        await db.delete(c)
    await audit(db, request, "competency.delete", actor=auth.user, entity="competency", entity_id=cid, data={"name": c.name})
    await db.commit()


# --- Lavozim profillari ---------------------------------------------------------------------


class ProfileCompIn(BaseModel):
    competency_id: int
    required_level: int = Field(default=3, ge=1, le=5)
    ideal_level: int = Field(default=4, ge=1, le=5)
    mandatory: bool = True
    method: str = Field(default="interview", pattern="^(practical|test|portfolio|interview)$")


class ProfileIn(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    competencies: list[ProfileCompIn] = Field(default_factory=list, max_length=200)


def _filled(data: dict[str, Any], comps: dict[str, int]) -> int:
    """To'ldirilganlik: 9 qadamdan nechtasi bor (kompetensiya qadamlari — shu turdagi kamida bitta kompetensiya)."""
    done = 0
    for s in STEPS:
        if s in ("hard", "soft", "management"):
            done += bool(comps.get(s))
        else:
            v = data.get(s)
            done += bool(v and (any(x for x in v.values()) if isinstance(v, dict) else v))
    return round(done / len(STEPS) * 100)


async def _profile_out(db: AsyncSession, p: PositionProfile, auth: AuthContext | None = None) -> dict[str, Any]:
    pos = await db.get(Position, p.position_id)
    dept = await db.get(Department, pos.department_id) if pos and pos.department_id else None
    rows = (await db.execute(select(ProfileCompetency, Competency).join(Competency, Competency.id == ProfileCompetency.competency_id).where(ProfileCompetency.profile_id == p.id).order_by(ProfileCompetency.id))).all()
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({x for x in (p.created_by, p.decided_by) if x})))).all()}
    out = {
        "id": p.id, "code": f"PP-{p.id:03d}", "position": {"id": p.position_id, "name": pos.name if pos else None}, "department": dept.name if dept else None,
        "version": p.version, "status": p.status, "data": p.data or {}, "filled_pct": p.filled_pct, "note": p.note,
        "created_by": names.get(p.created_by or 0), "decided_by": names.get(p.decided_by or 0), "submitted_at": p.submitted_at, "decided_at": p.decided_at, "updated_at": p.updated_at,
        "competencies": [{"competency_id": c.id, "name": c.name, "category": c.category, "required_level": pc.required_level, "ideal_level": pc.ideal_level, "mandatory": pc.mandatory, "method": pc.method} for pc, c in rows],
    }  # fmt: skip
    if auth is not None:
        editable = p.status in ("draft", "returned") and _has(auth, "recruit.manage", "org.manage")
        out["can"] = {"edit": editable, "submit": editable, "decide": p.status == "pending" and _approver(auth), "new_version": p.status == "approved" and _has(auth, "recruit.manage", "org.manage")}
    return out


@router.get("/profiles")
async def list_profiles(status: str | None = None, q: str | None = None, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_reader)):
    """Har lavozim bo'yicha oxirgi profil versiyasi (profili yo'q lavozimlar ham ko'rinadi)."""
    positions = (await db.scalars(select(Position).where(Position.is_active.is_(True)).order_by(Position.name))).all()
    latest = {}
    for p in (await db.scalars(select(PositionProfile).where(PositionProfile.status != "archived").order_by(PositionProfile.position_id, PositionProfile.version))).all():
        latest[p.position_id] = p
    depts = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    items = []
    for pos in positions:
        p = latest.get(pos.id)
        st = p.status if p else "none"
        if status and st != status:
            continue
        if q and q.strip().lower() not in pos.name.lower():
            continue
        items.append({"position": {"id": pos.id, "name": pos.name}, "department": depts.get(pos.department_id or 0), "profile": {"id": p.id, "version": p.version, "status": p.status, "filled_pct": p.filled_pct, "updated_at": p.updated_at} if p else None, "status": st})
    return {"items": items}


@router.post("/profiles", status_code=201)
async def create_profile(body: dict, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_editor)):
    """Lavozim uchun yangi versiya (oldingi versiyadan nusxa). Ochiq qoralama bo'lsa — o'shani qaytaradi."""
    pos = await db.get(Position, int(body.get("position_id") or 0))
    if not pos:
        raise error(400, "unknown_position")
    open_p = await db.scalar(select(PositionProfile).where(PositionProfile.position_id == pos.id, PositionProfile.status.in_(("draft", "returned", "pending"))))
    if open_p:
        return await _profile_out(db, open_p, auth)
    last = await db.scalar(select(PositionProfile).where(PositionProfile.position_id == pos.id).order_by(PositionProfile.version.desc()).limit(1))
    p = PositionProfile(position_id=pos.id, version=(last.version + 1) if last else 1, status="draft", data=dict(last.data or {}) if last else {"general": {"title": pos.name}}, filled_pct=last.filled_pct if last else 0, created_by=auth.user.id)
    db.add(p)
    await db.flush()
    if last:
        for pc in (await db.scalars(select(ProfileCompetency).where(ProfileCompetency.profile_id == last.id))).all():
            db.add(ProfileCompetency(profile_id=p.id, competency_id=pc.competency_id, required_level=pc.required_level, ideal_level=pc.ideal_level, mandatory=pc.mandatory, method=pc.method))
    await audit(db, request, "profile.create", actor=auth.user, entity="position_profile", entity_id=p.id, data={"position": pos.name, "version": p.version})
    await db.commit()
    return await _profile_out(db, p, auth)


@router.get("/profiles/approved/{position_id}")
async def approved_for(position_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Zayafka formasi uchun: lavozimning amaldagi tasdiqlangan profili (yo'q bo'lsa null)."""
    from app.services.company import get_setting

    p = await db.scalar(select(PositionProfile).where(PositionProfile.position_id == position_id, PositionProfile.status == "approved").order_by(PositionProfile.version.desc()).limit(1))
    return {"profile": await _profile_out(db, p) if p else None, "required": bool(await get_setting(db, "recruit.require_profile"))}


@router.get("/profiles/{pid}")
async def get_profile(pid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_reader)):
    p = await db.get(PositionProfile, pid)
    if not p:
        raise error(404, "not_found")
    return await _profile_out(db, p, auth)


@router.put("/profiles/{pid}")
async def save_profile(pid: int, body: ProfileIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_editor)):
    p = await db.scalar(select(PositionProfile).where(PositionProfile.id == pid).with_for_update())
    if not p:
        raise error(404, "not_found")
    if p.status not in ("draft", "returned"):
        raise error(409, "not_editable")
    ids = {c.competency_id for c in body.competencies}
    comps = {c.id: c for c in (await db.scalars(select(Competency).where(Competency.id.in_(ids)))).all()} if ids else {}
    if len(comps) != len(ids):
        raise error(400, "unknown_competency")
    for old in (await db.scalars(select(ProfileCompetency).where(ProfileCompetency.profile_id == p.id))).all():
        await db.delete(old)
    by_cat: dict[str, int] = {}
    for c in {c.competency_id: c for c in body.competencies}.values():
        db.add(ProfileCompetency(profile_id=p.id, competency_id=c.competency_id, required_level=c.required_level, ideal_level=max(c.ideal_level, c.required_level), mandatory=c.mandatory, method=c.method))
        by_cat[comps[c.competency_id].category] = by_cat.get(comps[c.competency_id].category, 0) + 1
    p.data = {k: v for k, v in body.data.items() if k in STEPS}
    p.filled_pct = _filled(p.data, by_cat)
    await db.flush()
    await db.commit()
    await db.refresh(p)
    return await _profile_out(db, p, auth)


class DecideIn(BaseModel):
    action: str = Field(pattern="^(submit|approve|return)$")
    note: str | None = Field(default=None, max_length=2000)


@router.post("/profiles/{pid}/action")
async def profile_action(pid: int, body: DecideIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    p = await db.scalar(select(PositionProfile).where(PositionProfile.id == pid).with_for_update())
    if not p:
        raise error(404, "not_found")
    pos = await db.get(Position, p.position_id)
    moment = now()
    notes: list = []
    params = {"position": pos.name if pos else "—", "version": p.version}
    if body.action == "submit":
        if not _has(auth, "recruit.manage", "org.manage") or p.status not in ("draft", "returned"):
            raise error(403, "forbidden")
        if p.filled_pct < 100:
            raise error(400, "profile_incomplete")
        p.status, p.submitted_at, p.note = "pending", moment, None
        targets = [u for u in await users_with_permission(db, "recruit.approve") if u != auth.user.id]
        notes = await notify(db, targets, "profile.submitted", params=params, link=f"/recruit/profiles/{p.id}")
    else:
        if not _approver(auth) or p.status != "pending":
            raise error(403, "forbidden")
        if body.action == "return" and not (body.note or "").strip():
            raise error(400, "note_required")
        if body.action == "approve":
            # avvalgi tasdiqlangan versiya arxivga
            for old in (await db.scalars(select(PositionProfile).where(PositionProfile.position_id == p.position_id, PositionProfile.status == "approved"))).all():
                old.status = "archived"
        p.status = "approved" if body.action == "approve" else "returned"
        p.decided_by, p.decided_at, p.note = auth.user.id, moment, (body.note or "").strip() or None
        if p.created_by and p.created_by != auth.user.id:
            notes = await notify(db, [p.created_by], "profile.decided", params={**params, "result": "tasdiqlandi" if body.action == "approve" else "qayta ishlashga qaytarildi"}, link=f"/recruit/profiles/{p.id}")
    await audit(db, request, f"profile.{body.action}", actor=auth.user, entity="position_profile", entity_id=p.id, data=params)
    await db.commit()
    await deliver(request.app, notes)
    await db.refresh(p)
    return await _profile_out(db, p, auth)


# --- Tasdiqlash markazi -------------------------------------------------------------------


@router.get("/approvals")
async def approvals(type: str = Query(default="all", pattern="^(all|profile|request)$"), q: str | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_reader)):
    since = now() - timedelta(days=90)
    items: list[dict[str, Any]] = []
    profiles = (await db.scalars(select(PositionProfile).where(or_(PositionProfile.status.in_(("pending", "returned")), PositionProfile.decided_at >= since), PositionProfile.status != "draft").order_by(PositionProfile.updated_at.desc()).limit(200))).all()
    reqs = (await db.scalars(select(HireRequest).where(or_(HireRequest.status == "pending", HireRequest.decided_at >= since)).order_by(HireRequest.created_at.desc()).limit(200))).all()
    uids = {x for p in profiles for x in (p.created_by,) if x} | {r.created_by for r in reqs if r.created_by}
    users = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(uids)))).all()} if uids else {}
    pos_ids = {p.position_id for p in profiles} | {r.position_id for r in reqs if r.position_id}
    positions = {p.id: p for p in (await db.scalars(select(Position).where(Position.id.in_(pos_ids)))).all()} if pos_ids else {}
    depts = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    st = {"pending": "pending", "returned": "returned", "approved": "approved", "archived": "approved", "rejected": "returned", "cancelled": "returned"}
    for p in profiles:
        pos = positions.get(p.position_id)
        items.append({"type": "profile", "id": p.id, "code": f"PP-{p.id:03d}", "title": f"{pos.name if pos else '—'} — profil (v{p.version})", "requester": users.get(p.created_by or 0),
                      "unit": depts.get(pos.department_id or 0) if pos else None, "sent_at": p.submitted_at or p.updated_at, "approver": "HRBP", "status": st.get(p.status, p.status), "link": f"/recruit/profiles/{p.id}"})  # fmt: skip
    for r in reqs:
        pos = positions.get(r.position_id)
        items.append({"type": "request", "id": r.id, "code": r.number, "title": f"{pos.name if pos else '—'} — zayavka", "requester": users.get(r.created_by or 0),
                      "unit": depts.get(r.department_id or 0), "sent_at": r.created_at, "approver": "HR direktori", "status": st.get(r.status, r.status), "link": f"/recruit/requests/{r.id}"})  # fmt: skip
    counts = {"all": len(items), "profile": sum(i["type"] == "profile" for i in items), "request": sum(i["type"] == "request" for i in items),
              "pending": sum(i["status"] == "pending" for i in items), "returned": sum(i["status"] == "returned" for i in items)}  # fmt: skip
    if type != "all":
        items = [i for i in items if i["type"] == type]
    if q:
        ql = q.strip().lower()
        items = [i for i in items if ql in f"{i['code']} {i['title']} {i['requester']}".lower()]
    items.sort(key=lambda i: (i["status"] != "pending", -(i["sent_at"].timestamp() if i["sent_at"] else 0)))
    return {"counts": counts, "items": items, "can_decide": _approver(auth)}


# --- Dashboard ------------------------------------------------------------------------------


@router.get("/competency-dashboard")
async def dashboard(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_reader)):
    positions = (await db.scalars(select(Position).where(Position.is_active.is_(True)))).all()
    latest: dict[int, str] = {}
    approved: set[int] = set()
    for p in (await db.scalars(select(PositionProfile).order_by(PositionProfile.position_id, PositionProfile.version))).all():
        if p.status == "approved":
            approved.add(p.position_id)
        if p.status != "archived":
            latest[p.position_id] = p.status
    status = {"approved": 0, "pending": 0, "draft": 0, "returned": 0, "none": 0}
    for pos in positions:
        s = "approved" if pos.id in approved and latest.get(pos.id) == "approved" else latest.get(pos.id, "none")
        status[s if s in status else "draft"] += 1
    depts = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    cov: dict[str, list[int]] = {}
    for pos in positions:
        name = depts.get(pos.department_id or 0) or "—"
        c = cov.setdefault(name, [0, 0])
        c[0] += 1
        c[1] += pos.id in approved
    coverage = sorted(({"department": k, "positions": v[0], "pct": round(v[1] / v[0] * 100)} for k, v in cov.items() if v[0]), key=lambda x: -x["pct"])[:8]
    return {
        "positions": len(positions),
        "competencies": await db.scalar(select(func.count()).select_from(Competency).where(Competency.is_active.is_(True))) or 0,
        "approved": len(approved & {p.id for p in positions}),
        "returned": status["returned"],
        "pending": status["pending"],
        "open_vacancies": await db.scalar(select(func.count()).select_from(Vacancy).where(Vacancy.status == "open")) or 0,
        "pending_requests": await db.scalar(select(func.count()).select_from(HireRequest).where(HireRequest.status == "pending")) or 0,
        "status": status,
        "coverage": coverage,
    }


@router.get("/overview")
async def overview(days: int = Query(default=30, ge=7, le=365), db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_reader)):
    """Rekruting dashboardi: zayavkalar dinamikasi (6 oy), so'nggi faoliyatlar, tasdiqlashni kutayotganlar, voronka va davr o'zgarishi."""
    from app.models.auth import AuditLog
    from app.services import recruit_core as core
    from app.timeutil import local_date

    moment = now()
    start, prev = moment - timedelta(days=days), moment - timedelta(days=days * 2)

    async def n(model, *cond) -> int:
        return await db.scalar(select(func.count()).select_from(model).where(*cond)) or 0

    def delta(cur: int, old: int) -> int | None:
        return round((cur - old) / old * 100) if old else None

    req_cur, req_old = await n(HireRequest, HireRequest.created_at >= start), await n(HireRequest, HireRequest.created_at >= prev, HireRequest.created_at < start)
    ap_cur = await n(PositionProfile, PositionProfile.status.in_(("approved", "archived")), PositionProfile.decided_at >= start)
    ap_old = await n(PositionProfile, PositionProfile.status.in_(("approved", "archived")), PositionProfile.decided_at >= prev, PositionProfile.decided_at < start)
    comp_cur, comp_old = await n(Competency, Competency.created_at >= start), await n(Competency, Competency.created_at >= prev, Competency.created_at < start)
    vac_cur, vac_old = await n(Vacancy, Vacancy.created_at >= start), await n(Vacancy, Vacancy.created_at >= prev, Vacancy.created_at < start)

    today = local_date(moment)
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    months.reverse()
    created = [local_date(c) for (c,) in (await db.execute(select(HireRequest.created_at).where(HireRequest.created_at >= prev - timedelta(days=200)))).all()]
    dynamics = [{"month": f"{yy}-{mm:02d}", "count": sum(1 for c in created if (c.year, c.month) == (yy, mm))} for yy, mm in months]

    logs = (await db.scalars(select(AuditLog).where(or_(AuditLog.action.like("profile.%"), AuditLog.action.like("recruit.request%"), AuditLog.action.like("competency.%"))).order_by(AuditLog.id.desc()).limit(8))).all()
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({x.actor_id for x in logs if x.actor_id})))).all()}
    activity = [{"action": x.action, "actor": names.get(x.actor_id or 0) or x.actor_login, "data": x.data or {}, "at": x.created_at} for x in logs]

    pend_p = (await db.scalars(select(PositionProfile).where(PositionProfile.status == "pending").order_by(PositionProfile.submitted_at).limit(5))).all()
    pend_r = (await db.scalars(select(HireRequest).where(HireRequest.status == "pending").order_by(HireRequest.created_at).limit(5))).all()
    pos = {p.id: p.name for p in (await db.scalars(select(Position).where(Position.id.in_({x.position_id for x in [*pend_p, *pend_r]})))).all()} if pend_p or pend_r else {}
    pending = sorted(
        [{"type": "profile", "title": pos.get(p.position_id), "link": f"/recruit/profiles/{p.id}", "since": p.submitted_at or p.updated_at} for p in pend_p]
        + [{"type": "request", "title": pos.get(r.position_id), "link": f"/recruit/requests/{r.id}", "since": r.created_at} for r in pend_r],
        key=lambda x: x["since"],
    )[:5]
    for x in pending:
        x["days"] = (moment - x["since"]).days

    f = await core.funnel(db, vacancy_id=None, start=local_date(start), end=today)
    funnel = [{"stage": "requests", "count": req_cur}, {"stage": "vacancies", "count": vac_cur}, *({"stage": s["stage"], "count": s["count"]} for s in f["steps"])]
    return {
        "days": days,
        "deltas": {"requests": delta(req_cur, req_old), "approved": delta(ap_cur, ap_old), "competencies": delta(comp_cur, comp_old), "vacancies": delta(vac_cur, vac_old)},
        "dynamics": dynamics, "activity": activity, "pending": pending, "pending_total": await n(PositionProfile, PositionProfile.status == "pending") + await n(HireRequest, HireRequest.status == "pending"),
        "funnel": funnel,
    }  # fmt: skip


@router.get("/funnel-report")
async def funnel_report(
    days: int = Query(default=90, ge=7, le=730),
    department_id: int | None = None,
    position_id: int | None = None,
    recruiter_id: int | None = None,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(_reader),
):
    """Voronka hisoboti: Zayavka -> Vakansiya -> Nomzod -> Saralash -> Intervyu -> Test -> Offer -> Ishga qabul.
    Har bosqich: soni, oldingisiga nisbatan konversiya, arizadan shu bosqichgacha o'rtacha kun."""
    from app.models.recruit import Application, ApplicationEvent, CandidateTest
    from app.services.recruit_core import RANK

    moment = now()
    start = moment - timedelta(days=days)
    vcond = []
    if department_id:
        vcond.append(Vacancy.department_id == department_id)
    if position_id:
        vcond.append(Vacancy.position_id == position_id)
    rcond = [HireRequest.created_at >= start]
    if department_id:
        rcond.append(HireRequest.department_id == department_id)
    if position_id:
        rcond.append(HireRequest.position_id == position_id)
    requests = await db.scalar(select(func.count()).select_from(HireRequest).where(*rcond)) or 0
    vac_cond = [*vcond, Vacancy.created_at >= start]
    if recruiter_id:
        vac_cond.append(Vacancy.recruiter_id == recruiter_id)
    vacancies = await db.scalar(select(func.count()).select_from(Vacancy).where(*vac_cond)) or 0

    astmt = select(Application, Vacancy.created_at).join(Vacancy, Vacancy.id == Application.vacancy_id).where(Application.applied_at >= start, *vcond)
    if recruiter_id:
        astmt = astmt.where(or_(Application.recruiter_id == recruiter_id, Vacancy.recruiter_id == recruiter_id))
    rows = (await db.execute(astmt.limit(10000))).all()
    apps = {a.id: a for a, _ in rows}
    vac_created = {a.id: vc for a, vc in rows}
    best = {a.id: RANK.get(a.stage, 0) for a in apps.values()}
    reached_at: dict[tuple[int, str], Any] = {}
    if apps:
        ev = (await db.execute(select(ApplicationEvent.application_id, ApplicationEvent.from_stage, ApplicationEvent.to_stage, ApplicationEvent.created_at).where(ApplicationEvent.application_id.in_(apps), ApplicationEvent.action.in_(("stage", "rejected", "hired"))))).all()
        for aid, frm, to, at in ev:
            for s in (frm, to):
                if s in RANK:
                    best[aid] = max(best[aid], RANK[s])
            if to in RANK and (aid, to) not in reached_at:
                reached_at[(aid, to)] = at
        tested = set((await db.scalars(select(CandidateTest.application_id).where(CandidateTest.application_id.in_(apps)))).all())
    else:
        tested = set()

    def avg_days(stage: str) -> float | None:
        vals = []
        for aid, a in apps.items():
            at = a.hired_at if stage == "hired" and a.hired_at else reached_at.get((aid, stage))
            if at and best[aid] >= RANK[stage]:
                vals.append((at - a.applied_at).total_seconds() / 86400)
        return round(sum(vals) / len(vals), 1) if vals else None

    def reached(stage: str) -> int:
        return sum(1 for aid in apps if best[aid] >= RANK[stage])

    stages = [
        {"stage": "requests", "count": requests, "days": None},
        {"stage": "vacancies", "count": vacancies, "days": None},
        {"stage": "found", "count": len(apps), "days": 0 if apps else None},
        {"stage": "screening", "count": reached("screening"), "days": avg_days("screening")},
        {"stage": "interview", "count": reached("interview"), "days": avg_days("interview")},
        {"stage": "test", "count": sum(1 for aid in apps if aid in tested), "days": None},
        {"stage": "offer", "count": reached("offer"), "days": avg_days("offer")},
        {"stage": "hired", "count": reached("hired"), "days": avg_days("hired")},
    ]
    for i, s in enumerate(stages):
        prev = stages[i - 1]["count"] if i else 0
        # nomzodlar soni vakansiyalar soniga bo'linmaydi (birlik boshqa)
        s["rate"] = None if s["stage"] == "found" else round(s["count"] / prev * 100, 1) if i and prev else (100.0 if i == 0 and s["count"] else None)
    hired = [a for a in apps.values() if a.hired_at]
    close = [(a.hired_at - vac_created[a.id]).total_seconds() / 86400 for a in hired if vac_created.get(a.id)]
    candidates = len({a.candidate_id for a in apps.values()})
    recruiters = (await db.execute(select(User.id, User.full_name).where(User.id.in_(select(Vacancy.recruiter_id).where(Vacancy.recruiter_id.is_not(None)).union(select(Application.recruiter_id).where(Application.recruiter_id.is_not(None))))).order_by(User.full_name))).all()
    return {
        "days": days,
        "kpi": {"candidates": candidates, "hired": len(hired), "conversion": round(len(hired) / candidates * 100, 1) if candidates else None, "avg_close_days": round(sum(close) / len(close)) if close else None},
        "stages": stages,
        "recruiters": [{"id": i, "name": n} for i, n in recruiters],
    }
