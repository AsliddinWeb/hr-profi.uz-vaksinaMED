import asyncio
import json
import secrets
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.employees import Employee
from app.models.org import Branch, Department, Position
from app.services import employee_io as io
from app.services import employees as svc
from app.services.audit import audit
from app.services.org import descendants, load_departments

router = APIRouter(prefix="/v1/employees", tags=["employee-io"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 2000
TOKEN_TTL = 1800
_KEY = "empimport:"


def _attachment(data: bytes, filename: str) -> Response:
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/import/template")
async def import_template(_: AuthContext = Depends(require("employees.import"))):
    return _attachment(await asyncio.to_thread(io.template_bytes), "xodimlar-shablon.xlsx")


@router.get("/export")
async def export(
    request: Request,
    q: str | None = None,
    department_id: int | None = None,
    branch_id: int | None = None,
    status: str | None = Query(default=None, pattern="^(active|dismissed)$"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.export")),
):
    stmt = select(Employee)
    if q and q.strip():
        stmt = stmt.where(Employee.full_name.ilike(f"%{q.strip()}%"))
    if department_id:
        ids = {department_id} | descendants(await load_departments(db), department_id)
        stmt = stmt.where(Employee.department_id.in_(ids))
    if branch_id:
        stmt = stmt.where(Employee.branch_id == branch_id)
    if status:
        stmt = stmt.where(Employee.status == status)
    rows = (await db.scalars(stmt.order_by(Employee.full_name))).all()
    refs = await svc.load_refs(db, list(rows))
    sensitive = auth.can("employees.sensitive")
    data = [svc.employee_out(e, refs, auth) for e in rows]
    content = await asyncio.to_thread(io.export_bytes, data, sensitive)
    await audit(db, request, "employee.export", actor=auth.user, entity="employee",
                data={"count": len(rows), "sensitive": sensitive})  # fmt: skip
    await db.commit()
    return _attachment(content, f"xodimlar-{date.today():%Y-%m-%d}.xlsx")


async def _context(db: AsyncSession) -> io.ImportContext:
    depts: dict[str, list[int]] = {}
    for d in (await db.scalars(select(Department).where(Department.is_active.is_(True)))).all():
        depts.setdefault(d.name.lower(), []).append(d.id)
    positions = [
        (p.id, p.name.lower(), p.department_id)
        for p in (await db.scalars(select(Position).where(Position.is_active.is_(True)))).all()
    ]
    by_num: dict[int, int] = {}
    by_name: dict[str, list[int]] = {}
    for b in (await db.scalars(select(Branch).where(Branch.is_active.is_(True)))).all():
        if b.number is not None:
            by_num[b.number] = b.id
        by_name.setdefault(b.name.lower(), []).append(b.id)
    return io.ImportContext(depts, positions, by_num, by_name)


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()}


def _revive(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for k in ("birth_date", "hire_date"):
        if out.get(k):
            out[k] = date.fromisoformat(out[k])
    return out


async def _classify(db: AsyncSession, parsed: list[tuple[dict, list]]) -> list[dict[str, Any]]:
    """Har qator uchun holat: ok | error | duplicate (bazada yoki faylning o'zida)."""
    results: list[dict[str, Any]] = []
    seen: dict[tuple, int] = {}
    for i, (data, errors) in enumerate(parsed, start=1):
        item: dict[str, Any] = {"row": i, "data": data, "errors": errors, "status": "ok", "matches": []}
        if errors:
            item["status"] = "error"
            results.append(item)
            continue
        full = svc.build_full_name(data["last_name"], data["first_name"], data.get("middle_name"))
        keys = [("pinfl", data["pinfl"]), ("passport", data["passport_no"]), ("phone", data["phone"])]
        if data.get("birth_date"):
            keys.append(("nb", (svc.name_key(full), data["birth_date"])))
        in_file = next((seen[k] for k in keys if k[1] and k in seen), None)
        for k in keys:
            if k[1]:
                seen.setdefault(k, i)
        if in_file is not None:
            item["status"], item["duplicate_of_row"] = "duplicate", in_file
        else:
            matches = await svc.find_duplicates(
                db, pinfl=data["pinfl"], passport_no=data["passport_no"], phone=data["phone"],
                full_name=full, birth_date=data.get("birth_date"),
            )  # fmt: skip
            if matches:
                item["status"] = "duplicate"
                item["matches"] = [svc.match_out(m) for m in matches]
        results.append(item)
    return results


@router.post("/import/preview")
async def import_preview(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.import")),
):
    raw = await file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise error(413, "file_too_large", max_mb=MAX_IMPORT_BYTES // (1024 * 1024))
    try:
        rows, unknown = await asyncio.to_thread(io.read_rows, file.filename or "", raw)
    except ValueError as exc:
        raise error(415, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001  (buzuq fayl)
        raise error(400, "file_unreadable") from exc
    if not rows:
        raise error(400, "file_empty")
    if len(rows) > MAX_IMPORT_ROWS:
        raise error(400, "too_many_rows", max=MAX_IMPORT_ROWS)

    ctx = await _context(db)
    parsed = [io.parse_row(r, ctx) for r in rows]
    results = await _classify(db, parsed)

    token = secrets.token_urlsafe(18)
    payload = {
        "user_id": auth.user.id,
        "rows": [_jsonable(r["data"]) for r in results if r["status"] == "ok"],
    }
    await request.app.state.redis.set(f"{_KEY}{token}", json.dumps(payload), ex=TOKEN_TTL)

    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("ok", "error", "duplicate")}
    return {
        "token": token,
        "total": len(results),
        "valid": counts["ok"],
        "errors": counts["error"],
        "duplicates": counts["duplicate"],
        "unknown_columns": unknown,
        "issues": [
            {
                "row": r["row"],
                "status": r["status"],
                "errors": r["errors"],
                "name": svc.build_full_name(r["data"].get("last_name") or "", r["data"].get("first_name") or "", None),
                "matches": r["matches"],
                "duplicate_of_row": r.get("duplicate_of_row"),
            }
            for r in results
            if r["status"] != "ok"
        ][:300],
    }


class ApplyIn(BaseModel):
    token: str


@router.post("/import/apply")
async def import_apply(
    body: ApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.import")),
):
    """Tekshirilgan (xatosiz va dublikat bo'lmagan) qatorlarni yaratadi. Qolganlari o'tkazib yuboriladi."""
    redis = request.app.state.redis
    raw = await redis.get(f"{_KEY}{body.token}")
    if not raw:
        raise error(410, "import_expired")
    payload = json.loads(raw)
    if payload["user_id"] != auth.user.id:
        raise error(403, "forbidden")
    await redis.delete(f"{_KEY}{body.token}")  # bir martalik

    ctx_rows = [_revive(r) for r in payload["rows"]]
    # Tekshiruvdan keyin bazada o'zgarish bo'lgan bo'lishi mumkin: qayta tekshiramiz
    created = skipped = 0
    for data in ctx_rows:
        full = svc.build_full_name(data["last_name"], data["first_name"], data.get("middle_name"))
        if await svc.find_duplicates(
            db, pinfl=data["pinfl"], passport_no=data["passport_no"], phone=data["phone"],
            full_name=full, birth_date=data.get("birth_date"),
        ):  # fmt: skip
            skipped += 1
            continue
        try:
            await svc.validate_assignment(db, data["department_id"], data["position_id"], data["branch_id"])
        except Exception:  # noqa: BLE001
            skipped += 1
            continue
        hire = data.get("hire_date") or date.today()
        emp = Employee(
            last_name=data["last_name"], first_name=data["first_name"], middle_name=data.get("middle_name"),
            full_name=full, birth_date=data.get("birth_date"), gender=data.get("gender"),
            phone=data["phone"], email=data["email"], address=data["address"],
            passport_no=data["passport_no"], pinfl=data["pinfl"], department_id=data["department_id"],
            position_id=data["position_id"], branch_id=data["branch_id"], status="active", hire_date=hire,
        )  # fmt: skip
        db.add(emp)
        await db.flush()
        svc.add_event(db, emp.id, "hired", hire, data={"source": "import"}, actor_id=auth.user.id)
        created += 1

    await audit(db, request, "employee.import", actor=auth.user, entity="employee",
                data={"created": created, "skipped": skipped})  # fmt: skip
    await db.commit()
    return {"created": created, "skipped": skipped}

