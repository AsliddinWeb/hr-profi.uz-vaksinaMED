"""Ommaviy amallar, dublikat guruhlari va birlashtirish. Statik yo'llar `/{employee_id}` dan OLDIN ro'yxatdan o'tadi."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.employees import (
    DismissIn,
    ReinstateIn,
    TransferIn,
    dismiss_one,
    get_employee,
    one_out,
    reinstate_one,
    transfer_one,
)
from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.employees import Employee, EmployeeDocument, EmployeeEvent
from app.services import employees as svc
from app.services.audit import audit
from app.services.employee_accounts import create_account
from app.services.notifications import deliver

router = APIRouter(prefix="/v1/employees", tags=["employee-bulk"])

ACTION_PERMISSION = {
    "transfer": "employees.transfer",
    "dismiss": "employees.dismiss",
    "reinstate": "employees.dismiss",
    "create_accounts": "employees.accounts",
    "assign_group": "employees.update",
}


class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    action: str = Field(pattern="^(transfer|dismiss|reinstate|create_accounts|assign_group)$")
    params: dict[str, Any] = {}


@router.post("/bulk")
async def bulk(
    body: BulkIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.read")),
):
    """Tanlangan xodimlarga bir xil amal. Har xodim alohida (savepoint): biri xato qilsa, qolganlari bajariladi."""
    perm = ACTION_PERMISSION[body.action]
    if not auth.can(perm):
        raise error(403, "forbidden", permission=perm)

    try:
        transfer = TransferIn(**body.params) if body.action == "transfer" else None
        dismiss = DismissIn(**body.params) if body.action == "dismiss" else None
        reinstate = ReinstateIn(**body.params) if body.action == "reinstate" else None
    except ValueError as exc:
        raise error(422, "validation") from exc
    role_key = body.params.get("role_key") if body.action == "create_accounts" else None
    if body.action == "create_accounts" and not role_key:
        raise error(400, "role_required")
    group_id = body.params.get("work_group_id") if body.action == "assign_group" else None
    if body.action == "assign_group":
        await svc.validate_work_group(db, group_id)

    results: list[dict[str, Any]] = []
    all_notes: list = []
    for emp_id in dict.fromkeys(body.ids):
        emp = await db.get(Employee, emp_id)
        item: dict[str, Any] = {"id": emp_id, "name": emp.full_name if emp else None, "ok": False}
        if emp is None:
            item["error"] = "not_found"
            results.append(item)
            continue
        try:
            async with db.begin_nested():
                if transfer:
                    _, notes = await transfer_one(db, emp, transfer, auth)
                    all_notes += notes
                elif dismiss:
                    await dismiss_one(db, emp, dismiss, auth)
                elif reinstate:
                    await reinstate_one(db, emp, reinstate, auth)
                elif body.action == "assign_group":
                    emp.work_group_id = group_id
                else:
                    user, password = await create_account(db, emp, role_key, auth)
                    item.update(login=user.login, temp_password=password)
            item["ok"] = True
        except Exception as exc:  # noqa: BLE001
            detail = getattr(exc, "detail", None)
            item["error"] = detail.get("code") if isinstance(detail, dict) else "failed"
            db.expire(emp)
        results.append(item)

    ok = sum(1 for r in results if r["ok"])
    await audit(db, request, f"employee.bulk_{body.action}", actor=auth.user, entity="employee",
                data={"requested": len(results), "succeeded": ok})  # fmt: skip
    await db.commit()
    await deliver(request.app, all_notes)
    return {"action": body.action, "total": len(results), "succeeded": ok, "results": results}


# --- Dublikatlar ----------------------------------------------------------------------


@router.get("/duplicates")
async def duplicates(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.merge")),
):
    groups = await svc.duplicate_groups(db)
    all_members = [e for g in groups for e in g]
    refs = await svc.load_refs(db, all_members)
    doc_counts = dict(
        (
            await db.execute(
                select(EmployeeDocument.employee_id, func.count())
                .where(EmployeeDocument.employee_id.in_([e.id for e in all_members]))
                .group_by(EmployeeDocument.employee_id)
            )
        ).all()
    ) if all_members else {}

    out = []
    for g in groups:
        reasons: set[str] = set()
        for key, getter in (
            ("pinfl", lambda e: {e.pinfl} - {None}),
            ("passport", lambda e: {e.passport_no} - {None}),
            ("phone", lambda e: {e.phone, e.phone2} - {None}),
            ("name_birth", lambda e: {(svc.name_key(e.full_name), e.birth_date)} if e.birth_date else set()),
        ):
            seen: set = set()
            for e in g:
                vals = getter(e)
                if seen & vals:
                    reasons.add(key)
                seen |= vals
        out.append(
            {
                "reasons": sorted(reasons),
                "members": [
                    {**svc.employee_out(e, refs, auth), "documents": doc_counts.get(e.id, 0)} for e in g
                ],
            }
        )
    return out


class MergeIn(BaseModel):
    primary_id: int
    secondary_ids: list[int] = Field(min_length=1, max_length=20)


MERGE_FIELDS = (
    "middle_name", "birth_date", "gender", "phone", "phone2", "email", "address",
    "department_id", "position_id", "branch_id", "hire_date",
)  # fmt: skip


@router.post("/merge")
async def merge(
    body: MergeIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.merge")),
):
    """Dublikatlarni asosiy xodimga birlashtiradi: hujjat/tarix ko'chadi, bo'sh maydonlar to'ldiriladi, dublikat o'chadi."""
    if body.primary_id in body.secondary_ids:
        raise error(400, "merge_same")
    primary = await get_employee(db, body.primary_id)
    merged: list[dict[str, Any]] = []

    for sid in dict.fromkeys(body.secondary_ids):
        sec = await get_employee(db, sid)
        merged.append({"id": sec.id, "employee_no": sec.employee_no, "name": sec.full_name})

        # Unikal maydonlarni avval bo'shatamiz (primaryga ko'chirish uchun)
        sec_pinfl, sec_passport, sec_user, sec_photo = sec.pinfl, sec.passport_no, sec.user_id, (sec.photo_key, sec.photo_mime)
        sec.pinfl = sec.passport_no = sec.user_id = None
        await db.flush()

        for f in MERGE_FIELDS:
            if getattr(primary, f) in (None, "") and getattr(sec, f) not in (None, ""):
                setattr(primary, f, getattr(sec, f))
        if primary.pinfl is None:
            primary.pinfl = sec_pinfl
        if primary.passport_no is None:
            primary.passport_no = sec_passport
        if primary.user_id is None and sec_user is not None:
            primary.user_id = sec_user
        if primary.photo_key is None and sec_photo[0]:
            primary.photo_key, primary.photo_mime = sec_photo
            sec.photo_key = sec.photo_mime = None  # fayl primaryniki, secondary o'chganda tegmasin

        await db.execute(update(EmployeeDocument).where(EmployeeDocument.employee_id == sec.id).values(employee_id=primary.id))
        await db.execute(update(EmployeeEvent).where(EmployeeEvent.employee_id == sec.id).values(employee_id=primary.id))
        await db.flush()
        await db.delete(sec)
        await db.flush()

    svc.add_event(db, primary.id, "merged", date.today(), data={"merged": merged}, actor_id=auth.user.id)
    await audit(db, request, "employee.merge", actor=auth.user, entity="employee", entity_id=primary.id,
                data={"merged": merged})  # fmt: skip
    await db.commit()
    return await one_out(db, primary, auth)
