from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from app import __version__
from app.db import engine

router = APIRouter(tags=["system"])


@router.get("/health")
async def liveness() -> dict[str, str]:
    """Jarayon tirikmi (tashqi bog'liqliksiz)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request, response: Response) -> dict:
    """DB, Redis va worker holati."""
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["db"] = f"error: {type(exc).__name__}"

    redis = request.app.state.redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
        checks["worker"] = "ok" if await redis.exists("worker:heartbeat") else "no-heartbeat"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {type(exc).__name__}"
        checks["worker"] = "unknown"

    # Worker heartbeat'i ogohlantirish, xizmatni "ready emas" qilmaydi
    critical_ok = checks["db"] == "ok" and checks["redis"] == "ok"
    if not critical_ok:
        response.status_code = 503
    return {"status": "ok" if critical_ok else "degraded", "version": __version__, "checks": checks}
