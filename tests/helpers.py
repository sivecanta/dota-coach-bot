import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dota_coach.clients.opendota import Cached, Fetched
from dota_coach.clients.opendota.models import (
    Benchmarks,
    Hero,
    Match,
    Player,
    PlayerHero,
    RecentMatch,
    SearchResult,
    WinLoss,
)

FIXTURES = Path(__file__).parent / "fixtures" / "opendota"
API = "https://api.opendota.com/api"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


class MemoryCache:
    """In-memory CacheBackend for client tests; the Postgres one has its own integration tests."""

    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=UTC)
        self.entries: dict[str, tuple[Any, datetime]] = {}
        self.sets: list[tuple[str, timedelta]] = []

    async def get(self, key: str, *, hot: bool = False) -> Cached | None:
        if key not in self.entries:
            return None
        payload, expires_at = self.entries[key]
        return Cached(payload, expires_at > self.now)

    async def set(self, key: str, payload: Any, ttl: timedelta, *, hot: bool = False) -> None:
        self.entries[key] = (payload, self.now + ttl)
        self.sets.append((key, ttl))

    def expire_all(self) -> None:
        self.now += timedelta(days=4000)


class Sleeps:
    """Replaces asyncio.sleep so retry tests run instantly and can assert the delays."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class FakeClient:
    """Serves recorded fixtures; just the calls the services make."""

    def __init__(self, *, hidden: bool = False) -> None:
        self.hidden = hidden

    async def search(self, query: str) -> Fetched[list[SearchResult]]:
        return Fetched([SearchResult.model_validate(r) for r in load_fixture("search__pro")])

    async def heroes(self) -> Fetched[list[Hero]]:
        return Fetched([Hero.model_validate(h) for h in load_fixture("heroes")])

    async def player(self, account_id: int) -> Fetched[Player]:
        name = "players__hidden_profile" if self.hidden else "players__profile"
        return Fetched(Player.model_validate(load_fixture(name)))

    async def win_loss(self, account_id: int) -> Fetched[WinLoss]:
        name = "players_wl__hidden" if self.hidden else "players_wl__ok"
        return Fetched(WinLoss.model_validate(load_fixture(name)))

    async def recent_matches(self, account_id: int) -> Fetched[list[RecentMatch]]:
        name = "players_recent_matches__hidden" if self.hidden else "players_recent_matches__ok"
        return Fetched([RecentMatch.model_validate(m) for m in load_fixture(name)])

    async def match(self, match_id: int) -> Fetched[Match]:
        return Fetched(Match.model_validate(load_fixture("matches__parsed")))

    async def benchmarks(self, hero_id: int) -> Fetched[Benchmarks]:
        return Fetched(Benchmarks.model_validate(load_fixture("benchmarks__hero")))

    async def player_heroes(self, account_id: int) -> Fetched[list[PlayerHero]]:
        return Fetched([PlayerHero.model_validate(h) for h in load_fixture("players_heroes__ok")])
