"""Prometheus metrikalari (`/api/metrics`): so'rovlar soni va kechikishi, DB/Redis/worker holati, navbat, foydalanuvchilar."""

import re
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select, text

from app import __version__
from app.config import get_settings
from app.db import SessionLocal, engine

router = APIRouter(tags=["system"])
BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
STARTED = time.time()

K_COUNT, K_HIST, K_SUM, K_MISC = "metrics:count", "metrics:hist", "metrics:sum", "metrics:misc"  # Redis hash lar: barcha worker jarayonlari bitta joyga yozadi


_ID = re.compile(r"/(\d+|[0-9a-fA-F-]{32,36}|[A-Za-z0-9_-]{24,})(?=/|$)")


def _norm(path: str) -> str:
    """Kardinallikni cheklash: raqam va uzun tokenlar `{id}` ga almashtiriladi."""
    return _ID.sub("/{id}", path)


def install(app) -> None:
    @app.middleware("http")
    async def collect(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        path = _norm(request.url.path)
        if path.startswith("/api") and path != "/api/metrics":
            dt = time.perf_counter() - start
            idx = next((i for i, b in enumerate(BUCKETS) if dt <= b), len(BUCKETS))
            try:  # Redis ishlamasa metrika yo'qoladi, so'rov buzilmaydi
                pipe = request.app.state.redis.pipeline()
                pipe.hincrby(K_COUNT, f"{request.method}|{path}|{response.status_code // 100}xx", 1)
                pipe.hincrby(K_HIST, f"{path}|{idx}", 1)
                pipe.hincrbyfloat(K_SUM, path, dt)
                if response.status_code == 429:
                    pipe.hincrby(K_MISC, "rate_limited", 1)
                await pipe.execute()
            except Exception:  # noqa: BLE001
                pass
        return response


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _authorized(request: Request) -> bool:
    token = get_settings().metrics_token
    if token:
        return request.headers.get("authorization") == f"Bearer {token}"
    return "x-forwarded-for" not in request.headers  # gateway orqali kelmagan: faqat ichki tarmoq


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    if not _authorized(request):
        return Response(status_code=404)
    out: list[str] = []

    def g(name: str, help_: str, value: float, typ: str = "gauge", labels: str = "") -> None:
        out.append(f"# HELP {name} {help_}\n# TYPE {name} {typ}\n{name}{labels} {value}")

    out.append(f'# HELP vaksina_info Versiya\n# TYPE vaksina_info gauge\nvaksina_info{{version="{__version__}",client="{_esc(request.app.state.client_config.name)}"}} 1')
    g("vaksina_uptime_seconds", "API ishlash vaqti", round(time.time() - STARTED, 1))
    db_ok = 0
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = 1
    except Exception:  # noqa: BLE001
        pass
    g("vaksina_db_up", "Baza ulanishi (1=ok)", db_ok)
    redis = request.app.state.redis
    redis_ok, hb_age, queue = 0, -1.0, -1
    try:
        await redis.ping()
        redis_ok = 1
        hb = await redis.get("worker:heartbeat")
        if hb:
            hb_age = round((datetime.now(UTC) - datetime.fromisoformat(hb)).total_seconds(), 1)
        queue = int(await redis.zcard("arq:queue"))
    except Exception:  # noqa: BLE001
        pass
    g("vaksina_redis_up", "Redis ulanishi (1=ok)", redis_ok)
    g("vaksina_worker_heartbeat_age_seconds", "Worker oxirgi yurak urishidan beri (-1: yo'q)", hb_age)
    g("vaksina_queue_depth", "arq navbatidagi vazifalar (-1: noma'lum)", queue)
    g("vaksina_ws_connections", "Ochiq WebSocket ulanishlar", request.app.state.hub.connections())
    if db_ok:
        from app.models.auth import User, UserSession
        from app.models.employees import Employee

        async with SessionLocal() as s:
            g("vaksina_users_active", "Faol foydalanuvchilar", await s.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0)
            g("vaksina_employees_active", "Faol xodimlar", await s.scalar(select(func.count()).select_from(Employee).where(Employee.status == "active")) or 0)
            g("vaksina_sessions_active", "Faol sessiyalar", await s.scalar(select(func.count()).select_from(UserSession).where(UserSession.revoked_at.is_(None), UserSession.expires_at > func.now())) or 0)
    counts: dict = {}
    hist: dict = {}
    sums: dict = {}
    limited = 0
    try:
        counts, hist, sums = await redis.hgetall(K_COUNT), await redis.hgetall(K_HIST), await redis.hgetall(K_SUM)
        limited = int(await redis.hget(K_MISC, "rate_limited") or 0)
    except Exception:  # noqa: BLE001
        pass
    g("vaksina_rate_limited_total", "429 (cheklov) javoblari", limited, "counter")
    out.append("# HELP vaksina_http_requests_total HTTP so'rovlar\n# TYPE vaksina_http_requests_total counter")
    for key, n in sorted(counts.items()):
        method, path, cls = key.split("|")
        out.append(f'vaksina_http_requests_total{{method="{method}",route="{_esc(path)}",status="{cls}"}} {n}')
    out.append("# HELP vaksina_http_request_duration_seconds So'rov kechikishi\n# TYPE vaksina_http_request_duration_seconds histogram")
    per: dict[str, list[int]] = {}
    for key, n in hist.items():
        path, i = key.rsplit("|", 1)
        per.setdefault(path, [0] * (len(BUCKETS) + 1))[int(i)] = int(n)
    for path, buckets in sorted(per.items()):
        acc = 0
        for i, b in enumerate(BUCKETS):
            acc += buckets[i]
            out.append(f'vaksina_http_request_duration_seconds_bucket{{route="{_esc(path)}",le="{b}"}} {acc}')
        acc += buckets[-1]
        out.append(f'vaksina_http_request_duration_seconds_bucket{{route="{_esc(path)}",le="+Inf"}} {acc}')
        out.append(f'vaksina_http_request_duration_seconds_sum{{route="{_esc(path)}"}} {round(float(sums.get(path, 0)), 4)}')
        out.append(f'vaksina_http_request_duration_seconds_count{{route="{_esc(path)}"}} {acc}')
    return Response("\n".join(out) + "\n", media_type="text/plain; version=0.0.4")
