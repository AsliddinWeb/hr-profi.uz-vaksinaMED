"""Cheklist holati: koordinatorlar filialga qachon kelgani, cheklistni qanday to'ldirgani va qancha vaqt qolgani — bitta joyda.
Bo'limlar: dashboard (umumiy holat), vaqt, koordinatorlar reytingi (100 ballik), tashriflar, filial qamrovi (oyiga 4 tagacha tashrif)."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.checklists import Access
from app.db import get_session
from app.deps import AuthContext
from app.models.checklists import ChecklistVisit
from app.models.org import Branch
from app.services import checklists as svc
from app.services.company import get_setting
from app.timeutil import local_date, now, tz

router = APIRouter(prefix="/v1/checklists/status", tags=["checklists"])




def _bucket(score: float | None) -> str:
    if score is None:
        return "none"
    return "good" if score >= 85 else "mid" if score >= 70 else "low"


def _period(period: str, today: date) -> tuple[date, date]:
    if period == "today":
        return today, today
    if period == "7d":
        return today - timedelta(days=6), today
    if period == "30d":
        return today - timedelta(days=29), today
    return date(2000, 1, 1), today


async def _visits(db: AsyncSession, auth: AuthContext, start: date, end: date, coordinator_id: int | None, branch_id: int | None) -> list[ChecklistVisit]:
    s_dt, e_dt = svc.range_dt(start, end)
    V = ChecklistVisit
    stmt = select(V).where(V.status == "submitted", V.submitted_at >= s_dt, V.submitted_at < e_dt)
    if not svc.sees_all(auth):
        stmt = stmt.where(V.coordinator_id == auth.user.id)
    if coordinator_id:
        stmt = stmt.where(V.coordinator_id == coordinator_id)
    if branch_id:
        stmt = stmt.where(V.branch_id == branch_id)
    return list((await db.scalars(stmt.order_by(V.submitted_at.desc()).limit(20000))).all())


def _rank(visits: list[ChecklistVisit], coords: dict[int, str]) -> list[dict[str, Any]]:
    """100 ballik baho: soni (40) — eng faol koordinatorga nisbatan, sifat (40) — o'rtacha ball, GPS (20) — filial ichida boshlanganlar ulushi."""
    by: dict[int, list[ChecklistVisit]] = defaultdict(list)
    for v in visits:
        if v.coordinator_id:
            by[v.coordinator_id].append(v)
    top = max((len(x) for x in by.values()), default=0)
    out = []
    for cid, name in coords.items():
        vs = by.get(cid, [])
        scores = [v.score for v in vs if v.score is not None]
        avg = sum(scores) / len(scores) if scores else 0.0
        gps = sum(1 for v in vs if v.geo_ok and v.latitude is not None) / len(vs) if vs else 0.0
        total = round((40 * len(vs) / top if top else 0) + 40 * avg / 100 + 20 * gps) if vs else 0
        out.append({"id": cid, "name": name, "points": total, "level": "none" if not vs else "good" if total >= 80 else "mid" if total >= 60 else "low",
                    "visits": len(vs), "branches": len({v.branch_id for v in vs}), "avg_score": round(avg, 1), "gps_pct": round(gps * 100),
                    "last": max((v.submitted_at for v in vs), default=None)})  # fmt: skip
    return sorted(out, key=lambda r: (-r["points"], -r["visits"], r["name"] or ""))


async def _coordinators(db: AsyncSession, auth: AuthContext) -> dict[int, str]:
    ids = {c for (c,) in (await db.execute(select(Branch.coordinator_user_id).where(Branch.is_active.is_(True), Branch.coordinator_user_id.is_not(None)))).all()}
    if not svc.sees_all(auth):
        ids = {auth.user.id}
    return await svc.names(db, ids)


@router.get("")
async def status(period: str = Query(default="all", pattern="^(all|today|7d|30d)$"), coordinator_id: int | None = None, branch_id: int | None = None,
                 db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):  # fmt: skip
    today = local_date(now())
    start, end = _period(period, today)
    visits = await _visits(db, auth, start, end, coordinator_id, branch_id)
    clause = svc.branch_clause(auth)
    bstmt = select(Branch.id).where(Branch.is_active.is_(True))
    if clause is not None:
        bstmt = bstmt.where(clause)
    if branch_id:
        bstmt = bstmt.where(Branch.id == branch_id)
    if coordinator_id:
        bstmt = bstmt.where(Branch.coordinator_user_id == coordinator_id)
    all_branches = {b for (b,) in (await db.execute(bstmt)).all()}
    visited = {v.branch_id for v in visits if v.branch_id}
    scores = [v.score for v in visits if v.score is not None]
    yes = no = 0
    for v in visits:
        for a in v.answers or []:
            if a.get("na") or a.get("value") is None:
                continue
            if svc.is_fail(a):
                no += 1
            else:
                yes += 1
    gps_yes = sum(1 for v in visits if v.latitude is not None)
    buckets = Counter(_bucket(v.score) for v in visits)
    daily = Counter(v.submitted_at.astimezone(tz()).date().isoformat() for v in visits if v.submitted_at)
    coords = await _coordinators(db, auth)
    return {
        "period": period, "start": start if period != "all" else None, "end": end,
        "kpis": {"visits": len(visits), "branches": len(visited), "coordinators": len({v.coordinator_id for v in visits if v.coordinator_id}),
                 "avg_score": round(sum(scores) / len(scores), 1) if scores else None, "coverage": {"visited": len(visited & all_branches), "total": len(all_branches)},
                 "gps_pct": round(gps_yes / len(visits) * 100) if visits else None},
        "score_buckets": {k: buckets.get(k, 0) for k in ("good", "mid", "low")},
        "answers": {"yes": yes, "no": no},
        "process": {"gps": gps_yes, "no_gps": len(visits) - gps_yes, "not_visited": len(all_branches - visited)},
        "daily": [{"date": (today - timedelta(days=13 - i)).isoformat(), "n": daily.get((today - timedelta(days=13 - i)).isoformat(), 0)} for i in range(14)],
        "coordinators": [{"id": i, "name": n} for i, n in sorted(coords.items(), key=lambda x: x[1] or "")],
    }  # fmt: skip


@router.get("/ranking")
async def ranking(span: str = Query(default="week", pattern="^(day|week|month)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    today = local_date(now())
    start = today if span == "day" else today - timedelta(days=6 if span == "week" else 29)
    visits = await _visits(db, auth, start, today, None, None)
    return {"start": start, "end": today, "items": _rank(visits, await _coordinators(db, auth))}


@router.get("/time")
async def time_stats(period: str = Query(default="30d", pattern="^(all|today|7d|30d)$"), coordinator_id: int | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Vaqt: tashrif davomiyligi (boshlash -> topshirish), kelish soatlari va koordinator bo'yicha o'rtacha."""
    today = local_date(now())
    start, end = _period(period, today)
    visits = await _visits(db, auth, start, end, coordinator_id, None)
    dur = [(v, (v.submitted_at - v.started_at).total_seconds() / 60) for v in visits if v.submitted_at and v.started_at]
    hours = Counter(v.started_at.astimezone(tz()).hour for v in visits if v.started_at)
    names_ = await svc.names(db, {v.coordinator_id for v in visits})
    bnames = await svc.branch_names(db)
    per: dict[int, list[float]] = defaultdict(list)
    for v, m in dur:
        if v.coordinator_id:
            per[v.coordinator_id].append(m)
    return {
        "avg_minutes": round(sum(m for _, m in dur) / len(dur), 1) if dur else None,
        "short": sum(1 for _, m in dur if m < 5), "long": sum(1 for _, m in dur if m > 120),
        "hours": [{"hour": h, "n": hours.get(h, 0)} for h in range(6, 24)],
        "by_coordinator": sorted([{"id": c, "name": names_.get(c), "visits": len(ms), "avg_minutes": round(sum(ms) / len(ms), 1)} for c, ms in per.items()], key=lambda r: r["avg_minutes"]),
        "recent": [{"id": v.id, "branch": bnames.get(v.branch_id or 0), "coordinator": names_.get(v.coordinator_id or 0), "started_at": v.started_at, "submitted_at": v.submitted_at, "minutes": round(m)} for v, m in dur[:50]],
    }  # fmt: skip


@router.get("/coverage")
async def coverage(month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"), coordinator_id: int | None = None, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(Access)):
    """Filial qamrovi: oy ichida har filialga nechta tashrif bo'lgan (limit 4), oxirgi tashrif va o'rtacha ball."""
    today = local_date(now())
    y, m = map(int, (month or today.strftime("%Y-%m")).split("-"))
    start = date(y, m, 1)
    end = min(date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1), today)
    visits = await _visits(db, auth, start, end, coordinator_id, None)
    clause = svc.branch_clause(auth)
    bstmt = select(Branch).where(Branch.is_active.is_(True))
    if clause is not None:
        bstmt = bstmt.where(clause)
    if coordinator_id:
        bstmt = bstmt.where(Branch.coordinator_user_id == coordinator_id)
    branches = (await db.scalars(bstmt.order_by(Branch.number.nulls_last(), Branch.name))).all()
    limit = await get_setting(db, "checklists.month_limit")
    by: dict[int, list[ChecklistVisit]] = defaultdict(list)
    for v in visits:
        if v.branch_id:
            by[v.branch_id].append(v)
    cn = await svc.names(db, {b.coordinator_user_id for b in branches})
    items = []
    for b in branches:
        vs = by.get(b.id, [])
        sc = [v.score for v in vs if v.score is not None]
        items.append({"id": b.id, "name": f"№{b.number} {b.name}" if b.number else b.name, "coordinator": cn.get(b.coordinator_user_id or 0),
                      "visits": len(vs), "limit": limit, "over_limit": len(vs) > limit, "avg_score": round(sum(sc) / len(sc), 1) if sc else None,
                      "last": max((v.submitted_at for v in vs), default=None)})  # fmt: skip
    items.sort(key=lambda r: (r["visits"], r["name"]))
    return {"month": f"{y}-{m:02d}", "limit": limit, "visited": sum(1 for i in items if i["visits"]), "total": len(items), "over_limit": sum(1 for i in items if i["over_limit"]), "items": items}



