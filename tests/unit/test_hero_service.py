from typing import cast

from dota_coach.clients.opendota import OpenDotaClient
from dota_coach.clients.opendota.client import Fetched
from dota_coach.clients.opendota.models import Hero
from dota_coach.services.heroes import load_catalog
from tests.helpers import load_fixture


class FakeClient:
    async def heroes(self) -> Fetched[list[Hero]]:
        return Fetched([Hero.model_validate(h) for h in load_fixture("heroes")])


async def test_load_catalog_from_fixture() -> None:
    catalog = await load_catalog(cast(OpenDotaClient, FakeClient()))
    assert len(catalog) == len(load_fixture("heroes"))
    assert catalog.resolve("am").hero is not None
    assert catalog.name(1) == "Anti-Mage"
