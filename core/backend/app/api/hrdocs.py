"""HR hujjatlar kutubxonasi: kartochkalar, versiyalar, fayl, «tanishdim» tasdig'i."""

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import AuthContext, error, get_auth
from app.models.auth import Role
from app.models.hrdocs import HrDocument, HrDocumentAck, HrDocumentVersion
from app.services import hrdocs as svc
from app.services.audit import audit
from app.services.notifications import deliver, notify
from app.services.uploads import MAX_DOC_BYTES, read_upload, storage_key
from app.timeutil import now

router = APIRouter(prefix="/v1/hrdocs", tags=["hrdocs"])


class DocIn(BaseModel):
    category: str = Field(pattern=f"^({'|'.join(svc.CATEGORIES)})$")
    title: str = Field(min_length=2, max_length=200)
    summary: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=200_000)
    requires_ack: bool = False
    roles: list[str] = Field(default_factory=list, max_length=30)
    sort_order: int = Field(default=0, ge=0, le=100000)


class PublishIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


def _need_manage(auth: AuthContext) -> None:
    if not svc.can_manage(auth):
        raise error(403, "forbidden")


async def _doc(db: AsyncSession, did: int, auth: AuthContext, *, lock: bool = False) -> HrDocument:
    stmt = select(HrDocument).where(HrDocument.id == did)
    doc = await db.scalar(stmt.with_for_update() if lock else stmt)
    if not doc or not svc.visible_to(doc, auth):
        raise error(404, "not_found")
    return doc


async def _valid_roles(db: AsyncSession, roles: list[str]) -> list[str]:
    known = set((await db.scalars(select(Role.key))).all())
    if any(r not in known for r in roles):
        raise error(400, "unknown_role")
    return list(dict.fromkeys(roles))


@router.get("/categories")
async def categories(auth: AuthContext = Depends(get_auth)) -> list[str]:
    return list(svc.CATEGORIES)


@router.get("/roles")
async def role_options(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Hujjat ko'rinishini rol bo'yicha cheklash uchun rollar (`roles.read` shart emas)."""
    _need_manage(auth)
    return [{"key": r.key, "name_uz": r.name_uz, "name_ru": r.name_ru} for r in (await db.scalars(select(Role).order_by(Role.id))).all()]


@router.get("")
async def list_docs(category: str | None = None, q: str | None = None, status: str | None = Query(default=None, pattern="^(draft|published)$"), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    if not (svc.has(auth, "hrdocs.read") or svc.can_manage(auth)):
        raise error(403, "forbidden")
    stmt = select(HrDocument).order_by(HrDocument.category, HrDocument.sort_order, HrDocument.id)
    if category:
        stmt = stmt.where(HrDocument.category == category)
    if q and q.strip():
        stmt = stmt.where(HrDocument.title.ilike(f"%{q.strip()}%"))
    if status:
        stmt = stmt.where(HrDocument.status == status)
    docs = [d for d in (await db.scalars(stmt)).all() if svc.visible_to(d, auth)]
    acks = {a.document_id: a for a in (await db.scalars(select(HrDocumentAck).where(HrDocumentAck.user_id == auth.user.id))).all()}
    counts = await svc.ack_counts(db, [d.id for d in docs]) if svc.can_manage(auth) else {}
    items = []
    for d in docs:
        o = svc.out(d, acks.get(d.id))
        if svc.can_manage(auth):
            o["ack_count"] = counts.get(d.id, 0)
        items.append(o)
    return {"items": items, "pending_ack": sum(1 for i in items if i["needs_ack"])}


@router.get("/pending/count")
async def pending_count(db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)) -> dict[str, int]:
    """Menga «tanishib chiqing» deb qolgan hujjatlar soni (menyu belgisi uchun)."""
    acks = {a.document_id: a for a in (await db.scalars(select(HrDocumentAck).where(HrDocumentAck.user_id == auth.user.id))).all()}
    docs = (await db.scalars(select(HrDocument).where(HrDocument.status == "published", HrDocument.requires_ack.is_(True)))).all()
    return {"count": sum(1 for d in docs if svc.visible_to(d, auth) and svc.needs_ack(d, acks.get(d.id)))}


@router.post("", status_code=201)
async def create_doc(body: DocIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = HrDocument(category=body.category, title=body.title.strip(), summary=body.summary, body=body.body, requires_ack=body.requires_ack, roles=await _valid_roles(db, body.roles), sort_order=body.sort_order, status="draft", version=0, updated_by=auth.user.id)
    db.add(doc)
    await db.flush()
    await audit(db, request, "hrdoc.create", actor=auth.user, entity="hr_document", entity_id=doc.id)
    await db.commit()
    return svc.out(doc, with_body=True)


@router.get("/{did}")
async def get_doc(did: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    doc = await _doc(db, did, auth)
    ack = await db.scalar(select(HrDocumentAck).where(HrDocumentAck.document_id == did, HrDocumentAck.user_id == auth.user.id))
    return svc.out(doc, ack, with_body=True)


@router.put("/{did}")
async def update_doc(did: int, body: DocIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await _doc(db, did, auth, lock=True)
    doc.category, doc.title, doc.summary, doc.body = body.category, body.title.strip(), body.summary, body.body
    doc.requires_ack, doc.roles, doc.sort_order, doc.updated_by = body.requires_ack, await _valid_roles(db, body.roles), body.sort_order, auth.user.id
    await audit(db, request, "hrdoc.update", actor=auth.user, entity="hr_document", entity_id=doc.id)
    await db.commit()
    return svc.out(doc, with_body=True)


@router.post("/{did}/publish")
async def publish(did: int, body: PublishIn, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    """Yangi versiyani e'lon qiladi: avvalgi tasdiqlar eskiradi (qayta tanishish kerak), ko'rinadigan foydalanuvchilarga xabar boradi."""
    _need_manage(auth)
    doc = await _doc(db, did, auth, lock=True)
    if not (doc.body and doc.body.strip()) and not doc.file_key:
        raise error(400, "document_empty")
    moment = now()
    doc.version += 1
    doc.status, doc.published_at, doc.updated_by = "published", moment, auth.user.id
    db.add(HrDocumentVersion(document_id=doc.id, version=doc.version, title=doc.title, body=doc.body, file_key=doc.file_key, file_name=doc.file_name, note=(body.note or "").strip() or None, changed_by=auth.user.id))
    notes: list = []
    if doc.requires_ack:
        ids = [u.id for u in await svc.audience(db, doc) if u.id != auth.user.id]
        notes = await notify(db, ids, "hrdoc.published", params={"title": doc.title, "version": doc.version}, link=f"/hr/library/{doc.id}")
    await audit(db, request, "hrdoc.publish", actor=auth.user, entity="hr_document", entity_id=doc.id, data={"version": doc.version})
    await db.commit()
    await deliver(request.app, notes)
    return svc.out(doc, with_body=True)


@router.post("/{did}/unpublish")
async def unpublish(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await _doc(db, did, auth, lock=True)
    doc.status = "draft"
    await audit(db, request, "hrdoc.unpublish", actor=auth.user, entity="hr_document", entity_id=doc.id)
    await db.commit()
    return svc.out(doc, with_body=True)


@router.delete("/{did}", status_code=204)
async def delete_doc(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await _doc(db, did, auth, lock=True)
    if doc.version > 0:
        raise error(409, "already_published")  # e'lon qilingan hujjat arxivga o'tkaziladi (qoralamaga qaytariladi), o'chirilmaydi
    key = doc.file_key
    await audit(db, request, "hrdoc.delete", actor=auth.user, entity="hr_document", entity_id=doc.id)
    await db.delete(doc)
    await db.commit()
    if key:
        await request.app.state.storage.delete(key)


@router.put("/{did}/file")
async def upload_file(did: int, request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await _doc(db, did, auth, lock=True)
    up = await read_upload(file, MAX_DOC_BYTES)
    key = storage_key(f"hrdocs/{doc.id}", up.filename)
    await request.app.state.storage.put(key, up.data, up.mime)
    old = doc.file_key
    doc.file_key, doc.file_name, doc.file_mime, doc.file_size, doc.updated_by = key, up.filename, up.mime, len(up.data), auth.user.id
    kept = bool(old and await db.scalar(select(HrDocumentVersion.id).where(HrDocumentVersion.file_key == old).limit(1)))
    await audit(db, request, "hrdoc.file", actor=auth.user, entity="hr_document", entity_id=doc.id)
    await db.commit()
    if old and not kept:
        await request.app.state.storage.delete(old)
    return svc.out(doc, with_body=True)


@router.delete("/{did}/file", status_code=204)
async def delete_file(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    doc = await _doc(db, did, auth, lock=True)
    old = doc.file_key
    doc.file_key = doc.file_name = doc.file_mime = doc.file_size = None
    kept = bool(old and await db.scalar(select(HrDocumentVersion.id).where(HrDocumentVersion.file_key == old).limit(1)))
    await db.commit()
    if old and not kept:
        await request.app.state.storage.delete(old)


@router.get("/{did}/file")
async def download_file(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    doc = await _doc(db, did, auth)
    if not doc.file_key:
        raise error(404, "not_found")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.file_name or 'document')}", "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"}
    return StreamingResponse(request.app.state.storage.stream(doc.file_key), media_type=doc.file_mime or "application/octet-stream", headers=headers)


@router.post("/{did}/ack")
async def acknowledge(did: int, request: Request, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    doc = await _doc(db, did, auth, lock=True)
    if doc.status != "published" or doc.version < 1:
        raise error(409, "not_published")
    ack = await db.scalar(select(HrDocumentAck).where(HrDocumentAck.document_id == did, HrDocumentAck.user_id == auth.user.id))
    if ack is None:
        ack = HrDocumentAck(document_id=did, user_id=auth.user.id, version=doc.version, acknowledged_at=now())
        db.add(ack)
    elif ack.version < doc.version:
        ack.version, ack.acknowledged_at = doc.version, now()
    await audit(db, request, "hrdoc.ack", actor=auth.user, entity="hr_document", entity_id=doc.id, data={"version": doc.version})
    await db.commit()
    return svc.out(doc, ack, with_body=True)


@router.get("/{did}/acks")
async def acks(did: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    """Kim tanishgan va kim hali tanishmagan (joriy versiya bo'yicha)."""
    _need_manage(auth)
    doc = await _doc(db, did, auth)
    got = {a.user_id: a for a in (await db.scalars(select(HrDocumentAck).where(HrDocumentAck.document_id == did))).all()}
    people = await svc.audience(db, doc)
    done, pending = [], []
    for u in people:
        a = got.get(u.id)
        row = {"user": {"id": u.id, "name": u.full_name}, "at": a.acknowledged_at if a else None, "version": a.version if a else None}
        (done if a and a.version >= doc.version else pending).append(row)
    return {"version": doc.version, "total": len(people), "done": done, "pending": pending}


@router.get("/{did}/versions")
async def versions(did: int, db: AsyncSession = Depends(get_session), auth: AuthContext = Depends(get_auth)):
    _need_manage(auth)
    await _doc(db, did, auth)
    rows = (await db.scalars(select(HrDocumentVersion).where(HrDocumentVersion.document_id == did).order_by(HrDocumentVersion.version.desc()))).all()
    return [{"version": v.version, "title": v.title, "note": v.note, "file_name": v.file_name, "created_at": v.created_at, "has_body": bool(v.body)} for v in rows]
