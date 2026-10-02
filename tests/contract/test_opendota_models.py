"""Models vs. recorded real responses: assert the fields the code relies on."""

from typing import Any

from pydantic import TypeAdapter
from tests.helpers import load_fixture

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


def parse[T](model: type[T], name: str) -> T:
    return TypeAdapter(model).validate_python(load_fixture(name))


def parse_list[T](model: type[T], name: str) -> list[T]:
    return TypeAdapter(list[model]).validate_python(load_fixture(name))  # type: ignore[valid-type]


def test_search_results() -> None:
    results = parse_list(SearchResult, "search__pro")
    assert results
    assert all(isinstance(r.account_id, int) for r in results)
    assert results[0].personaname


def test_numbers_sent_as_strings_are_coerced() -> None:
    # Not seen in recorded data, but the spec types some counts as strings; accept both.
    assert SearchResult.model_validate({"account_id": "440785246"}).account_id == 440785246
    assert WinLoss.model_validate({"win": "3", "lose": "4"}).win == 3


def test_player_profile() -> None:
    player = parse(Player, "players__profile")
    assert player.profile is not None
    assert player.profile.account_id == 105248644
    assert isinstance(player.rank_tier, int)


def test_hidden_profile_has_no_rank() -> None:
    player = parse(Player, "players__hidden_profile")
    assert player.profile is not None
    assert player.rank_tier is None


def test_win_loss_ok_and_hidden() -> None:
    ok = parse(WinLoss, "players_wl__ok")
    assert ok.win > 0
    assert ok.lose > 0
    hidden = parse(WinLoss, "players_wl__hidden")
    assert (hidden.win, hidden.lose) == (0, 0)


def test_recent_matches() -> None:
    matches = parse_list(RecentMatch, "players_recent_matches__ok")
    first = matches[0]
    assert first.match_id > 0
    assert first.player_slot is not None
    assert first.radiant_win is not None
    assert first.hero_id is not None
    assert first.gold_per_min is not None


def test_recent_matches_hidden_is_empty() -> None:
    assert parse_list(RecentMatch, "players_recent_matches__hidden") == []


def test_player_heroes() -> None:
    heroes = parse_list(PlayerHero, "players_heroes__ok")
    assert heroes[0].games >= heroes[0].win > 0


def test_parsed_match_has_time_series() -> None:
    match = parse(Match, "matches__parsed")
    assert match.is_parsed
    assert len(match.players) == 10
    assert match.radiant_gold_adv
    assert match.radiant_xp_adv
    player = match.players[0]
    assert player.gold_t
    assert player.xp_t
    assert player.lh_t
    assert player.purchase_log
    assert player.purchase_log[0].key
    assert isinstance(player.is_radiant, bool)
    assert match.picks_bans


def test_unparsed_match_degrades_to_summary() -> None:
    match = parse(Match, "matches__unparsed")
    assert not match.is_parsed
    assert match.radiant_gold_adv is None
    assert len(match.players) == 10
    assert all(p.gold_t is None and p.purchase_log is None for p in match.players)
    assert any(p.account_id is None for p in match.players)  # anonymous players
    assert match.radiant_win is not None


def test_heroes() -> None:
    heroes = parse_list(Hero, "heroes")
    assert heroes[0].id == 1
    assert heroes[0].localized_name == "Anti-Mage"
    assert heroes[0].roles


def test_hero_stats_rank_brackets_are_collected() -> None:
    stats = parse_list(HeroStats, "hero_stats")[0]
    assert stats.localized_name == "Anti-Mage"
    assert set(stats.bracket_picks) == set(range(1, 9))
    assert set(stats.bracket_wins) == set(range(1, 9))
    assert stats.bracket_picks[4] > stats.bracket_wins[4] > 0
    assert stats.pub_pick > 0


def test_benchmarks() -> None:
    bench = parse(Benchmarks, "benchmarks__hero")
    assert bench.hero_id == 1
    points = bench.result["gold_per_min"]
    assert points[0].percentile == 0.1
    assert points[0].value > 0


def test_nulls_and_missing_fields_do_not_break_parsing() -> None:
    data: dict[str, Any] = {"id": 1, "name": "npc", "localized_name": "X", "roles": None}
    assert Hero.model_validate(data).roles == []
