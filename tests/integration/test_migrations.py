import asyncio

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.conftest import alembic_config, database_url, recreate_database

TABLES = {"tg_users", "chats", "chat_players", "cache"}


async def table_names(url: str) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    await engine.dispose()
    return names


@pytest.mark.usefixtures("migrated_db_url")
def test_fresh_db_migrates_and_downgrades() -> None:
    name = "dota_test_migrations"
    asyncio.run(recreate_database(name))
    url = database_url(name)
    cfg = alembic_config(url)

    command.upgrade(cfg, "head")
    assert TABLES <= asyncio.run(table_names(url))

    command.downgrade(cfg, "base")
    assert not TABLES & asyncio.run(table_names(url))

    command.upgrade(cfg, "head")
    command.check(cfg)  # models and schema agree
