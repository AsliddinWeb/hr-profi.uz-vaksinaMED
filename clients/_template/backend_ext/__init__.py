"""__NAME__ mijoz extension (backend).

Qoidalar:
- core jadvallarini o'zgartirmang; o'z jadvallaringiz `client_` prefiksi bilan `migrations/versions/` da (revision `ext0001`, ...)
- core bilan aloqa: `ctx.events.on("<hodisa>", handler)`; hodisalar ro'yxati: docs/EXTENSIONS.md
- core modullarini import qilish mumkin (`from app...`), lekin ularning ichki tuzilmasiga bog'lanib qolmang
"""

import logging

log = logging.getLogger("client.__NAME__")


def setup(ctx) -> None:
    """Ilova ishga tushganda chaqiriladi: router, hodisa ishlovchilari shu yerda ulanadi."""

    def on_employee_created(employee_id: int, full_name: str, **_) -> None:
        log.info("Yangi xodim: %s (%s)", full_name, employee_id)

    ctx.events.on("employee.created", on_employee_created)


def setup_worker(registry) -> None:
    """Worker ishga tushganda: mijozga xos vazifa/cron shu yerda qo'shiladi (ixtiyoriy)."""
