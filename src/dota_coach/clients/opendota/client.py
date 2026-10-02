import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from dota_coach.clients.opendota.cache import CacheBackend, Cached, cache_key, is_hot, ttl_for
from dota_coach.clients.opendota.errors import (
    OpenDotaError,
    OpenDotaNotFound,
    OpenDotaUnavailable,
)
from dota_coach.clients.opendota.models import (
    Benchmarks,
    Hero,
    HeroStats,
    Match,
    Player,
    PlayerHero,
    RecentMatch,
    SearchResult,
    WinLoss,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opendota.com/api"
_MAX_RETRY_AFTER = 30.0


@dataclass(frozen=True)
class Fetched[T]:
    data: T
    stale: bool = False  # True: served from an expired cache because the API failed


class OpenDotaClient:
    """The single gateway to OpenDota: cache, concurrency limit, backoff, defensive parsing."""

    def __init__(
        self,
        cache: CacheBackend,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 15.0,
        max_concurrency: int = 4,
        max_attempts: int = 4,
        backoff_base: float = 0.5,
        backoff_cap: float = 8.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._cache = cache
        self._api_key = api_key
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._slots = asyncio.Semaphore(max_concurrency)
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._sleep = sleep
        self._jitter = jitter

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- transport -------------------------------------------------------------------------

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(float(retry_after), _MAX_RETRY_AFTER)
            except ValueError:
                pass
        ceiling = min(self._backoff_cap, self._backoff_base * 2.0**attempt)
        return ceiling * (0.5 + 0.5 * self._jitter())

    async def _request(self, path: str, params: dict[str, Any]) -> Any:
        query = dict(params)
        if self._api_key:
            query["api_key"] = self._api_key
        reason = "no attempt made"
        for attempt in range(self._max_attempts):
            retry_after: str | None = None
            try:
                async with self._slots:
                    response = await self._http.get(path, params=query)
            except httpx.TransportError as exc:  # timeouts, connection errors
                reason = type(exc).__name__
            else:
                status = response.status_code
                if status == 200:
                    return response.json()
                if status == 404:
                    raise OpenDotaNotFound(f"not found: {path}")
                if status != 429 and status < 500:
                    raise OpenDotaError(f"unexpected status {status} for {path}")
                reason = f"status {status}"
                retry_after = response.headers.get("Retry-After")
            if attempt + 1 < self._max_attempts:
                delay = self._delay(attempt, retry_after)
                logger.warning("opendota %s failed (%s), retry in %.1fs", path, reason, delay)
                await self._sleep(delay)
        raise OpenDotaUnavailable(
            f"{path} unavailable after {self._max_attempts} attempts: {reason}"
        )

    # --- cache + parsing -------------------------------------------------------------------

    @staticmethod
    def _parse[T](adapter: TypeAdapter[T], payload: Any, path: str) -> T:
        try:
            return adapter.validate_python(payload)
        except ValidationError as exc:
            raise OpenDotaError(f"unexpected response shape for {path}") from exc

    async def _get[T](
        self, path: str, adapter: TypeAdapter[T], params: dict[str, Any] | None = None
    ) -> Fetched[T]:
        params = params or {}
        key = cache_key(path, params)
        hot = is_hot(path)
        cached: Cached | None = await self._cache.get(key, hot=hot)
        if cached is not None and cached.fresh:
            try:
                return Fetched(self._parse(adapter, cached.payload, path))
            except OpenDotaError:
                logger.warning("ignoring cached %s: unexpected shape", path)
        try:
            payload = await self._request(path, params)
        except OpenDotaUnavailable:
            if cached is not None:
                logger.warning("serving stale cache for %s", path)
                return Fetched(self._parse(adapter, cached.payload, path), stale=True)
            raise
        data = self._parse(adapter, payload, path)
        await self._cache.set(key, payload, ttl_for(path, payload), hot=hot)
        return Fetched(data)

    # --- endpoints -------------------------------------------------------------------------

    async def health(self) -> bool:
        try:
            await self._request("/health", {})
        except OpenDotaError:
            return False
        return True

    async def search(self, query: str) -> Fetched[list[SearchResult]]:
        return await self._get("/search", _SEARCH, {"q": query})

    async def player(self, account_id: int) -> Fetched[Player]:
        return await self._get(f"/players/{account_id}", _PLAYER)

    async def win_loss(self, account_id: int) -> Fetched[WinLoss]:
        return await self._get(f"/players/{account_id}/wl", _WIN_LOSS)

    async def recent_matches(self, account_id: int) -> Fetched[list[RecentMatch]]:
        return await self._get(f"/players/{account_id}/recentMatches", _RECENT)

    async def player_heroes(self, account_id: int) -> Fetched[list[PlayerHero]]:
        return await self._get(f"/players/{account_id}/heroes", _PLAYER_HEROES)

    async def match(self, match_id: int) -> Fetched[Match]:
        return await self._get(f"/matches/{match_id}", _MATCH)

    async def heroes(self) -> Fetched[list[Hero]]:
        return await self._get("/heroes", _HEROES)

    async def hero_stats(self) -> Fetched[list[HeroStats]]:
        return await self._get("/heroStats", _HERO_STATS)

    async def benchmarks(self, hero_id: int) -> Fetched[Benchmarks]:
        return await self._get("/benchmarks", _BENCHMARKS, {"hero_id": hero_id})

    async def constants(self, resource: str) -> Fetched[dict[str, Any]]:
        return await self._get(f"/constants/{resource}", _RAW_DICT)


_SEARCH = TypeAdapter(list[SearchResult])
_PLAYER = TypeAdapter(Player)
_WIN_LOSS = TypeAdapter(WinLoss)
_RECENT = TypeAdapter(list[RecentMatch])
_PLAYER_HEROES = TypeAdapter(list[PlayerHero])
_MATCH = TypeAdapter(Match)
_HEROES = TypeAdapter(list[Hero])
_HERO_STATS = TypeAdapter(list[HeroStats])
_BENCHMARKS = TypeAdapter(Benchmarks)
_RAW_DICT = TypeAdapter(dict[str, Any])
