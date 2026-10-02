from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from dota_coach.clients.opendota import PostgresCache
from dota_coach.storage.models import CacheEntry


@pytest.fixture
async def sessions(migrated_db_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # PostgresCache commits on its own, so these tests clean up instead of rolling back.
    engine = create_async_engine(migrated_db_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    async with factory() as s:
        await s.execute(delete(CacheEntry))
        await s.commit()
    await engine.dispose()


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now


async def test_miss_fresh_and_stale(sessions: async_sessionmaker[AsyncSession]) -> None:
    clock = Clock()
    cache = PostgresCache(sessions, now=clock)
    assert await cache.get("k") is None

    await cache.set("k", {"a": 1}, timedelta(minutes=5))
    hit = await cache.get("k")
    assert hit is not None
    assert (hit.payload, hit.fresh) == ({"a": 1}, True)

    clock.now += timedelta(minutes=6)
    stale = await cache.get("k")
    assert stale is not None
    assert (stale.payload, stale.fresh) == ({"a": 1}, False)


async def test_hot_entries_are_served_from_memory(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    cache = PostgresCache(sessions)
    await cache.set("hot", [1, 2], timedelta(days=7), hot=True)
    await cache.set("cold", [3], timedelta(days=7))
    async with sessions() as s:
        await s.execute(delete(CacheEntry))  # drop DB rows; memory must still answer for "hot"
        await s.commit()
    hot = await cache.get("hot", hot=True)
    assert hot is not None
    assert hot.payload == [1, 2]
    assert await cache.get("cold") is None


async def test_memory_lru_evicts_oldest(sessions: async_sessionmaker[AsyncSession]) -> None:
    cache = PostgresCache(sessions, memory_size=2)
    for key in ("a", "b", "c"):
        await cache.set(key, key, timedelta(days=7), hot=True)
    async with sessions() as s:
        await s.execute(delete(CacheEntry))
        await s.commit()
    assert await cache.get("a") is None  # evicted from memory, gone from the DB
    assert await cache.get("c") is not None
