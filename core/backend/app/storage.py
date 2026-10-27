"""Fayl saqlash (MinIO / S3-mos). Fayllar brauzerga to'g'ridan-to'g'ri berilmaydi: API orqali, ruxsat tekshiruvi bilan."""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from io import BytesIO
from typing import Protocol

from minio import Minio
from minio.error import S3Error

log = logging.getLogger("vaksina.storage")
CHUNK = 64 * 1024


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def stream(self, key: str) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> None: ...


class MinioStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool):
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket
        self._ready = False

    def _ensure_bucket(self) -> None:
        if self._ready:
            return
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
        self._ready = True

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        def run() -> None:
            self._ensure_bucket()
            self._client.put_object(
                self._bucket, key, BytesIO(data), length=len(data), content_type=content_type
            )

        await asyncio.to_thread(run)

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        response = await asyncio.to_thread(self._client.get_object, self._bucket, key)
        iterator: Iterator[bytes] = response.stream(CHUNK)
        try:
            while True:
                chunk = await asyncio.to_thread(next, iterator, None)
                if chunk is None:
                    break
                yield chunk
        finally:
            response.close()
            response.release_conn()

    async def delete(self, key: str) -> None:
        def run() -> None:
            try:
                self._client.remove_object(self._bucket, key)
            except S3Error as exc:  # mavjud bo'lmagan obyekt xato emas
                if exc.code != "NoSuchKey":
                    raise

        await asyncio.to_thread(run)
