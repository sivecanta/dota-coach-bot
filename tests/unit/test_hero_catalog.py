import pytest

from dota_coach.domain.heroes import HeroCatalog, load_aliases
from dota_coach.domain.models import Hero

NAMES = [
    "Anti-Mage",
    "Axe",
    "Earthshaker",
    "Earth Spirit",
    "Juggernaut",
    "Lina",
    "Phantom Assassin",
    "Phantom Lancer",
    "Pudge",
    "Queen of Pain",
    "Shadow Fiend",
    "Shadow Shaman",
    "Storm Spirit",
    "Tidehunter",
    "Windranger",
]
SHORT = {"Anti-Mage": "antimage", "Windranger": "windrunner"}


def make_catalog() -> HeroCatalog:
    heroes = [
        Hero(
            id=i,
            name="npc_dota_hero_" + SHORT.get(n, n.lower().replace(" ", "_").replace("-", "")),
            localized_name=n,
        )
        for i, n in enumerate(NAMES, start=1)
    ]
    return HeroCatalog(heroes, load_aliases())


@pytest.fixture(scope="module")
def catalog() -> HeroCatalog:
    return make_catalog()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("pa", "Phantom Assassin"),
        ("PA", "Phantom Assassin"),
        ("sf", "Shadow Fiend"),
        ("qop", "Queen of Pain"),
        ("Anti-Mage", "Anti-Mage"),
        ("anti mage", "Anti-Mage"),
        ("antimage", "Anti-Mage"),
        ("windrunner", "Windranger"),
        ("па", "Phantom Assassin"),
        ("антімаг", "Anti-Mage"),
        ("тайд", "Tidehunter"),
        ("Ліна", "Lina"),
    ],
)
def test_exact_and_alias(catalog: HeroCatalog, query: str, expected: str) -> None:
    result = catalog.resolve(query)
    assert result.hero is not None
    assert result.hero.localized_name == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("juggernat", "Juggernaut"),
        ("tidehunetr", "Tidehunter"),
        ("phantom assasin", "Phantom Assassin"),
    ],
)
def test_typos_resolve(catalog: HeroCatalog, query: str, expected: str) -> None:
    result = catalog.resolve(query)
    assert result.hero is not None
    assert result.hero.localized_name == expected


def test_shared_alias_is_ambiguous(catalog: HeroCatalog) -> None:
    result = catalog.resolve("es")
    assert result.hero is None
    assert {h.localized_name for h in result.candidates} == {"Earthshaker", "Earth Spirit"}


def test_close_names_return_candidates(catalog: HeroCatalog) -> None:
    result = catalog.resolve("phantom")
    assert result.hero is None
    assert {h.localized_name for h in result.candidates} >= {"Phantom Assassin", "Phantom Lancer"}


@pytest.mark.parametrize("query", ["", "   ", "zzzzzz", "xq", "ax"])
def test_unknown_returns_nothing(catalog: HeroCatalog, query: str) -> None:
    result = catalog.resolve(query)
    assert result.hero is None
    assert result.candidates == []


def test_lookup_by_id(catalog: HeroCatalog) -> None:
    assert catalog.name(2) == "Axe"
    assert catalog.name(9999) == "Hero #9999"
    assert catalog.get(9999) is None
    assert len(catalog) == len(NAMES)


def test_aliases_for_missing_heroes_are_ignored() -> None:
    catalog = HeroCatalog([], load_aliases())
    assert len(catalog) == 0
    assert catalog.resolve("pa").hero is None
