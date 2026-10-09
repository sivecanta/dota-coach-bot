"""Summary of a player's most recent match, with benchmark percentiles."""

from pydantic import BaseModel, Field

from dota_coach.clients.opendota import OpenDotaClient, OpenDotaError
from dota_coach.clients.opendota.models import Benchmarks, Match, RecentMatch
from dota_coach.domain.heroes import HeroCatalog
from dota_coach.domain.rules import did_win, lane_role_name
from dota_coach.services.benchmarks import percentile_of

# review stat -> benchmark key
_BENCHMARKED = {
    "gpm": "gold_per_min",
    "xpm": "xp_per_min",
    "last_hits": "last_hits_per_min",
    "hero_damage": "hero_damage_per_min",
}


class MatchReview(BaseModel):
    match_id: int
    hero: str
    won: bool | None
    duration: int | None
    started_at: int | None
    kills: int | None
    deaths: int | None
    assists: int | None
    gpm: int | None
    xpm: int | None
    last_hits: int | None
    hero_damage: int | None
    tower_damage: int | None
    hero_healing: int | None
    lane: str | None
    is_parsed: bool
    radiant_score: int | None = None
    dire_score: int | None = None
    percentiles: dict[str, int] = Field(default_factory=dict)  # keys of _BENCHMARKED
    stale: bool = False


async def review_last_match(
    client: OpenDotaClient, catalog: HeroCatalog, account_id: int
) -> MatchReview | None:
    """None when the player has no visible matches (hidden profile or no games)."""
    recent = await client.recent_matches(account_id)
    if not recent.data:
        return None
    last = recent.data[0]
    stale = recent.stale

    match: Match | None = None
    try:
        fetched = await client.match(last.match_id)
        match, stale = fetched.data, stale or fetched.stale
    except OpenDotaError:
        pass  # the recent-match row is enough for a summary

    lane_role = last.lane_role
    if match:
        mine = next((p for p in match.players if p.account_id == account_id), None)
        if mine and mine.lane_role is not None:
            lane_role = mine.lane_role

    percentiles: dict[str, int] = {}
    if last.hero_id is not None and last.duration:
        try:
            benchmarks = await client.benchmarks(last.hero_id)
            stale = stale or benchmarks.stale
            percentiles = _percentiles(last, benchmarks.data)
        except OpenDotaError:
            pass

    return MatchReview(
        match_id=last.match_id,
        hero=catalog.name(last.hero_id) if last.hero_id is not None else "Unknown hero",
        won=did_win(last.player_slot, last.radiant_win) if last.player_slot is not None else None,
        duration=last.duration,
        started_at=last.start_time,
        kills=last.kills,
        deaths=last.deaths,
        assists=last.assists,
        gpm=last.gold_per_min,
        xpm=last.xp_per_min,
        last_hits=last.last_hits,
        hero_damage=last.hero_damage,
        tower_damage=last.tower_damage,
        hero_healing=last.hero_healing,
        lane=lane_role_name(lane_role),
        is_parsed=match.is_parsed if match else last.version is not None,
        radiant_score=match.radiant_score if match else None,
        dire_score=match.dire_score if match else None,
        percentiles=percentiles,
        stale=stale,
    )


def _percentiles(last: RecentMatch, benchmarks: Benchmarks) -> dict[str, int]:
    minutes = (last.duration or 0) / 60
    values = {
        "gpm": last.gold_per_min,
        "xpm": last.xp_per_min,
        "last_hits": _per_minute(last.last_hits, minutes),
        "hero_damage": _per_minute(last.hero_damage, minutes),
    }
    out: dict[str, int] = {}
    for stat, key in _BENCHMARKED.items():
        value = values[stat]
        if value is None:
            continue
        pct = percentile_of(value, benchmarks.result.get(key, []))
        if pct is not None:
            out[stat] = pct
    return out


def _per_minute(total: int | None, minutes: float) -> float | None:
    return total / minutes if total is not None and minutes > 0 else None
