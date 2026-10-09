"""Finding and checking Dota accounts."""

import re
from dataclasses import dataclass

from dota_coach.clients.opendota import OpenDotaClient
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
