"""Defensive models for OpenDota responses.

The published spec is partly wrong (string-typed counts, nulls where lists are typed, duplicate
fields), so fields are optional or defaulted, numeric strings are coerced, nulls are dropped before
validation and unknown fields are ignored. Shapes were checked against recorded fixtures in
tests/fixtures/opendota/.
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v is not None}
        return data


class SearchResult(_Model):
    account_id: int
    personaname: str | None = None
    avatarfull: str | None = None
    last_match_time: datetime | None = None
    similarity: float | None = None


class PlayerProfile(_Model):
    account_id: int | None = None
    personaname: str | None = None
    name: str | None = None
    avatarfull: str | None = None
    last_login: datetime | None = None


class Player(_Model):
    profile: PlayerProfile | None = None
    rank_tier: int | None = None  # tens = rank, ones = stars
    leaderboard_rank: int | None = None
    computed_mmr: float | None = None


class WinLoss(_Model):
    win: int = 0
    lose: int = 0


class RecentMatch(_Model):
    match_id: int
    player_slot: int | None = None
    radiant_win: bool | None = None
    hero_id: int | None = None
    start_time: int | None = None
    duration: int | None = None
    game_mode: int | None = None
    lobby_type: int | None = None
    version: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    gold_per_min: int | None = None
    xp_per_min: int | None = None
    hero_damage: int | None = None
    tower_damage: int | None = None
    hero_healing: int | None = None
    last_hits: int | None = None
    lane_role: int | None = None
    average_rank: int | None = None


class PlayerHero(_Model):
    hero_id: int
    games: int = 0
    win: int = 0
    last_played: int | None = None
    with_games: int = 0
    with_win: int = 0
    against_games: int = 0
    against_win: int = 0


class PurchaseEntry(_Model):
    time: int
    key: str
    charges: int | None = None


class MatchPlayer(_Model):
    account_id: int | None = None  # null for anonymous players
    player_slot: int
    is_radiant: bool | None = Field(default=None, alias="isRadiant")
    hero_id: int | None = None
    personaname: str | None = None
    rank_tier: int | None = None
    lane_role: int | None = None  # may be null
    position_est: int | None = None  # may be null
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    level: int | None = None
    net_worth: int | None = None
    gold_per_min: int | None = None
    xp_per_min: int | None = None
    last_hits: int | None = None
    denies: int | None = None
    hero_damage: int | None = None
    tower_damage: int | None = None
    hero_healing: int | None = None
    win: int | None = None
    # time series and logs: only present in parsed matches
    gold_t: list[int] | None = None
    xp_t: list[int] | None = None
    lh_t: list[int] | None = None
    purchase_log: list[PurchaseEntry] | None = None


class PickBan(_Model):
    is_pick: bool
    hero_id: int
    team: int
    order: int


class Match(_Model):
    match_id: int
    start_time: int | None = None
    duration: int | None = None
    radiant_win: bool | None = None
    radiant_score: int | None = None
    dire_score: int | None = None
    game_mode: int | None = None
    lobby_type: int | None = None
    patch: int | None = None
    radiant_name: str | None = None
    dire_name: str | None = None
    version: int | None = None  # present only once the replay is parsed
    radiant_gold_adv: list[int] | None = None
    radiant_xp_adv: list[int] | None = None
    picks_bans: list[PickBan] | None = None
    players: list[MatchPlayer] = Field(default_factory=list)

    @property
    def is_parsed(self) -> bool:
        return self.version is not None


class Hero(_Model):
    id: int
    name: str
    localized_name: str
    primary_attr: str | None = None
    attack_type: str | None = None
    roles: list[str] = Field(default_factory=list)


_BRACKET_KEY = re.compile(r"^(\d+)_(pick|win)$")


class HeroStats(_Model):
    id: int
    localized_name: str
    pro_pick: int = 0
    pro_win: int = 0
    pro_ban: int = 0
    pub_pick: int = 0
    pub_win: int = 0
    bracket_picks: dict[int, int] = Field(default_factory=dict)  # rank bracket 1-8 -> picks
    bracket_wins: dict[int, int] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _collect_brackets(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        picks: dict[int, int] = {}
        wins: dict[int, int] = {}
        for key, value in data.items():
            match = _BRACKET_KEY.match(key)
            if match and value is not None:
                (picks if match.group(2) == "pick" else wins)[int(match.group(1))] = int(value)
        out["bracket_picks"] = picks
        out["bracket_wins"] = wins
        return out


class BenchmarkPoint(_Model):
    percentile: float
    value: float


class Benchmarks(_Model):
    hero_id: int
    result: dict[str, list[BenchmarkPoint]] = Field(default_factory=dict)
