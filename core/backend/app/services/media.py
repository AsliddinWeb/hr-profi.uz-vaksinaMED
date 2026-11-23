"""Slayd va video yuklash: rasm, PDF va PPTX rasm-slaydlarga aylanadi, video fayl saqlanadi."""

import asyncio
import os
import tempfile
import uuid
from dataclasses import dataclass

import pymupdf
from fastapi import UploadFile

from app.deps import error
from app.services.uploads import read_upload, safe_filename

MAX_SLIDE_FILE_BYTES = 50 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_PAGES = 80
CONVERT_TIMEOUT = 180
IMAGE_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
VIDEO_MIME = {"mp4": "video/mp4", "webm": "video/webm"}
_convert_lock = asyncio.Semaphore(1)


@dataclass
class Stored:
    key: str
    data: bytes
    mime: str

    @property
    def name(self) -> str:
        return self.key.rsplit("/", 1)[-1]


def _stored(data: bytes, ext: str, mime: str) -> Stored:
    return Stored(f"hrdocs/media/{uuid.uuid4().hex}.{ext}", data, mime)


def _is_pptx(data: bytes, ext: str) -> bool:
    return ext == "pptx" and data.startswith(b"PK\x03\x04")


def _render_pdf(data: bytes) -> list[Stored]:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise error(422, "file_unreadable") from exc
    with doc:
        if doc.page_count == 0:
            raise error(422, "file_unreadable")
        if doc.page_count > MAX_PAGES:
            raise error(413, "too_many_pages", max=MAX_PAGES)
        out = []
        for page in doc:
            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(1920 / page.rect.width, 1920 / page.rect.width), alpha=False
            )
            out.append(_stored(pix.tobytes("jpg", jpg_quality=85), "jpg", "image/jpeg"))
        return out


async def _pptx_to_pdf(data: bytes) -> bytes:
    async with _convert_lock:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "slides.pptx")
            with open(src, "wb") as f:
                f.write(data)
            proc = await asyncio.create_subprocess_exec(
                "soffice",
                "--headless",
                "--norestore",
                f"-env:UserInstallation=file://{tmp}/profile",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                src,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(proc.wait(), CONVERT_TIMEOUT)
            except TimeoutError as exc:
                proc.kill()
                raise error(504, "convert_timeout") from exc
            out = os.path.join(tmp, "slides.pdf")
            if not os.path.exists(out):
                raise error(422, "file_unreadable")
            with open(out, "rb") as f:
                return f.read()


async def slides_from_upload(file: UploadFile) -> list[Stored]:
    head = await file.read(4)
    await file.seek(0)
    if head.startswith(b"PK"):
        data = await file.read(MAX_SLIDE_FILE_BYTES + 1)
        ext = safe_filename(file.filename or "").rsplit(".", 1)[-1].lower()
        if len(data) > MAX_SLIDE_FILE_BYTES:
            raise error(413, "file_too_large", max_mb=MAX_SLIDE_FILE_BYTES // (1024 * 1024))
        if not _is_pptx(data, ext):
            raise error(415, "file_type_not_allowed")
        pdf = await _pptx_to_pdf(data)
        return await asyncio.to_thread(_render_pdf, pdf)
    up = await read_upload(file, MAX_SLIDE_FILE_BYTES)
    if up.mime == "application/pdf":
        return await asyncio.to_thread(_render_pdf, up.data)
    if up.mime in IMAGE_EXT:
        return [_stored(up.data, IMAGE_EXT[up.mime], up.mime)]
    raise error(415, "file_type_not_allowed")


async def video_from_upload(file: UploadFile) -> Stored:
    data = await file.read(MAX_VIDEO_BYTES + 1)
    if len(data) > MAX_VIDEO_BYTES:
        raise error(413, "file_too_large", max_mb=MAX_VIDEO_BYTES // (1024 * 1024))
    if data[4:8] == b"ftyp":
        return _stored(data, "mp4", VIDEO_MIME["mp4"])
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return _stored(data, "webm", VIDEO_MIME["webm"])
    raise error(415, "file_type_not_allowed")
