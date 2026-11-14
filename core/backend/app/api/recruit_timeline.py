"""Nomzod profili: intervyuga kelish nazorati (keldi / kelmadi) va nomzodning to'liq xronologiyasi (TZ).

Timeline faqat o'qiladi: arizalar, bosqich hodisalari, qo'ng'iroqlar (nomzod yoki uning telefoni bo'yicha), intervyu taklifnomalari,
xavfsizlik tekshiruvi, offer va ishga qabul bitta lentada ko'rsatiladi.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.recruit import require
from app.db import get_session
from app.deps import AuthContext, error
from app.models.auth import User
from app.models.recruit import (
    Application,
    ApplicationEvent,
    BackgroundCheck,
    Candidate,
    InterviewInvite,
    RecruitCall,
    Vacancy,
)
from app.services import recruit as rsvc
from app.services.audit import audit
from app.timeutil import now

router = APIRouter(prefix="/v1/recruit", tags=["recruit"])
Read = require("recruit.read")
Manage = require("recruit.manage")


class AttendanceIn(BaseModel):
    attended: bool
    note: str | None = Field(default=None, max_length=500)


@router.post("/applications/{aid}/attendance")
async def mark_attendance(aid: int, body: AttendanceIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    a = await db.scalar(select(Application).where(Application.id == aid).with_for_update())
    if not a:
        raise error(404, "not_found")
    if a.stage in ("new", "hired") and not a.interview_at:
        raise error(409, "no_interview")
    moment = now()
    a.interview_attended, a.attendance_at = body.attended, moment
    action = "attended" if body.attended else "no_show"
    rsvc.log(db, a, auth.user.id, action, note=(body.note or "").strip() or None)
    await audit(db, request, f"recruit.interview_{action}", actor=auth.user, entity="application", entity_id=a.id)
    await db.commit()
    return {"id": a.id, "interview_attended": a.interview_attended, "attendance_at": a.attendance_at}


@router.get("/candidates/{cid}/timeline")
async def candidate_timeline(cid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    c = await db.get(Candidate, cid)
    if not c:
        raise error(404, "not_found")
    ev: list[dict[str, Any]] = []

    def add(kind: str, at: datetime | None, action: str, actor: int | None = None, **data: Any) -> None:
        if at:
            ev.append({"kind": kind, "at": at, "action": action, "actor_id": actor, "data": data})

    add("candidate", c.created_at, "candidate_created", c.created_by, source=c.source)
    add("candidate", c.profile_confirmed_at, "profile_confirmed")
    apps = (await db.execute(select(Application, Vacancy.title).join(Vacancy, Vacancy.id == Application.vacancy_id).where(Application.candidate_id == cid))).all()
    titles = {a.id: title for a, title in apps}
    for a, title in apps:
        add("application", a.applied_at, "applied", None, vacancy=title, application_id=a.id)
        add("interview", a.interview_at, "interview_scheduled", None, vacancy=title, application_id=a.id)
        add("interview", a.attendance_at, "attended" if a.interview_attended else "no_show", None, vacancy=title, application_id=a.id)
        add("interview", a.interviewed_at, "interviewed", a.interviewed_by, vacancy=title, application_id=a.id, hard=a.hard_skill, soft=a.soft_skill)
        add("offer", a.offer_sent_at, "offer_sent", a.offer_by, vacancy=title, application_id=a.id, salary=a.offer_salary)
        add("offer", a.offer_response_at, f"offer_{a.offer_response}", None, vacancy=title, application_id=a.id, reason=a.offer_decline_reason)
        add("hire", a.hired_at, "hired", None, vacancy=title, application_id=a.id)
    ids = list(titles)
    if ids:
        for e in (await db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id.in_(ids)))).all():
            if e.action in ("applied", "hired", "attended", "no_show"):
                continue  # yuqorida aniq sanasi bilan bor
            add("stage", e.created_at, e.action, e.actor_id, vacancy=titles.get(e.application_id), application_id=e.application_id, from_stage=e.from_stage, to_stage=e.to_stage, note=(e.note or "")[:300])
        for inv in (await db.scalars(select(InterviewInvite).where(InterviewInvite.application_id.in_(ids)))).all():
            add("interview", inv.created_at, "invite_sent", inv.created_by, vacancy=titles.get(inv.application_id), mode=inv.mode, place=inv.place)
            add("interview", inv.replied_at, "invite_replied", None, vacancy=titles.get(inv.application_id), status=inv.status, reply=inv.reply)
        for b in (await db.scalars(select(BackgroundCheck).where(BackgroundCheck.application_id.in_(ids)))).all():
            add("background", b.created_at, "bg_started", b.created_by, vacancy=titles.get(b.application_id))
            add("background", b.finished_at, "bg_finished", b.checked_by, vacancy=titles.get(b.application_id), decision=b.decision)
    conds = [RecruitCall.candidate_id == cid]
    if c.phone:
        conds.append(RecruitCall.phone == c.phone)
    for rc in (await db.scalars(select(RecruitCall).where(or_(*conds)))).all():
        add("call", rc.called_at, "call", rc.recruiter_id, outcome=rc.outcome, direction=rc.direction, note=(rc.note or "")[:300], callback_date=rc.callback_date)

    ev.sort(key=lambda x: x["at"], reverse=True)
    uids = {x["actor_id"] for x in ev if x["actor_id"]}
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(uids)))).all()} if uids else {}
    counts: dict[str, int] = {}
    for x in ev:
        counts[x["kind"]] = counts.get(x["kind"], 0) + 1
        x["actor"] = names.get(x.pop("actor_id") or 0)
    return {"items": ev[:1000], "total": len(ev), "counts": counts}
