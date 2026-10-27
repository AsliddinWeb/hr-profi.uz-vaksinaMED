"""KOSHI tarifi va litsenziya holati: joriy tarif, foydalanuvchi o'rinlari, muddat, tarif taqqoslash jadvali."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import plans
from app.db import get_session
from app.deps import AuthContext, require
from app.timeutil import local_date, now

router = APIRouter(prefix="/v1/plan", tags=["plan"])


@router.get("")
async def get_plan(request: Request, db: AsyncSession = Depends(get_session), _: AuthContext = Depends(require("roles.read"))) -> dict[str, Any]:
    cfg = request.app.state.client_config
    lic = cfg.license or {}
    today = local_date(now())
    used = await plans.seats_used(db)
    seats = lic.get("seats")
    until = lic.get("valid_until")
    until_d = until if isinstance(until, date) else (date.fromisoformat(str(until)) if until else None)
    current = cfg.plan
    return {
        "plan": current, "name": plans.PLAN_INFO[current]["name"] if current else None,
        "price_usd": plans.PLAN_INFO[current]["price_usd"] if current else None,
        "license": {"holder": lic.get("holder"), "seats": seats, "used": used, "free": (int(seats) - used) if seats else None, "valid_until": until_d,
                    "days_left": (until_d - today).days if until_d else None, "status": plans.license_status(lic, today) if lic else "unlimited"},
        "enabled_modules": cfg.enabled_modules,
        "features": [
            {"key": f.key, "uz": f.uz, "ru": f.ru, "min_plan": f.min_plan, "built": f.built, "available": plans.feature_available(f.key, current)}
            for f in plans.FEATURES
        ],
        "plans": [{"key": k, "name": plans.PLAN_INFO[k]["name"], "price_usd": plans.PLAN_INFO[k]["price_usd"], "tagline": plans.PLAN_INFO[k]["tagline"], "modules": len(plans.PLAN_MODULES[k])} for k in plans.PLAN_ORDER],
    }  # fmt: skip
