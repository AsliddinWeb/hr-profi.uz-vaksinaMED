"""Fon vazifalari navbati. Prod: arq (Redis). Testlarda FakeQueue bilan almashtiriladi."""

from typing import Any, Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings


class Queue(Protocol):
    async def enqueue(self, function: str, *args: Any, defer_seconds: float | None = None) -> None: ...


class ArqQueue:
    def __init__(self, pool: ArqRedis):
        self._pool = pool

    @classmethod
    async def connect(cls, redis_url: str) -> "ArqQueue":
        return cls(await create_pool(RedisSettings.from_dsn(redis_url)))

    async def enqueue(self, function: str, *args: Any, defer_seconds: float | None = None) -> None:
        await self._pool.enqueue_job(function, *args, _defer_by=defer_seconds)

    async def close(self) -> None:
        await self._pool.aclose()
