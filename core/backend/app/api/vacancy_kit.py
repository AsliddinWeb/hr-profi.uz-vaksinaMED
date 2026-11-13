"""Vakansiya paneli: rekruter uchun «Xodim qidirish» to'plami va HR uchun nazorat ma'lumotlari.

Kompetensiyalar (lavozim profili + zayavka kartochkasi), nomzod havolalari (bosilish va arizalar soni), kelgan rezyumelar,
statistika (qidirilmoqda / topildi) va rekruter faoliyati.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.competency import Competency, PositionProfile, ProfileCompetency
from app.models.recruit import (
    Application,
    ApplicationEvent,
    Candidate,
    HireRequest,
    SourceLink,
    Vacancy,
)
from app.rbac import matches
from app.services import recruit_sources as src
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/recruit/vacancies", tags=["recruit"])


def _reader(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not any(matches(auth.permissions, p) for p in ("recruit.read", "recruit.manage", "recruit.approve")):
        raise error(403, "forbidden")
    return auth


async def vacancy_competencies(db: AsyncSession, v: Vacancy) -> dict[str, Any]:
    """Vakansiya kompetensiyalari: lavozimning tasdiqlangan profili va zayavka kartochkasi birlashtiriladi."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    duties: list[str] = []
    if v.position_id:
        prof = await db.scalar(select(PositionProfile).where(PositionProfile.position_id == v.position_id, PositionProfile.status == "approved").order_by(PositionProfile.version.desc()).limit(1))
        if prof:
            rows = (await db.execute(select(ProfileCompetency, Competency).join(Competency, Competency.id == ProfileCompetency.competency_id).where(ProfileCompetency.profile_id == prof.id))).all()
            for pc, c in rows:
                by_cat.setdefault(c.category, []).append({"name": c.name, "level": pc.required_level, "mandatory": pc.mandatory})
            duties += [x for x in (prof.data or {}).get("functions") or [] if x]
    req = await db.scalar(select(HireRequest).where(HireRequest.vacancy_id == v.id).limit(1))
    questions: list[str] = []
    if req and req.card:
        card = req.card
        for cat, key in (("hard", "hard_skills"), ("soft", "soft_skills"), ("knowledge", "languages")):
            have = {x["name"].lower() for x in by_cat.get(cat, [])}
            for name in card.get(key) or []:
                if name.lower() not in have:
                    by_cat.setdefault(cat, []).append({"name": name, "level": None, "mandatory": True})
        if card.get("duties"):
            duties.append(str(card["duties"]))
        questions = list(card.get("questions") or [])
    return {"by_category": by_cat, "duties": duties, "questions": questions, "min_experience": (req.card or {}).get("min_experience") if req else None}


@router.get("/{vid}/kit")
async def vacancy_kit(vid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_reader)):
    v = await db.get(Vacancy, vid)
    if not v:
        raise error(404, "not_found")
    apps = (await db.execute(select(Application, Candidate).join(Candidate, Candidate.id == Application.candidate_id).where(Application.vacancy_id == vid).order_by(Application.applied_at.desc()))).all()
    links = (await db.scalars(select(SourceLink).where(SourceLink.vacancy_id == vid).order_by(SourceLink.id))).all()
    per_link = dict((await db.execute(select(Application.source_link_id, func.count()).where(Application.vacancy_id == vid, Application.source_link_id.is_not(None)).group_by(Application.source_link_id))).all())
    by_stage: dict[str, int] = {}
    for a, _ in apps:
        by_stage[a.stage] = by_stage.get(a.stage, 0) + 1
    hired = by_stage.get("hired", 0)
    today = local_date(now())
    events = (await db.execute(
        select(ApplicationEvent, Candidate.full_name).join(Application, Application.id == ApplicationEvent.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id).where(Application.vacancy_id == vid).order_by(ApplicationEvent.id.desc()).limit(20)
    )).all()  # fmt: skip
    uids = {e.actor_id for e, _ in events if e.actor_id} | ({v.recruiter_id} if v.recruiter_id else set())
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(uids)))).all()} if uids else {}
    opened = v.opened_at or v.created_at
    return {
        "vacancy": {"id": v.id, "title": v.title, "status": v.status, "openings": v.openings, "hired": hired, "found": hired >= v.openings,
                    "recruiter": names.get(v.recruiter_id or 0), "deadline": v.deadline, "days_open": (datetime.now(opened.tzinfo) - opened).days if opened else None},
        "competencies": await vacancy_competencies(db, v),
        "links": [{"id": lk.id, "url": src.apply_url(lk.code), "label": lk.label, "channel": lk.channel, "clicks": lk.clicks, "applications": per_link.get(lk.id, 0), "active": lk.is_active} for lk in links],
        "stats": {"total": len(apps), "by_stage": by_stage, "today": sum(1 for a, _ in apps if a.applied_at and local_date(a.applied_at) == today),
                  "with_resume": sum(1 for _, c in apps if c.resume_text or c.profile_confirmed_at)},
        "resumes": [{"application_id": a.id, "candidate_id": c.id, "name": c.full_name, "phone": c.phone, "stage": a.stage, "applied_at": a.applied_at,
                     "has_resume": bool(c.resume_text), "anketa": bool(c.profile_confirmed_at)} for a, c in apps[:200]],
        "activity": [{"at": e.created_at, "actor": names.get(e.actor_id or 0), "action": e.action, "to": e.to_stage, "candidate": n} for e, n in events],
    }  # fmt: skip
