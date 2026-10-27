from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.employees import get_employee
from app.db import get_session
from app.deps import AuthContext, error, require
from app.models.employees import EmployeeDocument
from app.services.audit import audit
from app.services.employees import DOC_KINDS
from app.services.uploads import MAX_DOC_BYTES, MAX_PHOTO_BYTES, read_upload, storage_key

router = APIRouter(prefix="/v1/employees", tags=["employee-files"])


def _storage(request: Request):
    return request.app.state.storage


def _doc_out(d: EmployeeDocument) -> dict:
    today = date.today()
    return {
        "id": d.id,
        "employee_id": d.employee_id,
        "kind": d.kind,
        "title": d.title,
        "filename": d.filename,
        "mime": d.mime,
        "size": d.size,
        "issued_at": d.issued_at,
        "expires_at": d.expires_at,
        "expired": d.expires_at is not None and d.expires_at < today,
        "expires_soon": d.expires_at is not None and 0 <= (d.expires_at - today).days <= 30,
        "note": d.note,
        "created_at": d.created_at,
    }


def _stream_response(request: Request, key: str, mime: str, filename: str | None, inline: bool):
    disposition = "inline" if inline else "attachment"
    headers = {
        "Cache-Control": "private, max-age=300",
        # Tur magic bytes bilan tekshirilgan (services/uploads); brauzer o'zi taxmin qilmasin
        "X-Content-Type-Options": "nosniff",
    }
    if filename:
        headers["Content-Disposition"] = f"{disposition}; filename*=UTF-8''{quote(filename)}"
    return StreamingResponse(_storage(request).stream(key), media_type=mime, headers=headers)


# --- Rasm -----------------------------------------------------------------------------


@router.put("/{employee_id}/photo", status_code=204)
async def upload_photo(
    employee_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.update")),
):
    emp = await get_employee(db, employee_id)
    up = await read_upload(file, MAX_PHOTO_BYTES, photo=True)
    key = storage_key(f"employees/{emp.id}/photo", "photo")
    await _storage(request).put(key, up.data, up.mime)
    old = emp.photo_key
    emp.photo_key, emp.photo_mime = key, up.mime
    await audit(db, request, "employee.photo_update", actor=auth.user, entity="employee", entity_id=emp.id)
    await db.commit()
    if old:
        await _storage(request).delete(old)


@router.get("/{employee_id}/photo")
async def get_photo(
    employee_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("employees.read")),
):
    emp = await get_employee(db, employee_id)
    if not emp.photo_key:
        raise error(404, "not_found")
    return _stream_response(request, emp.photo_key, emp.photo_mime or "image/jpeg", None, inline=True)


@router.delete("/{employee_id}/photo", status_code=204)
async def delete_photo(
    employee_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.update")),
):
    emp = await get_employee(db, employee_id)
    if emp.photo_key:
        old = emp.photo_key
        emp.photo_key = emp.photo_mime = None
        await audit(db, request, "employee.photo_delete", actor=auth.user, entity="employee", entity_id=emp.id)
        await db.commit()
        await _storage(request).delete(old)


# --- Hujjatlar ------------------------------------------------------------------------


@router.get("/{employee_id}/documents")
async def list_documents(
    employee_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("employees.documents")),
):
    await get_employee(db, employee_id)
    rows = (
        await db.scalars(
            select(EmployeeDocument)
            .where(EmployeeDocument.employee_id == employee_id)
            .order_by(EmployeeDocument.created_at.desc())
        )
    ).all()
    return [_doc_out(d) for d in rows]


@router.post("/{employee_id}/documents", status_code=201)
async def upload_document(
    employee_id: int,
    request: Request,
    file: UploadFile = File(...),
    kind: str = Form(...),
    title: str = Form(..., min_length=1, max_length=160),
    issued_at: date | None = Form(default=None),
    expires_at: date | None = Form(default=None),
    note: str | None = Form(default=None, max_length=2000),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.documents")),
):
    emp = await get_employee(db, employee_id)
    if kind not in DOC_KINDS:
        raise error(400, "unknown_doc_kind")
    if issued_at and expires_at and expires_at < issued_at:
        raise error(400, "expiry_before_issue")
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"employees/{emp.id}/docs", up.filename)
    await _storage(request).put(key, up.data, up.mime)
    doc = EmployeeDocument(
        employee_id=emp.id, kind=kind, title=title.strip(), file_key=key, filename=up.filename,
        mime=up.mime, size=len(up.data), issued_at=issued_at, expires_at=expires_at,
        note=note or None, uploaded_by=auth.user.id,
    )  # fmt: skip
    db.add(doc)
    await db.flush()
    await audit(db, request, "employee.document_add", actor=auth.user, entity="employee",
                entity_id=emp.id, data={"doc_id": doc.id, "kind": kind, "title": doc.title})  # fmt: skip
    await db.commit()
    return _doc_out(doc)


async def _doc(db: AsyncSession, employee_id: int, doc_id: int) -> EmployeeDocument:
    d = await db.get(EmployeeDocument, doc_id)
    if not d or d.employee_id != employee_id:
        raise error(404, "not_found")
    return d


@router.get("/{employee_id}/documents/{doc_id}")
async def get_document(
    employee_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_session),
    _: AuthContext = Depends(require("employees.documents")),
):
    return _doc_out(await _doc(db, employee_id, doc_id))


@router.get("/{employee_id}/documents/{doc_id}/download")
async def download_document(
    employee_id: int,
    doc_id: int,
    request: Request,
    inline: bool = False,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.documents")),
):
    d = await _doc(db, employee_id, doc_id)
    await audit(db, request, "employee.document_download", actor=auth.user, entity="employee",
                entity_id=employee_id, data={"doc_id": d.id})  # fmt: skip
    await db.commit()
    return _stream_response(request, d.file_key, d.mime, d.filename, inline=inline and d.mime != "application/zip")


class DocumentPatch(BaseModel):
    kind: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    issued_at: date | None = None
    expires_at: date | None = None
    note: str | None = Field(default=None, max_length=2000)


@router.patch("/{employee_id}/documents/{doc_id}")
async def update_document(
    employee_id: int,
    doc_id: int,
    body: DocumentPatch,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.documents")),
):
    d = await _doc(db, employee_id, doc_id)
    sent = body.model_fields_set
    if "kind" in sent:
        if body.kind not in DOC_KINDS:
            raise error(400, "unknown_doc_kind")
        d.kind = body.kind
    if "title" in sent and body.title:
        d.title = body.title.strip()
    for f in ("issued_at", "expires_at", "note"):
        if f in sent:
            setattr(d, f, getattr(body, f) or None)
    if d.issued_at and d.expires_at and d.expires_at < d.issued_at:
        raise error(400, "expiry_before_issue")
    await audit(db, request, "employee.document_update", actor=auth.user, entity="employee",
                entity_id=employee_id, data={"doc_id": d.id})  # fmt: skip
    await db.commit()
    return _doc_out(d)


@router.delete("/{employee_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    employee_id: int,
    doc_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(require("employees.documents")),
):
    d = await _doc(db, employee_id, doc_id)
    key = d.file_key
    await audit(db, request, "employee.document_delete", actor=auth.user, entity="employee",
                entity_id=employee_id, data={"doc_id": d.id, "title": d.title})  # fmt: skip
    await db.delete(d)
    await db.commit()
    await _storage(request).delete(key)

