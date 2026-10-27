"""Stajirovka: dastur bosqichlari, test baholash, progress va "ishga tayyor" holati."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext, error
from app.models.employees import Employee
from app.models.internship import (
    InternshipEnrollment,
    InternshipProgram,
    InternshipProgress,
    InternshipStep,
)
from app.rbac import matches
from app.services.answers import users_with_permission
from app.services.notifications import notify, register_template

KINDS = ("video", "document", "text", "test")

register_template("internship.enrolled", {"uz": "Stajirovka boshlandi", "ru": "Стажировка началась"}, {"uz": "{program}: {intern}", "ru": "{program}: {intern}"}, "info")
register_template("internship.ready", {"uz": "Stajyor ishga tayyor", "ru": "Стажёр готов к работе"}, {"uz": "{intern}: {score}", "ru": "{intern}: {score}"}, "success")
register_template("internship.completed", {"uz": "Stajirovka yakunlandi", "ru": "Стажировка завершена"}, {"uz": "{program}", "ru": "{program}"}, "success")


def has(auth: AuthContext, perm: str) -> bool:
    return matches(auth.permissions, perm)


def sees_all(auth: AuthContext) -> bool:
    return has(auth, "internship.read") or has(auth, "internship.manage")


def can_manage(auth: AuthContext) -> bool:
    return has(auth, "internship.manage")


def is_intern(auth: AuthContext, emp: Employee | None) -> bool:
    return bool(emp and emp.user_id == auth.user.id)


def is_mentor(auth: AuthContext, e: InternshipEnrollment) -> bool:
    return e.mentor_id == auth.user.id


def can_view(auth: AuthContext, e: InternshipEnrollment, emp: Employee | None) -> bool:
    return sees_all(auth) or is_mentor(auth, e) or is_intern(auth, emp)


def can_supervise(auth: AuthContext, e: InternshipEnrollment) -> bool:
    """Tasdiqlash/tiklash: boshqaruvchi yoki shu stajyorning murabbiyi."""
    return can_manage(auth) or (is_mentor(auth, e) and has(auth, "internship.own"))


# --- Savollar va baholash -----------------------------------------------------------------


def clean_questions(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for q in raw:
        text = str(q.get("text") or "").strip()
        opts = [str(o).strip() for o in q.get("options") or []]
        correct = sorted({int(c) for c in q.get("correct") or []})
        if not text or not 2 <= len(opts) <= 6 or any(not o for o in opts) or not correct or any(c < 0 or c >= len(opts) for c in correct):
            raise error(400, "questions_invalid")
        qid = str(q.get("id") or "")
        if not qid or qid in seen:
            qid = uuid.uuid4().hex[:8]
        seen.add(qid)
        out.append({"id": qid, "text": text, "options": opts, "correct": correct})
    return out


def public_questions(step: InternshipStep) -> list[dict[str, Any]]:
    """Stajyorga to'g'ri javoblarsiz: faqat savol, variantlar va bir nechta to'g'ri javob borligi."""
    return [{"id": q["id"], "text": q["text"], "options": q["options"], "multiple": len(q["correct"]) > 1} for q in step.questions or []]


def grade(step: InternshipStep, answers: dict[str, list[int]]) -> tuple[int, list[str]]:
    qs = step.questions or []
    wrong = [q["id"] for q in qs if sorted(set(answers.get(q["id"], []))) != q["correct"]]
    return round((len(qs) - len(wrong)) / len(qs) * 100) if qs else 0, wrong


def threshold(step: InternshipStep, program: InternshipProgram) -> int:
    return step.pass_score if step.pass_score is not None else program.pass_score


# --- Progress ----------------------------------------------------------------------------


async def steps_of(db: AsyncSession, program_id: int) -> list[InternshipStep]:
    return list((await db.scalars(select(InternshipStep).where(InternshipStep.program_id == program_id).order_by(InternshipStep.position, InternshipStep.id))).all())


async def progress_of(db: AsyncSession, enrollment_id: int) -> dict[int, InternshipProgress]:
    return {p.step_id: p for p in (await db.scalars(select(InternshipProgress).where(InternshipProgress.enrollment_id == enrollment_id))).all()}


def step_states(program: InternshipProgram, steps: list[InternshipStep], prog: dict[int, InternshipProgress]) -> list[dict[str, Any]]:
    """Har bosqich: done | available | locked (ketma-ket dasturda oldingi majburiy bosqich bajarilmagan)."""
    out, blocked = [], False
    for s in steps:
        p = prog.get(s.id)
        done = bool(p and p.done)
        state = "done" if done else ("locked" if program.sequential and blocked else "available")
        out.append({"step": s, "state": state, "score": p.score if p else None, "attempts": p.attempts if p else 0, "completed_at": p.completed_at if p else None})
        if s.required and not done:
            blocked = True
    return out


def summarize(steps: list[InternshipStep], prog: dict[int, InternshipProgress]) -> dict[str, Any]:
    req = [s for s in steps if s.required]
    done = [s for s in req if prog.get(s.id) and prog[s.id].done]
    scores = [prog[s.id].score for s in steps if s.kind == "test" and prog.get(s.id) and prog[s.id].score is not None]
    return {
        "required": len(req), "done": len(done), "percent": round(len(done) / len(req) * 100) if req else 0,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
    }  # fmt: skip


async def complete_step(db: AsyncSession, e: InternshipEnrollment, step: InternshipStep, moment: datetime, *, score: int | None = None, done: bool = True) -> InternshipProgress:
    p = (await db.scalars(select(InternshipProgress).where(InternshipProgress.enrollment_id == e.id, InternshipProgress.step_id == step.id))).first()
    if p is None:
        p = InternshipProgress(enrollment_id=e.id, step_id=step.id, attempts=0, done=False)
        db.add(p)
    if score is not None:
        p.score = max(p.score or 0, score)
    if done and not p.done:
        p.done, p.completed_at = True, moment
    await db.flush()
    return p


async def check_ready(db: AsyncSession, e: InternshipEnrollment, program: InternshipProgram, intern_name: str, moment: datetime):
    """Hamma majburiy bosqich bajarilgan bo'lsa: holat "tayyor", murabbiy va HR ga xabar."""
    if e.status != "active":
        return []
    steps = await steps_of(db, program.id)
    s = summarize(steps, await progress_of(db, e.id))
    if not s["required"] or s["done"] < s["required"]:
        return []
    e.status, e.ready_at, e.final_score = "ready", moment, s["avg_score"]
    targets = {u for u in [e.mentor_id, *await users_with_permission(db, "internship.manage")] if u}
    notes = await notify(db, list(targets), "internship.ready", link=f"/internship/enrollments/{e.id}", params={"intern": intern_name, "score": f"{s['avg_score']:g}%" if s["avg_score"] is not None else "—"})
    if e.phase == "preboarding":  # test o'tdi: xodimga filial paketi, mudir/koordinator/trenerga «xodim keladi»
        from app.services import onboarding  # noqa: PLC0415

        notes += await onboarding.send_package(db, e)
    return notes


def step_out(s: InternshipStep, *, reveal: bool) -> dict[str, Any]:
    return {
        "id": s.id, "program_id": s.program_id, "position": s.position, "kind": s.kind, "title": s.title, "description": s.description, "url": s.url, "required": s.required,
        "pass_score": s.pass_score, "max_attempts": s.max_attempts, "file": {"name": s.file_name, "mime": s.file_mime, "size": s.file_size} if s.file_key else None,
        "questions": s.questions if reveal else public_questions(s), "question_count": len(s.questions or []),
    }  # fmt: skip
