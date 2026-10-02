from collections.abc import AsyncIterator, Callable

import pytest

from dota_coach.clients.opendota import OpenDotaClient
from tests.helpers import MemoryCache, Sleeps


@pytest.fixture
def cache() -> MemoryCache:
    return MemoryCache()


@pytest.fixture
def sleeps() -> Sleeps:
    return Sleeps()


@pytest.fixture
async def make_client(
    cache: MemoryCache, sleeps: Sleeps
) -> AsyncIterator[Callable[..., OpenDotaClient]]:
    clients: list[OpenDotaClient] = []

    def factory(**kwargs: object) -> OpenDotaClient:
        options: dict[str, object] = {
            "api_key": "test-key",
            "sleep": sleeps,
            "jitter": lambda: 1.0,  # deterministic: full delay
        }
        client = OpenDotaClient(cache, **{**options, **kwargs})  # type: ignore[arg-type]
        clients.append(client)
        return client

    yield factory
    for client in clients:
        await client.aclose()
