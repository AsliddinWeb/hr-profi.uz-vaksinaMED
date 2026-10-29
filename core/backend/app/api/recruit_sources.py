"""Rekruting: lavozim talablari, vakansiya e'loni va kanallari, shaxsiy manba linklari, ommaviy ariza va manba hisoboti."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.recruit import Manage, Read
from app.db import get_session
from app.deps import AuthContext, error
from app.models.org import Branch, Position
from app.models.recruit import (
    Application,
    Candidate,
    PositionRequirement,
    PositionRequirementVersion,
    SourceLink,
    Vacancy,
    VacancyChannel,
)
from app.services import employees as emp_svc
from app.services import recruit as rsvc
from app.services import recruit_core as core
from app.services import recruit_sources as svc
from app.services.audit import audit, client_ip
from app.services.notifications import deliver
from app.timeutil import now

router = APIRouter(prefix="/v1/recruit", tags=["recruit-sources"])
public_router = APIRouter(prefix="/v1/public", tags=["public"])


# --- Lavozim talablari --------------------------------------------------------------------


class CardIn(BaseModel):
    duties: str | None = Field(default=None, max_length=3000)
    hard_skills: list[str] = Field(default_factory=list, max_length=30)
    soft_skills: list[str] = Field(default_factory=list, max_length=30)
    languages: list[str] = Field(default_factory=list, max_length=10)
    education: str | None = Field(default=None, max_length=200)
    min_experience: int | None = Field(default=None, ge=0, le=50)
    exclusions: list[str] = Field(default_factory=list, max_length=30)


class RequirementIn(BaseModel):
    requirements: str | None = Field(default=None, max_length=4000)
    competencies: list[str] = Field(default_factory=list, max_length=30)
    ad_template: str | None = Field(default=None, max_length=4000)
    profile: CardIn | None = None
    note: str | None = Field(default=None, max_length=300)


def _req_out(r: PositionRequirement, position: str | None) -> dict[str, Any]:
    return {"position_id": r.position_id, "position": position, "requirements": r.requirements, "competencies": r.competencies or [], "ad_template": r.ad_template, "profile": r.profile or core.clean_card({}), "version": r.version or 1}


@router.get("/requirements")
async def list_requirements(db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    pos = {p.id: p.name for p in (await db.scalars(select(Position))).all()}
    have = {r.position_id: r for r in (await db.scalars(select(PositionRequirement))).all()}
    return [{"position_id": pid, "position": name, "filled": pid in have, "competencies": (have[pid].competencies if pid in have else []) or []} for pid, name in sorted(pos.items(), key=lambda x: x[1])]


@router.get("/requirements/{position_id}")
async def get_requirement(position_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    p = await db.get(Position, position_id)
    if not p:
        raise error(404, "not_found")
    r = await svc.requirement_for(db, position_id)
    return _req_out(r, p.name) if r else {"position_id": position_id, "position": p.name, "requirements": None, "competencies": [], "ad_template": None, "profile": core.clean_card({}), "version": 0}


@router.get("/requirements/{position_id}/versions")
async def requirement_versions(position_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    rows = (await db.scalars(select(PositionRequirementVersion).where(PositionRequirementVersion.position_id == position_id).order_by(PositionRequirementVersion.version.desc()))).all()
    names = await rsvc.names(db, {v.changed_by for v in rows})
    return [{"version": v.version, "snapshot": v.snapshot, "note": v.note, "changed_by": names.get(v.changed_by or 0), "created_at": v.created_at} for v in rows]


@router.put("/requirements/{position_id}")
async def put_requirement(position_id: int, body: RequirementIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    p = await db.get(Position, position_id)
    if not p:
        raise error(404, "not_found")
    if body.ad_template:
        try:  # shablon faqat ma'lum o'rinbosarlarni ishlatsin
            body.ad_template.format(title="", branch="", salary="", requirements="", link="")
        except (KeyError, IndexError, ValueError):
            raise error(400, "template_invalid") from None
    r = await svc.requirement_for(db, position_id)
    new_vals = {"requirements": (body.requirements or "").strip() or None, "ad_template": (body.ad_template or "").strip() or None, "competencies": [c.strip() for c in body.competencies if c.strip()],
                "profile": core.clean_card(body.profile.model_dump() if body.profile else (r.profile if r else {}))}  # fmt: skip
    if r is None:
        r = PositionRequirement(position_id=position_id, version=1)
        db.add(r)
        await db.flush()
    elif core.snapshot(r) != new_vals:  # o'zgarish bo'lsa eski holat versiya sifatida saqlanadi
        db.add(PositionRequirementVersion(position_id=position_id, version=r.version or 1, snapshot=core.snapshot(r), note=(body.note or "").strip() or None, changed_by=auth.user.id))
        r.version = (r.version or 1) + 1
    r.requirements, r.ad_template, r.competencies, r.profile, r.updated_by = new_vals["requirements"], new_vals["ad_template"], new_vals["competencies"], new_vals["profile"], auth.user.id
    await audit(db, request, "recruit.requirement", actor=auth.user, entity="position", entity_id=position_id)
    await db.commit()
    return _req_out(r, p.name)


# --- E'lon, kanallar, linklar -------------------------------------------------------------


async def _vacancy(db: AsyncSession, vid: int) -> Vacancy:
    v = await db.get(Vacancy, vid)
    if not v:
        raise error(404, "not_found")
    return v


async def _links_out(db: AsyncSession, vid: int) -> list[dict[str, Any]]:
    links = list((await db.scalars(select(SourceLink).where(SourceLink.vacancy_id == vid).order_by(SourceLink.id))).all())
    if not links:
        return []
    ids = [lk.id for lk in links]
    apps = dict((await db.execute(select(Application.source_link_id, func.count()).where(Application.source_link_id.in_(ids)).group_by(Application.source_link_id))).all())
    hired = dict((await db.execute(select(Application.source_link_id, func.count()).where(Application.source_link_id.in_(ids), Application.stage == "hired").group_by(Application.source_link_id))).all())
    names = await rsvc.names(db, {lk.owner_user_id for lk in links})
    return [svc.link_out(lk, names.get(lk.owner_user_id or 0), apps.get(lk.id, 0), hired.get(lk.id, 0)) for lk in links]


@router.get("/vacancies/{vid}/promo")
async def promo(vid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    v = await _vacancy(db, vid)
    branch = await db.get(Branch, v.branch_id) if v.branch_id else None
    req = await svc.requirement_for(db, v.position_id)
    links = await _links_out(db, vid)
    chans = list((await db.scalars(select(VacancyChannel).where(VacancyChannel.vacancy_id == vid).order_by(VacancyChannel.id.desc()))).all())
    names = await rsvc.names(db, {c.posted_by for c in chans})
    return {
        "vacancy": {"id": v.id, "title": v.title, "status": v.status, "branch": svc.branch_label(branch) if branch else None},
        "ad": svc.ad_text(v, branch, req, links[0]["url"] if links else svc.apply_url("…")),
        "channels": [{"id": c.id, "channel": c.channel, "url": c.url, "note": c.note, "posted_by": names.get(c.posted_by or 0), "posted_at": c.posted_at, "closed_at": c.closed_at} for c in chans],
        "links": links,
    }  # fmt: skip


class ChannelIn(BaseModel):
    channel: str = Field(pattern=svc.CHANNEL_RE)
    url: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=300)


@router.post("/vacancies/{vid}/channels", status_code=201)
async def add_channel(vid: int, body: ChannelIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    await _vacancy(db, vid)
    if body.url and not body.url.lower().startswith(("http://", "https://")):
        raise error(400, "url_invalid")
    c = VacancyChannel(vacancy_id=vid, channel=body.channel, url=(body.url or "").strip() or None, note=(body.note or "").strip() or None, posted_by=auth.user.id)
    db.add(c)
    await audit(db, request, "recruit.channel_add", actor=auth.user, entity="vacancy", entity_id=vid, data={"channel": body.channel})
    await db.commit()
    return {"id": c.id}


@router.delete("/vacancies/{vid}/channels/{cid}", status_code=204)
async def remove_channel(vid: int, cid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Manage)):
    c = await db.get(VacancyChannel, cid)
    if not c or c.vacancy_id != vid:
        raise error(404, "not_found")
    await db.delete(c)
    await db.commit()


class LinkIn(BaseModel):
    channel: str = Field(pattern=svc.CHANNEL_RE)
    owner_user_id: int | None = None
    label: str | None = Field(default=None, max_length=120)


@router.post("/vacancies/{vid}/links", status_code=201)
async def add_link(vid: int, body: LinkIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Manage)):
    await _vacancy(db, vid)
    owner = body.owner_user_id if body.owner_user_id is not None else auth.user.id
    lk = SourceLink(code=await svc.unique_code(db), vacancy_id=vid, channel=body.channel, owner_user_id=owner, label=(body.label or "").strip() or None)
    db.add(lk)
    await db.flush()
    await audit(db, request, "recruit.link_add", actor=auth.user, entity="vacancy", entity_id=vid, data={"channel": body.channel, "owner": owner})
    await db.commit()
    names = await rsvc.names(db, {owner})
    return svc.link_out(lk, names.get(owner or 0))


@router.post("/links/{link_id}/deactivate")
async def deactivate_link(link_id: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Manage)):
    lk = await db.get(SourceLink, link_id)
    if not lk:
        raise error(404, "not_found")
    lk.is_active = False
    await db.commit()
    return {"ok": True}


@router.get("/sources")
async def sources_report(vacancy_id: int | None = None, start: str | None = None, end: str | None = None, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(Read)):
    """Manba hisobi: kanal va link egasi bo'yicha ariza, ishga olingan va linkni ochganlar soni."""
    stmt = select(Application, SourceLink).join(SourceLink, SourceLink.id == Application.source_link_id, isouter=True)
    if vacancy_id:
        stmt = stmt.where(Application.vacancy_id == vacancy_id)
    if start:
        stmt = stmt.where(Application.applied_at >= datetime.fromisoformat(start))
    if end:
        stmt = stmt.where(Application.applied_at < datetime.fromisoformat(end))
    rows = (await db.execute(stmt)).all()
    cands = {c.id: c for c in (await db.scalars(select(Candidate).where(Candidate.id.in_({a.candidate_id for a, _ in rows})))).all()} if rows else {}
    by_channel: dict[str, dict[str, int]] = {}
    by_owner: dict[int | None, dict[str, int]] = {}
    for a, lk in rows:
        ch = lk.channel if lk else (cands[a.candidate_id].source if a.candidate_id in cands and cands[a.candidate_id].source else "other")
        for bucket, key in ((by_channel, ch), (by_owner, lk.owner_user_id if lk else None)):
            d = bucket.setdefault(key, {"applications": 0, "hired": 0})  # type: ignore[arg-type]
            d["applications"] += 1
            d["hired"] += a.stage == "hired"
    link_stmt = select(SourceLink.channel, func.coalesce(func.sum(SourceLink.clicks), 0), func.count()).group_by(SourceLink.channel)
    if vacancy_id:
        link_stmt = link_stmt.where(SourceLink.vacancy_id == vacancy_id)
    clicks = {r[0]: (int(r[1]), r[2]) for r in (await db.execute(link_stmt)).all()}
    names = await rsvc.names(db, {k for k in by_owner if k})
    return {
        "by_channel": sorted([{"channel": k, **v, "clicks": clicks.get(k, (0, 0))[0], "links": clicks.get(k, (0, 0))[1]} for k, v in by_channel.items()], key=lambda x: -x["applications"]),
        "by_owner": sorted([{"owner": names.get(k) if k else None, **v} for k, v in by_owner.items()], key=lambda x: -x["applications"]),
        "total": len(rows),
    }  # fmt: skip


# --- Ommaviy ariza (login talab qilinmaydi) -----------------------------------------------


async def _rate(request: Request, kind: str, limit: int, window: int) -> None:
    redis = request.app.state.redis
    key = f"rl:{kind}:{client_ip(request)}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, window)
    if n > limit:
        raise error(429, "too_many_attempts", retry_after=max(await redis.ttl(key), 1))


async def _open_link(db: AsyncSession, code: str) -> tuple[SourceLink, Vacancy]:
    lk = await db.scalar(select(SourceLink).where(SourceLink.code == code[:16]))
    v = await db.get(Vacancy, lk.vacancy_id) if lk else None
    if not lk or not v or not lk.is_active or v.status != "open":
        raise error(404, "not_found")
    return lk, v


@public_router.get("/apply/{code}")
async def apply_info(code: str, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "apply_view", 120, 60)
    lk, v = await _open_link(db, code)
    lk.clicks += 1
    branch = await db.get(Branch, v.branch_id) if v.branch_id else None
    await db.commit()
    return {"title": v.title, "branch": svc.branch_label(branch) if branch else None, "salary_from": v.salary_from, "salary_to": v.salary_to, "requirements": v.requirements}


class ApplyIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=250)
    phone: str = Field(min_length=7, max_length=20)
    note: str | None = Field(default=None, max_length=1000)
    website: str | None = Field(default=None, max_length=100)  # ko'rinmas tuzoq maydon: botlar to'ldiradi


@public_router.post("/apply/{code}", status_code=201)
async def apply(code: str, body: ApplyIn, request: Request, db: AsyncSession = Depends(get_session)):
    await _rate(request, "apply_post", 5, 3600)
    lk, v = await _open_link(db, code)
    if body.website:  # bot: jim "muvaffaqiyat" qaytaramiz, hech narsa yozmaymiz
        return {"ok": True}
    try:
        phone = emp_svc.normalize_phone(body.phone)
    except ValueError:
        raise error(400, "phone_invalid") from None
    status, _, notes = await svc.submit_application(db, lk, v, full_name=body.full_name, phone=phone, note=body.note, chat_id=None, moment=now())
    await db.commit()
    await deliver(request.app, notes)
    return {"ok": True, **({"duplicate": True} if status == "duplicate" else {})}
