"""Eslatmalar: bir martalik va takrorlanuvchi, ilova ichida va Telegramda."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.reminders import Reminder, ReminderEvent
from app.rbac import matches
from app.services import reminders as svc
from app.services.audit import audit
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/reminders", tags=["reminders"])


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


async def Own(auth: AuthContext = Depends(get_auth)) -> AuthContext:  # noqa: N802
    if not (has(auth, "reminders.own") or has(auth, "reminders.assign")):
        raise error(403, "forbidden")
    return auth


class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    link: str | None = Field(default=None, max_length=300)
    first_at: datetime
    repeat: str = Field(default="once", pattern="^(once|daily|weekly|monthly|yearly)$")
    interval: int = Field(default=1, ge=1, le=52)
    weekdays: list[int] = []
    until: date | None = None
    recipients: list[int] = Field(default=[], max_length=20)
    telegram: bool = True

    @model_validator(mode="after")
    def _check(self):
        if self.link and not (self.link.startswith("/") and not self.link.startswith("//")):
            raise ValueError("link_invalid")
        if any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("weekday_invalid")
        if self.first_at.tzinfo is None:
            raise ValueError("timezone_required")
        if self.until and self.until < self.first_at.astimezone(tz()).date():
            raise ValueError("until_before_start")
        return self


def _build(body: ReminderIn, rem: Reminder) -> None:
    rem.title, rem.note, rem.link = body.title.strip(), (body.note or "").strip() or None, body.link
    rem.repeat, rem.interval, rem.until, rem.telegram = body.repeat, body.interval, body.until, body.telegram
    rem.weekdays = sorted(set(body.weekdays)) if body.repeat == "weekly" else []
    rem.first_at = body.first_at
    rem.recipients = sorted({u for u in body.recipients if u != rem.owner_id})


async def _validate_recipients(db: AsyncSession, auth: AuthContext, ids: list[int]) -> None:
    if not ids:
        return
    if not has(auth, "reminders.assign"):
        raise error(403, "cannot_assign_others")
    found = {u for (u,) in (await db.execute(select(User.id).where(User.id.in_(ids), User.is_active.is_(True)))).all()}
    if set(ids) - found:
        raise error(400, "unknown_user")


def _preview_obj(body: ReminderIn) -> Reminder:
    r = Reminder(owner_id=0)
    _build(body, r)
    return r


async def _names(db: AsyncSession, rems: list[Reminder]) -> dict[int, str]:
    ids = {u for r in rems for u in (r.recipients or [])} | {r.owner_id for r in rems}
    if not ids:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()}


async def _load(db: AsyncSession, rid: int, auth: AuthContext, *, owner_only: bool = False, lock: bool = False) -> Reminder:
    stmt = select(Reminder).where(Reminder.id == rid)
    rem = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not rem:
        raise error(404, "not_found")
    me = auth.user.id
    if rem.owner_id != me and (owner_only or me not in (rem.recipients or [])):
        raise error(404, "not_found")
    return rem


@router.get("")
async def list_reminders(
    scope: str = Query(default="mine", pattern="^(mine|shared)$"),
    state: str = Query(default="active", pattern="^(active|paused|finished|all)$"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(Own),
):
    """mine: o'zimniki; shared: menga boshqalar qo'ygan."""
    me = auth.user.id
    conds: list[Any] = [Reminder.owner_id == me] if scope == "mine" else [Reminder.recipients.contains([me]), Reminder.owner_id != me]
    if state == "active":
        conds.append(Reminder.is_active.is_(True))
    elif state == "paused":
        conds += [Reminder.is_active.is_(False), or_(Reminder.next_at.is_not(None), Reminder.snooze_at.is_not(None))]
    elif state == "finished":
        conds += [Reminder.next_at.is_(None), Reminder.snooze_at.is_(None)]
    if q and q.strip():
        conds.append(Reminder.title.ilike(f"%{q.strip()}%"))
    total = await db.scalar(select(func.count()).select_from(Reminder).where(*conds)) or 0
    rows = (await db.scalars(select(Reminder).where(*conds).order_by(Reminder.next_at.asc().nulls_last(), Reminder.id.desc()).offset((page - 1) * size).limit(size))).all()
    names = await _names(db, list(rows))
    return {"total": total, "page": page, "size": size, "items": [svc.reminder_out(r, names) for r in rows]}


@router.get("/upcoming")
async def upcoming(days: int = Query(7, ge=1, le=60), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    """Keyingi `days` kun ichidagi barcha ishga tushishlar (takrorlar yoyilgan), vaqt bo'yicha."""
    me, moment = auth.user.id, now()
    end = moment + timedelta(days=days)
    rows = (await db.scalars(select(Reminder).where(Reminder.is_active.is_(True), or_(Reminder.owner_id == me, Reminder.recipients.contains([me]))))).all()
    out = []
    for r in rows:
        cur = moment - timedelta(seconds=1)
        for _ in range(60):
            nxt = svc.compute_next(r, cur) if r.next_at is not None else None
            if nxt is None or nxt > end:
                break
            out.append({"reminder_id": r.id, "title": r.title, "at": nxt, "repeat": r.repeat})
            cur = nxt
        if r.snooze_at and r.snooze_at <= end:
            out.append({"reminder_id": r.id, "title": r.title, "at": r.snooze_at, "repeat": "snooze"})
    out.sort(key=lambda x: x["at"])
    return out[:200]


@router.post("/preview")
async def preview(body: ReminderIn, _: AuthContext = Depends(Own)):
    """Formani to'ldirayotganda keyingi 5 ta ishga tushish vaqtini ko'rsatadi."""
    r = _preview_obj(body)
    first = svc.initial_next(r, now())
    return {"next": svc.upcoming(r, first - timedelta(seconds=1), 5) if first else []}


@router.post("", status_code=201)
async def create(body: ReminderIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    await _validate_recipients(db, auth, body.recipients)
    active = await db.scalar(select(func.count()).select_from(Reminder).where(Reminder.owner_id == auth.user.id, Reminder.is_active.is_(True))) or 0
    if active >= svc.MAX_ACTIVE:
        raise error(409, "too_many_reminders", max=svc.MAX_ACTIVE)
    rem = Reminder(owner_id=auth.user.id)
    _build(body, rem)
    rem.next_at = svc.initial_next(rem, now())
    if rem.next_at is None:
        raise error(400, "no_future_occurrence")
    db.add(rem)
    await db.flush()
    svc.log(db, rem, auth.user.id, "created")
    await audit(db, request, "reminders.create", actor=auth.user, entity="reminder", entity_id=rem.id, data={"repeat": rem.repeat})
    await db.commit()
    return svc.reminder_out(rem, await _names(db, [rem]))


@router.get("/{reminder_id}")
async def detail(reminder_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    rem = await _load(db, reminder_id, auth)
    events = (await db.scalars(select(ReminderEvent).where(ReminderEvent.reminder_id == rem.id).order_by(ReminderEvent.id.desc()).limit(50))).all()
    out = svc.reminder_out(rem, await _names(db, [rem]))
    out["is_owner"] = rem.owner_id == auth.user.id
    out["next_five"] = svc.upcoming(rem, now(), 5) if rem.is_active and rem.next_at else []
    out["events"] = [{"id": e.id, "action": e.action, "data": e.data, "created_at": e.created_at} for e in events]
    return out


@router.put("/{reminder_id}")
async def update(reminder_id: int, body: ReminderIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    rem = await _load(db, reminder_id, auth, owner_only=True, lock=True)
    await _validate_recipients(db, auth, body.recipients)
    _build(body, rem)
    rem.next_at = svc.initial_next(rem, now())
    if rem.next_at is None:
        raise error(400, "no_future_occurrence")
    rem.snooze_at = None
    rem.is_active = True
    svc.log(db, rem, auth.user.id, "updated")
    await audit(db, request, "reminders.update", actor=auth.user, entity="reminder", entity_id=rem.id)
    await db.commit()
    return svc.reminder_out(rem, await _names(db, [rem]))


@router.delete("/{reminder_id}", status_code=204)
async def delete(reminder_id: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    rem = await _load(db, reminder_id, auth, owner_only=True, lock=True)
    await audit(db, request, "reminders.delete", actor=auth.user, entity="reminder", entity_id=rem.id, data={"title": rem.title})
    await db.delete(rem)
    await db.commit()


@router.post("/{reminder_id}/pause")
async def pause(reminder_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    rem = await _load(db, reminder_id, auth, owner_only=True, lock=True)
    rem.is_active = False
    svc.log(db, rem, auth.user.id, "paused")
    await db.commit()
    return svc.reminder_out(rem)


@router.post("/{reminder_id}/resume")
async def resume(reminder_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    rem = await _load(db, reminder_id, auth, owner_only=True, lock=True)
    moment = now()
    # to'xtatilgan vaqtda o'tib ketgan takrorlar yig'ilmaydi: keyingisidan davom etadi
    rem.next_at = rem.next_at if rem.next_at and rem.next_at > moment else svc.compute_next(rem, moment)
    if rem.next_at is None:
        raise error(409, "reminder_finished")
    rem.is_active = True
    svc.log(db, rem, auth.user.id, "resumed")
    await db.commit()
    return svc.reminder_out(rem)


class SnoozeIn(BaseModel):
    minutes: int | None = Field(default=None, ge=1, le=7 * 24 * 60)
    tomorrow: bool = False


@router.post("/{reminder_id}/snooze")
async def snooze(reminder_id: int, body: SnoozeIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    """Eslatmani kechiktirish: N daqiqadan keyin yoki ertaga 09:00 da yana yuboriladi."""
    rem = await _load(db, reminder_id, auth, lock=True)
    moment = now()
    if body.tomorrow:
        t = (local_date(moment) + timedelta(days=1))
        at = datetime(t.year, t.month, t.day, 9, 0, tzinfo=tz())
    elif body.minutes:
        at = moment + timedelta(minutes=body.minutes)
    else:
        raise error(400, "snooze_required")
    rem.snooze_at = at
    rem.is_active = True
    svc.log(db, rem, auth.user.id, "snoozed", {"until": at.isoformat()})
    await db.commit()
    return svc.reminder_out(rem)


@router.post("/{reminder_id}/ack")
async def ack(reminder_id: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Own)):
    """«Bajarildi»: kechiktirishni bekor qiladi; takrorlanuvchi eslatma keyingi vaqtda davom etadi."""
    rem = await _load(db, reminder_id, auth, lock=True)
    rem.last_ack_at, rem.snooze_at = now(), None
    svc.log(db, rem, auth.user.id, "done")
    if rem.next_at is None:
        rem.is_active = False
    await db.commit()
    return svc.reminder_out(rem)
