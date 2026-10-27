"""Mijozga xos (client) extension tizimi.

Mijoz papkasi tuzilmasi:
    <client_dir>/client.yaml          sozlamalar (brend, modullar, qoidalar)
    <client_dir>/backend_ext/__init__.py   setup(ctx) va ixtiyoriy setup_worker(registry)
    <client_dir>/migrations/          faqat shu mijozning jadvallari (alohida alembic branch)
"""

import importlib.util
import logging
import sys
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from fastapi import FastAPI

from app import plans
from app.modules import CORE_MODULES

log = logging.getLogger("vaksina.ext")

EXT_MODULE_NAME = "client_ext"

DEFAULT_BRAND = {
    "name": "HR-Profi",
    "tagline": "Kadrlar va filiallarni boshqarish tizimi",
    "primary": "#0b5ed7",  # standart HR-Profi ko'k (frontend bu holda brend rangini qo'llamaydi)
    "accent": "#3ecf8e",
    "logo": "/logo.png",
}

Handler = Callable[..., Awaitable[None] | None]


@dataclass
class ClientConfig:
    name: str
    brand: dict[str, Any]
    modules: dict[str, bool]
    settings: dict[str, Any] = field(default_factory=dict)
    plan: str | None = None
    license: dict[str, Any] = field(default_factory=dict)

    @property
    def enabled_modules(self) -> list[str]:
        return [k for k, v in self.modules.items() if v]


def load_client_config(client_dir: str | Path, fallback_name: str = "default") -> ClientConfig:
    """client.yaml ni o'qiydi. Fayl yo'q yoki buzuq bo'lsa, core standartlariga qaytadi."""
    path = Path(client_dir) / "client.yaml"
    raw: dict[str, Any] = {}
    if path.is_file():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                raise ValueError("client.yaml ildizi mapping bo'lishi kerak")
        except Exception:
            log.exception("client.yaml o'qilmadi (%s), standart ishlatiladi", path)
            raw = {}

    plan = raw.get("plan")
    if plan is not None and plan not in plans.PLAN_MODULES:
        log.warning("client.yaml: noma'lum tarif %r, cheklovsiz ishlatiladi", plan)
        plan = None
    for key in (raw.get("modules") or {}):
        if key not in CORE_MODULES:
            log.warning("client.yaml: noma'lum modul '%s' e'tiborsiz qoldirildi", key)
    modules = plans.resolve_modules(plan, raw.get("modules"))

    brand = {**DEFAULT_BRAND, **(raw.get("brand") or {})}
    return ClientConfig(
        name=str(raw.get("name") or fallback_name),
        brand=brand,
        modules=modules,
        settings=raw.get("settings") or {},
        plan=plan,
        license=raw.get("license") or {},
    )


class EventBus:
    """Core hodisalariga extension ulanishi uchun oddiy pub/sub."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    async def emit(self, event: str, **payload: Any) -> None:
        for handler in self._handlers.get(event, []):
            try:
                result = handler(**payload)
                if result is not None:
                    await result
            except Exception:
                # Extension xatosi core oqimini buzmasligi kerak
                log.exception("Event handler xatosi: %s", event)


@dataclass
class ExtensionContext:
    app: FastAPI
    config: ClientConfig
    events: EventBus


@dataclass
class WorkerRegistry:
    functions: list[Callable[..., Any]] = field(default_factory=list)
    cron_jobs: list[Any] = field(default_factory=list)


def _import_ext(client_dir: str | Path) -> ModuleType | None:
    pkg_dir = Path(client_dir) / "backend_ext"
    init = pkg_dir / "__init__.py"
    if not init.is_file():
        return None
    if EXT_MODULE_NAME in sys.modules:
        return sys.modules[EXT_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(
        EXT_MODULE_NAME, init, submodule_search_locations=[str(pkg_dir)]
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[EXT_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def load_backend_extension(client_dir: str | Path, ctx: ExtensionContext) -> bool:
    module = _import_ext(client_dir)
    if module is None:
        return False
    setup = getattr(module, "setup", None)
    if not callable(setup):
        log.warning("backend_ext: setup(ctx) topilmadi")
        return False
    setup(ctx)
    log.info("Mijoz extension yuklandi: %s", ctx.config.name)
    return True


def load_worker_extension(client_dir: str | Path, registry: WorkerRegistry) -> bool:
    module = _import_ext(client_dir)
    setup = getattr(module, "setup_worker", None) if module else None
    if not callable(setup):
        return False
    setup(registry)
    return True
