"""Koordinator checklist: filialga borish (GPS), shablon nusxasi, ball hisobi, qamrov, reyting va trend."""

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.geo import haversine_m, valid_coordinates
from app.models.auth import User
from app.models.checklists import ChecklistVisit
from app.models.org import Branch
from app.rbac import matches
from app.services.notifications import notify, register_template
from app.timeutil import local_date, tz

KINDS = ("yesno", "score")
LOW_SCORE = 60.0
COVERAGE_DAYS = 14
MAX_ITEMS = 100

register_template("checklists.submitted", {"uz": "Filialingiz tekshirildi", "ru": "Ваш филиал проверен"}, {"uz": "{branch}: {score}%", "ru": "{branch}: {score}%"}, "info")
register_template("checklists.low_score", {"uz": "Past checklist bahosi", "ru": "Низкая оценка чек-листа"}, {"uz": "{branch}: {score}% ({coordinator})", "ru": "{branch}: {score}% ({coordinator})"}, "danger")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "checklists.read") or has(auth, "checklists.manage")


def can_manage(auth: AuthContext) -> bool:
    return has(auth, "checklists.manage")


def branch_clause(auth: AuthContext):
    """Qaysi filiallar: hammasi (None) yoki o'zining (koordinatori yoki mudiri)."""
    if sees_all(auth):
        return None
    me = auth.user.id
    return (Branch.coordinator_user_id == me) | (Branch.manager_user_id == me)


def my_branch(auth: AuthContext, b: Branch) -> bool:
    return b.coordinator_user_id == auth.user.id


# --- Shablon elementlari -----------------------------------------------------------------


def clean_items(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw or len(raw) > MAX_ITEMS:
        raise error(400, "items_invalid", max=MAX_ITEMS)
    out, seen = [], set()
    for r in raw:
        text = str(r.get("text") or "").strip()
        kind = r.get("kind", "yesno")
        weight = int(r.get("weight", 1))
        if not text or len(text) > 300 or kind not in KINDS or not 1 <= weight <= 10:
            raise error(400, "items_invalid", max=MAX_ITEMS)
        iid = str(r.get("id") or "")
        if not iid or iid in seen:
            iid = uuid.uuid4().hex[:8]
        seen.add(iid)
        out.append({"id": iid, "section": (str(r.get("section") or "").strip()[:80]) or None, "text": text, "kind": kind, "weight": weight, "required": bool(r.get("required", True)), "critical": bool(r.get("critical", False))})
    return out


def fresh_answers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**i, "value": None, "na": False, "comment": None} for i in items]


def apply_answers(current: list[dict[str, Any]], given: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {a["id"]: a for a in current}
    for g in given:
        a = by_id.get(g["id"])
        if a is None:
            raise error(400, "unknown_item")
        na, value = bool(g.get("na")), g.get("value")
        if na and a.get("required"):
            raise error(400, "na_not_allowed", item=a["id"])
        if not na and value is not None:
            ok = value in (0, 1) if a["kind"] == "yesno" else 0 <= value <= 5
            if not ok:
                raise error(400, "value_invalid", item=a["id"])
        a["value"] = None if na else value
        a["na"] = na
        a["comment"] = (str(g.get("comment") or "").strip()[:500]) or None
    return list(by_id.values())


def is_fail(a: dict[str, Any]) -> bool:
    if a.get("na") or a.get("value") is None:
        return False
    return a["value"] == 0 if a["kind"] == "yesno" else a["value"] <= 1


def compute(answers: list[dict[str, Any]]) -> tuple[float | None, int]:
    """Ball (0..100): javob berilgan va "kerak emas" bo'lmagan bandlar vazn bo'yicha; kritik bandlar soni."""
    total = got = 0.0
    for a in answers:
        if a.get("na") or a.get("value") is None:
            continue
        w = a["weight"]
        total += w
        got += w * (a["value"] if a["kind"] == "yesno" else a["value"] / 5)
    score = round(got / total * 100, 1) if total else None
    return score, sum(1 for a in answers if a.get("critical") and is_fail(a))


def unanswered(answers: list[dict[str, Any]]) -> list[str]:
    return [a["id"] for a in answers if a.get("required") and not a.get("na") and a.get("value") is None]


# --- GPS ---------------------------------------------------------------------------------


def check_geo(b: Branch, lat: float | None, lng: float | None) -> tuple[int | None, bool]:
    """(masofa, ichkarida). Filial koordinatasi yo'q bo'lsa tekshirib bo'lmaydi: (None, True)."""
    if b.latitude is None or b.longitude is None:
        return None, True
    if not valid_coordinates(lat, lng):
        raise error(400, "coordinates_required")
    dist = round(haversine_m(lat, lng, float(b.latitude), float(b.longitude)))  # type: ignore[arg-type]
    return dist, dist <= b.geofence_radius_m


# --- Natija ------------------------------------------------------------------------------


async def names(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids2 = {i for i in ids if i}
    if not ids2:
        return {}
    return {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(ids2)))).all()}


def visit_out(v: ChecklistVisit, user_names: dict[int, str], branches: dict[int, str]) -> dict[str, Any]:
    answered = sum(1 for a in v.answers if a.get("na") or a.get("value") is not None)
    return {
        "id": v.id, "status": v.status, "template": {"id": v.template_id, "name": v.template_name},
        "branch": {"id": v.branch_id, "name": branches.get(v.branch_id or 0)} if v.branch_id else None,
        "coordinator": {"id": v.coordinator_id, "name": user_names.get(v.coordinator_id or 0)} if v.coordinator_id else None,
        "started_at": v.started_at, "submitted_at": v.submitted_at, "score": v.score, "critical_fails": v.critical_fails,
        "geo_ok": v.geo_ok, "distance_m": v.distance_m, "answered": answered, "total": len(v.answers),
    }  # fmt: skip


async def branch_names(db: AsyncSession) -> dict[int, str]:
    return {b.id: b.name for b in (await db.scalars(select(Branch))).all()}


async def notify_submitted(db: AsyncSession, v: ChecklistVisit, coordinator: User, readers: list[int]):
    b = await db.get(Branch, v.branch_id) if v.branch_id else None
    params = {"branch": b.name if b else "—", "score": f"{v.score:g}" if v.score is not None else "—", "coordinator": coordinator.full_name}
    notes = []
    if b and b.manager_user_id and b.manager_user_id != coordinator.id:
        notes += await notify(db, [b.manager_user_id], "checklists.submitted", link=f"/checklists/{v.id}", params=params)
    if v.score is not None and (v.score < LOW_SCORE or v.critical_fails):
        notes += await notify(db, [u for u in readers if u != coordinator.id], "checklists.low_score", link=f"/checklists/{v.id}", params=params)
    return notes


# --- Hisobotlar --------------------------------------------------------------------------


def range_dt(start: date, end: date) -> tuple[datetime, datetime]:
    return (datetime.combine(start, datetime.min.time(), tzinfo=tz()), datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz()))


async def coverage(db: AsyncSession, auth: AuthContext, start: date, end: date, moment: datetime, days: int = COVERAGE_DAYS) -> list[dict[str, Any]]:
    """Har bir faol filial: davrdagi tekshiruvlar, oxirgisi, necha kun o'tgani va o'rtacha ball."""
    s_dt, e_dt = range_dt(start, end)
    stmt = select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.number, Branch.name)
    clause = branch_clause(auth)
    if clause is not None:
        stmt = stmt.where(clause)
    branches = (await db.scalars(stmt)).all()
    V = ChecklistVisit
    done = (V.status == "submitted", V.branch_id.in_([b.id for b in branches]) if branches else V.branch_id.is_(None))
    in_range = (await db.execute(select(V.branch_id, func.count(), func.avg(V.score)).where(*done, V.submitted_at >= s_dt, V.submitted_at < e_dt).group_by(V.branch_id))).all()
    last = {r[0]: r[1] for r in (await db.execute(select(V.branch_id, func.max(V.submitted_at)).where(*done).group_by(V.branch_id))).all()}
    last_score: dict[int, float | None] = {}
    for bid, at in last.items():
        last_score[bid] = await db.scalar(select(V.score).where(V.branch_id == bid, V.submitted_at == at).limit(1))
    stats = {r[0]: (r[1], r[2]) for r in in_range}
    users = await names(db, {b.coordinator_user_id for b in branches})
    today = local_date(moment)
    out = []
    for b in branches:
        cnt, avg = stats.get(b.id, (0, None))
        at = last.get(b.id)
        since = (today - local_date(at)).days if at else None
        out.append({
            "branch": {"id": b.id, "name": b.name, "number": b.number},
            "coordinator": {"id": b.coordinator_user_id, "name": users.get(b.coordinator_user_id or 0)} if b.coordinator_user_id else None,
            "visits": cnt, "avg_score": round(float(avg), 1) if avg is not None else None, "last_at": at, "last_score": last_score.get(b.id),
            "days_since": since, "overdue": since is None or since > days,
        })  # fmt: skip
    return out


async def ranking(db: AsyncSession, auth: AuthContext, start: date, end: date) -> dict[str, list[dict[str, Any]]]:
    s_dt, e_dt = range_dt(start, end)
    V = ChecklistVisit
    conds: list = [V.status == "submitted", V.submitted_at >= s_dt, V.submitted_at < e_dt]
    if not sees_all(auth):
        conds.append(V.coordinator_id == auth.user.id)
    by_branch = (await db.execute(select(V.branch_id, func.count(), func.avg(V.score), func.sum(V.critical_fails)).where(*conds).group_by(V.branch_id))).all()
    by_coord = (await db.execute(select(V.coordinator_id, func.count(), func.avg(V.score), func.count(func.distinct(V.branch_id))).where(*conds).group_by(V.coordinator_id))).all()
    bnames = await branch_names(db)
    unames = await names(db, {r[0] for r in by_coord})
    return {
        "branches": sorted(
            [{"id": r[0], "name": bnames.get(r[0] or 0), "visits": r[1], "avg_score": round(float(r[2]), 1) if r[2] is not None else None, "critical_fails": int(r[3] or 0)} for r in by_branch],
            key=lambda x: (-(x["avg_score"] if x["avg_score"] is not None else -1), -x["visits"]),
        ),
        "coordinators": sorted(
            [{"id": r[0], "name": unames.get(r[0] or 0), "visits": r[1], "avg_score": round(float(r[2]), 1) if r[2] is not None else None, "branches": r[3]} for r in by_coord],
            key=lambda x: -x["visits"],
        ),
    }  # fmt: skip


async def trend(db: AsyncSession, auth: AuthContext, start: date, end: date, branch_id: int | None) -> list[dict[str, Any]]:
    """Haftalik o'rtacha ball (dushanba boshi, Toshkent vaqti)."""
    s_dt, e_dt = range_dt(start, end)
    V = ChecklistVisit
    week = func.date_trunc("week", func.timezone(literal_column("'Asia/Tashkent'"), V.submitted_at))
    conds: list = [V.status == "submitted", V.submitted_at >= s_dt, V.submitted_at < e_dt]
    if branch_id:
        conds.append(V.branch_id == branch_id)
    if not sees_all(auth):
        conds.append(V.coordinator_id == auth.user.id)
    rows = (await db.execute(select(week, func.count(), func.avg(V.score)).where(*conds).group_by(week).order_by(week))).all()
    return [{"week": r[0].date(), "visits": r[1], "avg_score": round(float(r[2]), 1) if r[2] is not None else None} for r in rows]
