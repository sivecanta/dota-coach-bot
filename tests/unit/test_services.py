from typing import Any

import pytest

from dota_coach.clients.opendota import Fetched, OpenDotaNotFound
from dota_coach.clients.opendota.models import (
    BenchmarkPoint,
    Player,
    RecentMatch,
)
from dota_coach.domain.heroes import HeroCatalog
from dota_coach.domain.models import Hero
from dota_coach.services.benchmarks import percentile_of
from dota_coach.services.match_review import review_last_match
from dota_coach.services.players import STEAM64_BASE, check_profile, parse_account_id
from dota_coach.services.targets import (
    RosterEntry,
    TargetError,
    resolve_target,
    unique_nickname,
)
from dota_coach.services.trends import build_form, hero_detail, hero_pool
from tests.helpers import FakeClient, load_fixture


def client() -> Any:
    return FakeClient()


def catalog() -> HeroCatalog:
    rows: list[dict[str, Any]] = load_fixture("heroes")
    return HeroCatalog(
        Hero(id=r["id"], name=r["name"], localized_name=r["localized_name"]) for r in rows
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("123456", 123456),
        (str(STEAM64_BASE + 123456), 123456),
        ("https://www.opendota.com/players/123456", 123456),
        ("https://www.dotabuff.com/players/123456/matches", 123456),
        (f"https://steamcommunity.com/profiles/{STEAM64_BASE + 99}", 99),
        ("https://steamcommunity.com/id/vanity", None),
        ("Dendi", None),
        ("0", None),
        ("", None),
    ],
)
def test_parse_account_id(text: str, expected: int | None) -> None:
    assert parse_account_id(text) == expected


def test_percentile_interpolates_and_clamps() -> None:
    raw = [(0.1, 100), (0.5, 300), (0.9, 500)]
    points = [BenchmarkPoint(percentile=p, value=v) for p, v in raw]
    assert percentile_of(300, points) == 50
    assert percentile_of(400, points) == 70
    assert percentile_of(50, points) == 10
    assert percentile_of(9999, points) == 90
    assert percentile_of(1, []) is None


async def test_check_profile_visible() -> None:
    status = await check_profile(client(), 1)
    assert status.has_matches
    assert status.wins + status.losses > 0


async def test_check_profile_hidden() -> None:
    status = await check_profile(FakeClient(hidden=True), 1)  # type: ignore[arg-type]
    assert not status.has_matches
    assert status.wins == status.losses == 0


async def test_check_profile_unknown_id_propagates() -> None:
    class Missing(FakeClient):
        async def player(self, account_id: int) -> Fetched[Player]:
            raise OpenDotaNotFound("404")

    with pytest.raises(OpenDotaNotFound):
        await check_profile(Missing(), 1)  # type: ignore[arg-type]


async def test_review_last_match() -> None:
    review = await review_last_match(client(), catalog(), 1)
    assert review is not None
    first = load_fixture("players_recent_matches__ok")[0]
    assert review.match_id == first["match_id"]
    assert review.kills == first["kills"]
    assert review.is_parsed
    assert set(review.percentiles) == {"gpm", "xpm", "last_hits", "hero_damage"}
    assert all(0 <= v <= 99 for v in review.percentiles.values())


async def test_review_without_matches_is_none() -> None:
    assert await review_last_match(FakeClient(hidden=True), catalog(), 1) is None  # type: ignore[arg-type]


async def test_hero_pool_and_detail() -> None:
    report = await hero_pool(client(), catalog(), 1)
    rows = load_fixture("players_heroes__ok")
    assert report.total_games == sum(r["games"] for r in rows)
    assert report.top[0].games == max(r["games"] for r in rows)
    first = rows[0]["hero_id"]
    detail = await hero_detail(client(), catalog(), 1, first)
    assert detail.games == rows[0]["games"]
    missing = await hero_detail(client(), catalog(), 1, 99999)
    assert missing.games == 0
    assert missing.small_sample


def match(win: bool, k: int = 5) -> RecentMatch:
    return RecentMatch(
        match_id=1, player_slot=0, radiant_win=win, kills=k, deaths=2, assists=3,
        gold_per_min=500, xp_per_min=600,
    )  # fmt: skip


def games(*results: tuple[bool, int]) -> list[RecentMatch]:
    """games((True, 8), (False, 2)) -> 8 wins then 2 losses, newest first."""
    return [match(win) for win, count in results for _ in range(count)]


def test_form_direction_is_deterministic() -> None:
    improving = games((True, 8), (False, 2), (False, 8), (True, 2))
    assert build_form(improving).direction == "improving"
    declining = games((False, 8), (True, 2), (True, 8), (False, 2))
    assert build_form(declining).direction == "declining"
    flat = games((True, 5), (False, 5), (True, 5), (False, 5))
    assert build_form(flat).direction == "flat"
    assert build_form(games((True, 10))).direction == "unknown"  # nothing to compare with
    assert build_form(games((True, 10), (False, 3))).direction == "unknown"  # tiny earlier window


def test_form_averages() -> None:
    report = build_form([match(True, 10), match(False, 0)])
    assert report.recent.games == 2
    assert report.recent.wins == 1
    assert report.recent.avg_kills == 5


ROSTER = [RosterEntry(10, "Dima"), RosterEntry(20, "Kolya")]


def test_target_resolution() -> None:
    def resolve(text: str, **kw: Any) -> tuple[int, str]:
        t = resolve_target(text, me=kw.get("me", 1), replied=kw.get("replied"), players=ROSTER)
        return t.account_id, t.label

    assert resolve("") == (1, "you")
    assert resolve("me") == (1, "you")
    assert resolve("dima") == (10, "Dima")
    assert resolve("999") == (999, "999")
    assert resolve("20") == (20, "Kolya")
    assert resolve("", replied=10) == (10, "Dima")


def test_target_errors() -> None:
    with pytest.raises(TargetError, match="linked"):
        resolve_target("", me=None, replied=None, players=ROSTER)
    with pytest.raises(TargetError, match="Vasya"):
        resolve_target("Vasya", me=1, replied=None, players=ROSTER)


def test_unique_nickname() -> None:
    assert unique_nickname("Slava K", []) == "Slava_K"
    assert unique_nickname("Dima", ["dima"]) == "Dima_2"
    assert unique_nickname("Dima", ["Dima", "Dima_2"]) == "Dima_3"
    assert unique_nickname("   ", []) == "player"
