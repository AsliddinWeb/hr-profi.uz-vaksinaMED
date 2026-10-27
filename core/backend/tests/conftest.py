import asyncio
import os

os.environ.setdefault("CLIENT_DIR", "/nonexistent")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "test-minio-password-0123456789")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-0123456789")

import fakeredis.aioredis  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.migrate import main as migrate  # noqa: E402
from app.models.auth import Role, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.seed import ensure_roles  # noqa: E402

PASSWORD = "Passw0rd-test"
HEADERS = {"X-Requested-With": "test"}


def _needs_db() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Test bazasini tozalab, core migratsiyalarini qo'llaydi (DATABASE_URL berilgan bo'lsa)."""
    if not _needs_db():
        yield
        return

    async def reset():
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(reset())
    migrate()
    # migrate() o'z event loop'ida ishlagan: undagi ulanishlarni pool'dan chiqaramiz
    engine.sync_engine.dispose(close=False)
    yield


@pytest_asyncio.fixture(autouse=True)
async def _clean(_database):
    if not _needs_db():
        yield
        return
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE audit_log, user_sessions, users, role_permissions, roles, schedule_entries, "
                "schedule_patterns, holidays, work_groups, shift_templates, face_attempts, leave_requests, "
                "explanation_letters, letter_templates, penalties, tasks, task_templates, reminders, staff_needs, need_requests, need_categories, checklist_visits, checklist_templates, vacancies, candidates, internship_enrollments, internship_programs, pay_schemes, pay_items, payroll_runs, canteen_menus, canteen_settings, trips, vehicles, driver_profiles, warehouses, mobile_permits, visits, tickets, ticket_categories, calls, ai_requests, ai_summaries, report_schedules, report_runs, migration_batches, migration_mappings, migration_checks RESTART IDENTITY CASCADE"
            )
        )
        await conn.execute(text("ALTER SEQUENCE need_no_seq RESTART"))
        await conn.execute(text("ALTER SEQUENCE ticket_no_seq RESTART"))
    async with SessionLocal() as s:
        await ensure_roles(s)
        from app.services.letters import ensure_default_template

        await ensure_default_template(s)
        from app.services.penalties import ensure_default_rules

        await ensure_default_rules(s)
    yield


class FakeQueue:
    def __init__(self):
        self.calls: list[tuple] = []

    async def enqueue(self, function, *args, defer_seconds=None):
        self.calls.append((function, *args))


class FakeFaceEngine:
    """Testlar uchun: "rasm" = JSON {"id", "yaw", "noise", "reason"}. Embedding id dan deterministik olinadi."""

    model_name = "fake"

    def analyze(self, data: bytes):
        import json

        import numpy as np

        from app.face.engine import FrameResult

        spec = json.loads(data.decode())
        if spec.get("reason"):
            return FrameResult(False, spec["reason"])
        seed = int.from_bytes(spec["id"].encode().ljust(8, b"_")[:8], "little") % (2**32)
        base = np.random.default_rng(seed).normal(size=128)
        noise = np.random.default_rng().normal(size=128) * spec.get("noise", 0.02)
        vec = (base / np.linalg.norm(base) + noise).astype(np.float32)
        vec /= np.linalg.norm(vec)
        return FrameResult(True, None, spec.get("yaw", 0.0), spec.get("quality", 0.8), vec)


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key, data, content_type):
        self.objects[key] = (data, content_type)

    async def stream(self, key):
        yield self.objects[key][0]

    async def delete(self, key):
        self.objects.pop(key, None)


@pytest_asyncio.fixture
async def app():
    application = create_app()
    application.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    application.state.queue = FakeQueue()
    application.state.storage = FakeStorage()
    application.state.face_engine = FakeFaceEngine()
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=HEADERS) as c:
        yield c


@pytest_asyncio.fixture
async def new_client(app):
    """Alohida cookie jar li qo'shimcha mijoz (boshqa foydalanuvchi sifatida kirish uchun)."""
    clients: list[httpx.AsyncClient] = []

    def make() -> httpx.AsyncClient:
        c = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", headers=HEADERS
        )
        clients.append(c)
        return c

    yield make
    for c in clients:
        await c.aclose()


async def make_user(login: str, role_key: str, *, must_change=False, active=True, name=None) -> int:
    from sqlalchemy import select

    async with SessionLocal() as s:
        role = await s.scalar(select(Role).where(Role.key == role_key))
        u = User(
            login=login,
            password_hash=hash_password(PASSWORD),
            full_name=name or login.title(),
            role_id=role.id,
            must_change_password=must_change,
            is_active=active,
        )
        s.add(u)
        await s.commit()
        return u.id


async def login(c: httpx.AsyncClient, login_name: str, password: str = PASSWORD):
    return await c.post("/api/auth/login", json={"login": login_name, "password": password})
