"""Yuk testi: haqiqiy foydalanuvchilar (HR va xodimlar) aralash trafigi. Faqat `httpx` kerak (backend imidjida bor).

    python loadtest.py --base http://vk-load-api:8000 --users 40 --duration 45 --stages 10,30,60

Har bosqich (parallel foydalanuvchilar soni) alohida o'lchanadi: RPS, p50/p95/p99, xato ulushi, endpoint kesimi.
Chiqish kodi 1: p95 > --p95-limit (soniya) yoki xato ulushi > 1%.
"""

import argparse
import asyncio
import random
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, timedelta

import httpx

H = {"X-Requested-With": "loadtest"}
PASSWORD = "Load-test-1234"


def week() -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    return str(end - timedelta(days=6)), str(end)


# (nom, og'irlik, rol, funksiya)
async def hr_scenarios(c: httpx.AsyncClient, rnd: random.Random, rec):
    s, e = week()
    month_s = str(date.today() - timedelta(days=30))
    page = rnd.randrange(1, 20)
    r = await rec("employees.list", c.get("/api/v1/employees", params={"page": page, "size": 25}))
    if r is not None and r.status_code == 200 and r.json().get("items"):
        await rec("employees.one", c.get(f"/api/v1/employees/{rnd.choice(r.json()['items'])['id']}"))
    pick = rnd.random()
    if pick < 0.25:
        await rec("attendance.dashboard", c.get("/api/v1/attendance/dashboard", params={"start": s, "end": e}))
    elif pick < 0.5:
        await rec("attendance.timesheet", c.get("/api/v1/attendance/timesheet", params={"start": s, "end": e, "size": 50}))
    elif pick < 0.65:
        await rec("attendance.dashboard.month", c.get("/api/v1/attendance/dashboard", params={"start": month_s, "end": e}))
    elif pick < 0.8:
        await rec("search", c.get("/api/v1/search", params={"q": rnd.choice(["Karimov", "Aziz", "Filial 3", "Ticket 1"])}))
    elif pick < 0.9:
        await rec("tasks.list", c.get("/api/v1/tasks", params={"scope": "all"}))
    else:
        await rec("reports.run", c.post("/api/v1/reports/run", json={"type": "attendance", "start": s, "end": e, "format": "xlsx"}))


async def staff_scenarios(c: httpx.AsyncClient, rnd: random.Random, rec):
    s, e = week()
    await rec("me", c.get("/api/auth/me"))
    await rec("notifications", c.get("/api/v1/notifications"))
    pick = rnd.random()
    if pick < 0.35:
        await rec("attendance.me", c.get("/api/v1/attendance/me", params={"start": s, "end": e}))
    elif pick < 0.6:
        await rec("tasks.mine", c.get("/api/v1/tasks"))
    elif pick < 0.8:
        await rec("helpdesk.mine", c.get("/api/v1/helpdesk", params={"scope": "mine"}))
    elif pick < 0.95:
        await rec("needs.mine", c.get("/api/v1/needs", params={"scope": "mine"}))
    else:
        await rec("helpdesk.create", c.post("/api/v1/helpdesk", json={"title": "Yuk testi ticketi", "priority": "low"}))


async def worker(base: str, login: str, hr: bool, stop: float, stats: dict, errors: dict, seed: int):
    rnd = random.Random(seed)
    async with httpx.AsyncClient(base_url=base, headers=H, timeout=30) as c:
        r = await c.post("/api/auth/login", json={"login": login, "password": PASSWORD})
        if r.status_code != 200:
            errors["login"] += 1
            return

        async def rec(name: str, coro):
            t = time.perf_counter()
            try:
                resp = await coro
            except Exception:  # noqa: BLE001
                errors[name] += 1
                stats[name].append((time.perf_counter() - t, False))
                return None
            ok = resp.status_code < 400
            if not ok:
                errors[f"{name}:{resp.status_code}"] += 1
            stats[name].append((time.perf_counter() - t, ok))
            return resp

        while time.perf_counter() < stop:
            await (hr_scenarios if hr else staff_scenarios)(c, rnd, rec)
            await asyncio.sleep(rnd.uniform(0.05, 0.4))  # "o'ylash" pauzasi


def pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(len(vals) * p))]


async def stage(base: str, concurrency: int, duration: int, staff_users: int) -> dict:
    stats: dict[str, list] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    stop = time.perf_counter() + duration
    n_hr = max(1, round(concurrency * 0.12))
    tasks = [asyncio.create_task(worker(base, f"hr{i % 5}", True, stop, stats, errors, i)) for i in range(n_hr)]
    tasks += [asyncio.create_task(worker(base, f"u{i % staff_users}", False, stop, stats, errors, 1000 + i)) for i in range(concurrency - n_hr)]
    t0 = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0
    allv = [d for v in stats.values() for d, _ in v]
    bad = sum(1 for v in stats.values() for _, ok in v if not ok)
    return {
        "concurrency": concurrency, "requests": len(allv), "rps": round(len(allv) / elapsed, 1), "p50": pct(allv, 0.5), "p95": pct(allv, 0.95), "p99": pct(allv, 0.99),
        "error_rate": round(bad / len(allv), 4) if allv else 1.0, "errors": dict(errors),
        "by_endpoint": {k: {"n": len(v), "p50": pct([d for d, _ in v], 0.5), "p95": pct([d for d, _ in v], 0.95), "max": max(d for d, _ in v)} for k, v in sorted(stats.items())},
        "mean": statistics.fmean(allv) if allv else 0,
    }  # fmt: skip


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--users", type=int, default=40, help="bazadagi oddiy foydalanuvchilar soni (u0..uN-1)")
    ap.add_argument("--duration", type=int, default=45)
    ap.add_argument("--stages", default="10,30,60")
    ap.add_argument("--p95-limit", type=float, default=1.0)
    a = ap.parse_args()
    worst = 0
    for c in (int(x) for x in a.stages.split(",")):
        r = await stage(a.base, c, a.duration, a.users)
        print(f"\n== {c} parallel foydalanuvchi, {a.duration}s ==")
        print(f"so'rovlar {r['requests']}  RPS {r['rps']}  p50 {r['p50'] * 1000:.0f}ms  p95 {r['p95'] * 1000:.0f}ms  p99 {r['p99'] * 1000:.0f}ms  xato {r['error_rate'] * 100:.2f}%")
        if r["errors"]:
            print("xatolar:", r["errors"])
        print(f"{'endpoint':28} {'n':>6} {'p50':>7} {'p95':>7} {'max':>7}")
        for k, v in sorted(r["by_endpoint"].items(), key=lambda kv: -kv[1]["p95"]):
            print(f"{k:28} {v['n']:6d} {v['p50'] * 1000:6.0f}ms {v['p95'] * 1000:6.0f}ms {v['max'] * 1000:6.0f}ms")
        if r["p95"] > a.p95_limit or r["error_rate"] > 0.01:
            worst = 1
    print("\nNATIJA:", "O'TMADI" if worst else "O'TDI", f"(p95 <= {a.p95_limit}s, xato <= 1%)")
    return worst


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
