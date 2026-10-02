import asyncio
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from dota_coach.config import load_settings

TEST_DB = "dota_test"


def _base_url() -> URL:
    return make_url(load_settings().database_url.get_secret_value())


async def recreate_database(name: str) -> None:
    url = _base_url()
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database="postgres",
        timeout=3,
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


def alembic_config(db_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def database_url(name: str) -> str:
    return _base_url().set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def migrated_db_url() -> Iterator[str]:
    try:
        asyncio.run(recreate_database(TEST_DB))
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Postgres is not reachable ({exc}); start it with `make up`")
    url = database_url(TEST_DB)
    command.upgrade(alembic_config(url), "head")
    yield url


@pytest.fixture
async def session(migrated_db_url: str) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is rolled back after the test."""
    engine = create_async_engine(migrated_db_url, poolclass=NullPool)
    async with engine.connect() as conn:
        outer = await conn.begin()
        async with AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as s:
            yield s
        await outer.rollback()
    await engine.dispose()
