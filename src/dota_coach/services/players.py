"""Finding and checking Dota accounts."""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime

from dota_coach.clients.opendota import OpenDotaClient, OpenDotaError
from dota_coach.clients.opendota.models import SearchResult
from dota_coach.domain.models import RankTier
from dota_coach.domain.rules import decode_rank_tier

STEAM64_BASE = 76561197960265728
MAX_CANDIDATES = 5

_URL_ID = re.compile(r"(?:players|profiles)/(\d+)")


def parse_account_id(text: str) -> int | None:
    """Steam32 id, Steam64 id, or a profile URL (OpenDota, Dotabuff, Steam /profiles/).

    Returns None for anything else, including Steam vanity URLs (/id/name), which need Steam's API.
    """
    text = text.strip()
    if match := _URL_ID.search(text):
        text = match.group(1)
    if not text.isdigit():
        return None
    value = int(text)
    if value >= STEAM64_BASE:
        value -= STEAM64_BASE
    return value if 0 < value < 2**32 else None


@dataclass(frozen=True)
class ProfileStatus:
    account_id: int
    name: str
    rank: RankTier | None
    wins: int
    losses: int
    has_matches: bool  # False for hidden profiles ("Expose public match data" is off)
    stale: bool = False


async def search_players(client: OpenDotaClient, query: str) -> list[SearchResult]:
    fetched = await client.search(query)
    return fetched.data[:MAX_CANDIDATES]


@dataclass(frozen=True)
class Candidate:
    """A search hit, enriched so users can tell similarly named accounts apart."""

    account_id: int
    name: str
    last_match_time: datetime | None
    rank: RankTier | None = None
    games: int | None = None  # None when the profile could not be fetched


async def describe_candidates(
    client: OpenDotaClient, results: list[SearchResult]
) -> list[Candidate]:
    async def describe(result: SearchResult) -> Candidate:
        base = Candidate(
            result.account_id, result.personaname or str(result.account_id), result.last_match_time
        )
        try:
            player, win_loss = await asyncio.gather(
                client.player(result.account_id), client.win_loss(result.account_id)
            )
        except OpenDotaError:
            return base
        return Candidate(
            base.account_id,
            base.name,
            base.last_match_time,
            rank=decode_rank_tier(player.data.rank_tier),
            games=win_loss.data.win + win_loss.data.lose,
        )

    return list(await asyncio.gather(*(describe(r) for r in results)))


async def check_profile(client: OpenDotaClient, account_id: int) -> ProfileStatus:
    """Raises OpenDotaNotFound for an unknown id."""
    player = await client.player(account_id)
    win_loss = await client.win_loss(account_id)
    recent = await client.recent_matches(account_id)
    profile = player.data.profile
    name = (profile.personaname or profile.name) if profile else None
    return ProfileStatus(
        account_id=account_id,
        name=name or str(account_id),
        rank=decode_rank_tier(player.data.rank_tier),
        wins=win_loss.data.win,
        losses=win_loss.data.lose,
        has_matches=bool(recent.data),
        stale=player.stale or win_loss.stale or recent.stale,
    )
