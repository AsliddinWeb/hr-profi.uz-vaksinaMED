import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app import (
    __version__,
    permissions,  # noqa: F401  (ruxsatlar katalogini yuklaydi)
    plans,
)
from app.api import (
    ai,
    answers,
    attendance,
    attendance_issues,
    attestation,
    audit,
    auth,
    branches,
    calls,
    canteen,
    checklists,
    complaints,
    coord_report,
    employee_bulk,
    employee_files,
    employee_io,
    employees,
    face,
    growth,
    health,
    helpdesk,
    integrations,
    internship,
    letters,
    logistics,
    meta,
    migration,
    mobile,
    needs,
    notifications,
    onboarding,
    org,
    payroll,
    penalties,
    pharmacy,
    plan,
    reception,
    recruit,
    recruit_pipeline,
    recruit_sources,
    reminders,
    reports,
    retention,
    roles,
    rotations,
    schedule,
    schedule_config,
    tasks,
    telegram,
    users,
    warehouse,
    ws,
)
from app.config import get_settings
from app.db import engine
from app.extensions import (
    EventBus,
    ExtensionContext,
    load_backend_extension,
    load_client_config,
)
from app.queue import ArqQueue
from app.realtime import RealtimeHub
from app.storage import MinioStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from app.hardening import check_production_config

        problems = check_production_config(settings)
        for pr in problems:
            logging.getLogger("vaksina.security").critical("XAVFSIZLIK: %s", pr)
        if problems:
            raise RuntimeError("Production sozlamalari xavfsiz emas: " + "; ".join(problems) + " (ENV=development bilan o'chiriladi)")
        app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.queue = await ArqQueue.connect(settings.redis_url)
        app.state.storage = MinioStorage(
            settings.minio_endpoint,
            settings.minio_root_user,
            settings.minio_root_password,
            settings.minio_bucket,
            settings.minio_secure,
        )
        listener = asyncio.create_task(app.state.hub.listen(app.state.redis))
        yield
        listener.cancel()
        await asyncio.gather(listener, return_exceptions=True)
        await app.state.queue.close()
        await app.state.redis.aclose()
        await engine.dispose()

    app = FastAPI(
        title="HR-Profi API",
        version=__version__,
        docs_url="/api/docs" if (settings.is_dev or settings.api_docs) else None,
        openapi_url="/api/openapi.json" if (settings.is_dev or settings.api_docs) else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    from app.client_schema import validate_client_dir

    _errs, _warns = validate_client_dir(settings.client_dir) if Path(settings.client_dir).is_dir() else ([], [])
    for _m in _errs:
        logging.getLogger("vaksina.client").error("client.yaml: %s", _m)
    for _m in _warns:
        logging.getLogger("vaksina.client").warning("client.yaml: %s", _m)
    config = load_client_config(settings.client_dir, fallback_name=settings.client_name)
    app.state.client_config = config
    plans.configure(config.plan, config.license)
    app.state.events = EventBus()
    app.state.hub = RealtimeHub()

    @app.middleware("http")
    async def module_gate(request: Request, call_next):
        """O'chirilgan modul (tarifda yo'q yoki client.yaml da o'chirilgan) API yo'llari 403 qaytaradi."""
        parts = request.url.path.split("/")  # ['', 'api', 'v1', '<modul>', ...]
        if len(parts) > 3 and parts[1] == "api" and parts[2] == "v1":
            module = plans.PREFIX_MODULE.get(parts[3])
            if module and module not in request.app.state.client_config.enabled_modules:
                return JSONResponse(status_code=403, content={"detail": {"code": "module_disabled", "module": module}})
        return await call_next(request)

    from app import hardening, metrics

    hardening.install(app, settings)
    metrics.install(app)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        """422 ni `{detail: {code: 'validation', fields: [{field, code}]}}` ko'rinishiga keltiradi."""
        fields = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path", "form")]
            msg = str(err.get("msg", ""))
            code = msg.removeprefix("Value error, ") if msg.startswith("Value error, ") else err.get("type", "invalid")
            fields.append({"field": ".".join(loc), "code": code})
        return JSONResponse({"detail": {"code": "validation", "fields": fields}}, status_code=422)

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        # Cookie asosidagi auth uchun: o'zgartiruvchi so'rovlarda maxsus header shart.
        # Boshqa domendan formadan yuborilgan so'rovda bu header bo'lmaydi.
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path.startswith("/api/")
            and request.url.path != "/api/v1/calls/webhook"  # LiveKit server: cookie yo'q, JWT imzosi bilan himoyalangan
            and not request.url.path.startswith("/api/ext/")  # tashqi API: cookie yo'q, X-API-Key bilan himoyalangan
            and not request.headers.get("x-requested-with")
        ):
            return JSONResponse({"detail": {"code": "csrf"}}, status_code=403)
        return await call_next(request)

    # Statik yo'llar (/bulk, /export, /import/*, /duplicates) `/{employee_id}` dan OLDIN
    for module in (
        health, metrics, meta, auth, users, roles, audit, notifications, telegram, org, branches,
        employee_io, employee_bulk, employees, employee_files,
        schedule_config, schedule, attendance, attendance_issues, attestation, growth, integrations, complaints, coord_report, face, answers, letters, penalties, tasks, reminders, pharmacy, needs, checklists, recruit, recruit_pipeline, recruit_sources, retention, rotations, internship, onboarding, plan, payroll, canteen, logistics, warehouse, mobile, reception, helpdesk, calls, ai, reports, migration,
    ):  # fmt: skip
        app.include_router(module.router, prefix="/api")
    app.include_router(letters.public_router, prefix="/api")
    app.include_router(answers.public_router, prefix="/api")
    app.include_router(onboarding.kadr_router, prefix="/api")
    app.include_router(integrations.ext_router, prefix="/api")
    app.include_router(retention.off_router, prefix="/api")
    app.include_router(retention.control_router, prefix="/api")
    app.include_router(recruit_sources.public_router, prefix="/api")
    app.include_router(ws.router)  # /ws/... (gateway /ws/ ni API ga yo'naltiradi)

    ctx = ExtensionContext(app=app, config=config, events=app.state.events)
    app.state.extension_loaded = load_backend_extension(settings.client_dir, ctx)
    return app


app = create_app()
