"""Koordinator davomat hisoboti: koordinator x smena kesimida kelmagan/kechikkanlar, oy tarixi, uzoq kelmaganlar va
koordinatorning sabab/chora izohlari (HR ga hisobot). Telegram/ilova xabari matni shu yerda yasaladi."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_issues import AttendanceExplanation
from app.models.auth import User
from app.models.employees import Employee
from app.models.org import Branch, Position
from app.services import attendance as att
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template
from app.timeutil import local_date, tz

for _k, _t in (("daily", "Davomat hisoboti"), ("hr", "Davomat hisoboti"), ("overdue", "Izoh berilmadi")):
    register_template(f"coord_report.{_k}", {"uz": _t, "ru": _t}, {"uz": "{text}", "ru": "{text}"}, "info")

EXPLAIN_HOURS = 24  # izoh berish muddati: hisobot chiqqandan keyin
LONG_ABSENCE_DAYS = 3  # shuncha kun ketma-ket kelmagan xodim HR ga alohida chiqariladi
NOT_COUNTED = {"off", "holiday", "leave", "exempt", "future", "no_shift"}  # ketma-ketlikni uzmaydi
TG_LIMIT = 3800

MONTHS_UZ = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def _fmt_t(dt: datetime | None) -> str | None:
    return dt.astimezone(tz()).strftime("%H:%M") if dt else None


async def build(db: AsyncSession, day: date, moment: datetime, *, coordinator_id: int | None = None) -> dict[str, Any]:
    """{date, time, coordinators: [{user_id, name, absent, late, shifts: [{name, start, end, absent: [...], late: [...]}]}], long_absent}"""
    from app.api.attendance import _rows  # noqa: PLC0415  (api -> service sikli oldini olish)

    branch_stmt = select(Branch).where(Branch.coordinator_user_id.is_not(None))
    if coordinator_id is not None:
        branch_stmt = branch_stmt.where(Branch.coordinator_user_id == coordinator_id)
    branches = {b.id: b for b in (await db.scalars(branch_stmt)).all()}
    employees = list((await db.scalars(select(Employee).where(Employee.status == "active", Employee.branch_id.in_(branches)).order_by(Employee.full_name))).all()) if branches else []
    month_start = day.replace(day=1)
    rows = await _rows(db, employees, month_start, day) if employees else {}
    positions = {p.id: p.name for p in (await db.scalars(select(Position))).all()}
    users = {u.id: u for u in (await db.scalars(select(User).where(User.id.in_({b.coordinator_user_id for b in branches.values()})))).all()} if branches else {}

    groups: dict[int, dict[tuple, dict[str, Any]]] = defaultdict(dict)
    long_absent: list[dict[str, Any]] = []
    for e in employees:
        days = [d for d in rows[e.id] if not e.hire_date or d["date"] >= e.hire_date]  # ishga olinishidan oldingi kunlar hisobga olinmaydi
        today = next((d for d in days if d["date"] == day), None)
        if today is None:
            continue
        status, rec, shift = today["status"], today["record"], today["shift"]
        kind: str | None = None
        if status == "absent":
            kind = "absent"
        elif status == "pending" and shift is not None and shift.kind != "flexible":
            start, _ = att.planned_window(shift, day)
            if start is not None and start <= moment:
                kind = "absent"  # smena boshlangan, hali belgilamagan
        elif rec is not None and rec.late_minutes:
            kind = "late"
        if kind is None:
            continue
        history = []
        for d in days:
            if d["date"] > day:
                continue
            r = d["record"]
            if d["date"] == day:
                history.append({"date": d["date"].isoformat(), "kind": kind, "arrived": _fmt_t(rec.check_in_at) if rec else None})
            elif d["status"] == "absent":
                history.append({"date": d["date"].isoformat(), "kind": "absent", "arrived": None})
            elif r is not None and r.late_minutes:
                history.append({"date": d["date"].isoformat(), "kind": "late", "arrived": _fmt_t(r.check_in_at)})
        streak = 0
        for d in reversed(days):
            st = "absent" if d["date"] == day and kind == "absent" else d["status"]
            if st == "absent":
                streak += 1
            elif st in NOT_COUNTED:
                continue
            else:
                break
        branch = branches[e.branch_id]  # type: ignore[index]
        item = {
            "employee_id": e.id, "full_name": e.full_name, "position": positions.get(e.position_id or 0),
            "branch": f"№{branch.number} {branch.name}" if branch.number else branch.name, "kind": kind,
            "arrived": _fmt_t(rec.check_in_at) if rec else None, "streak": streak, "month": history,
            "anomaly": "arrived_before_shift" if kind == "late" and rec and rec.planned_start and rec.check_in_at < rec.planned_start else None,
        }  # fmt: skip
        cid = branch.coordinator_user_id
        planned = att.planned_window(shift, day) if shift else (None, None)
        key = (shift.id if shift else 0,)
        g = groups[cid].setdefault(key, {"name": shift.name if shift else "—", "start": _fmt_t(planned[0]), "end": _fmt_t(planned[1]), "absent": [], "late": []})  # type: ignore[index]
        g["absent" if kind == "absent" else "late"].append(item)
        if kind == "absent" and streak >= LONG_ABSENCE_DAYS:
            long_absent.append({**item, "coordinator_id": cid})
    coordinators = []
    for cid, gs in groups.items():
        sh = sorted(gs.values(), key=lambda g: g["start"] or "")
        coordinators.append({
            "user_id": cid, "name": users[cid].full_name if cid in users else str(cid), "shifts": sh,
            "absent": sum(len(g["absent"]) for g in sh), "late": sum(len(g["late"]) for g in sh),
        })  # fmt: skip
    coordinators.sort(key=lambda c: c["name"])
    return {"date": day.isoformat(), "time": moment.astimezone(tz()).strftime("%H:%M"), "coordinators": coordinators, "long_absent": long_absent}


def _day_label(iso: str, lang: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}-{MONTHS_UZ[d.month - 1]}" if lang == "uz" else d.strftime("%d.%m")


def render_text(report: dict[str, Any], coord: dict[str, Any], lang: str = "uz") -> str:
    """Koordinatorga yuboriladigan matn (mijoz shabloniga mos)."""
    d = date.fromisoformat(report["date"])
    uz = lang == "uz"
    head = f"{coord['name']} — xodimlaringiz davomati\n{d.day}-{MONTHS_UZ[d.month - 1]} {d.year}, soat {report['time']}" if uz else f"{coord['name']} — посещаемость ваших сотрудников\n{d:%d.%m.%Y}, {report['time']}"
    lines = [head, ""]
    for g in coord["shifts"]:
        total = len(g["absent"]) + len(g["late"])
        lines.append(f"🕘 {g['name']} ({g['start']}–{g['end']}): {total} {'kishi' if uz else 'чел.'}")
        lines.append(f"• {'Kelmaganlar' if uz else 'Не пришли'}: {len(g['absent'])}")
        lines.append(f"• {'Kechikkanlar' if uz else 'Опоздали'}: {len(g['late'])}")
        for it in g["absent"] + g["late"]:
            tag = ("kelmagan" if uz else "не пришёл") if it["kind"] == "absent" else (f"kechikkan {it['arrived']}" if uz else f"опоздал {it['arrived']}")
            streak = f" ⚠️ {it['streak']} {'kun ketma-ket' if uz else 'дн. подряд'}" if it["kind"] == "absent" and it["streak"] >= LONG_ABSENCE_DAYS else ""
            lines.append(f"   – {it['full_name']} ({it['branch']}): {tag}{streak}")
        lines.append("")
    lines.append(
        "⚠️ Diqqat! Har bir xodim kelmaganligi yoki kechikkanligi sababini va qayta takrorlanmasligi uchun ko'rgan choralaringizni tizimda (Davomat → Koordinator hisoboti) kiritishingiz shart. Aks holda sizga jarima solinishi mumkin."
        if uz
        else "⚠️ Внимание! По каждому сотруднику укажите причину отсутствия/опоздания и принятые меры в системе (Посещаемость → Отчёт координатора). Иначе возможен штраф."
    )
    text = "\n".join(lines)
    return text if len(text) <= TG_LIMIT else text[: TG_LIMIT - 1] + "…"


async def sync_explanations(db: AsyncSession, report: dict[str, Any], moment: datetime) -> int:
    """Hisobotdagi har bir holat uchun izoh qatorini yaratadi (takrorlanmaydi). Yangi qatorlar sonini qaytaradi."""
    day = date.fromisoformat(report["date"])
    existing = {
        (x.employee_id, x.kind)
        for x in (await db.scalars(select(AttendanceExplanation).where(AttendanceExplanation.work_date == day))).all()
    }
    created = 0
    for c in report["coordinators"]:
        for g in c["shifts"]:
            for it in g["absent"] + g["late"]:
                if (it["employee_id"], it["kind"]) in existing:
                    continue
                db.add(AttendanceExplanation(employee_id=it["employee_id"], work_date=day, kind=it["kind"], coordinator_user_id=c["user_id"], status="pending", due_at=moment + timedelta(hours=EXPLAIN_HOURS)))
                created += 1
    await db.flush()
    return created


async def run_daily(db: AsyncSession, moment: datetime) -> list:
    """20:00 hisobot: izoh qatorlarini yaratadi, har koordinatorga va HR ga xabar yuboradi. Notification ro'yxatini qaytaradi."""
    day = local_date(moment)
    report = await build(db, day, moment)
    await sync_explanations(db, report, moment)
    notes: list = []
    for c in report["coordinators"]:
        if not c["absent"] and not c["late"]:
            continue
        notes += await notify(
            db, [c["user_id"]], "coord_report.daily", link="/attendance/coordinator-report",
            title={"uz": f"Davomat hisoboti: {c['absent']} kelmagan, {c['late']} kechikkan", "ru": f"Отчёт посещаемости: {c['absent']} не пришли, {c['late']} опоздали"},
            body={"uz": render_text(report, c, "uz"), "ru": render_text(report, c, "ru")},
        )  # fmt: skip
    hr = await users_with_permission(db, "attendance.edit")
    total_abs = sum(c["absent"] for c in report["coordinators"])
    total_late = sum(c["late"] for c in report["coordinators"])
    long_ = report["long_absent"]
    if hr and (total_abs or total_late):
        extra_uz = "\n\nUzoq kelmaganlar:\n" + "\n".join(f"• {x['full_name']} ({x['branch']}): {x['streak']} kun" for x in long_) if long_ else ""
        extra_ru = "\n\nДолго отсутствуют:\n" + "\n".join(f"• {x['full_name']} ({x['branch']}): {x['streak']} дн." for x in long_) if long_ else ""
        notes += await notify(
            db, hr, "coord_report.hr", link="/attendance/coordinator-report", severity="warning" if long_ else "info",
            title={"uz": f"Davomat: {total_abs} kelmagan, {total_late} kechikkan", "ru": f"Посещаемость: {total_abs} не пришли, {total_late} опоздали"},
            body={"uz": f"Koordinatorlar: {len(report['coordinators'])}. Izohlar muddati: {EXPLAIN_HOURS} soat.{extra_uz}"[:TG_LIMIT], "ru": f"Координаторов: {len(report['coordinators'])}. Срок пояснений: {EXPLAIN_HOURS} ч.{extra_ru}"[:TG_LIMIT]},
        )  # fmt: skip
    return notes


async def overdue_check(db: AsyncSession, moment: datetime) -> list:
    """Muddati o'tgan izohlar haqida HR va koordinatorga bir marta xabar beradi."""
    rows = list(
        (await db.scalars(select(AttendanceExplanation).where(AttendanceExplanation.status == "pending", AttendanceExplanation.due_at <= moment, AttendanceExplanation.overdue_notified_at.is_(None)))).all()
    )
    if not rows:
        return []
    emps = {e.id: e for e in (await db.scalars(select(Employee).where(Employee.id.in_({r.employee_id for r in rows})))).all()}
    by_coord: dict[int | None, list[AttendanceExplanation]] = defaultdict(list)
    for r in rows:
        r.overdue_notified_at = moment
        by_coord[r.coordinator_user_id].append(r)
    notes: list = []
    hr = await users_with_permission(db, "attendance.edit")
    users = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_({c for c in by_coord if c})))).all()}
    for cid, items in by_coord.items():
        names = ", ".join(emps[i.employee_id].full_name for i in items[:10]) + ("…" if len(items) > 10 else "")
        t = {"uz": f"Izoh berilmadi: {len(items)} ta", "ru": f"Пояснения не даны: {len(items)}"}
        if cid:
            notes += await notify(db, [cid], "coord_report.overdue", link="/attendance/coordinator-report", severity="danger", title=t, body={"uz": f"Muddati o'tdi: {names}", "ru": f"Срок истёк: {names}"})
        if hr:
            who = users.get(cid or 0, "—")
            notes += await notify(db, hr, "coord_report.overdue", link="/attendance/coordinator-report", severity="danger", title=t, body={"uz": f"Koordinator {who} izoh bermadi: {names}", "ru": f"Координатор {who} не дал пояснений: {names}"})
    return notes
