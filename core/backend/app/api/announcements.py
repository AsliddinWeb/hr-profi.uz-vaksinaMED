"""E'lonlar: tasdiqlangan zayavkadan avtomatik e'lon qoralamasi, AI tekshiruvi, joylar (kanallar) va tasdiq -> vakansiya."""

import json
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import User
from app.models.org import Branch, Department, Position
from app.models.recruit import Announcement, HireRequest, Vacancy, VacancyChannel
from app.rbac import matches
from app.services import growth
from app.services import recruit_sources as src
from app.services.audit import audit
from app.services.notifications import deliver, notify, register_template
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/recruit/announcements", tags=["recruit"])

CHANNELS = ("instagram", "telegram", "target", "hh_uz", "olx", "site", "other")
register_template("ann.draft", {"uz": "E'lon tayyorlandi", "ru": "Объявление подготовлено"}, {"uz": "{title}: tekshirib tasdiqlang", "ru": "{title}: проверьте и утвердите"}, "info")
register_template("ann.approved", {"uz": "E'lon tasdiqlandi, vakansiya ochildi", "ru": "Объявление утверждено, вакансия открыта"}, {"uz": "{title}", "ru": "{title}"}, "success")


def _has(auth: AuthContext, *p: str) -> bool:
    return any(matches(auth.permissions, x) for x in p)


def _reader(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not _has(auth, "recruit.read", "recruit.manage", "recruit.approve"):
        raise error(403, "forbidden")
    return auth


def _editor(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not _has(auth, "recruit.manage", "recruit.approve"):
        raise error(403, "forbidden")
    return auth


def _money(n: int | None) -> str | None:
    return f"{n:,}".replace(",", " ") if n else None


def compose_text(r: HireRequest, title: str, branch: Branch | None, template: str | None) -> str:
    """E'lon matni: lavozim shabloni (bo'lsa) + zayavka talablari + bo'lim boshlig'i kartochkasi."""
    card = r.card or {}
    parts: list[str] = []
    if card.get("duties"):
        parts.append("Vazifalar:\n" + str(card["duties"]).strip())
    if r.requirements:
        parts.append(r.requirements.strip())
    skills = [*card.get("hard_skills", []), *card.get("soft_skills", [])]
    if skills:
        parts.append("Talab etiladigan ko'nikmalar: " + ", ".join(skills))
    if card.get("languages"):
        parts.append("Tillar: " + ", ".join(card["languages"]))
    if card.get("education"):
        parts.append("Ma'lumot: " + card["education"])
    if card.get("min_experience"):
        parts.append(f"Tajriba: kamida {card['min_experience']} yil")
    reqs = "\n\n".join(parts) or "—"
    lo, hi = _money(r.salary_from), _money(r.salary_to)
    salary = ("💰 Maosh: " + (f"{lo} – {hi}" if lo and hi else (lo or hi or "")) + " so'm\n") if (lo or hi) else ""
    values = {"title": title, "branch": src.branch_label(branch) if branch else "", "salary": salary, "requirements": reqs, "link": "{link}"}
    try:
        return (template or src.DEFAULT_AD).format(**values)
    except (KeyError, IndexError, ValueError):
        return src.DEFAULT_AD.format(**values)


async def draft_from_request(db: AsyncSession, r: HireRequest, recruiter_id: int | None, actor_id: int) -> Announcement:
    pos = await db.get(Position, r.position_id) if r.position_id else None
    dep = await db.get(Department, r.department_id) if r.department_id else None
    br = await db.get(Branch, r.branch_id) if r.branch_id else None
    title = f"{pos.name if pos else 'Xodim'} — {(dep.name if dep else None) or (br.name if br else '')}".rstrip(" —")[:200]
    req = await src.requirement_for(db, r.position_id)
    ann = Announcement(request_id=r.id, position_id=r.position_id, title=title, text=compose_text(r, title, br, req.ad_template if req else None),
                       channels=[{"channel": "telegram", "targets": []}, {"channel": "hh_uz", "targets": []}], status="draft", recruiter_id=recruiter_id, created_by=actor_id)  # fmt: skip
    db.add(ann)
    await db.flush()
    return ann


async def _out(db: AsyncSession, a: Announcement) -> dict[str, Any]:
    r = await db.get(HireRequest, a.request_id) if a.request_id else None
    ids = {x for x in (a.created_by, a.approved_by, a.recruiter_id) if x}
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}
    return {
        "id": a.id, "title": a.title, "text": a.text, "channels": a.channels or [], "status": a.status, "ai_review": a.ai_review, "vacancy_id": a.vacancy_id,
        "request": {"id": r.id, "number": r.number, "count": r.count, "salary_from": r.salary_from, "salary_to": r.salary_to, "card": r.card or {}} if r else None,
        "recruiter": names.get(a.recruiter_id or 0), "created_by": names.get(a.created_by or 0), "approved_by": names.get(a.approved_by or 0),
        "approved_at": a.approved_at, "created_at": a.created_at, "updated_at": a.updated_at, "channel_options": CHANNELS,
    }  # fmt: skip


@router.get("")
async def list_announcements(status: str | None = Query(default=None, pattern="^(draft|approved|cancelled)$"), db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_reader)):
    stmt = select(Announcement).order_by(Announcement.status != "draft", Announcement.id.desc()).limit(300)
    if status:
        stmt = stmt.where(Announcement.status == status)
    rows = (await db.scalars(stmt)).all()
    counts = dict((await db.execute(select(Announcement.status, func.count()).group_by(Announcement.status))).all())
    return {
        "items": [{"id": a.id, "title": a.title, "status": a.status, "channels": a.channels or [], "vacancy_id": a.vacancy_id, "created_at": a.created_at} for a in rows],
        "counts": {k: counts.get(k, 0) for k in ("draft", "approved", "cancelled")},
    }


async def _load(db: AsyncSession, aid: int) -> Announcement:
    a = await db.get(Announcement, aid)
    if not a:
        raise error(404, "not_found")
    return a


@router.get("/{aid}")
async def get_announcement(aid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_reader)):
    return await _out(db, await _load(db, aid))


class ChannelIn(BaseModel):
    channel: str = Field(pattern="^(instagram|telegram|target|hh_uz|olx|site|other)$")
    targets: list[str] = Field(default_factory=list, max_length=50)


class AnnIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    text: str = Field(min_length=10, max_length=8000)
    channels: list[ChannelIn] = Field(default_factory=list, max_length=20)


def _clean_channels(chs: list[ChannelIn]) -> list[dict[str, Any]]:
    out: dict[str, list[str]] = {}
    for c in chs:
        tg = out.setdefault(c.channel, [])
        for x in c.targets:
            x = x.strip()[:120]
            if x and x not in tg:
                tg.append(x)
    return [{"channel": k, "targets": v} for k, v in out.items()]


@router.put("/{aid}")
async def save_announcement(aid: int, body: AnnIn, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_editor)):
    a = await _load(db, aid)
    if a.status != "draft":
        raise error(409, "not_editable")
    a.title, a.text, a.channels = body.title.strip(), body.text.strip(), _clean_channels(body.channels)
    await db.commit()
    await db.refresh(a)
    return await _out(db, a)


@router.post("/{aid}/ai-review")
async def ai_review(aid: int, body: AnnIn, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_editor)):
    """AI e'lonni tekshiradi: kamchiliklar va yaxshilangan matn (saqlanmaydi; foydalanuvchi qo'llaydi)."""
    from app.services import ai

    a = await _load(db, aid)
    system = (
        f"{ai.SYSTEM_RULES}\nVazifa: siz tajribali HR-marketolog siz. Vakansiya e'lonini tekshiring. Javob tili: o'zbek (lotin); faqat shu alifboda yozing. "
        'FAQAT JSON: {"score": 0-100, "issues": [str], "improved": str}. issues — 3–8 ta aniq kamchilik (maosh, vazifa, talablar, sharoit, aloqa, uzunlik, ijtimoiy tarmoqqa moslik). '
        "improved — shu ma'lumotlar asosida tayyor, jozibali, qisqa e'lon matni (emoji mumkin); yangi fakt to'qimang; {link} o'rinbosarini saqlang."
    )
    payload = json.dumps({"title": body.title, "text": body.text}, ensure_ascii=False)[:8000]
    raw, _ = await ai.run(db, auth, "profile", system, f"<data>\n{payload}\n</data>", max_tokens=2000, entity="announcement", entity_id=a.id)
    d = ai.extract_json(raw)
    review = {"score": d.get("score") if isinstance(d.get("score"), int) else None, "issues": [str(x)[:300] for x in (d.get("issues") or []) if x][:10], "improved": str(d.get("improved") or "")[:8000]}
    a.ai_review = review
    await db.commit()
    return review


@router.post("/{aid}/approve")
async def approve(aid: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_editor)):
    """E'lon tasdiqlanadi: vakansiya ochiladi, tanlangan joylar vakansiyaga yoziladi, avtomatik havolalar yaratiladi."""
    a = await db.scalar(select(Announcement).where(Announcement.id == aid).with_for_update())
    if not a:
        raise error(404, "not_found")
    if a.status != "draft":
        raise error(409, "already_decided")
    if not a.channels:
        raise error(400, "channels_required")
    r = await db.get(HireRequest, a.request_id) if a.request_id else None
    moment = now()
    br = await db.get(Branch, r.branch_id) if r and r.branch_id else None
    sla = (await growth.get_setting(db, "recruit"))["sla_days"]
    v = Vacancy(
        title=a.title, department_id=r.department_id if r else None, branch_id=r.branch_id if r else None, position_id=a.position_id,
        requirements=r.requirements if r else None, salary_from=r.salary_from if r else None, salary_to=r.salary_to if r else None, openings=r.count if r else 1,
        status="open", recruiter_id=a.recruiter_id, deadline=(r.needed_from if r and r.needed_from else local_date(moment) + timedelta(days=sla)),
        opened_at=moment, created_by=auth.user.id, description=a.text,
    )  # fmt: skip
    db.add(v)
    await db.flush()
    for c in a.channels:
        ch = c["channel"] if c["channel"] in src.CHANNELS else "other"
        for tgt in c.get("targets") or [None]:
            db.add(VacancyChannel(vacancy_id=v.id, channel=ch, note=(f"{c['channel']}: {tgt}" if tgt else c["channel"])[:300], posted_by=auth.user.id))
    a.status, a.vacancy_id, a.approved_by, a.approved_at = "approved", v.id, auth.user.id, moment
    if r:
        r.vacancy_id = v.id
    post = await src.auto_publish(db, v, br, a.recruiter_id or auth.user.id, auth.user.id)
    targets = [x for x in {a.created_by, a.recruiter_id, r.created_by if r else None} if x and x != auth.user.id]
    notes = await notify(db, targets, "ann.approved", params={"title": a.title}, link=f"/recruit/vacancies/{v.id}")
    await audit(db, request, "recruit.announcement_approve", actor=auth.user, entity="announcement", entity_id=a.id, data={"vacancy_id": v.id, "channels": a.channels})
    await db.commit()
    await deliver(request.app, notes)
    await src.send_post(request.app, post)
    await db.refresh(a)
    return await _out(db, a)


@router.post("/{aid}/cancel")
async def cancel(aid: int, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_editor)):
    a = await _load(db, aid)
    if a.status != "draft":
        raise error(409, "already_decided")
    a.status = "cancelled"
    await db.commit()
    await db.refresh(a)
    return await _out(db, a)
