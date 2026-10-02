import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dota_coach.clients.opendota import Cached

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
