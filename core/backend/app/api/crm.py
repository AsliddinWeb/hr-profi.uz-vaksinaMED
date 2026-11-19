"""CRM API: voronka (Kanban), bitim kartasi, o'ng panel (xabar / eslatma / faoliyat / tarix), faoliyatlar ro'yxati, hisobot.

Ruxsatlar: `crm.own` — o'z bitimlari (egasi yoki yaratuvchisi); `crm.read` — hammasini ko'rish; `crm.manage` — istalgan bitim va bosqich sozlamalari.
"""

from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.crm import CrmActivity, CrmDeal, CrmMessage, CrmStage
from app.services import crm as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/crm", tags=["crm"])

Kind = Literal["call", "meeting", "email", "task"]


class DealIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=160)
    contact_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=160)
    amount: float = Field(default=0, ge=0, le=1e15)
    probability: int | None = Field(default=None, ge=0, le=100)
    priority: int = Field(default=0, ge=0, le=3)
    tags: list[str] = Field(default_factory=list, max_length=10)
    source: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=5000)
    expected_close: date | None = None
    stage_id: int | None = None
    owner_id: int | None = None


class MoveIn(BaseModel):
    stage_id: int
    before_id: int | None = None


class LostIn(BaseModel):
    reason: str = Field(min_length=2, max_length=300)


class MessageIn(BaseModel):
    kind: Literal["message", "note"] = "message"
    body: str = Field(min_length=1, max_length=4000)


class ActivityIn(BaseModel):
    kind: Kind = "call"
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    due_date: date
    assignee_id: int | None = None


class DoneIn(BaseModel):
    result: str | None = Field(default=None, max_length=2000)
    next: ActivityIn | None = None  # bajarilgach keyingisini darhol rejalashtirish


class StageIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    probability: int = Field(ge=0, le=100)
    sort_order: int = 0
    is_won: bool = False
    auto_activity: str | None = Field(default=None, max_length=160)
    auto_activity_kind: Kind = "call"
    auto_activity_days: int = Field(default=1, ge=0, le=60)
    is_active: bool = True


# --- Ruxsatlar ------------------------------------------------------------------------


def _need_any(auth: AuthContext) -> None:
    if not (auth.can("crm.own") or auth.can("crm.read") or auth.can("crm.manage")):
        raise error(403, "forbidden")


def _sees_all(auth: AuthContext) -> bool:
    return auth.can("crm.read") or auth.can("crm.manage")


def _mine(auth: AuthContext, d: CrmDeal) -> bool:
    return auth.user.id in (d.owner_id, d.created_by)


def _can_view(auth: AuthContext, d: CrmDeal) -> bool:
    return _sees_all(auth) or _mine(auth, d)


def _can_edit(auth: AuthContext, d: CrmDeal) -> bool:
    return auth.can("crm.manage") or (auth.can("crm.own") and _mine(auth, d))


async def _deal(db: AsyncSession, auth: AuthContext, deal_id: int, *, edit: bool = False) -> CrmDeal:
    d = await db.get(CrmDeal, deal_id)
    if not d or d.archived_at or not _can_view(auth, d):
        raise error(404, "not_found")
    if edit and not _can_edit(auth, d):
        raise error(403, "forbidden")
    return d


async def _stage(db: AsyncSession, stage_id: int) -> CrmStage:
    s = await db.get(CrmStage, stage_id)
    if not s or not s.is_active:
        raise error(422, "stage_not_found")
    return s


async def _stages(db: AsyncSession) -> list[CrmStage]:
    return list((await db.scalars(select(CrmStage).where(CrmStage.is_active.is_(True)).order_by(CrmStage.sort_order, CrmStage.id))).all())


async def _names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids.discard(None)
    if not ids:
        return {}
    return dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all())  # type: ignore[arg-type]


async def _check_user(db: AsyncSession, uid: int | None) -> None:
    if uid and not await db.get(User, uid):
        raise error(422, "user_not_found")


def _stage_out(s: CrmStage) -> dict[str, Any]:
    return {
        "id": s.id, "name": s.name, "probability": s.probability, "sort_order": s.sort_order, "is_won": s.is_won,
        "auto_activity": s.auto_activity, "auto_activity_kind": s.auto_activity_kind, "auto_activity_days": s.auto_activity_days, "is_active": s.is_active,
    }  # fmt: skip


async def _next_activities(db: AsyncSession, deal_ids: list[int]) -> dict[int, CrmActivity]:
    """Har bir bitimning eng yaqin ochiq faoliyati."""
    if not deal_ids:
        return {}
    rows = (await db.scalars(select(CrmActivity).where(CrmActivity.deal_id.in_(deal_ids), CrmActivity.done_at.is_(None)).order_by(CrmActivity.due_date, CrmActivity.id))).all()
    out: dict[int, CrmActivity] = {}
    for a in rows:
        out.setdefault(a.deal_id, a)
    return out


def _card(d: CrmDeal, names: dict[int, str], nxt: CrmActivity | None, today: date) -> dict[str, Any]:
    return {
        "id": d.id, "title": d.title, "company": d.company, "contact_name": d.contact_name, "amount": d.amount, "probability": d.probability,
        "priority": d.priority, "tags": d.tags or [], "stage_id": d.stage_id, "owner": {"id": d.owner_id, "name": names.get(d.owner_id)} if d.owner_id else None,  # type: ignore[arg-type]
        "expected_close": d.expected_close, "created_at": d.created_at, "won": d.won_at is not None, "lost": d.lost_at is not None,
        "next_activity": {"id": nxt.id, "kind": nxt.kind, "title": nxt.title, **(svc.activity_state(nxt.due_date, today) or {})} if nxt else None,
    }  # fmt: skip


def _scope(auth: AuthContext, owner: str | None):
    """Ro'yxat filtri: `mine` — o'zimniki; boshqalar faqat `crm.read` bilan."""
    me = auth.user.id
    if owner == "mine" or not _sees_all(auth):
        return or_(CrmDeal.owner_id == me, CrmDeal.created_by == me)
    if owner and owner.isdigit():
        return CrmDeal.owner_id == int(owner)
    return None


# --- Bosqichlar --------------------------------------------------------------------------


@router.get("/stages")
async def list_stages(all_: bool = Query(default=False, alias="all"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_any(auth)
    q = select(CrmStage).order_by(CrmStage.sort_order, CrmStage.id)
    if not (all_ and auth.can("crm.manage")):
        q = q.where(CrmStage.is_active.is_(True))
    return [_stage_out(s) for s in (await db.scalars(q)).all()]


@router.post("/stages", status_code=201)
async def create_stage(body: StageIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not auth.can("crm.manage"):
        raise error(403, "forbidden")
    s = CrmStage(**body.model_dump())
    s.auto_activity = (s.auto_activity or "").strip() or None
    db.add(s)
    await db.flush()
    await audit(db, request, "crm.stage_create", actor=auth.user, entity="crm_stage", entity_id=s.id, data={"name": s.name})
    await db.commit()
    return _stage_out(s)


@router.put("/stages/{sid}")
async def update_stage(sid: int, body: StageIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not auth.can("crm.manage"):
        raise error(403, "forbidden")
    s = await db.get(CrmStage, sid)
    if not s:
        raise error(404, "not_found")
    if not body.is_active and await db.scalar(select(func.count()).select_from(CrmDeal).where(CrmDeal.stage_id == sid, CrmDeal.archived_at.is_(None), CrmDeal.lost_at.is_(None))):
        raise error(409, "stage_has_deals")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    s.auto_activity = (s.auto_activity or "").strip() or None
    await audit(db, request, "crm.stage_update", actor=auth.user, entity="crm_stage", entity_id=s.id, data={"name": s.name})
    await db.commit()
    return _stage_out(s)


# --- Voronka ------------------------------------------------------------------------------


@router.get("/board")
async def board(
    owner: str | None = Query(default=None, max_length=12),
    q: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    _need_any(auth)
    stages = await _stages(db)
    cond = [CrmDeal.archived_at.is_(None), CrmDeal.lost_at.is_(None)]
    if (sc := _scope(auth, owner)) is not None:
        cond.append(sc)
    if q and q.strip():
        like = f"%{q.strip()}%"
        cond.append(or_(CrmDeal.title.ilike(like), CrmDeal.company.ilike(like), CrmDeal.contact_name.ilike(like), CrmDeal.phone.ilike(like)))
    deals = (await db.scalars(select(CrmDeal).where(and_(*cond)).order_by(CrmDeal.position, CrmDeal.id.desc()))).all()
    names = await _names(db, {d.owner_id for d in deals})
    nxt = await _next_activities(db, [d.id for d in deals])
    today = local_date(now())
    cols = []
    for s in stages:
        items = [d for d in deals if d.stage_id == s.id]
        cols.append({
            **_stage_out(s), "count": len(items), "total": sum(d.amount for d in items),
            "overdue": sum(1 for d in items if (a := nxt.get(d.id)) and a.due_date < today),
            "deals": [_card(d, names, nxt.get(d.id), today) for d in items],
        })  # fmt: skip
    return {"stages": cols, "can_create": auth.can("crm.own") or auth.can("crm.manage"), "can_manage": auth.can("crm.manage"), "sees_all": _sees_all(auth)}


# --- Bitim ---------------------------------------------------------------------------------


@router.post("/deals", status_code=201)
async def create_deal(body: DealIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not (auth.can("crm.own") or auth.can("crm.manage")):
        raise error(403, "forbidden")
    stages = await _stages(db)
    if not stages:
        raise error(409, "no_stages")
    stage = await _stage(db, body.stage_id) if body.stage_id else stages[0]
    owner = body.owner_id if (body.owner_id and auth.can("crm.manage")) else auth.user.id
    await _check_user(db, owner)
    first = await db.scalar(select(func.min(CrmDeal.position)).where(CrmDeal.stage_id == stage.id))
    data = body.model_dump(exclude={"stage_id", "owner_id", "probability"})
    data["tags"] = [t.strip()[:30] for t in body.tags if t.strip()]
    d = CrmDeal(**data, stage_id=stage.id, owner_id=owner, created_by=auth.user.id, probability=stage.probability, position=(first or 0) - 1)
    db.add(d)
    await db.flush()
    svc.log(db, d, auth.user.id, "created", stage=stage.name)
    notes = await svc.enter_stage(db, d, stage, auth.user.id, from_stage=None)
    if body.probability is not None:
        d.probability = body.probability
    if owner != auth.user.id:
        notes += await notify(db, [owner], "crm.deal_assigned", params={"deal": d.title}, link=f"/crm/deals/{d.id}")
    await audit(db, request, "crm.deal_create", actor=auth.user, entity="crm_deal", entity_id=d.id, data={"title": d.title})
    await db.commit()
    await deliver(request.app, notes)
    return {"id": d.id}


@router.get("/deals/{deal_id}")
async def get_deal(deal_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_any(auth)
    d = await _deal(db, auth, deal_id)
    names = await _names(db, {d.owner_id, d.created_by})
    nxt = await _next_activities(db, [d.id])
    stages = await _stages(db)
    return {
        **_card(d, names, nxt.get(d.id), local_date(now())),
        "phone": d.phone, "email": d.email, "source": d.source, "description": d.description, "lost_reason": d.lost_reason, "won_at": d.won_at, "lost_at": d.lost_at,
        "created_by": names.get(d.created_by) if d.created_by else None, "stage_changed_at": d.stage_changed_at, "updated_at": d.updated_at,  # type: ignore[arg-type]
        "stages": [_stage_out(s) for s in stages], "can_edit": _can_edit(auth, d), "can_assign": auth.can("crm.manage"),
    }  # fmt: skip


@router.put("/deals/{deal_id}")
async def update_deal(deal_id: int, body: DealIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    d = await _deal(db, auth, deal_id, edit=True)
    before = svc.snapshot(d)
    data = body.model_dump(exclude={"stage_id", "owner_id", "probability"})
    data["tags"] = [t.strip()[:30] for t in body.tags if t.strip()]
    for k, v in data.items():
        setattr(d, k, v)
    if body.probability is not None:
        d.probability = body.probability
    notes: list = []
    if body.owner_id and body.owner_id != d.owner_id:
        if not auth.can("crm.manage"):
            raise error(403, "forbidden")
        await _check_user(db, body.owner_id)
        d.owner_id = body.owner_id
        if body.owner_id != auth.user.id:
            notes += await notify(db, [body.owner_id], "crm.deal_assigned", params={"deal": d.title}, link=f"/crm/deals/{d.id}")
    svc.track(db, d, auth.user.id, before)
    if body.stage_id and body.stage_id != d.stage_id:
        notes += await svc.enter_stage(db, d, await _stage(db, body.stage_id), auth.user.id, from_stage=await db.get(CrmStage, d.stage_id))
    await db.commit()
    await deliver(request.app, notes)
    return {"id": d.id}


@router.post("/deals/{deal_id}/move")
async def move_deal(deal_id: int, body: MoveIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    d = await _deal(db, auth, deal_id, edit=True)
    if d.lost_at:
        raise error(409, "deal_lost")
    stage = await _stage(db, body.stage_id)
    # Tartib: `before_id` dan oldin, yo'q bo'lsa ustun oxiriga
    if body.before_id:
        b = await db.get(CrmDeal, body.before_id)
        if not b or b.stage_id != stage.id:
            raise error(422, "bad_before")
        prev = await db.scalar(select(func.max(CrmDeal.position)).where(CrmDeal.stage_id == stage.id, CrmDeal.position < b.position, CrmDeal.id != d.id))
        d.position = (b.position - 1) if prev is None else (prev + b.position) / 2
    else:
        last = await db.scalar(select(func.max(CrmDeal.position)).where(CrmDeal.stage_id == stage.id, CrmDeal.id != d.id))
        d.position = (last or 0) + 1
    notes: list = []
    if stage.id != d.stage_id:
        notes = await svc.enter_stage(db, d, stage, auth.user.id, from_stage=await db.get(CrmStage, d.stage_id))
    await db.commit()
    await deliver(request.app, notes)
    return {"id": d.id, "stage_id": d.stage_id, "probability": d.probability}


@router.post("/deals/{deal_id}/won")
async def win_deal(deal_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    d = await _deal(db, auth, deal_id, edit=True)
    won = next((s for s in await _stages(db) if s.is_won), None)
    if not won:
        raise error(409, "no_won_stage")
    d.lost_at = d.lost_reason = None
    notes = await svc.enter_stage(db, d, won, auth.user.id, from_stage=await db.get(CrmStage, d.stage_id)) if d.stage_id != won.id else []
    await audit(db, request, "crm.deal_won", actor=auth.user, entity="crm_deal", entity_id=d.id, data={"amount": d.amount})
    await db.commit()
    await deliver(request.app, notes)
    return {"id": d.id, "stage_id": d.stage_id}


@router.post("/deals/{deal_id}/lost")
async def lose_deal(deal_id: int, body: LostIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    d = await _deal(db, auth, deal_id, edit=True)
    d.lost_at, d.lost_reason, d.won_at = now(), body.reason.strip(), None
    d.probability = 0
    for a in (await db.scalars(select(CrmActivity).where(CrmActivity.deal_id == d.id, CrmActivity.done_at.is_(None)))).all():
        await db.delete(a)  # yo'qotilgan bitimda ochiq faoliyat qolmaydi
    svc.log(db, d, auth.user.id, "lost", reason=d.lost_reason)
    await audit(db, request, "crm.deal_lost", actor=auth.user, entity="crm_deal", entity_id=d.id, data={"reason": d.lost_reason})
    await db.commit()
    return {"id": d.id}


@router.post("/deals/{deal_id}/reopen")
async def reopen_deal(deal_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    d = await _deal(db, auth, deal_id, edit=True)
    if not d.lost_at:
        raise error(409, "deal_not_lost")
    d.lost_at = d.lost_reason = None
    stage = await db.get(CrmStage, d.stage_id)
    svc.log(db, d, auth.user.id, "reopened")
    notes = await svc.enter_stage(db, d, stage, auth.user.id, from_stage=None) if stage else []  # type: ignore[arg-type]
    await db.commit()
    await deliver(request.app, notes)
    return {"id": d.id}


@router.delete("/deals/{deal_id}", status_code=204)
async def archive_deal(deal_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    d = await _deal(db, auth, deal_id, edit=True)
    d.archived_at = now()
    await audit(db, request, "crm.deal_archive", actor=auth.user, entity="crm_deal", entity_id=d.id, data={"title": d.title})
    await db.commit()


@router.get("/deals")
async def list_deals(
    status: Literal["open", "won", "lost", "all"] = "open",
    owner: str | None = Query(default=None, max_length=12),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    _need_any(auth)
    cond = [CrmDeal.archived_at.is_(None)]
    if status == "open":
        cond += [CrmDeal.lost_at.is_(None), CrmDeal.won_at.is_(None)]
    elif status == "won":
        cond.append(CrmDeal.won_at.is_not(None))
    elif status == "lost":
        cond.append(CrmDeal.lost_at.is_not(None))
    if (sc := _scope(auth, owner)) is not None:
        cond.append(sc)
    if q and q.strip():
        like = f"%{q.strip()}%"
        cond.append(or_(CrmDeal.title.ilike(like), CrmDeal.company.ilike(like), CrmDeal.contact_name.ilike(like), CrmDeal.phone.ilike(like)))
    deals = (await db.scalars(select(CrmDeal).where(and_(*cond)).order_by(CrmDeal.updated_at.desc()).limit(limit))).all()
    names = await _names(db, {d.owner_id for d in deals})
    nxt = await _next_activities(db, [d.id for d in deals])
    stage_names = {s.id: s.name for s in (await db.scalars(select(CrmStage))).all()}
    today = local_date(now())
    return [{**_card(d, names, nxt.get(d.id), today), "stage": stage_names.get(d.stage_id), "lost_reason": d.lost_reason} for d in deals]


# --- O'ng panel: lenta, xabar, eslatma -------------------------------------------------------


@router.get("/deals/{deal_id}/feed")
async def feed(deal_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_any(auth)
    d = await _deal(db, auth, deal_id)
    msgs = (await db.scalars(select(CrmMessage).where(CrmMessage.deal_id == d.id).order_by(CrmMessage.id.desc()).limit(300))).all()
    acts = (await db.scalars(select(CrmActivity).where(CrmActivity.deal_id == d.id, CrmActivity.done_at.is_(None)).order_by(CrmActivity.due_date, CrmActivity.id))).all()
    names = await _names(db, {m.author_id for m in msgs} | {a.assignee_id for a in acts} | {a.created_by for a in acts})
    today = local_date(now())
    return {
        "planned": [{
            "id": a.id, "kind": a.kind, "title": a.title, "note": a.note, "due_date": a.due_date, "auto": a.auto,
            "assignee": {"id": a.assignee_id, "name": names.get(a.assignee_id)} if a.assignee_id else None,  # type: ignore[arg-type]
            "created_by": names.get(a.created_by) if a.created_by else None, **(svc.activity_state(a.due_date, today) or {}),  # type: ignore[arg-type]
            "can_done": _can_edit(auth, d) or a.assignee_id == auth.user.id,
        } for a in acts],
        "items": [{"id": m.id, "kind": m.kind, "body": m.body, "data": m.data, "author": names.get(m.author_id) if m.author_id else None, "author_id": m.author_id, "created_at": m.created_at} for m in msgs],  # type: ignore[arg-type]
        "can_write": _can_view(auth, d),
    }  # fmt: skip


@router.post("/deals/{deal_id}/messages", status_code=201)
async def post_message(deal_id: int, body: MessageIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_any(auth)
    d = await _deal(db, auth, deal_id)
    m = CrmMessage(deal_id=d.id, kind=body.kind, body=body.body.strip(), author_id=auth.user.id)
    db.add(m)
    d.updated_at = now()
    await db.commit()
    return {"id": m.id}


# --- Faoliyatlar ----------------------------------------------------------------------------


@router.post("/deals/{deal_id}/activities", status_code=201)
async def create_activity(deal_id: int, body: ActivityIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    d = await _deal(db, auth, deal_id, edit=True)
    if d.lost_at:
        raise error(409, "deal_lost")
    assignee = body.assignee_id or d.owner_id or auth.user.id
    await _check_user(db, assignee)
    a, notes = await svc.add_activity(db, d, kind=body.kind, title=body.title.strip(), due=body.due_date, assignee_id=assignee, actor_id=auth.user.id, note=body.note)
    await db.commit()
    await deliver(request.app, notes)
    return {"id": a.id}


@router.post("/activities/{aid}/done")
async def done_activity(aid: int, body: DoneIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_any(auth)
    a = await db.get(CrmActivity, aid)
    if not a or a.done_at:
        raise error(404, "not_found")
    d = await _deal(db, auth, a.deal_id)
    if not (_can_edit(auth, d) or a.assignee_id == auth.user.id):
        raise error(403, "forbidden")
    a.done_at, a.done_by, a.result = now(), auth.user.id, (body.result or "").strip() or None
    svc.log(db, d, auth.user.id, "activity_done", activity_id=a.id, kind=a.kind, title=a.title, result=a.result)
    notes: list = []
    if body.next:
        _, notes = await svc.add_activity(db, d, kind=body.next.kind, title=body.next.title.strip(), due=body.next.due_date, assignee_id=body.next.assignee_id or a.assignee_id or d.owner_id, actor_id=auth.user.id, note=body.next.note)
    await db.commit()
    await deliver(request.app, notes)
    return {"id": a.id}


@router.delete("/activities/{aid}", status_code=204)
async def cancel_activity(aid: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_any(auth)
    a = await db.get(CrmActivity, aid)
    if not a or a.done_at:
        raise error(404, "not_found")
    d = await _deal(db, auth, a.deal_id, edit=True)
    svc.log(db, d, auth.user.id, "activity_cancelled", kind=a.kind, title=a.title)
    await db.delete(a)
    await db.commit()


@router.get("/activities")
async def my_activities(scope: Literal["mine", "all"] = "mine", db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Rejalashtirilgan faoliyatlar: kechikkan, bugungi va keyingi (ochiq bitimlar bo'yicha)."""
    _need_any(auth)
    cond = [CrmActivity.done_at.is_(None), CrmDeal.archived_at.is_(None), CrmDeal.lost_at.is_(None)]
    if scope == "mine" or not _sees_all(auth):
        cond.append(or_(CrmActivity.assignee_id == auth.user.id, and_(CrmActivity.assignee_id.is_(None), CrmDeal.owner_id == auth.user.id)))
    rows = (await db.execute(select(CrmActivity, CrmDeal).join(CrmDeal, CrmDeal.id == CrmActivity.deal_id).where(*cond).order_by(CrmActivity.due_date, CrmActivity.id).limit(500))).all()
    names = await _names(db, {a.assignee_id for a, _ in rows})
    today = local_date(now())
    return [{
        "id": a.id, "kind": a.kind, "title": a.title, "note": a.note, "due_date": a.due_date, "auto": a.auto, **(svc.activity_state(a.due_date, today) or {}),
        "assignee": names.get(a.assignee_id) if a.assignee_id else None,  # type: ignore[arg-type]
        "deal": {"id": d.id, "title": d.title, "company": d.company, "phone": d.phone, "amount": d.amount},
    } for a, d in rows]  # fmt: skip


# --- Hisobot --------------------------------------------------------------------------------


@router.get("/stats")
async def stats(days: int = Query(default=30, ge=1, le=366), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_any(auth)
    since = now() - timedelta(days=days)
    base = [CrmDeal.archived_at.is_(None)]
    if not _sees_all(auth):
        base.append(or_(CrmDeal.owner_id == auth.user.id, CrmDeal.created_by == auth.user.id))
    stages = await _stages(db)
    per = dict(
        (sid, (n, s or 0))
        for sid, n, s in (await db.execute(select(CrmDeal.stage_id, func.count(), func.sum(CrmDeal.amount)).where(*base, CrmDeal.lost_at.is_(None)).group_by(CrmDeal.stage_id))).all()
    )
    won_n, won_sum = (await db.execute(select(func.count(), func.coalesce(func.sum(CrmDeal.amount), 0)).where(*base, CrmDeal.won_at >= since))).one()
    lost_n = await db.scalar(select(func.count()).select_from(CrmDeal).where(*base, CrmDeal.lost_at >= since)) or 0
    new_n = await db.scalar(select(func.count()).select_from(CrmDeal).where(*base, CrmDeal.created_at >= since)) or 0
    weighted = await db.scalar(select(func.coalesce(func.sum(CrmDeal.amount * CrmDeal.probability / 100.0), 0)).where(*base, CrmDeal.lost_at.is_(None), CrmDeal.won_at.is_(None))) or 0
    overdue = await db.scalar(
        select(func.count()).select_from(CrmActivity).join(CrmDeal, CrmDeal.id == CrmActivity.deal_id).where(*base, CrmDeal.lost_at.is_(None), CrmActivity.done_at.is_(None), CrmActivity.due_date < local_date(now()))
    ) or 0
    reasons = (await db.execute(select(CrmDeal.lost_reason, func.count()).where(*base, CrmDeal.lost_at >= since).group_by(CrmDeal.lost_reason).order_by(func.count().desc()).limit(8))).all()
    owners = (
        await db.execute(
            select(CrmDeal.owner_id, func.count(), func.coalesce(func.sum(CrmDeal.amount), 0)).where(*base, CrmDeal.won_at >= since).group_by(CrmDeal.owner_id).order_by(func.sum(CrmDeal.amount).desc()).limit(10)
        )
    ).all()
    names = await _names(db, {o for o, _, _ in owners})
    closed = won_n + lost_n
    return {
        "days": days,
        "funnel": [{"id": s.id, "name": s.name, "is_won": s.is_won, "count": per.get(s.id, (0, 0))[0], "total": per.get(s.id, (0, 0))[1]} for s in stages],
        "new": new_n, "won": won_n, "won_amount": won_sum, "lost": lost_n, "win_rate": round(won_n / closed * 100) if closed else None,
        "weighted_pipeline": weighted, "overdue_activities": overdue,
        "lost_reasons": [{"reason": r or "—", "count": n} for r, n in reasons],
        "top_owners": [{"name": names.get(o, "—") if o else "—", "won": n, "amount": s} for o, n, s in owners],  # type: ignore[arg-type]
    }  # fmt: skip
