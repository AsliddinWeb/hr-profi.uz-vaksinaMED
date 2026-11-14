"""Rekruting tahlili (TZ: HR PROFI Recruitment Management & Analytics).

Bitta so'rov bilan: KPI kartochkalari, 10 bosqichli voronka, formulalar (contact rate, screening pass, interview attendance/pass,
offer acceptance, hiring conversion, time to hire / time to fill), manbalar (konversiya, cost per hire), soatlik/kunlik arizalar
(lavozim bo'yicha ham), rad etish sabablari (% bilan) va rekruterlar reytingi.

Muhim qoida: nomzodlar, arizalar va faoliyat (qo'ng'iroq) hodisalari alohida sanaladi — qo'ng'iroqlar soni nomzodlar soni emas.
Davr kogorta usulida: arizalar `applied_at` bo'yicha tanlanadi va ularning hozirgi holati kuzatiladi.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.ai import AiRequest
from app.models.auth import User
from app.models.org import Position
from app.models.recruit import (
    Application,
    BackgroundCheck,
    Candidate,
    IntegrationLog,
    InterviewInvite,
    RecruitCall,
    SourceLink,
    Vacancy,
    VacancyChannel,
)
from app.rbac import matches
from app.services import ai
from app.services import recruit as rsvc
from app.services.company import get_setting
from app.services.recruit_core import REJECT_CODES
from app.timeutil import localize, now, tz

router = APIRouter(prefix="/v1/recruit/analytics", tags=["recruit"])

# voronka bosqichlari (TZ 3-bo'lim): har bir ariza qaysi bosqichlarga yetganini belgilaymiz
STAGES = ("applied", "contacted", "screening_passed", "interview_invited", "interview_attended", "interview_passed", "background", "offer", "offer_accepted", "hired")
METRICS = STAGES + ("rejected", "no_show", "active")


def _reader(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not any(matches(auth.permissions, p) for p in ("recruit.read", "recruit.manage", "recruit.approve")):
        raise error(403, "forbidden")
    return auth


async def _scope(db: AsyncSession, auth: AuthContext, f: "Filters") -> str:
    """Rollar bo'yicha ko'rinish (TZ): HR direktor, rahbariyat va auditor — hammasi; rekruter (faqat recruit.manage) — sozlama
    yoqilgan bo'lsa faqat o'z vakansiya/nomzodlari. Rekruterning boshqa rekruter filtri e'tiborsiz qoldiriladi."""
    if rsvc.has(auth, "recruit.approve") or rsvc.has(auth, "org.manage") or not rsvc.has(auth, "recruit.manage"):
        return "all"
    if not await get_setting(db, "recruit.analytics_own"):
        return "all"
    f.recruiter_id = auth.user.id
    return "own"


def _pct(a: int, b: int) -> float | None:
    return round(a * 100 / b, 1) if b else None


def _avg(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 1) if xs else None


class Filters:
    def __init__(
        self,
        start: date | None = None,
        end: date | None = None,
        branch_id: int | None = None,
        department_id: int | None = None,
        position_id: int | None = None,
        vacancy_id: int | None = None,
        recruiter_id: int | None = None,
        source: str | None = Query(default=None, max_length=20),
    ):
        today = now().astimezone(tz()).date()
        self.end = end or today
        self.start = start or (self.end - timedelta(days=29))
        if self.end < self.start or (self.end - self.start).days > 800:
            raise error(400, "range_invalid", max_days=800)
        self.branch_id, self.department_id, self.position_id = branch_id, department_id, position_id
        self.vacancy_id, self.recruiter_id, self.source = vacancy_id, recruiter_id, source

    @property
    def lo(self) -> datetime:
        return localize(datetime.combine(self.start, time.min))

    @property
    def hi(self) -> datetime:
        return localize(datetime.combine(self.end + timedelta(days=1), time.min))

    def vacancy_where(self) -> list[Any]:
        w: list[Any] = []
        if self.branch_id:
            w.append(Vacancy.branch_id == self.branch_id)
        if self.department_id:
            w.append(Vacancy.department_id == self.department_id)
        if self.position_id:
            w.append(Vacancy.position_id == self.position_id)
        if self.vacancy_id:
            w.append(Vacancy.id == self.vacancy_id)
        return w


def _source(link: SourceLink | None, cand: Candidate) -> str:
    return (link.channel if link else None) or (cand.source or "").strip().lower()[:20] or "manual"


async def _collect(db: AsyncSession, f: Filters) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(Application, Vacancy, Candidate, SourceLink)
            .join(Vacancy, Vacancy.id == Application.vacancy_id)
            .join(Candidate, Candidate.id == Application.candidate_id)
            .outerjoin(SourceLink, SourceLink.id == Application.source_link_id)
            .where(Application.applied_at >= f.lo, Application.applied_at < f.hi, *f.vacancy_where())
        )
    ).all()
    apps: list[dict[str, Any]] = []
    for a, v, c, link in rows:
        rec = a.recruiter_id or v.recruiter_id
        src = _source(link, c)
        if f.recruiter_id and rec != f.recruiter_id:
            continue
        if f.source and src != f.source:
            continue
        apps.append({"a": a, "v": v, "c": c, "src": src, "rec": rec})

    app_ids = [x["a"].id for x in apps]
    cand_ids = {x["c"].id for x in apps}
    invited = set(app_ids and (await db.scalars(select(InterviewInvite.application_id).where(InterviewInvite.application_id.in_(app_ids)))).all())
    bg = set(app_ids and (await db.scalars(select(BackgroundCheck.application_id).where(BackgroundCheck.application_id.in_(app_ids)))).all())

    # qo'ng'iroqlar (faoliyat hodisalari) — davr ichida, filtrlar bo'yicha
    cq = select(RecruitCall).where(RecruitCall.called_at >= f.lo, RecruitCall.called_at < f.hi)
    if f.recruiter_id:
        cq = cq.where(RecruitCall.recruiter_id == f.recruiter_id)
    vw = f.vacancy_where()
    if vw:
        cq = cq.join(Vacancy, Vacancy.id == RecruitCall.vacancy_id).where(*vw)
    calls = list((await db.scalars(cq)).all())
    reached_cands = {c.candidate_id for c in calls if c.candidate_id and c.outcome != "no_answer"}
    called_cands = {c.candidate_id for c in calls if c.candidate_id}

    for x in apps:
        a: Application = x["a"]
        st = a.stage
        later = st in ("interview", "offer", "hired")
        m = {"applied"}
        if st != "new" or x["c"].id in reached_cands or later:
            m.add("contacted")
        if later or a.interview_at or a.id in invited:
            m.add("screening_passed")
        if a.interview_at or a.id in invited or a.interviewed_at or st in ("offer", "hired"):
            m.add("interview_invited")
        if a.interview_attended or a.interviewed_at or st in ("offer", "hired") or a.offer_status:
            m.add("interview_attended")
        if st in ("offer", "hired") or a.offer_status or a.bg_status in ("pending", "passed") or a.id in bg:
            m.add("interview_passed")
        if a.bg_status or a.id in bg:
            m.add("background")
        if st in ("offer", "hired") or a.offer_status or a.offer_sent_at:
            m.add("offer")
        if a.offer_response == "accepted" or st == "hired":
            m.add("offer_accepted")
        if st == "hired" or a.hired_at:
            m.add("hired")
        if a.interview_attended is False or a.reject_code == "no_show":
            m.add("no_show")
        if st == "rejected":
            m.add("rejected")
        elif "hired" not in m:
            m.add("active")
        x["m"] = m
    return {"apps": apps, "calls": calls, "cand_ids": cand_ids, "called_cands": called_cands}


@router.get("")
async def analytics(f: Filters = Depends(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_reader)):
    scope = await _scope(db, auth, f)
    d = await _collect(db, f)
    apps, calls = d["apps"], d["calls"]
    cnt = Counter(k for x in apps for k in x["m"])
    n = len(apps)

    # vakansiyalar: faol soni va time to fill (davr ichida yopilganlar)
    vw = f.vacancy_where()
    vacs = list((await db.scalars(select(Vacancy).where(*vw))).all())
    if f.recruiter_id:
        vacs = [v for v in vacs if v.recruiter_id == f.recruiter_id]
    active_vac = sum(1 for v in vacs if v.status == "open")
    fill = [(v.closed_at - v.opened_at).total_seconds() / 86400 for v in vacs if v.opened_at and v.closed_at and f.lo <= v.closed_at < f.hi]
    tth = [(x["a"].hired_at - x["a"].applied_at).total_seconds() / 86400 for x in apps if x["a"].hired_at]

    kpi = {
        "active_vacancies": active_vac,
        "applications": n,
        "candidates": len(d["cand_ids"]),
        "calls": len(calls),
        "called_candidates": len(d["called_cands"]),
        **{k: cnt[k] for k in STAGES[1:]},
        "rejected": cnt["rejected"],
        "no_show": cnt["no_show"],
        "active": cnt["active"],
    }
    formulas = {
        "contact_rate": _pct(cnt["contacted"], n),
        "screening_pass": _pct(cnt["screening_passed"], cnt["contacted"]),
        "interview_attendance": _pct(cnt["interview_attended"], cnt["interview_invited"]),
        "interview_pass": _pct(cnt["interview_passed"], cnt["interview_attended"]),
        "offer_acceptance": _pct(cnt["offer_accepted"], cnt["offer"]),
        "hiring_conversion": _pct(cnt["hired"], n),
        "time_to_hire": _avg(tth),
        "time_to_fill": _avg(fill),
    }
    funnel = [{"key": k, "count": cnt[k], "pct": _pct(cnt[k], n), "step_pct": _pct(cnt[k], cnt[STAGES[i - 1]]) if i else None} for i, k in enumerate(STAGES)]

    # manbalar: bosish (havolalar, umumiy), arizalar, intervyu, offer, ishga olingan, konversiya, xarajat
    vids = [v.id for v in vacs]
    links = list(await db.scalars(select(SourceLink).where(SourceLink.vacancy_id.in_(vids)))) if vids else []
    chans = list(await db.scalars(select(VacancyChannel).where(VacancyChannel.vacancy_id.in_(vids), VacancyChannel.posted_at >= f.lo, VacancyChannel.posted_at < f.hi))) if vids else []
    src: dict[str, dict[str, Any]] = defaultdict(lambda: {"clicks": 0, "applications": 0, "contacted": 0, "interview_invited": 0, "offer": 0, "hired": 0, "cost": 0})
    for lk in links:
        src[lk.channel]["clicks"] += lk.clicks or 0
    for ch in chans:
        src[ch.channel]["cost"] += ch.cost or 0
    for x in apps:
        s = src[x["src"]]
        s["applications"] += 1
        for k in ("contacted", "interview_invited", "offer", "hired"):
            s[k] += k in x["m"]
    sources = sorted(
        ({"source": k, **s, "conversion": _pct(s["hired"], s["applications"]), "interview_rate": _pct(s["interview_invited"], s["applications"]), "cost_per_hire": round(s["cost"] / s["hired"]) if s["hired"] and s["cost"] else None} for k, s in src.items() if not f.source or k == f.source),
        key=lambda r: (-r["applications"], r["source"]),
    )

    # vaqt bo'yicha: soat (0-23), hafta kuni x soat, kunlik qator, lavozim bo'yicha
    hours = [0] * 24
    heat = [[0] * 24 for _ in range(7)]
    daily: Counter[str] = Counter()
    daily_hired: Counter[str] = Counter()
    by_pos: dict[str, dict[str, Any]] = {}
    pos_ids = {x["v"].position_id for x in apps if x["v"].position_id}
    pos_names = {p.id: p.name for p in (await db.scalars(select(Position).where(Position.id.in_(pos_ids)))).all()} if pos_ids else {}
    for x in apps:
        t = x["a"].applied_at.astimezone(tz())
        hours[t.hour] += 1
        heat[t.weekday()][t.hour] += 1
        daily[t.date().isoformat()] += 1
        if x["a"].hired_at:
            daily_hired[x["a"].hired_at.astimezone(tz()).date().isoformat()] += 1
        name = pos_names.get(x["v"].position_id or 0) or x["v"].title
        p = by_pos.setdefault(name, {"position": name, "applications": 0, "hours": [0] * 24, "hired": 0})
        p["applications"] += 1
        p["hours"][t.hour] += 1
        p["hired"] += "hired" in x["m"]
    days = [(f.start + timedelta(days=i)).isoformat() for i in range((f.end - f.start).days + 1)]
    peak = max(range(24), key=lambda h: hours[h]) if n else None

    # rad etish sabablari
    rej = [x for x in apps if "rejected" in x["m"]]
    rc = Counter((x["a"].reject_code or "other") for x in rej)
    reasons = [{"code": k, "count": rc[k], "pct": _pct(rc[k], len(rej))} for k in REJECT_CODES if rc[k]]

    # rekruterlar reytingi
    rs: dict[int, dict[str, Any]] = defaultdict(lambda: {"applications": 0, "calls": 0, "contacted": 0, "interview_invited": 0, "interview_attended": 0, "offer": 0, "hired": 0, "rejected": 0, "tth": []})
    for x in apps:
        if not x["rec"]:
            continue
        r = rs[x["rec"]]
        r["applications"] += 1
        for k in ("contacted", "interview_invited", "interview_attended", "offer", "hired", "rejected"):
            r[k] += k in x["m"]
        if x["a"].hired_at:
            r["tth"].append((x["a"].hired_at - x["a"].applied_at).total_seconds() / 86400)
    for c in calls:
        rs[c.recruiter_id]["calls"] += 1
    names = {u.id: u.full_name for u in (await db.scalars(select(User).where(User.id.in_(list(rs))))).all()} if rs else {}
    recruiters = [
        {"id": uid, "name": names.get(uid) or f"#{uid}", **{k: v for k, v in r.items() if k != "tth"}, "conversion": _pct(r["hired"], r["applications"]), "contact_rate": _pct(r["contacted"], r["applications"]), "time_to_hire": _avg(r["tth"])}
        for uid, r in rs.items()
    ]
    recruiters.sort(key=lambda r: (-r["hired"], -(r["conversion"] or 0), -r["calls"]))
    for i, r in enumerate(recruiters, 1):
        r["rank"] = i

    call_outcomes = Counter(c.outcome for c in calls)
    return {
        "period": {"start": f.start, "end": f.end},
        "scope": scope,
        "kpi": kpi,
        "formulas": formulas,
        "funnel": funnel,
        "sources": sources,
        "hours": hours,
        "peak_hour": peak,
        "heatmap": heat,
        "daily": [{"date": dd, "applications": daily[dd], "hired": daily_hired[dd]} for dd in days],
        "positions": sorted(by_pos.values(), key=lambda p: -p["applications"])[:15],
        "reasons": reasons,
        "rejected_total": len(rej),
        "recruiters": recruiters,
        "call_outcomes": dict(call_outcomes),
    }


@router.get("/list")
async def drill(metric: str = Query(pattern="^(" + "|".join(METRICS) + ")$"), hour: int | None = Query(default=None, ge=0, le=23), reason: str | None = None, f: Filters = Depends(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_reader)):
    """Drill-down: KPI/voronka/manba/soat/sabab ustiga bosilganda — shu ko'rsatkichdagi arizalar ro'yxati."""
    await _scope(db, auth, f)
    d = await _collect(db, f)
    out = []
    for x in d["apps"]:
        if metric not in x["m"]:
            continue
        a: Application = x["a"]
        if hour is not None and a.applied_at.astimezone(tz()).hour != hour:
            continue
        if reason and (a.reject_code or "other") != reason:
            continue
        out.append({"id": a.id, "candidate_id": x["c"].id, "name": x["c"].full_name, "phone": x["c"].phone, "vacancy_id": x["v"].id, "vacancy": x["v"].title, "stage": a.stage, "source": x["src"], "applied_at": a.applied_at, "hired_at": a.hired_at, "reject_code": a.reject_code})
    out.sort(key=lambda r: r["applied_at"], reverse=True)
    return {"items": out[:500], "total": len(out)}


@router.get("/integrations")
async def integrations(days: int = Query(default=7, ge=1, le=90), db: AsyncSession = Depends(get_session), _: AuthContext = Depends(_reader)):
    """Integratsiyalar holati (TZ): ulanganmi, oxirgi muvaffaqiyat/xato, davr ichidagi soni; va umumiy jurnal."""
    s = get_settings()
    since = now() - timedelta(days=days)
    logs = list((await db.scalars(select(IntegrationLog).where(IntegrationLog.created_at >= since).order_by(IntegrationLog.id.desc()))).all())
    ai_rows = list((await db.scalars(select(AiRequest).where(AiRequest.created_at >= since).order_by(AiRequest.id.desc()))).all())
    apps = (await db.execute(select(SourceLink.channel, Application.applied_at).join(SourceLink, SourceLink.id == Application.source_link_id).where(Application.applied_at >= since))).all()

    def stat(rows: list[tuple[bool, datetime, str | None]]) -> dict[str, Any]:
        oks = [r for r in rows if r[0]]
        errs = [r for r in rows if not r[0]]
        return {"ok": len(oks), "errors": len(errs), "last_ok": oks[0][1] if oks else None, "last_error": errs[0][1] if errs else None, "last_error_text": errs[0][2] if errs else None}

    def tg(p: str) -> dict[str, Any]:
        return stat([(lg.ok, lg.created_at, lg.message) for lg in logs if lg.provider == p])

    inbound: dict[str, list[datetime]] = defaultdict(list)
    for ch, at in apps:
        inbound[ch].append(at)
    ai_name = ai.provider()
    items = [
        {"key": "telegram_bot", "kind": "api", "configured": bool(s.telegram_bot_token), **tg("telegram_bot")},
        {"key": "telegram_channel", "kind": "api", "configured": bool(s.telegram_bot_token and s.telegram_vacancy_chat_id.strip()), **tg("telegram_channel")},
        {"key": "ai", "kind": "api", "configured": ai_name is not None, "provider": ai_name, **stat([(r.ok, r.created_at, r.error) for r in ai_rows])},
    ]
    for ch in ("site", "telegram", "hh_uz", "olx", "instagram", "target", "referral"):
        at = sorted(inbound.get(ch, []), reverse=True)
        items.append({"key": ch, "kind": "link", "configured": True, "ok": len(at), "errors": 0, "last_ok": at[0] if at else None, "last_error": None, "last_error_text": None})
    feed = [{"at": lg.created_at, "provider": lg.provider, "action": lg.action, "ok": lg.ok, "message": lg.message} for lg in logs[:150]]
    feed += [{"at": r.created_at, "provider": "ai", "action": r.feature, "ok": r.ok, "message": r.error} for r in ai_rows[:150]]
    feed.sort(key=lambda x: x["at"], reverse=True)
    return {"days": days, "items": items, "logs": feed[:200]}


XL = {
    "uz": {
        "kpi": "KPI", "formulas": "Formulalar", "funnel": "Voronka", "sources": "Manbalar", "hours": "Soatlar", "reasons": "Rad sabablari", "recruiters": "Rekruterlar", "apps": "Arizalar",
        "metric": "Ko'rsatkich", "value": "Qiymat", "stage": "Bosqich", "count": "Soni", "step": "Oldingi bosqichdan %", "source": "Manba", "clicks": "Bosishlar",
        "applications": "Arizalar", "contacted": "Bog'lanildi", "interviews": "Intervyu", "offers": "Offer", "hired": "Ishga olindi", "conversion": "Konversiya %",
        "cost": "Xarajat", "cph": "1 xodim narxi", "hour": "Soat", "reason": "Sabab", "rank": "O'rin", "recruiter": "Rekruter", "calls": "Qo'ng'iroqlar",
        "attended": "Intervyuga keldi", "rejected": "Rad etildi", "tth": "Time to Hire (kun)", "candidate": "Nomzod", "phone": "Telefon", "vacancy": "Vakansiya",
        "applied": "Ariza sanasi", "period": "Davr", "scope_own": "Faqat o'z ko'rsatkichlari",
    },
    "ru": {
        "kpi": "KPI", "formulas": "Формулы", "funnel": "Воронка", "sources": "Источники", "hours": "Часы", "reasons": "Причины отказов", "recruiters": "Рекрутеры", "apps": "Отклики",
        "metric": "Показатель", "value": "Значение", "stage": "Этап", "count": "Кол-во", "step": "% от пред. этапа", "source": "Источник", "clicks": "Переходы",
        "applications": "Отклики", "contacted": "Связались", "interviews": "Интервью", "offers": "Оффер", "hired": "Наняты", "conversion": "Конверсия %",
        "cost": "Расходы", "cph": "Стоимость найма", "hour": "Час", "reason": "Причина", "rank": "Место", "recruiter": "Рекрутер", "calls": "Звонки",
        "attended": "Пришли на интервью", "rejected": "Отказ", "tth": "Time to Hire (дн.)", "candidate": "Кандидат", "phone": "Телефон", "vacancy": "Вакансия",
        "applied": "Дата отклика", "period": "Период", "scope_own": "Только свои показатели",
    },
}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export.xlsx")
async def export_xlsx(lang: str = Query(default="uz", pattern="^(uz|ru)$"), f: Filters = Depends(), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(_reader)):
    """Tahlilni Excel faylga: KPI, formulalar, voronka, manbalar, soatlar, rad sabablari, rekruterlar va arizalar ro'yxati."""
    import io

    from fastapi.responses import Response
    from openpyxl import Workbook
    from openpyxl.styles import Font

    from app.services.xlsx_safe import harden

    d = await analytics(f, db, auth)
    rows = (await _collect(db, f))["apps"]
    lb = XL[lang]
    wb = Workbook()

    def sheet(title: str, head: list[str], data: list[list[Any]], first: bool = False) -> None:
        ws = wb.active if first else wb.create_sheet()
        ws.title = title[:31]
        ws.append(head)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in data:
            ws.append(r)
        for i, h in enumerate(head):
            ws.column_dimensions[ws.cell(1, i + 1).column_letter].width = max(12, min(40, len(str(h)) + 4))
        ws.freeze_panes = "A2"

    kpi = [[lb["period"], f"{f.start} — {f.end}"]] + ([[lb["scope_own"], "✓"]] if d["scope"] == "own" else []) + [[k, v] for k, v in d["kpi"].items()]
    sheet(lb["kpi"], [lb["metric"], lb["value"]], kpi, first=True)
    sheet(lb["formulas"], [lb["metric"], lb["value"]], [[k, v] for k, v in d["formulas"].items()])
    sheet(lb["funnel"], [lb["stage"], lb["count"], "%", lb["step"]], [[s["key"], s["count"], s["pct"], s["step_pct"]] for s in d["funnel"]])
    sheet(
        lb["sources"],
        [lb["source"], lb["clicks"], lb["applications"], lb["contacted"], lb["interviews"], lb["offers"], lb["hired"], lb["conversion"], lb["cost"], lb["cph"]],
        [[s["source"], s["clicks"], s["applications"], s["contacted"], s["interview_invited"], s["offer"], s["hired"], s["conversion"], s["cost"], s["cost_per_hire"]] for s in d["sources"]],
    )
    sheet(lb["hours"], [lb["hour"], lb["applications"]], [[f"{h:02d}:00", v] for h, v in enumerate(d["hours"])])
    sheet(lb["reasons"], [lb["reason"], lb["count"], "%"], [[r["code"], r["count"], r["pct"]] for r in d["reasons"]])
    sheet(
        lb["recruiters"],
        [lb["rank"], lb["recruiter"], lb["applications"], lb["calls"], lb["contacted"], lb["interviews"], lb["attended"], lb["offers"], lb["hired"], lb["rejected"], lb["conversion"], lb["tth"]],
        [[r["rank"], r["name"], r["applications"], r["calls"], r["contacted"], r["interview_invited"], r["interview_attended"], r["offer"], r["hired"], r["rejected"], r["conversion"], r["time_to_hire"]] for r in d["recruiters"]],
    )
    apps = sorted(rows, key=lambda x: x["a"].applied_at, reverse=True)
    sheet(
        lb["apps"],
        [lb["candidate"], lb["phone"], lb["vacancy"], lb["stage"], lb["source"], lb["applied"], lb["hired"]],
        [[x["c"].full_name, x["c"].phone, x["v"].title, x["a"].stage, x["src"], x["a"].applied_at.astimezone(tz()).strftime("%Y-%m-%d %H:%M"),
          x["a"].hired_at.astimezone(tz()).strftime("%Y-%m-%d") if x["a"].hired_at else ""] for x in apps[:5000]],
    )
    harden(wb)
    buf = io.BytesIO()
    wb.save(buf)
    name = f"rekruting-tahlili-{f.start}_{f.end}.xlsx"
    return Response(buf.getvalue(), media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})
