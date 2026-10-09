"""Pure helpers that decode OpenDota's packed fields. See .project/OPENDOTA.md."""

from dota_coach.domain.models import Bracket, RankTier, Role, Team

# Bit positions as documented by OpenDota; a set bit means the building is still standing.
_TOWER_BITS = (
    "ancient bottom",
    "ancient top",
    "bottom T3",
    "bottom T2",
    "bottom T1",
    "middle T3",
    "middle T2",
    "middle T1",
    "top T3",
    "top T2",
    "top T1",
)
_BARRACKS_BITS = (
    "bottom ranged",
    "bottom melee",
    "middle ranged",
    "middle melee",
    "top ranged",
    "top melee",
)
_LANE_ROLES = {1: "safe lane", 2: "mid", 3: "off lane", 4: "jungle"}


def team_of_slot(player_slot: int) -> Team:
    """Slots 0-127 are Radiant, 128-255 are Dire."""
    return Team.DIRE if player_slot >= 128 else Team.RADIANT


def did_win(player_slot: int, radiant_win: bool | None) -> bool | None:
    """None when the match result is unknown."""
    if radiant_win is None:
        return None
    return (team_of_slot(player_slot) is Team.RADIANT) == radiant_win


def decode_rank_tier(rank_tier: int | None) -> RankTier | None:
    """Tens digit is the medal (1-8), ones digit the stars. None for unranked or invalid."""
    if not rank_tier:
        return None
    medal, stars = divmod(rank_tier, 10)
    if not 1 <= medal <= len(Bracket) or stars > 5:
        return None
    return RankTier(bracket=Bracket(medal), stars=stars)


def towers_standing(mask: int | None) -> list[str]:
    return _standing(mask, _TOWER_BITS)


def barracks_standing(mask: int | None) -> list[str]:
    return _standing(mask, _BARRACKS_BITS)


def _standing(mask: int | None, names: tuple[str, ...]) -> list[str]:
    if mask is None:
        return []
    return [name for bit, name in enumerate(names) if mask >> bit & 1]


def lane_role_name(lane_role: int | None) -> str | None:
    return _LANE_ROLES.get(lane_role) if lane_role is not None else None


def role_from_position(position: int | None) -> Role | None:
    """`position_est` may be null or out of range; never guess."""
    if position is None or not 1 <= position <= len(Role):
        return None
    return Role(position)
