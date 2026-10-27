"""Global qidiruv: har modul o'z ruxsatlariga ko'ra, bitta so'rovda guruhlangan natija (har guruhdan 6 tagacha)."""

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import AuthContext
from app.models.calls import Call, CallParticipant
from app.models.employees import Employee
from app.models.helpdesk import Ticket
from app.models.logistics import Vehicle
from app.models.needs import NeedRequest
from app.models.org import Branch
from app.models.reception import Visit
from app.models.recruit import Candidate, Vacancy
from app.models.tasks import Task
from app.rbac import matches

LIMIT = 6


def _has(auth: AuthContext, *perms: str) -> bool:
    return any(matches(auth.permissions, p) for p in perms)


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"


def _item(id_: int, title: str | None, sub: str | None, link: str, **extra: Any) -> dict[str, Any]:
    return {"id": id_, "title": title or "—", "subtitle": sub, "link": link, **extra}


async def search(db: AsyncSession, auth: AuthContext, q: str) -> dict[str, Any]:
    q = q.strip()
    like = _like(q)
    uid = auth.user.id
    digits = "".join(ch for ch in q if ch.isdigit())
    groups: list[dict[str, Any]] = []

    def add(kind: str, items: list[dict[str, Any]]) -> None:
        if items:
            groups.append({"type": kind, "items": items})

    if _has(auth, "employees.read"):
        cond = [Employee.full_name.ilike(like, escape="\\")]
        if len(digits) >= 3:
            cond.append(Employee.phone.ilike(f"%{digits}%"))
        if digits and len(digits) <= 6:
            cond.append(Employee.employee_no == int(digits))
        rows = (await db.scalars(select(Employee).where(or_(*cond)).order_by(Employee.status, Employee.full_name).limit(LIMIT))).all()
        add("employees", [_item(e.id, e.full_name, f"№{e.employee_no}" + (f" · {e.phone}" if e.phone else "") + (" · ✕" if e.status != "active" else ""), f"/employees/{e.id}") for e in rows])
    if _has(auth, "branches.read"):
        rows = (await db.scalars(select(Branch).where(or_(Branch.name.ilike(like, escape="\\"), Branch.address.ilike(like, escape="\\"))).order_by(Branch.name).limit(LIMIT))).all()
        add("branches", [_item(b.id, b.name, b.address, f"/branches/{b.id}/edit") for b in rows])
    if _has(auth, "recruit.read", "recruit.manage"):
        cond = [Candidate.full_name.ilike(like, escape="\\"), Candidate.email.ilike(like, escape="\\")]
        if len(digits) >= 3:
            cond.append(Candidate.phone.ilike(f"%{digits}%"))
        rows = (await db.scalars(select(Candidate).where(or_(*cond)).order_by(Candidate.full_name).limit(LIMIT))).all()
        add("candidates", [_item(c.id, c.full_name, c.phone or c.email, f"/recruit/candidates/{c.id}") for c in rows])
        rows = (await db.scalars(select(Vacancy).where(Vacancy.title.ilike(like, escape="\\")).order_by(Vacancy.id.desc()).limit(LIMIT))).all()
        add("vacancies", [_item(v.id, v.title, v.status, f"/recruit/vacancies/{v.id}") for v in rows])
    t_cond = [Task.title.ilike(like, escape="\\")]
    if not _has(auth, "tasks.read", "tasks.manage"):
        t_cond.append(or_(Task.creator_id == uid, Task.assignee_id == uid, Task.watchers.contains([uid])))
    if _has(auth, "tasks.own", "tasks.read", "tasks.manage"):
        rows = (await db.scalars(select(Task).where(t_cond[0], *t_cond[1:]).order_by(Task.id.desc()).limit(LIMIT))).all()
        add("tasks", [_item(t.id, t.title, t.status, f"/tasks/{t.id}") for t in rows])
    if _has(auth, "needs.own", "needs.work", "needs.dispatch", "needs.manage"):
        cond = [or_(NeedRequest.title.ilike(like, escape="\\"), NeedRequest.number.ilike(like, escape="\\"))]
        if not _has(auth, "needs.dispatch", "needs.manage"):
            cond.append(or_(NeedRequest.requester_id == uid, NeedRequest.assignee_id == uid))
        rows = (await db.scalars(select(NeedRequest).where(*cond).order_by(NeedRequest.id.desc()).limit(LIMIT))).all()
        add("needs", [_item(n.id, n.title, f"{n.number} · {n.status}", f"/needs/{n.id}") for n in rows])
    if _has(auth, "helpdesk.own", "helpdesk.work", "helpdesk.read", "helpdesk.manage"):
        cond = [or_(Ticket.title.ilike(like, escape="\\"), Ticket.number.ilike(like, escape="\\"))]
        if not _has(auth, "helpdesk.work", "helpdesk.read", "helpdesk.manage"):
            cond.append(or_(Ticket.requester_id == uid, Ticket.assignee_id == uid))
        rows = (await db.scalars(select(Ticket).where(*cond).order_by(Ticket.id.desc()).limit(LIMIT))).all()
        add("tickets", [_item(t.id, t.title, f"{t.number} · {t.status}", f"/helpdesk/{t.id}") for t in rows])
    if _has(auth, "reception.own", "reception.desk", "reception.read"):
        cond = [or_(Visit.visitor_name.ilike(like, escape="\\"), Visit.company.ilike(like, escape="\\"), Visit.vehicle_plate.ilike(like, escape="\\"))]
        if not _has(auth, "reception.desk", "reception.read"):
            cond.append(Visit.registered_by == uid)
        rows = (await db.scalars(select(Visit).where(*cond).order_by(Visit.id.desc()).limit(LIMIT))).all()
        add("visits", [_item(v.id, v.visitor_name, v.company or v.status, f"/reception/{v.id}") for v in rows])
    if _has(auth, "logistics.read"):
        rows = (await db.scalars(select(Vehicle).where(or_(Vehicle.plate.ilike(like, escape="\\"), Vehicle.name.ilike(like, escape="\\"))).order_by(Vehicle.plate).limit(LIMIT))).all()
        add("vehicles", [_item(v.id, v.plate, v.name, f"/logistics/vehicles/{v.id}") for v in rows])
    if _has(auth, "calls.own", "calls.read", "calls.manage"):
        cond = [Call.title.ilike(like, escape="\\")]
        if not _has(auth, "calls.read", "calls.manage"):
            cond.append(Call.id.in_(select(CallParticipant.call_id).where(CallParticipant.user_id == uid)))
        rows = (await db.scalars(select(Call).where(*cond).order_by(Call.id.desc()).limit(LIMIT))).all()
        add("calls", [_item(c.id, c.title, c.status, f"/calls/{c.id}") for c in rows])
    return {"q": q, "total": sum(len(g["items"]) for g in groups), "groups": groups}


__all__ = ["func"]
