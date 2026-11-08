"""Prebording: lavozim bo'yicha dars bosqichlari (video + slayd + test), ko'rish nazorati va kamera/mikrofon kuzatuvi.

Dastur = `InternshipProgram(phase="preboarding", position_id=...)`; bosqich = `InternshipStep(kind="lesson")`.
Bosqich bajarilgan hisoblanadi: video yetarli ko'rilgan, slayd yetarli o'qilgan va test o'tilgan bo'lsa (qaysi biri bor bo'lsa).
Stajyor ishga stajyor lavozimida olinsa, birinchi kirishda shu lavozim dasturiga o'zi biriktiriladi.
"""

import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import error
from app.models.employees import Employee
from app.models.internship import (
    InternshipEnrollment,
    InternshipMonitor,
    InternshipProgram,
    InternshipProgress,
    InternshipStep,
    InternshipView,
)
from app.models.org import Position
from app.services import internship as isvc

VIDEO_DONE_RATIO = 0.9  # YouTube: video kamida 90% ko'rilsin
DEFAULT_MIN_VIDEO_S = 120  # Drive video: davomiyligi noma'lum, kamida shuncha soniya
DEFAULT_MIN_SLIDES_S = 60
MAX_TICK_S = 20  # bitta yurak urishida qo'shiladigan eng ko'p soniya (soxta yuborishdan himoya)
LIVE_WINDOW_S = 45  # shu vaqt ichida signal bo'lsa sessiya «jonli»
MAX_CLIP_BYTES = 12 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 600 * 1024
RETENTION_DAYS = 90

GOAL = "Maqsad: yangi xodim filialga kelguncha va birinchi 7 kunda bir xil standartda tayyorlanadi."
CONTROL = "Nazorat va hisobot: koordinator jarayonni kuzatadi, HR auditor konfliktlarni tekshiradi, HRD barcha hisobotlarni platformada ko'radi."
TEMPLATE_STAGES: tuple[tuple[str, str], ...] = (
    ("1-bosqich: Tajriba darajasi", "Suhbatdan keyin tajribaga qarab bosqichlar ochiladi. Tajribasiz xodim stajyordan boshlaydi."),
    ("2-bosqich: 1 kunlik test", "Darslarni (video va slayd) ko'ring va test topshiring. O'tish chegarasidan yuqori natija keyingi bosqichni ochadi; yaxshi natijaga rag'bat bor."),
    ("3-bosqich: Filialga tayyorgarlik", "Filial manzili va ish vaqti, ustozlaringiz (trener, HR, filial mudiri) va hamkasblaringiz bilan tanishing."),
    ("4-bosqich: Filialda 7 kun", "Har kuni dars ko'rasiz va hisobot yozasiz; mudir, trener va HR har kuni fidbek beradi."),
    ("5-bosqich: 7-kun qarori", "HR menejer va trener moslikni hal qiladi. Mos bo'lsangiz 90 kunlik onboarding boshlanadi."),
)


# --- Video havolasi --------------------------------------------------------------------


def youtube_id(url: str | None) -> str | None:
    m = re.search(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/))([\w-]{11})", url or "")
    return m.group(1) if m else None


def drive_id(url: str | None) -> str | None:
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]{10,})", url or "")
    return m.group(1) if m else None


def media_out(s: InternshipStep) -> dict[str, Any]:
    yt, dv, sl = youtube_id(s.url), drive_id(s.url), drive_id(s.slides_url)
    return {
        "video": {"kind": "youtube" if yt else "drive" if dv else ("link" if s.url else None), "id": yt or dv, "url": s.url,
                  "thumb": f"https://img.youtube.com/vi/{yt}/hqdefault.jpg" if yt else None,
                  "embed": f"https://drive.google.com/file/d/{dv}/preview" if dv else None},
        "slides": {"id": sl, "url": s.slides_url, "embed": f"https://drive.google.com/file/d/{sl}/preview" if sl else (s.slides_url or None)},
    }  # fmt: skip


def check_urls(url: str | None, slides: str | None) -> None:
    for u in (url, slides):
        if u and not u.lower().startswith(("http://", "https://")):
            raise error(400, "url_invalid")


# --- Lavozim dasturlari ----------------------------------------------------------------


async def ensure_track(db: AsyncSession, position: Position) -> InternshipProgram:
    """Lavozim uchun prebording dasturi; yo'q bo'lsa shablondagi 5 bosqich bilan yaratiladi."""
    p = await db.scalar(select(InternshipProgram).where(InternshipProgram.phase == "preboarding", InternshipProgram.position_id == position.id, InternshipProgram.is_active.is_(True)).order_by(InternshipProgram.id))
    if p:
        return p
    p = InternshipProgram(name=f"{position.name}: prebording", description=f"{GOAL}\n{CONTROL}", pass_score=50, sequential=True, is_active=True, phase="preboarding", position_id=position.id, duration_days=7)
    db.add(p)
    await db.flush()
    for i, (title, desc) in enumerate(TEMPLATE_STAGES):
        db.add(InternshipStep(program_id=p.id, position=i, kind="lesson", title=title, description=desc, questions=[], pass_score=None, max_attempts=3, required=True, audience="all", published=True))
    await db.flush()
    return p


async def tracks(db: AsyncSession) -> list[InternshipProgram]:
    return list((await db.scalars(select(InternshipProgram).where(InternshipProgram.phase == "preboarding", InternshipProgram.position_id.is_not(None), InternshipProgram.is_active.is_(True)).order_by(InternshipProgram.id))).all())


async def my_enrollment(db: AsyncSession, emp: Employee, moment: datetime) -> InternshipEnrollment | None:
    """Stajyorning faol prebordingi; yo'q bo'lsa va lavozimida dastur bo'lsa o'zi biriktiriladi."""
    e = await db.scalar(
        select(InternshipEnrollment).where(InternshipEnrollment.employee_id == emp.id, InternshipEnrollment.phase == "preboarding", InternshipEnrollment.status.in_(("active", "ready"))).order_by(InternshipEnrollment.id.desc())
    )  # fmt: skip
    if e or not emp.position_id or emp.status != "active":
        return e
    p = await db.scalar(select(InternshipProgram).where(InternshipProgram.phase == "preboarding", InternshipProgram.position_id == emp.position_id, InternshipProgram.is_active.is_(True)).order_by(InternshipProgram.id))
    if not p:
        return None
    e = InternshipEnrollment(program_id=p.id, employee_id=emp.id, status="active", started_at=moment, due_date=(moment + timedelta(days=p.duration_days or 7)).date(), phase="preboarding")
    db.add(e)
    await db.flush()
    return e


# --- Dars talablari va ko'rish ---------------------------------------------------------


async def views_of(db: AsyncSession, enrollment_id: int) -> dict[tuple[int, str], InternshipView]:
    return {(v.step_id, v.kind): v for v in (await db.scalars(select(InternshipView).where(InternshipView.enrollment_id == enrollment_id))).all()}


def requirements(s: InternshipStep, views: dict[tuple[int, str], InternshipView], prog: InternshipProgress | None, threshold: int) -> dict[str, Any]:
    """Darsning har qismi bo'yicha holat: kerakmi, qancha bajarilgan, tayyormi."""
    out: dict[str, Any] = {}
    if s.url:
        v = views.get((s.id, "video"))
        yt = youtube_id(s.url)
        need = int(v.duration * VIDEO_DONE_RATIO) if yt and v and v.duration else (s.min_video_seconds or DEFAULT_MIN_VIDEO_S)
        seen = v.seconds if v else 0
        out["video"] = {"need": need, "seen": seen, "duration": v.duration if v else None, "done": bool(v and (v.done or seen >= need))}
    if s.slides_url:
        v = views.get((s.id, "slides"))
        need = s.min_slides_seconds or DEFAULT_MIN_SLIDES_S
        seen = v.seconds if v else 0
        out["slides"] = {"need": need, "seen": seen, "done": seen >= need}
    if s.questions:
        out["test"] = {"threshold": threshold, "score": prog.score if prog else None, "attempts": prog.attempts if prog else 0, "max_attempts": s.max_attempts, "done": bool(prog and prog.score is not None and prog.score >= threshold)}
    return out


def media_ready(req: dict[str, Any]) -> bool:
    """Testdan oldin: video va slayd ko'rib bo'linganmi."""
    return all(req[k]["done"] for k in ("video", "slides") if k in req)


async def record_view(db: AsyncSession, e: InternshipEnrollment, s: InternshipStep, kind: str, delta: int, pos: int | None, duration: int | None) -> InternshipView:
    v = await db.scalar(select(InternshipView).where(InternshipView.enrollment_id == e.id, InternshipView.step_id == s.id, InternshipView.kind == kind).with_for_update())
    if v is None:
        v = InternshipView(enrollment_id=e.id, step_id=s.id, kind=kind, seconds=0, max_pos=0, done=False)
        db.add(v)
    v.seconds = (v.seconds or 0) + max(0, min(int(delta), MAX_TICK_S))
    if pos is not None:
        v.max_pos = max(v.max_pos or 0, int(pos))
    if duration and kind == "video":
        v.duration = int(duration)
    if kind == "video" and v.duration and v.seconds >= v.duration * VIDEO_DONE_RATIO:
        v.done = True
    from app.timeutil import now  # noqa: PLC0415

    v.updated_at = now()
    await db.flush()
    return v


async def try_complete(db: AsyncSession, e: InternshipEnrollment, s: InternshipStep, program: InternshipProgram, moment: datetime) -> bool:
    """Hamma qism bajarilgan bo'lsa bosqichni yopadi. Test bo'lmasa video/slayd yetarli; hech narsa bo'lmasa «o'qidim»."""
    prog = (await isvc.progress_of(db, e.id)).get(s.id)
    if prog and prog.done:
        return True
    req = requirements(s, await views_of(db, e.id), prog, isvc.threshold(s, program))
    if req and all(r["done"] for r in req.values()):
        await isvc.complete_step(db, e, s, moment, score=prog.score if prog else None)
        return True
    return False


# --- Kamera / mikrofon kuzatuvi -------------------------------------------------------


def monitoring_of(p: InternshipProgram) -> dict[str, bool]:
    m = p.monitoring or {}
    return {k: bool(m.get(k, True)) for k in ("camera", "live", "record", "snapshots")}


async def start_session(db: AsyncSession, e: InternshipEnrollment, s: InternshipStep, moment: datetime) -> InternshipMonitor:
    """Dars kuzatuvi sessiyasi (bitta ochiq sessiya qayta ishlatiladi)."""
    m = await db.scalar(select(InternshipMonitor).where(InternshipMonitor.enrollment_id == e.id, InternshipMonitor.ended_at.is_(None)).order_by(InternshipMonitor.id.desc()))
    if m and (moment - m.last_seen_at).total_seconds() < 120:
        m.step_id, m.last_seen_at = s.id, moment
        return m
    if m:
        m.ended_at = m.last_seen_at
    m = InternshipMonitor(enrollment_id=e.id, step_id=s.id, room=f"preboard-{e.id}-{secrets.token_hex(4)}", started_at=moment, last_seen_at=moment, clips=[], snapshots=[], events=[])
    db.add(m)
    await db.flush()
    return m


def is_live(m: InternshipMonitor, moment: datetime) -> bool:
    return m.ended_at is None and (moment - m.last_seen_at).total_seconds() <= LIVE_WINDOW_S


def monitor_out(m: InternshipMonitor, moment: datetime, step_titles: dict[int, str] | None = None) -> dict[str, Any]:
    return {
        "id": m.id, "step_id": m.step_id, "step": (step_titles or {}).get(m.step_id or 0), "started_at": m.started_at, "last_seen_at": m.last_seen_at,
        "ended_at": m.ended_at, "live": is_live(m, moment), "clips": len(m.clips or []), "snapshots": len(m.snapshots or []),
        "seconds": int(((m.ended_at or m.last_seen_at) - m.started_at).total_seconds()), "events": (m.events or [])[-20:],
    }  # fmt: skip


def viewer_token(room: str, user_id: int, name: str) -> str:
    """HR/trener uchun: faqat ko'rish va eshitish (nashr qilish yo'q)."""
    from app.services import calls  # noqa: PLC0415

    grant = {"roomJoin": True, "room": room, "canPublish": False, "canSubscribe": True, "canPublishData": False, "hidden": True}
    return calls._sign({"name": name, "video": grant}, 2 * 3600, f"w{user_id}")


def publisher_token(room: str, user_id: int, name: str) -> str:
    """Stajyor uchun: faqat o'z kamerasi va mikrofonini nashr qiladi, boshqalarni ko'rmaydi."""
    from app.services import calls  # noqa: PLC0415

    grant = {"roomJoin": True, "room": room, "canPublish": True, "canSubscribe": False, "canPublishData": False}
    return calls._sign({"name": name, "video": grant}, 3 * 3600, calls.identity_of(user_id))


async def purge_recordings(db: AsyncSession, storage, moment: datetime) -> int:
    """Saqlash muddati (90 kun) o'tgan kuzatuv yozuvlari va suratlarini o'chiradi; sessiya qatori (vaqtlar, hodisalar) qoladi."""
    old = (await db.scalars(select(InternshipMonitor).where(InternshipMonitor.started_at < moment - timedelta(days=RETENTION_DAYS)))).all()
    n = 0
    for m in old:
        for item in [*(m.clips or []), *(m.snapshots or [])]:
            await storage.delete(item["key"])
            n += 1
        m.clips, m.snapshots = [], []
    return n
