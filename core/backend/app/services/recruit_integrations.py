"""Rekruting integratsiyalari jurnali va eslatmalar (TZ: integratsiyalar holati/loglari, bildirishnomalar)."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.recruit import Application, HireRequest, IntegrationLog, RecruitCall, Vacancy
from app.services.notifications import notify, register_template
from app.timeutil import local_date

log = logging.getLogger("vaksina.recruit")

register_template(
    "recruit.no_show",
    {"uz": "Nomzod intervyuga kelmadi", "ru": "Кандидат не пришёл на интервью"},
    {"uz": "{candidate} — «{vacancy}»", "ru": "{candidate} — «{vacancy}»"},
    "warning",
)
register_template(
    "recruit.followup",
    {"uz": "Rekruting: bugungi vazifalar", "ru": "Подбор: задачи на сегодня"},
    {"uz": "Qotib qolgan nomzodlar: {stuck}, javobsiz offerlar: {offers}, bugun qayta qo'ng'iroq: {callbacks}",
     "ru": "Зависшие кандидаты: {stuck}, офферы без ответа: {offers}, перезвонить сегодня: {callbacks}"},
    "info",
)

STUCK_DAYS = 3
OFFER_DAYS = 3


async def log_integration(provider: str, action: str, ok: bool, message: str | None = None, ref: str | None = None) -> None:
    """Alohida sessiyada yoziladi: jurnal xatosi asosiy ishni to'xtatmasin."""
    try:
        async with SessionLocal() as s:
            s.add(IntegrationLog(provider=provider, action=action, ok=ok, message=(message or None) and message[:300], ref=ref))
            await s.commit()
    except Exception:  # noqa: BLE001
        log.exception("integration log yozilmadi")


async def no_show_notes(db: AsyncSession, a: Application, candidate: str, actor_id: int) -> list[Any]:
    v = await db.get(Vacancy, a.vacancy_id)
    if not v:
        return []
    targets = {a.recruiter_id, v.recruiter_id, v.created_by}
    targets |= set((await db.scalars(select(HireRequest.created_by).where(HireRequest.vacancy_id == v.id))).all())
    targets = {u for u in targets if u and u != actor_id}
    if not targets:
        return []
    return await notify(db, sorted(targets), "recruit.no_show", params={"candidate": candidate, "vacancy": v.title}, link=f"/recruit/applications/{a.id}")


async def followup_scan(db: AsyncSession, moment: datetime) -> list[Any]:
    """Har bir rekruterga bitta xulosa: N kundan beri harakatsiz arizalar, javob kutilayotgan offerlar, bugungi qayta qo'ng'iroqlar."""
    per: dict[int, dict[str, int]] = defaultdict(lambda: {"stuck": 0, "offers": 0, "callbacks": 0})
    rows = (await db.execute(
        select(Application, Vacancy.recruiter_id).join(Vacancy, Vacancy.id == Application.vacancy_id)
        .where(Vacancy.status == "open", Application.stage.in_(("new", "screening", "interview", "offer")))
    )).all()  # fmt: skip
    for a, vrec in rows:
        rec = a.recruiter_id or vrec
        if not rec:
            continue
        if a.stage in ("new", "screening") and a.stage_changed_at and a.stage_changed_at < moment - timedelta(days=STUCK_DAYS):
            per[rec]["stuck"] += 1
        if a.offer_sent_at and not a.offer_response and a.offer_sent_at < moment - timedelta(days=OFFER_DAYS):
            per[rec]["offers"] += 1
    today = local_date(moment)
    for rc in (await db.scalars(select(RecruitCall).where(RecruitCall.outcome == "callback", RecruitCall.callback_date == today))).all():
        per[rc.recruiter_id]["callbacks"] += 1
    notes: list[Any] = []
    for uid, c in per.items():
        if any(c.values()):
            notes += await notify(db, [uid], "recruit.followup", params=c, link="/recruit/today")
    return notes
