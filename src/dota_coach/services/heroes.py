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


class CatalogProvider:
    """Loads the hero catalog on first use, so the bot can start while OpenDota is down."""

    def __init__(self, client: OpenDotaClient) -> None:
        self._client = client
        self._catalog: HeroCatalog | None = None

    async def get(self) -> HeroCatalog:
        if self._catalog is None:
            self._catalog = await load_catalog(self._client)
        return self._catalog
