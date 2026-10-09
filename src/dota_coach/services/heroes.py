"""Builds the hero catalog from OpenDota's /heroes."""

from dota_coach.clients.opendota import OpenDotaClient
from dota_coach.domain.heroes import HeroCatalog, load_aliases
from dota_coach.domain.models import Hero


async def load_catalog(client: OpenDotaClient) -> HeroCatalog:
    fetched = await client.heroes()
    heroes = [
        Hero(
            id=h.id,
            name=h.name,
            localized_name=h.localized_name,
            primary_attr=h.primary_attr,
            attack_type=h.attack_type,
            roles=tuple(h.roles),
        )
        for h in fetched.data
    ]
    return HeroCatalog(heroes, load_aliases())
