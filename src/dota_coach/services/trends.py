"""Hero pool and recent-form reports."""

from typing import Literal

from pydantic import BaseModel

from dota_coach.clients.opendota import OpenDotaClient
from dota_coach.clients.opendota.models import PlayerHero, RecentMatch
from dota_coach.domain.heroes import HeroCatalog
from dota_coach.domain.rules import did_win

MIN_SAMPLE = 5  # games needed before a hero win rate counts as meaningful
POOL_SIZE = 8
FORM_WINDOW = 10  # recentMatches returns up to 20 games: last 10 vs previous 10
FORM_DELTA = 0.15  # win-rate change that counts as a real trend

Direction = Literal["improving", "flat", "declining", "unknown"]


class HeroRecord(BaseModel):
    hero: str
    games: int
    wins: int

    @property
    def winrate(self) -> float:
        return self.wins / self.games if self.games else 0.0


class HeroPoolReport(BaseModel):
    total_games: int
    top: list[HeroRecord]  # most played
    best: HeroRecord | None  # best win rate among heroes with MIN_SAMPLE+ games
    worst: HeroRecord | None
    stale: bool = False


class HeroDetail(BaseModel):
    hero: str
    games: int
    wins: int
    with_games: int
    with_wins: int
    against_games: int
    against_wins: int
    last_played: int | None
    small_sample: bool
    stale: bool = False


class FormWindow(BaseModel):
    games: int
    wins: int
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    avg_gpm: float
    avg_xpm: float

    @property
    def winrate(self) -> float:
        return self.wins / self.games if self.games else 0.0


class FormReport(BaseModel):
    recent: FormWindow
    previous: FormWindow | None
    direction: Direction
    stale: bool = False


async def hero_pool(
    client: OpenDotaClient, catalog: HeroCatalog, account_id: int
) -> HeroPoolReport:
    fetched = await client.player_heroes(account_id)
    played = [h for h in fetched.data if h.games > 0]
    records = [_record(h, catalog) for h in played]
    ranked = [r for r in records if r.games >= MIN_SAMPLE]
    return HeroPoolReport(
        total_games=sum(r.games for r in records),
        top=sorted(records, key=lambda r: -r.games)[:POOL_SIZE],
        best=max(ranked, key=lambda r: (r.winrate, r.games), default=None),
        worst=min(ranked, key=lambda r: (r.winrate, -r.games), default=None),
        stale=fetched.stale,
    )


async def hero_detail(
    client: OpenDotaClient, catalog: HeroCatalog, account_id: int, hero_id: int
) -> HeroDetail:
    fetched = await client.player_heroes(account_id)
    row = next((h for h in fetched.data if h.hero_id == hero_id), PlayerHero(hero_id=hero_id))
    return HeroDetail(
        hero=catalog.name(hero_id),
        games=row.games,
        wins=row.win,
        with_games=row.with_games,
        with_wins=row.with_win,
        against_games=row.against_games,
        against_wins=row.against_win,
        last_played=row.last_played or None,
        small_sample=row.games < MIN_SAMPLE,
        stale=fetched.stale,
    )


async def recent_form(client: OpenDotaClient, account_id: int) -> FormReport | None:
    """None when there are no visible matches."""
    fetched = await client.recent_matches(account_id)
    if not fetched.data:
        return None
    return build_form(fetched.data, stale=fetched.stale)


def build_form(matches: list[RecentMatch], *, stale: bool = False) -> FormReport:
    """`matches` is newest first."""
    recent = _window(matches[:FORM_WINDOW])
    older = matches[FORM_WINDOW : FORM_WINDOW * 2]
    previous = _window(older) if older else None
    return FormReport(
        recent=recent, previous=previous, direction=_direction(recent, previous), stale=stale
    )


def _direction(recent: FormWindow, previous: FormWindow | None) -> Direction:
    if previous is None or recent.games < MIN_SAMPLE or previous.games < MIN_SAMPLE:
        return "unknown"
    delta = recent.winrate - previous.winrate
    if delta >= FORM_DELTA:
        return "improving"
    if delta <= -FORM_DELTA:
        return "declining"
    return "flat"


def _window(matches: list[RecentMatch]) -> FormWindow:
    n = len(matches)

    def avg(values: list[int | None]) -> float:
        present = [v for v in values if v is not None]
        return sum(present) / len(present) if present else 0.0

    wins = sum(
        1 for m in matches if m.player_slot is not None and did_win(m.player_slot, m.radiant_win)
    )
    return FormWindow(
        games=n,
        wins=wins,
        avg_kills=avg([m.kills for m in matches]),
        avg_deaths=avg([m.deaths for m in matches]),
        avg_assists=avg([m.assists for m in matches]),
        avg_gpm=avg([m.gold_per_min for m in matches]),
        avg_xpm=avg([m.xp_per_min for m in matches]),
    )


def _record(row: PlayerHero, catalog: HeroCatalog) -> HeroRecord:
    return HeroRecord(hero=catalog.name(row.hero_id), games=row.games, wins=row.win)
