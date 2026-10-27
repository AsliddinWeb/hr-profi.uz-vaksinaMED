"""Core va mijoz migratsiyalari uchun umumiy Alembic env.

Har branch o'z `version_table` iga ega (core: alembic_version, mijoz: alembic_version_ext),
shuning uchun ular bir-birini buzmaydi.
"""

import asyncio

from alembic import context
from sqlalchemy import MetaData, pool
from sqlalchemy.ext.asyncio import async_engine_from_config


def run(target_metadata: MetaData | None = None) -> None:
    config = context.config
    version_table = config.get_main_option("version_table") or "alembic_version"

    def do_run(connection) -> None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=version_table,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    async def run_async() -> None:
        engine = async_engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        async with engine.connect() as connection:
            await connection.run_sync(do_run)
        await engine.dispose()

    if context.is_offline_mode():
        context.configure(
            url=config.get_main_option("sqlalchemy.url"),
            target_metadata=target_metadata,
            version_table=version_table,
            literal_binds=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        asyncio.run(run_async())
