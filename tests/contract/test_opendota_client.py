"""Client endpoints against recorded responses served by respx (never the network)."""

from collections.abc import Callable

import httpx
import respx
from tests.helpers import API, MemoryCache, load_fixture

from dota_coach.clients.opendota import OpenDotaClient

Factory = Callable[..., OpenDotaClient]


async def test_search(respx_mock: respx.MockRouter, make_client: Factory) -> None:
    route = respx_mock.get(f"{API}/search").respond(json=load_fixture("search__pro"))
    result = await make_client().search("Miracle")
    assert result.stale is False
    assert result.data[0].account_id == 440785246
    request = route.calls.last.request
    assert request.url.params["q"] == "Miracle"
    assert request.url.params["api_key"] == "test-key"


async def test_player_and_win_loss(respx_mock: respx.MockRouter, make_client: Factory) -> None:
    respx_mock.get(f"{API}/players/105248644").respond(json=load_fixture("players__profile"))
    respx_mock.get(f"{API}/players/105248644/wl").respond(json=load_fixture("players_wl__ok"))
    client = make_client()
    assert (await client.player(105248644)).data.profile is not None
    assert (await client.win_loss(105248644)).data.win > 0


async def test_recent_matches_and_hero_pool(
    respx_mock: respx.MockRouter, make_client: Factory
) -> None:
    recent = load_fixture("players_recent_matches__ok")
    respx_mock.get(f"{API}/players/105248644/recentMatches").respond(json=recent)
    respx_mock.get(f"{API}/players/105248644/heroes").respond(
        json=load_fixture("players_heroes__ok")
    )
    client = make_client()
    assert len((await client.recent_matches(105248644)).data) == len(recent)
    assert (await client.player_heroes(105248644)).data[0].games > 0


async def test_match(respx_mock: respx.MockRouter, make_client: Factory) -> None:
    fixture = load_fixture("matches__parsed")
    respx_mock.get(f"{API}/matches/{fixture['match_id']}").respond(json=fixture)
    match = (await make_client().match(fixture["match_id"])).data
    assert match.is_parsed
    assert len(match.players) == 10


async def test_heroes_stats_benchmarks_constants(
    respx_mock: respx.MockRouter, make_client: Factory
) -> None:
    respx_mock.get(f"{API}/heroes").respond(json=load_fixture("heroes"))
    respx_mock.get(f"{API}/heroStats").respond(json=load_fixture("hero_stats"))
    bench = respx_mock.get(f"{API}/benchmarks").respond(json=load_fixture("benchmarks__hero"))
    respx_mock.get(f"{API}/constants/heroes").respond(json=load_fixture("constants_heroes"))
    client = make_client()
    assert (await client.heroes()).data[0].localized_name == "Anti-Mage"
    assert (await client.hero_stats()).data[0].bracket_picks
    assert (await client.benchmarks(1)).data.hero_id == 1
    assert bench.calls.last.request.url.params["hero_id"] == "1"
    assert "1" in (await client.constants("heroes")).data


async def test_health(respx_mock: respx.MockRouter, make_client: Factory) -> None:
    respx_mock.get(f"{API}/health").respond(json=load_fixture("health"))
    assert await make_client().health() is True


async def test_health_false_when_down(respx_mock: respx.MockRouter, make_client: Factory) -> None:
    respx_mock.get(f"{API}/health").mock(side_effect=httpx.ConnectError("boom"))
    assert await make_client(max_attempts=2).health() is False


async def test_second_call_is_served_from_cache(
    respx_mock: respx.MockRouter, make_client: Factory, cache: MemoryCache
) -> None:
    route = respx_mock.get(f"{API}/heroes").respond(json=load_fixture("heroes"))
    client = make_client()
    await client.heroes()
    await client.heroes()
    assert route.call_count == 1
    assert len(cache.sets) == 1
