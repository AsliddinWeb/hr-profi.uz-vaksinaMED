"""CRM avtomatikasi: bosqich o'zgarishi (ehtimollik + avtomatik faoliyat), maydonlar tarixi, faoliyat holati, muddat nazorati."""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import CrmActivity, CrmDeal, CrmMessage, CrmStage
from app.services.notifications import notify, register_template
from app.timeutil import local_date, now

register_template("crm.activity_assigned", {"uz": "Sizga CRM faoliyati biriktirildi", "ru": "Вам назначено действие в CRM"}, {"uz": "{title} — {deal} ({due})", "ru": "{title} — {deal} ({due})"}, "info")
register_template("crm.activity_overdue", {"uz": "CRM faoliyati kechikdi", "ru": "Действие в CRM просрочено"}, {"uz": "{title} — {deal} (muddat: {due})", "ru": "{title} — {deal} (срок: {due})"}, "warning")
register_template("crm.deal_assigned", {"uz": "Sizga bitim biriktirildi", "ru": "Вам назначена сделка"}, {"uz": "{deal}", "ru": "{deal}"}, "info")
register_template("crm.deal_won", {"uz": "Bitim yutildi", "ru": "Сделка выиграна"}, {"uz": "{deal}: {amount}", "ru": "{deal}: {amount}"}, "success")

KINDS = ("call", "meeting", "email", "task")
# Lentada kuzatiladigan maydonlar (o'zgarsa avtomatik yozuv tushadi)
TRACKED = ("title", "company", "contact_name", "phone", "email", "amount", "probability", "priority", "expected_close", "owner_id", "source")


def log(db: AsyncSession, deal: CrmDeal, actor_id: int | None, action: str, **data: Any) -> CrmMessage:
    m = CrmMessage(deal_id=deal.id, kind="event", author_id=actor_id, data={"action": action, **data})
    db.add(m)
    return m


def fmt_amount(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") + " UZS"


def activity_state(due: date | None, today: date) -> dict[str, Any] | None:
    """Kartadagi belgi: kechikdi (N kun) / bugun / reja."""
    if due is None:
        return None
    if due < today:
        return {"state": "overdue", "days": (today - due).days, "due": due}
    if due == today:
        return {"state": "today", "days": 0, "due": due}
    return {"state": "planned", "days": (due - today).days, "due": due}


async def add_activity(
    db: AsyncSession,
    deal: CrmDeal,
    *,
    kind: str,
    title: str,
    due: date,
    assignee_id: int | None,
    actor_id: int | None,
    note: str | None = None,
    auto: bool = False,
) -> tuple[CrmActivity, list]:
    a = CrmActivity(deal_id=deal.id, kind=kind if kind in KINDS else "task", title=title, note=note, due_date=due, assignee_id=assignee_id, created_by=actor_id, auto=auto)
    db.add(a)
    await db.flush()
    log(db, deal, actor_id, "activity_added", activity_id=a.id, kind=a.kind, title=title, due=due.isoformat(), auto=auto)
    notes = []
    if assignee_id and assignee_id != actor_id:
        notes = await notify(db, [assignee_id], "crm.activity_assigned", params={"title": title, "deal": deal.title, "due": due.strftime("%d.%m.%Y")}, link=f"/crm/deals/{deal.id}")
    return a, notes


async def enter_stage(db: AsyncSession, deal: CrmDeal, stage: CrmStage, actor_id: int | None, *, from_stage: CrmStage | None) -> list:
    """Bitim yangi bosqichga kirdi: ehtimollik bosqichdan olinadi, yutish belgilanadi, avtomatik faoliyat qo'yiladi."""
    moment = now()
    deal.stage_id = stage.id
    deal.stage_changed_at = moment
    deal.probability = stage.probability
    notes: list = []
    if stage.is_won and not deal.won_at:
        deal.won_at, deal.lost_at, deal.lost_reason = moment, None, None
        # Yutilgan bitimdagi ochiq avtomatik faoliyatlar endi kerak emas
        for a in (await db.scalars(select(CrmActivity).where(CrmActivity.deal_id == deal.id, CrmActivity.done_at.is_(None), CrmActivity.auto.is_(True)))).all():
            await db.delete(a)
        to = [u for u in {deal.owner_id, deal.created_by} if u and u != actor_id]
        if to:
            notes += await notify(db, to, "crm.deal_won", params={"deal": deal.title, "amount": fmt_amount(deal.amount)}, link=f"/crm/deals/{deal.id}")
    elif not stage.is_won:
        deal.won_at = None
    if from_stage is not None:
        log(db, deal, actor_id, "stage", **{"from": from_stage.name, "to": stage.name, "probability": stage.probability})
    if stage.auto_activity and not stage.is_won and deal.lost_at is None:
        # Shu bosqichning avtomatik faoliyati allaqachon ochiq bo'lsa takrorlanmaydi
        exists = await db.scalar(select(CrmActivity.id).where(CrmActivity.deal_id == deal.id, CrmActivity.done_at.is_(None), CrmActivity.title == stage.auto_activity))
        if not exists:
            _, n = await add_activity(
                db, deal, kind=stage.auto_activity_kind, title=stage.auto_activity, due=local_date(moment) + timedelta(days=max(0, stage.auto_activity_days)),
                assignee_id=deal.owner_id, actor_id=actor_id, auto=True,
            )  # fmt: skip
            notes += n
    return notes


def track(db: AsyncSession, deal: CrmDeal, actor_id: int | None, before: dict[str, Any]) -> dict[str, Any]:
    """Kuzatiladigan maydonlardagi farqni lentaga yozadi; o'zgarganlarni qaytaradi."""
    changed = {}
    for f in TRACKED:
        old, new = before.get(f), getattr(deal, f)
        if isinstance(old, date):
            old = old.isoformat()
        if isinstance(new, date):
            new = new.isoformat()
        if old != new:
            changed[f] = {"from": old, "to": new}
    if changed:
        log(db, deal, actor_id, "updated", fields=changed)
    return changed


def snapshot(deal: CrmDeal) -> dict[str, Any]:
    return {f: getattr(deal, f) for f in TRACKED}


async def check_overdue(db: AsyncSession, moment: datetime) -> tuple[int, list]:
    """Muddati o'tgan ochiq faoliyatlar: mas'ulga (yo'q bo'lsa bitim egasiga) bir marta xabar."""
    today = local_date(moment)
    rows = (
        await db.execute(
            select(CrmActivity, CrmDeal)
            .join(CrmDeal, CrmDeal.id == CrmActivity.deal_id)
            .where(CrmActivity.done_at.is_(None), CrmActivity.due_date < today, CrmActivity.notified_overdue.is_(False), CrmDeal.archived_at.is_(None), CrmDeal.lost_at.is_(None))
        )
    ).all()
    notes: list = []
    for a, d in rows:
        a.notified_overdue = True
        to = a.assignee_id or d.owner_id
        if to:
            notes += await notify(db, [to], "crm.activity_overdue", params={"title": a.title, "deal": d.title, "due": a.due_date.strftime("%d.%m.%Y")}, link=f"/crm/deals/{d.id}")
    return len(rows), notes
