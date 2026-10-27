"""Ish haqi hisob-kitobi. Formulalar (hammasi so'mgacha yaxlitlanadi, ROUND_HALF_UP):

  oklad      = fix * to'langan_kunlar / reja_kunlar        (reja_kun = grafik bo'yicha ish kunlari; sababsiz kelmagan kun to'lanmaydi)
  komissiya  = savdo * foiz / 100
  reja bonus = bonus_summasi, agar reja > 0 va savdo >= reja
  KPI bonus  = kpi_maks * KPI_bali / 100
  yalpi      = oklad + komissiya + reja bonus + KPI bonus + qo'lda bonuslar
  soliq bazasi = max(yalpi - jarimalar - ushlanmalar, 0)
  soliq (JShDS) = baza * soliq% ; INPS = baza * inps%
  sof        = baza - soliq - INPS
  to'lanadi  = sof - avans   (yalpi jarima/ushlanmadan kichik bo'lsa, farq ham ayriladi)
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.employees import Employee
from app.models.org import Branch, Department
from app.models.payroll import PayItem, PayrollLine, PayrollRun, PayScheme
from app.models.penalties import Penalty
from app.rbac import matches
from app.services.notifications import register_template
from app.timeutil import local_date

KINDS = ("sales", "plan", "kpi", "bonus", "advance", "deduction")
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DEFAULT_SETTINGS = {"tax_percent": "12", "inps_percent": "0.1", "paid_leave": True}
ZERO = Decimal(0)

register_template("payroll.payslip", {"uz": "Ish haqi varaqasi tayyor", "ru": "Расчётный лист готов"}, {"uz": "{period}: {amount} so'm", "ru": "{period}: {amount} сум"}, "success")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def money(x: Decimal | int | float | str) -> Decimal:
    return Decimal(str(x)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def check_period(period: str) -> str:
    if not PERIOD_RE.match(period):
        raise error(400, "period_invalid")
    return period


def month_bounds(period: str) -> tuple[date, date]:
    y, m = int(period[:4]), int(period[5:])
    start = date(y, m, 1)
    end = (date(y + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)
    return start, end


def num(v: Any) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


@dataclass
class Inputs:
    sales: Decimal = ZERO
    plan: Decimal = ZERO
    kpi: Decimal | None = None
    bonus: Decimal = ZERO
    advance: Decimal = ZERO
    deduction: Decimal = ZERO
    item_ids: list[int] = field(default_factory=list)


def resolve_scheme(schemes: list[PayScheme], period_end: date) -> PayScheme | None:
    """Oy oxirigacha kuchga kirgan eng yangi sxema."""
    ok = [s for s in schemes if s.effective_from <= period_end]
    return max(ok, key=lambda s: (s.effective_from, s.id)) if ok else None


def compute_line(scheme: PayScheme, days: list[tuple[str, bool]], inp: Inputs, penalties: Decimal, settings: dict[str, Any]) -> dict[str, Any]:
    """`days`: ish davridagi har kun uchun (holat kodi, grafik bo'yicha ish kunimi). Sof hisob: bazaga tegmaydi."""
    paid_leave = bool(settings.get("paid_leave", True))
    plan_days = sum(1 for _, working in days if working)
    absent = sum(1 for st, working in days if working and st == "absent")
    unpaid_leave = 0 if paid_leave else sum(1 for st, working in days if working and st == "leave")
    paid_days = plan_days - absent - unpaid_leave
    warnings: list[str] = []
    counts = {k: sum(1 for st, _ in days if st == k) for k in ("no_checkout", "incomplete", "pending", "future", "no_shift", "leave")}
    for k in ("no_checkout", "incomplete", "pending", "future"):
        if counts[k]:
            warnings.append(k)
    fixed = money(num(scheme.fixed_amount) * paid_days / plan_days) if plan_days else ZERO
    if not plan_days and num(scheme.fixed_amount):
        warnings.append("no_plan_days")
    commission = money(inp.sales * num(scheme.commission_percent) / 100)
    plan_bonus = money(scheme.plan_bonus) if inp.plan > 0 and inp.sales >= inp.plan else ZERO
    kpi = min(max(inp.kpi, ZERO), Decimal(100)) if inp.kpi is not None else ZERO
    kpi_bonus = money(num(scheme.kpi_amount) * kpi / 100)
    if num(scheme.kpi_amount) and inp.kpi is None:
        warnings.append("kpi_missing")
    bonus = money(inp.bonus)
    gross = fixed + commission + plan_bonus + kpi_bonus + bonus
    pen, ded, adv = money(penalties), money(inp.deduction), money(inp.advance)
    base_raw = gross - pen - ded
    taxable = max(base_raw, ZERO)
    tax = money(taxable * Decimal(str(settings.get("tax_percent", 0))) / 100)
    inps = money(taxable * Decimal(str(settings.get("inps_percent", 0))) / 100)
    net = taxable - tax - inps
    to_pay = net - adv + min(base_raw, ZERO)
    if to_pay < 0:
        warnings.append("negative")
    return {
        "plan_days": plan_days, "paid_days": paid_days, "fixed": fixed, "commission": commission, "plan_bonus": plan_bonus, "kpi_bonus": kpi_bonus, "bonus": bonus,
        "gross": gross, "penalties": pen, "deductions": ded, "taxable": taxable, "tax": tax, "inps": inps, "net": net, "advance": adv, "to_pay": to_pay,
        "details": {
            "absent_days": absent, "unpaid_leave_days": unpaid_leave, "day_counts": counts, "sales": str(inp.sales), "plan": str(inp.plan), "kpi_score": str(inp.kpi) if inp.kpi is not None else None,
            "scheme": {"id": scheme.id, "effective_from": scheme.effective_from.isoformat(), "fixed_amount": str(scheme.fixed_amount), "commission_percent": str(scheme.commission_percent), "plan_bonus": str(scheme.plan_bonus), "kpi_amount": str(scheme.kpi_amount)},
            "settings": {k: (v if isinstance(v, bool) else str(v)) for k, v in settings.items()}, "item_ids": inp.item_ids, "warnings": warnings,
        },
    }  # fmt: skip


def line_out(ln: PayrollLine, *, detail: bool = False) -> dict[str, Any]:
    out = {
        "id": ln.id, "employee": {"id": ln.employee_id, "name": ln.employee_name, "employee_no": ln.employee_no}, "branch": ln.branch_name, "department": ln.department_name,
        "plan_days": ln.plan_days, "paid_days": ln.paid_days, "warnings": (ln.details or {}).get("warnings", []),
    }  # fmt: skip
    for k in ("fixed", "commission", "plan_bonus", "kpi_bonus", "bonus", "gross", "penalties", "deductions", "taxable", "tax", "inps", "net", "advance", "to_pay"):
        out[k] = int(getattr(ln, k))
    if detail:
        out["details"] = ln.details
    return out


async def load_inputs(db: AsyncSession, period: str) -> dict[int, Inputs]:
    out: dict[int, Inputs] = {}
    for it in (await db.scalars(select(PayItem).where(PayItem.period == period).order_by(PayItem.id))).all():
        x = out.setdefault(it.employee_id, Inputs())
        x.item_ids.append(it.id)
        a = num(it.amount)
        if it.kind == "sales":
            x.sales += a
        elif it.kind == "plan":
            x.plan += a
        elif it.kind == "kpi":
            x.kpi = a  # eng oxirgi kiritilgan
        elif it.kind == "bonus":
            x.bonus += a
        elif it.kind == "advance":
            x.advance += a
        elif it.kind == "deduction":
            x.deduction += a
    return out


async def approved_penalties(db: AsyncSession, start: date, end: date) -> tuple[dict[int, Decimal], dict[int, int]]:
    sums = dict((await db.execute(select(Penalty.employee_id, func.sum(Penalty.amount)).where(Penalty.status == "approved", Penalty.incident_date.between(start, end)).group_by(Penalty.employee_id))).all())
    pend = dict((await db.execute(select(Penalty.employee_id, func.count()).where(Penalty.status == "pending", Penalty.incident_date.between(start, end)).group_by(Penalty.employee_id))).all())
    return {k: num(v) for k, v in sums.items()}, pend


async def employees_for(db: AsyncSession, start: date, end: date) -> list[Employee]:
    stmt = select(Employee).where((Employee.hire_date.is_(None)) | (Employee.hire_date <= end), (Employee.status == "active") | (Employee.dismissal_date >= start)).order_by(Employee.full_name, Employee.id)
    return list((await db.scalars(stmt)).all())


async def inputs_signature(db: AsyncSession, period: str) -> str:
    """Hisobga ta'sir qiluvchi kiritmalar, tasdiqlangan jarimalar va sxemalar izi: o'zgarsa, hisob eskirgan."""
    start, end = month_bounds(period)
    items = (await db.execute(select(PayItem.id, PayItem.employee_id, PayItem.kind, PayItem.amount).where(PayItem.period == period).order_by(PayItem.id))).all()
    pens = (await db.execute(select(Penalty.id, Penalty.amount).where(Penalty.status == "approved", Penalty.incident_date.between(start, end)).order_by(Penalty.id))).all()
    schs = (await db.execute(select(PayScheme.id, PayScheme.effective_from, PayScheme.fixed_amount, PayScheme.commission_percent, PayScheme.plan_bonus, PayScheme.kpi_amount).where(PayScheme.effective_from <= end).order_by(PayScheme.id))).all()
    return hashlib.sha256(repr((items, pens, schs)).encode()).hexdigest()


async def calculate(db: AsyncSession, run: PayrollRun, moment) -> dict[str, Any]:
    """Qoralama hisobni qayta quradi: sxemasi bor hamma xodim uchun satr. Sxemasizlar ogohlantirishda."""
    from app.api.attendance import _rows  # tabel bilan bir manba (day_status)

    start, end = month_bounds(run.period)
    emps = await employees_for(db, start, end)
    schemes: dict[int, list[PayScheme]] = {}
    for s in (await db.scalars(select(PayScheme).where(PayScheme.effective_from <= end))).all():
        schemes.setdefault(s.employee_id, []).append(s)
    inputs = await load_inputs(db, run.period)
    pen_sum, pen_pending = await approved_penalties(db, start, end)
    branches = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    depts = {d.id: d.name for d in (await db.scalars(select(Department))).all()}
    for old in (await db.scalars(select(PayrollLine).where(PayrollLine.run_id == run.id))).all():
        await db.delete(old)
    await db.flush()
    missing: list[dict[str, Any]] = []
    count = 0
    todo = []
    for e in emps:
        sch = resolve_scheme(schemes.get(e.id, []), end)
        if sch is None:
            if e.status == "active":
                missing.append({"id": e.id, "name": e.full_name})
            continue
        todo.append((e, sch))
    for i in range(0, len(todo), 100):
        chunk = todo[i : i + 100]
        rows = await _rows(db, [e for e, _ in chunk], start, end)
        for e, sch in chunk:
            lo = max(start, e.hire_date) if e.hire_date else start
            hi = min(end, e.dismissal_date) if e.dismissal_date else end
            days = [(d["status"], bool(d["cell"].working)) for d in rows[e.id] if lo <= d["date"] <= hi]
            calc = compute_line(sch, days, inputs.get(e.id, Inputs()), pen_sum.get(e.id, ZERO), run.settings)
            if pen_pending.get(e.id):
                calc["details"]["warnings"].append("pending_penalties")
                calc["details"]["pending_penalties"] = pen_pending[e.id]
            db.add(PayrollLine(run_id=run.id, employee_id=e.id, employee_name=e.full_name, employee_no=e.employee_no, branch_name=branches.get(e.branch_id or 0), department_name=depts.get(e.department_id or 0), **calc))
            count += 1
    run.calculated_at = moment
    run.settings = {**run.settings, "_sig": await inputs_signature(db, run.period)}
    await db.flush()
    return {"lines": count, "missing_scheme": missing, "month_finished": local_date(moment) > end}


async def totals(db: AsyncSession, run_id: int) -> dict[str, Any]:
    cols = ("fixed", "commission", "plan_bonus", "kpi_bonus", "bonus", "gross", "penalties", "deductions", "tax", "inps", "net", "advance", "to_pay")
    row = (await db.execute(select(func.count(), *[func.coalesce(func.sum(getattr(PayrollLine, c)), 0) for c in cols]).where(PayrollLine.run_id == run_id))).one()
    out: dict[str, Any] = {"employees": row[0]}
    out.update({c: int(row[i + 1]) for i, c in enumerate(cols)})
    return out
