"""Xavfsizlik qatlami: so'rov chastotasi cheklovi (Redis), xavfsiz sarlavhalar, production sozlamalarini tekshirish."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import Settings

log = logging.getLogger("vaksina.security")

WEAK_SECRETS = {"", "change-me", "changeme", "secret", "__generate__"}
EXEMPT_PREFIXES = ("/api/health", "/api/v1/calls/webhook", "/api/metrics")

# (yo'l prefiksi yoki qismi, qoida nomi, daqiqada so'rov / IP). Birinchi mos kelgani ishlaydi; oxirgisi umumiy.
RULES: list[tuple[Callable[[str, str], bool], str, int]] = [
    (lambda p, m: p.startswith("/api/auth/"), "auth", 120),
    (lambda p, m: p.startswith("/api/v1/ai/"), "ai", 90),
    (lambda p, m: p.startswith("/api/v1/search"), "search", 240),
    (lambda p, m: p.startswith("/api/v1/reports/run") or "/export" in p or p.endswith("/pdf"), "export", 60),
    (lambda p, m: m in ("POST", "PUT") and ("/files" in p or "/import" in p or p.startswith("/api/v1/migration/batches") or p.endswith("/photo") or "/face/" in p), "upload", 240),
    (lambda p, m: p.startswith("/api/"), "api", 3000),
]


def check_production_config(s: Settings) -> list[str]:
    """Production da xavfli sozlamalar ro'yxati (bo'sh bo'lsa yaxshi)."""
    if s.env == "development":
        return []
    problems: list[str] = []
    if s.secret_key.lower() in WEAK_SECRETS or len(s.secret_key) < 32:
        problems.append("SECRET_KEY zaif yoki standart (kamida 32 belgi, tasodifiy bo'lishi kerak)")
    if not s.minio_root_password or s.minio_root_password in WEAK_SECRETS:
        problems.append("MINIO_ROOT_PASSWORD bo'sh yoki standart")
    if s.database_url.endswith("vaksina:vaksina@db:5432/vaksina"):
        problems.append("POSTGRES_PASSWORD standart (vaksina)")
    if s.livekit_api_key and (not s.livekit_api_secret or len(s.livekit_api_secret) < 32):
        problems.append("LIVEKIT_API_SECRET qisqa (kamida 32 belgi)")
    return problems


async def _hit(redis, key: str, window: int) -> int:
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, window + 1)
    return int(n)


def install(app, settings: Settings) -> None:
    """HTTP middleware: chastota cheklovi va xavfsiz sarlavhalar."""

    @app.middleware("http")
    async def rate_limit_and_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path, method = request.url.path, request.method
        if settings.rate_limit_enabled and path.startswith("/api/") and not path.startswith(EXEMPT_PREFIXES):
            redis = getattr(request.app.state, "redis", None)
            ip = request.client.host if request.client else "?"
            for match, name, per_min in RULES:
                if match(path, method):
                    limit = max(1, int(per_min * settings.rate_limit_multiplier))
                    window = 60
                    bucket = int(time.time() // window)
                    try:
                        n = await _hit(redis, f"rl:{name}:{ip}:{bucket}", window) if redis is not None else 0
                    except Exception:  # noqa: BLE001  (Redis ishlamasa cheklov o'chadi, xizmat to'xtamaydi)
                        n = 0
                    if n > limit:
                        retry = window - int(time.time()) % window
                        log.warning("rate limit: %s %s ip=%s (%s: %d/%d)", method, path, ip, name, n, limit)
                        return JSONResponse({"detail": {"code": "rate_limited", "retry_after": retry}}, status_code=429, headers={"Retry-After": str(retry)})
                    break
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")  # API javoblari shaxsiy: oraliq keshlarda saqlanmasin
        return response
