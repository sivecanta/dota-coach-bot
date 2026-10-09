import pytest

from dota_coach.domain.formatting import (
    format_duration,
    format_kda,
    format_percent,
    format_winrate,
)
from dota_coach.domain.models import Bracket, Role, Team
from dota_coach.domain.rules import (
    barracks_standing,
    decode_rank_tier,
    did_win,
    lane_role_name,
    role_from_position,
    team_of_slot,
    towers_standing,
)


@pytest.mark.parametrize(
    ("slot", "team"),
    [(0, Team.RADIANT), (4, Team.RADIANT), (127, Team.RADIANT), (128, Team.DIRE), (132, Team.DIRE)],
)
def test_team_of_slot(slot: int, team: Team) -> None:
    assert team_of_slot(slot) is team


@pytest.mark.parametrize(
    ("slot", "radiant_win", "won"),
    [(0, True, True), (0, False, False), (128, True, False), (128, False, True), (3, None, None)],
)
def test_did_win(slot: int, radiant_win: bool | None, won: bool | None) -> None:
    assert did_win(slot, radiant_win) is won


def test_rank_tier_decodes_medal_and_stars() -> None:
    tier = decode_rank_tier(53)
    assert tier is not None
    assert (tier.bracket, tier.stars) == (Bracket.LEGEND, 3)
    assert str(tier) == "Legend 3"


def test_immortal_has_no_stars() -> None:
    tier = decode_rank_tier(80)
    assert tier is not None
    assert str(tier) == "Immortal"


@pytest.mark.parametrize("value", [None, 0, 9, 96, 16])
def test_rank_tier_unranked_or_invalid(value: int | None) -> None:
    assert decode_rank_tier(value) is None


def test_towers_bitmask() -> None:
    assert len(towers_standing(2047)) == 11
    assert towers_standing(0) == []
    assert towers_standing(None) == []
    assert towers_standing(0b11) == ["ancient bottom", "ancient top"]


def test_barracks_bitmask() -> None:
    assert len(barracks_standing(63)) == 6
    assert barracks_standing(0b100000) == ["top melee"]


def test_null_safe_roles() -> None:
    assert lane_role_name(None) is None
    assert lane_role_name(2) == "mid"
    assert lane_role_name(9) is None
    assert role_from_position(None) is None
    assert role_from_position(0) is None
    assert role_from_position(6) is None
    assert role_from_position(5) is Role.HARD_SUPPORT


def test_formatting() -> None:
    assert format_duration(2527) == "42:07"
    assert format_duration(3727) == "1:02:07"
    assert format_duration(None) == "-"
    assert format_kda(10, 2, 7) == "10/2/7"
    assert format_kda(10, None, 7) == "-"
    assert format_percent(0.617) == "62%"
    assert format_percent(0.617, 1) == "61.7%"
    assert format_percent(None) == "-"
    assert format_winrate(8, 13) == "62% (8/13)"
    assert format_winrate(0, 0) == "-"
