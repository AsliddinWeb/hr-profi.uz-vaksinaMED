import sys
import textwrap

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.extensions import (
    EventBus,
    ExtensionContext,
    WorkerRegistry,
    load_backend_extension,
    load_client_config,
    load_worker_extension,
)


@pytest.fixture(autouse=True)
def _clean_ext_module():
    sys.modules.pop("client_ext", None)
    yield
    sys.modules.pop("client_ext", None)


def test_config_defaults_when_missing(tmp_path):
    cfg = load_client_config(tmp_path, fallback_name="x")
    assert cfg.name == "x"
    assert "logistics" in cfg.enabled_modules


def test_config_overrides_and_ignores_unknown(tmp_path):
    (tmp_path / "client.yaml").write_text(
        textwrap.dedent(
            """
            name: acme
            brand: {name: Acme HR, primary: "#000000"}
            modules: {logistics: false, nonsense: true}
            """
        )
    )
    cfg = load_client_config(tmp_path)
    assert cfg.name == "acme"
    assert cfg.brand["name"] == "Acme HR"
    assert cfg.brand["accent"]  # standart saqlanadi
    assert "logistics" not in cfg.enabled_modules
    assert "nonsense" not in cfg.modules


def test_broken_yaml_falls_back(tmp_path):
    (tmp_path / "client.yaml").write_text(": : :\n- [")
    cfg = load_client_config(tmp_path, fallback_name="fb")
    assert cfg.name == "fb"


def _write_ext(tmp_path, body: str):
    pkg = tmp_path / "backend_ext"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(textwrap.dedent(body))


def test_extension_adds_route_and_worker_job(tmp_path):
    _write_ext(
        tmp_path,
        """
        from fastapi import APIRouter

        def setup(ctx):
            r = APIRouter()
            @r.get("/ext/hello")
            def hello():
                return {"client": ctx.config.name}
            ctx.app.include_router(r, prefix="/api")

        async def _job(ctx): return 1

        def setup_worker(registry):
            registry.functions.append(_job)
        """,
    )
    (tmp_path / "client.yaml").write_text("name: acme\n")
    app = FastAPI()
    cfg = load_client_config(tmp_path)
    assert load_backend_extension(tmp_path, ExtensionContext(app, cfg, EventBus())) is True
    assert TestClient(app).get("/api/ext/hello").json() == {"client": "acme"}

    reg = WorkerRegistry()
    assert load_worker_extension(tmp_path, reg) is True
    assert len(reg.functions) == 1


def test_no_extension_returns_false(tmp_path):
    cfg = load_client_config(tmp_path)
    assert load_backend_extension(tmp_path, ExtensionContext(FastAPI(), cfg, EventBus())) is False


async def test_event_bus_isolates_handler_errors():
    bus = EventBus()
    seen: list[int] = []

    def bad(**_):
        raise RuntimeError("boom")

    async def good(value):
        seen.append(value)

    bus.on("e", bad)
    bus.on("e", good)
    await bus.emit("e", value=7)
    assert seen == [7]
