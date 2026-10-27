"""Namuna mijoz extension.

Qoidalar:
- core jadvallarini o'zgartirmang; o'z jadvallaringizni `migrations/` da yarating (prefiks: client_*)
- core bilan aloqa: `ctx.events.on(...)` hodisalari va o'z routerlaringiz
- core ichki modullarini import qilish mumkin (`from app...`), lekin ularning tuzilmasiga bog'lanib qolmang
"""

import logging

from fastapi import APIRouter

log = logging.getLogger("client.example")


def setup(ctx) -> None:
    router = APIRouter(prefix="/ext", tags=["client:example"])

    @router.get("/hello")
    async def hello() -> dict:
        return {"client": ctx.config.name, "message": "Mijoz extension ishlayapti"}

    ctx.app.include_router(router, prefix="/api")

    # Hodisa misoli (core `events.emit("employee.created", ...)` chaqirganda ishlaydi)
    def on_employee_created(employee_id: int, **_) -> None:
        log.info("Yangi xodim: %s", employee_id)

    ctx.events.on("employee.created", on_employee_created)


def setup_worker(registry) -> None:
    async def client_daily_job(ctx: dict) -> None:
        log.info("Mijozga xos kunlik vazifa")

    registry.functions.append(client_daily_job)
