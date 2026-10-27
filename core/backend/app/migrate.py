"""`python -m app.migrate`: avval core, keyin (bo'lsa) mijoz migratsiyalarini qo'llaydi."""

import asyncio
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.db import SessionLocal
from app.services.seed import ensure_roles

log = logging.getLogger("vaksina.migrate")
CORE_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _config(script_location: Path, version_table: str, url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("version_table", version_table)
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()

    log.info("Core migratsiyalari...")
    command.upgrade(_config(CORE_DIR, "alembic_version", settings.database_url), "head")

    client_migrations = Path(settings.client_dir) / "migrations"
    if (client_migrations / "env.py").is_file():
        log.info("Mijoz migratsiyalari (%s)...", settings.client_name)
        command.upgrade(
            _config(client_migrations, "alembic_version_ext", settings.database_url), "head"
        )

    async def _seed() -> None:
        async with SessionLocal() as session:
            await ensure_roles(session)

    asyncio.run(_seed())
    return 0


if __name__ == "__main__":
    sys.exit(main())
