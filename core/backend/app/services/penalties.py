"""Jarimalar: versiyalangan 6 bosqichli qoidalar, davomatdan avtomatik hisob, tasdiq/bekor, vaqtincha blok."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.auth import User
from app.models.employees import Employee
from app.models.penalties import Penalty, PenaltyRuleVersion
from app.services.auth import revoke_user_sessions
from app.services.notifications import notify, register_template
from app.timeutil import local_date

INCIDENTS = ("late", "absent", "early_leave", "no_checkout", "discipline", "other")
AUTO_TYPES = ("late", "early_leave", "absent", "no_checkout")
STEPS = 6
LIVE = ("pending", "approved")  # hisobga olinadigan (bekor qilinmagan) jarimalar

register_template(
    "penalties.approved",
    {"uz": "Sizga jarima/chora qo'llandi", "ru": "К вам применена мера/штраф"},
    {"uz": "{label}{amount}. Sana: {date}", "ru": "{label}{amount}. Дата: {date}"},
    "danger",
)
register_template(
    "penalties.blocked",
    {"uz": "Hisobingiz vaqtincha bloklandi", "ru": "Ваша учётная запись временно заблокирована"},
    {"uz": "{until} gacha. Sabab: {label}", "ru": "До {until}. Причина: {label}"},
    "danger",
)
register_template(
    "penalties.cancelled",
    {"uz": "Jarima bekor qilindi", "ru": "Штраф отменён"},
    {"uz": "{label}. Sana: {date}", "ru": "{label}. Дата: {date}"},
    "success",
)


class Trigger(BaseModel):
    enabled: bool = True
    min_minutes: int = Field(default=0, ge=0, le=600)


class Step(BaseModel):
    step: int
    label: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("1000000000"))
    block_days: int = Field(default=0, ge=0, le=90)


class RulesConfig(BaseModel):
    auto_scan: bool = False
    window_days: int = Field(default=90, ge=7, le=730)
    count_mode: str = Field(default="all", pattern="^(all|per_type)$")
    triggers: dict[str, Trigger]
    steps: list[Step]

    @model_validator(mode="after")
    def _check(self):
        if set(self.triggers) != set(AUTO_TYPES):
            raise ValueError("triggers_invalid")
        if len(self.steps) != STEPS or [s.step for s in self.steps] != list(range(1, STEPS + 1)):
            raise ValueError("steps_invalid")
        return self


def config_json(cfg: RulesConfig) -> dict[str, Any]:
    return json.loads(cfg.model_dump_json())


async def current_rules(db: AsyncSession) -> PenaltyRuleVersion:
    v = await db.scalar(select(PenaltyRuleVersion).order_by(PenaltyRuleVersion.version.desc()).limit(1))
    if v is None:
        raise error(409, "no_rules")
    return v


def step_for(count_prior: int, cfg: dict[str, Any]) -> dict[str, Any]:
    """Oldingi jarimalar soniga ko'ra bosqich: 0 -> 1-bosqich ... 5 va undan ko'p -> 6-bosqich."""
    idx = min(count_prior, len(cfg["steps"]) - 1)
    return cfg["steps"][idx]


async def count_prior(db: AsyncSession, emp_id: int, incident_type: str, day: date, cfg: dict[str, Any]) -> int:
    stmt = select(func.count()).select_from(Penalty).where(
        Penalty.employee_id == emp_id, Penalty.status.in_(LIVE), Penalty.source == "auto",
        Penalty.incident_date < day, Penalty.incident_date >= day - timedelta(days=cfg["window_days"]),
    )  # fmt: skip
    if cfg["count_mode"] == "per_type":
        stmt = stmt.where(Penalty.incident_type == incident_type)
    return await db.scalar(stmt) or 0


def amount_text(p: Penalty) -> str:
    return f" — {int(p.amount):,}".replace(",", " ") + " so'm" if p.amount else ""


# --- Avtomatik hisob --------------------------------------------------------------------


def detect(status: str, rec, cfg: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Kun holatidan qoidabuzarlik turini (va tafsilotlarini) aniqlaydi; qoida o'chiq yoki chegaradan past bo'lsa None."""
    trig = cfg["triggers"]
    if status == "absent" and trig["absent"]["enabled"]:
        return "absent", {"status": status}
    if status == "no_checkout" and trig["no_checkout"]["enabled"]:
        return "no_checkout", {"status": status}
    if rec is not None:
        if status in ("late", "late_early") and trig["late"]["enabled"] and rec.late_minutes >= max(trig["late"]["min_minutes"], 1):
            return "late", {"status": status, "late_minutes": rec.late_minutes}
        if status in ("early", "late_early") and trig["early_leave"]["enabled"] and rec.early_leave_minutes >= max(trig["early_leave"]["min_minutes"], 1):
            return "early_leave", {"status": status, "early_minutes": rec.early_leave_minutes}
    return None


async def scan_day(db: AsyncSession, day: date, rules: PenaltyRuleVersion, *, dry_run: bool, moment: datetime) -> dict[str, int]:
    """Bitta o'tgan kun uchun davomatdan jarimalarni hisoblaydi (takrorlanmaydi). Natija: soni."""
    from app.api.attendance import _rows  # davomat holati bilan BIR manba

    cfg = rules.config
    employees = list((await db.scalars(select(Employee).where(Employee.status == "active", (Employee.hire_date.is_(None)) | (Employee.hire_date <= day)).order_by(Employee.id))).all())
    stats = {"employees": len(employees), "created": 0, "existing": 0, "warnings": 0, "fines": 0, "blocks": 0}
    for i in range(0, len(employees), 500):
        chunk = employees[i : i + 500]
        rows = await _rows(db, chunk, day, day)
        for emp in chunk:
            d = rows[emp.id][0]
            found = detect(d["status"], d["record"], cfg)
            if not found:
                continue
            itype, details = found
            if await db.scalar(select(Penalty.id).where(Penalty.employee_id == emp.id, Penalty.incident_date == day, Penalty.incident_type == itype, Penalty.source == "auto")):
                stats["existing"] += 1
                continue
            step = step_for(await count_prior(db, emp.id, itype, day, cfg), cfg)
            stats["created"] += 1
            stats["blocks" if step["block_days"] else "fines" if step["amount"] else "warnings"] += 1
            if dry_run:
                continue
            db.add(Penalty(
                employee_id=emp.id, incident_type=itype, incident_date=day, source="auto", rule_version_id=rules.id,
                step=step["step"], label=step["label"], amount=Decimal(str(step["amount"])), block_days=step["block_days"],
                details=details, status="pending",
            ))  # fmt: skip
            await db.flush()
    return stats


async def scan_range(db: AsyncSession, start: date, end: date, *, dry_run: bool, moment: datetime) -> dict[str, Any]:
    today = local_date(moment)
    if end >= today:
        raise error(400, "range_not_finished")  # tugamagan kunni hisoblab bo'lmaydi
    if end < start or (end - start).days + 1 > 92:
        raise error(400, "range_invalid", max_days=92)
    rules = await current_rules(db)
    total = {"employees": 0, "created": 0, "existing": 0, "warnings": 0, "fines": 0, "blocks": 0}
    d = start
    while d <= end:  # tartib bilan: bosqich oldingi kunlardagi jarimalarga bog'liq
        s = await scan_day(db, d, rules, dry_run=dry_run, moment=moment)
        for k in total:
            total[k] = max(total[k], s[k]) if k == "employees" else total[k] + s[k]
        d += timedelta(days=1)
    return {**total, "rule_version": rules.version, "dry_run": dry_run}


# --- Qo'lda jarima, qaror ----------------------------------------------------------------


async def create_manual(db: AsyncSession, auth: AuthContext, emp: Employee, *, incident_type: str, incident_date: date, step: int | None, amount: Decimal | None, block_days: int | None, label: str | None, reason: str):
    rules = await current_rules(db)
    s = rules.config["steps"][step - 1] if step else None
    amt = amount if amount is not None else Decimal(str(s["amount"])) if s else Decimal(0)
    blk = block_days if block_days is not None else (s["block_days"] if s else 0)
    p = Penalty(
        employee_id=emp.id, incident_type=incident_type, incident_date=incident_date, source="manual", rule_version_id=rules.id,
        step=step or 0, label=(label or (s["label"] if s else "Jarima")).strip(), amount=amt, block_days=blk,
        reason=reason.strip(), status="pending", created_by=auth.user.id,
    )  # fmt: skip
    db.add(p)
    await db.flush()
    return p


async def _apply_block(db: AsyncSession, p: Penalty, emp: Employee, moment: datetime):
    user = await db.get(User, emp.user_id) if emp.user_id else None
    if p.block_days <= 0 or not user or not user.is_active:
        return []
    user.is_active = False
    await revoke_user_sessions(db, user.id)
    p.block_applied, p.blocked_until, p.unblocked_at = True, local_date(moment) + timedelta(days=p.block_days), None
    return await notify(db, [user.id], "penalties.blocked", params={"until": p.blocked_until.strftime("%d.%m.%Y"), "label": p.label}, link="/penalties")


async def _lift_block(db: AsyncSession, p: Penalty, emp: Employee | None, moment: datetime) -> None:
    p.unblocked_at = moment
    user = await db.get(User, emp.user_id) if emp and emp.user_id else None
    # Faqat faol xodimning hisobi qayta yoqiladi (bo'shatilgan xodim hisobi ochilmaydi)
    if user and not user.is_active and emp and emp.status == "active":
        others = await db.scalar(
            select(func.count()).select_from(Penalty).where(Penalty.employee_id == emp.id, Penalty.id != p.id, Penalty.block_applied.is_(True), Penalty.unblocked_at.is_(None), Penalty.status == "approved")
        )
        if not others:
            user.is_active = True


async def decide(db: AsyncSession, p: Penalty, emp: Employee, auth: AuthContext, action: str, note: str | None, moment: datetime):
    note = (note or "").strip() or None
    if action == "approve":
        if p.status != "pending":
            raise error(409, "already_decided")
        p.status = "approved"
        notes = await notify(
            db, [emp.user_id] if emp.user_id else [], "penalties.approved", link="/penalties",
            params={"label": p.label, "amount": amount_text(p), "date": p.incident_date.strftime("%d.%m.%Y")},
        )
        notes += await _apply_block(db, p, emp, moment)
    else:
        if p.status == "cancelled":
            raise error(409, "already_decided")
        if not note:
            raise error(400, "note_required")
        was_approved = p.status == "approved"
        p.status = "cancelled"
        if p.block_applied and p.unblocked_at is None:
            await _lift_block(db, p, emp, moment)
        notes = await notify(db, [emp.user_id] if emp.user_id and was_approved else [], "penalties.cancelled", link="/penalties", params={"label": p.label, "date": p.incident_date.strftime("%d.%m.%Y")})
    p.decided_by, p.decided_at, p.decision_note = auth.user.id, moment, note
    return notes


async def release_expired_blocks(db: AsyncSession, moment: datetime) -> int:
    today = local_date(moment)
    due = (await db.scalars(select(Penalty).where(Penalty.block_applied.is_(True), Penalty.unblocked_at.is_(None), Penalty.blocked_until <= today, Penalty.status == "approved"))).all()
    for p in due:
        await _lift_block(db, p, await db.get(Employee, p.employee_id), moment)
    return len(due)


def penalty_out(p: Penalty, emp: Employee) -> dict[str, Any]:
    return {
        "id": p.id, "employee": {"id": emp.id, "employee_no": emp.employee_no, "full_name": emp.full_name},
        "incident_type": p.incident_type, "incident_date": p.incident_date, "source": p.source, "step": p.step, "label": p.label,
        "amount": float(p.amount), "block_days": p.block_days, "details": p.details, "reason": p.reason, "status": p.status,
        "rule_version_id": p.rule_version_id, "created_at": p.created_at, "decided_at": p.decided_at, "decision_note": p.decision_note,
        "block_applied": p.block_applied, "blocked_until": p.blocked_until, "unblocked_at": p.unblocked_at,
    }  # fmt: skip


DEFAULT_CONFIG: dict[str, Any] = {
    "auto_scan": False, "window_days": 90, "count_mode": "all",
    "triggers": {
        "late": {"enabled": True, "min_minutes": 10}, "early_leave": {"enabled": True, "min_minutes": 10},
        "absent": {"enabled": True, "min_minutes": 0}, "no_checkout": {"enabled": False, "min_minutes": 0},
    },
    "steps": [
        {"step": 1, "label": "Og'zaki ogohlantirish", "amount": 0, "block_days": 0},
        {"step": 2, "label": "Yozma ogohlantirish", "amount": 0, "block_days": 0},
        {"step": 3, "label": "Jarima (1-daraja)", "amount": 50000, "block_days": 0},
        {"step": 4, "label": "Jarima (2-daraja)", "amount": 100000, "block_days": 0},
        {"step": 5, "label": "Jarima (3-daraja)", "amount": 200000, "block_days": 0},
        {"step": 6, "label": "Jarima va vaqtincha blok", "amount": 200000, "block_days": 3},
    ],
}  # fmt: skip


async def ensure_default_rules(db: AsyncSession) -> None:
    """Qoida versiyasi bo'lmasa boshlang'ich (misol) qoidalarni yaratadi (migratsiya ham qo'shadi)."""
    if await db.scalar(select(PenaltyRuleVersion.id).limit(1)):
        return
    db.add(PenaltyRuleVersion(version=1, config=DEFAULT_CONFIG, note="Boshlang'ich (misol) qoidalar"))
    await db.commit()
