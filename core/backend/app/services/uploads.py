"""Yuklangan fayllarni tekshirish: hajm, kengaytma va HAQIQIY tur (magic bytes), mijoz MIME ga ishonmaymiz."""

import re
import uuid
from dataclasses import dataclass

from fastapi import UploadFile

from app.deps import error

MAX_DOC_BYTES = 15 * 1024 * 1024
MAX_PHOTO_BYTES = 5 * 1024 * 1024

# magic -> (mime, ruxsat etilgan kengaytmalar)
_SIGNATURES: list[tuple[bytes, str, set[str]]] = [
    (b"%PDF-", "application/pdf", {"pdf"}),
    (b"\xff\xd8\xff", "image/jpeg", {"jpg", "jpeg"}),
    (b"\x89PNG\r\n\x1a\n", "image/png", {"png"}),
    (b"PK\x03\x04", "application/zip", {"docx", "xlsx"}),  # Office ochiq formatlari
]
_OFFICE_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
PHOTO_MIMES = {"image/jpeg", "image/png", "image/webp"}


@dataclass
class Upload:
    data: bytes
    filename: str
    mime: str


def safe_filename(name: str) -> str:
    base = (name or "file").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[^\w.\- ()]", "_", base, flags=re.UNICODE).strip(" .")
    return (base or "file")[:150]


def sniff(data: bytes, ext: str) -> str | None:
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp" if ext == "webp" else None
    for magic, mime, exts in _SIGNATURES:
        if data.startswith(magic):
            if ext not in exts:
                return None
            return _OFFICE_MIME.get(ext, mime)
    return None


async def read_upload(file: UploadFile, max_bytes: int, photo: bool = False) -> Upload:
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise error(413, "file_too_large", max_mb=max_bytes // (1024 * 1024))
    if not data:
        raise error(400, "file_empty")
    filename = safe_filename(file.filename or "file")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime = sniff(data, ext)
    if mime is None or (photo and mime not in PHOTO_MIMES):
        raise error(415, "file_type_not_allowed")
    return Upload(data, filename, mime)


def storage_key(prefix: str, filename: str) -> str:
    return f"{prefix}/{uuid.uuid4().hex}-{filename}"
