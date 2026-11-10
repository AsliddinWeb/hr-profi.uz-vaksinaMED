"""Parol tekshiruvi (Argon2) event loop'ni to'xtatmasligi kerak: aks holda bitta login paytida shu jarayondagi
barcha so'rovlar kutib qoladi (yuklama testida login 1000 kishida 50 s gacha cho'zilgan edi)."""

import asyncio
import time

from app.security import hash_password, hash_password_async, verify_password, verify_password_async


async def test_password_check_does_not_block_event_loop():
    h = hash_password("Parol-1234")
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.005)
            ticks += 1

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0)
    started = time.perf_counter()
    results = await asyncio.gather(*[verify_password_async("Parol-1234", h) for _ in range(8)], verify_password_async("noto'g'ri", h))
    elapsed = time.perf_counter() - started
    task.cancel()
    assert results[:8] == [True] * 8 and results[8] is False
    # Tekshiruv davomida boshqa korutinalar ishlay oldi (sinxron bo'lsa ticks ~0 bo'lardi)
    assert ticks >= max(3, int(elapsed / 0.005 * 0.3))


async def test_async_hash_roundtrip():
    h = await hash_password_async("Yangi-parol-77")
    assert verify_password("Yangi-parol-77", h) and not verify_password("boshqa", h)
    assert await verify_password_async("x", None) is False
