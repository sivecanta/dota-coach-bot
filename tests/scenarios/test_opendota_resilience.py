"""Failure modes: rate limits, outages, missing data, secrets."""

import asyncio
from collections.abc import Callable
from datetime import timedelta

import httpx
import pytest
import respx
from tests.helpers import API, MemoryCache, Sleeps, load_fixture

from dota_coach.clients.opendota import (
    OpenDotaClient,
    OpenDotaError,
    OpenDotaNotFound,
    OpenDotaUnavailable,
)

Factory = Callable[..., OpenDotaClient]


async def test_429_then_success_honours_retry_after(
    respx_mock: respx.MockRouter, make_client: Factory, sleeps: Sleeps
) -> None:
    route = respx_mock.get(f"{API}/heroes").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json=load_fixture("heroes")),
        ]
    )
    result = await make_client().heroes()
    assert result.stale is False
    assert route.call_count == 2
    assert sleeps.delays == [2.0]


async def test_5xx_backs_off_exponentially(
    respx_mock: respx.MockRouter, make_client: Factory, sleeps: Sleeps
) -> None:
    respx_mock.get(f"{API}/heroes").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(502),
            httpx.Response(200, json=load_fixture("heroes")),
        ]
    )
    await make_client().heroes()
    assert sleeps.delays == [0.5, 1.0]  # backoff_base * 2**attempt, jitter fixed at 1.0


async def test_timeout_falls_back_to_stale_cache(
    respx_mock: respx.MockRouter, make_client: Factory, cache: MemoryCache
) -> None:
    client = make_client(max_attempts=3)
    respx_mock.get(f"{API}/heroes").respond(json=load_fixture("heroes"))
    await client.heroes()
    cache.expire_all()

    respx_mock.get(f"{API}/heroes").mock(side_effect=httpx.ReadTimeout("slow"))
    result = await client.heroes()
    assert result.stale is True
    assert result.data[0].localized_name == "Anti-Mage"


async def test_outage_without_cache_raises_unavailable(
    respx_mock: respx.MockRouter, make_client: Factory
) -> None:
    route = respx_mock.get(f"{API}/heroes").respond(503)
    with pytest.raises(OpenDotaUnavailable):
        await make_client(max_attempts=3).heroes()
    assert route.call_count == 3


async def test_404_is_not_retried(
    respx_mock: respx.MockRouter, make_client: Factory, sleeps: Sleeps
) -> None:
    route = respx_mock.get(f"{API}/players/0").respond(404, json={"error": "Not Found"})
    with pytest.raises(OpenDotaNotFound):
        await make_client().player(0)
    assert route.call_count == 1
    assert sleeps.delays == []


async def test_other_4xx_is_not_retried(respx_mock: respx.MockRouter, make_client: Factory) -> None:
    route = respx_mock.get(f"{API}/heroes").respond(400)
    with pytest.raises(OpenDotaError):
        await make_client().heroes()
    assert route.call_count == 1


async def test_hidden_profile_returns_empty_results(
    respx_mock: respx.MockRouter, make_client: Factory
) -> None:
    respx_mock.get(f"{API}/players/1").respond(json=load_fixture("players__hidden_profile"))
    respx_mock.get(f"{API}/players/1/recentMatches").respond(json=[])
    respx_mock.get(f"{API}/players/1/wl").respond(json=load_fixture("players_wl__hidden"))
    client = make_client()
    assert (await client.player(1)).data.rank_tier is None
    assert (await client.recent_matches(1)).data == []
    wl = (await client.win_loss(1)).data
    assert (wl.win, wl.lose) == (0, 0)


async def test_unexpected_shape_raises_and_is_not_cached(
    respx_mock: respx.MockRouter, make_client: Factory, cache: MemoryCache
) -> None:
    respx_mock.get(f"{API}/heroes").respond(json={"not": "a list"})
    with pytest.raises(OpenDotaError, match="unexpected response shape"):
        await make_client().heroes()
    assert cache.entries == {}


async def test_api_key_is_sent_but_never_cached_or_reported(
    respx_mock: respx.MockRouter, make_client: Factory, cache: MemoryCache
) -> None:
    ok = respx_mock.get(f"{API}/heroes").respond(json=load_fixture("heroes"))
    await make_client().heroes()
    assert ok.calls.last.request.url.params["api_key"] == "test-key"
    assert all("test-key" not in key for key in cache.entries)

    respx_mock.get(f"{API}/heroStats").respond(503)
    with pytest.raises(OpenDotaUnavailable) as exc:
        await make_client(max_attempts=1).hero_stats()
    assert "test-key" not in str(exc.value)


async def test_match_ttl_depends_on_parse_state(
    respx_mock: respx.MockRouter, make_client: Factory, cache: MemoryCache
) -> None:
    parsed = load_fixture("matches__parsed")
    unparsed = load_fixture("matches__unparsed")
    respx_mock.get(f"{API}/matches/{parsed['match_id']}").respond(json=parsed)
    respx_mock.get(f"{API}/matches/{unparsed['match_id']}").respond(json=unparsed)
    client = make_client()
    await client.match(parsed["match_id"])
    await client.match(unparsed["match_id"])
    ttls = {key.split("/")[-1]: ttl for key, ttl in cache.sets}
    assert ttls[str(parsed["match_id"])] > timedelta(days=365)
    assert ttls[str(unparsed["match_id"])] == timedelta(minutes=10)


async def test_concurrency_is_limited(respx_mock: respx.MockRouter, make_client: Factory) -> None:
    in_flight = 0
    peak = 0

    async def slow(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return httpx.Response(200, json=load_fixture("benchmarks__hero"))

    respx_mock.get(f"{API}/benchmarks").mock(side_effect=slow)
    client = make_client(max_concurrency=2)
    await asyncio.gather(*(client.benchmarks(i) for i in range(1, 7)))
    assert peak == 2
