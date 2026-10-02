import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dota_coach.storage.repositories import CacheRepository

_MATCH = re.compile(r"^/matches/\d+$")
_FOREVER = timedelta(days=3650)


@dataclass(frozen=True)
class Cached:
    payload: Any
    fresh: bool  # False means expired: usable only as a stale fallback


class CacheBackend(Protocol):
    async def get(self, key: str, *, hot: bool = False) -> Cached | None: ...

    async def set(self, key: str, payload: Any, ttl: timedelta, *, hot: bool = False) -> None: ...


def ttl_for(path: str, payload: Any) -> timedelta:
    """How long a response stays fresh."""
    if path == "/heroes" or path.startswith("/constants/"):
        return timedelta(days=7)
    if path in ("/heroStats", "/benchmarks"):
        return timedelta(hours=12)
    if _MATCH.match(path):
        # A finished, parsed match never changes; an unparsed one may be parsed later.
        parsed = isinstance(payload, dict) and payload.get("version") is not None
        return _FOREVER if parsed else timedelta(minutes=10)
    if path.startswith("/players/"):
        return timedelta(minutes=3)
    return timedelta(minutes=5)


def is_hot(path: str) -> bool:
    """Hot entries (constants) are also kept in the in-process LRU."""
    return path == "/heroes" or path.startswith("/constants/")


def cache_key(path: str, params: dict[str, Any]) -> str:
    query = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return f"opendota:{path}?{query}" if query else f"opendota:{path}"


class PostgresCache:
    """TTL cache in the `cache` table, with a small in-process LRU for hot entries."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        memory_size: int = 64,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._memory_size = memory_size
        self._now = now
        self._memory: OrderedDict[str, tuple[datetime, Any]] = OrderedDict()

    def _remember(self, key: str, payload: Any, expires_at: datetime) -> None:
        self._memory[key] = (expires_at, payload)
        self._memory.move_to_end(key)
        while len(self._memory) > self._memory_size:
            self._memory.popitem(last=False)

    async def get(self, key: str, *, hot: bool = False) -> Cached | None:
        now = self._now()
        hit = self._memory.get(key)
        if hit is not None and hit[0] > now:
            self._memory.move_to_end(key)
            return Cached(hit[1], True)
        async with self._sessions() as session:
            entry = await CacheRepository(session).get(key, include_expired=True)
        if entry is None:
            return None
        fresh = entry.expires_at > now
        if fresh and hot:
            self._remember(key, entry.payload, entry.expires_at)
        return Cached(entry.payload, fresh)

    async def set(self, key: str, payload: Any, ttl: timedelta, *, hot: bool = False) -> None:
        expires_at = self._now() + ttl
        async with self._sessions() as session:
            await CacheRepository(session).set(key, payload, expires_at)
            await session.commit()
        if hot:
            self._remember(key, payload, expires_at)
