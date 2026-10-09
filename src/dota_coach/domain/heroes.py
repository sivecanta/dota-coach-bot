"""Hero catalog: id/name lookup and tolerant name resolution (English and Ukrainian).

Resolution order: exact name or alias, then unique-or-ambiguous prefix ("phantom"), then fuzzy
match for typos.
"""

import re
from collections.abc import Iterable, Mapping
from importlib import resources

import yaml
from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

from dota_coach.domain.models import Hero

FUZZY_CUTOFF = 80.0
FUZZY_MIN_LENGTH = 4  # shorter queries must match exactly, or "ax" would guess
FUZZY_CLEAR_GAP = 10.0  # best match must beat the next hero by this much to count as certain

_NON_WORD = re.compile(r"[\W_]+")


class Resolution(BaseModel):
    """`hero` is set when the match is certain. Otherwise `candidates` lists the plausible heroes
    (ambiguous input); both empty means the name is unknown."""

    hero: Hero | None = None
    candidates: list[Hero] = Field(default_factory=list)


def _key(text: str) -> str:
    """Lowercase, drop punctuation and spaces: "Anti-Mage" == "anti mage" == "antimage"."""
    return _NON_WORD.sub("", text.casefold())


def load_aliases() -> dict[str, list[str]]:
    text = resources.files("dota_coach.domain").joinpath("hero_aliases.yaml").read_text("utf-8")
    return {name: [str(a) for a in aliases] for name, aliases in yaml.safe_load(text).items()}


class HeroCatalog:
    def __init__(self, heroes: Iterable[Hero], aliases: Mapping[str, list[str]] | None = None):
        self._by_id = {hero.id: hero for hero in heroes}
        by_name = {hero.localized_name: hero for hero in self._by_id.values()}
        self._index: dict[str, set[int]] = {}
        for hero in self._by_id.values():
            self._add(hero.localized_name, hero)
            self._add(hero.short_name, hero)
        for name, names in (aliases or {}).items():
            if target := by_name.get(name):
                for alias in names:
                    self._add(alias, target)

    def _add(self, name: str, hero: Hero) -> None:
        self._index.setdefault(_key(name), set()).add(hero.id)

    def __len__(self) -> int:
        return len(self._by_id)

    def all(self) -> list[Hero]:
        return sorted(self._by_id.values(), key=lambda h: h.localized_name)

    def get(self, hero_id: int) -> Hero | None:
        return self._by_id.get(hero_id)

    def name(self, hero_id: int) -> str:
        """Display name; falls back to a readable placeholder for unknown (new) heroes."""
        hero = self._by_id.get(hero_id)
        return hero.localized_name if hero else f"Hero #{hero_id}"

    def resolve(self, query: str) -> Resolution:
        key = _key(query)
        if not key:
            return Resolution()
        if ids := self._index.get(key):
            return self._result(sorted(ids))
        if len(key) < FUZZY_MIN_LENGTH:
            return Resolution()
        prefixed = sorted({i for k, ids in self._index.items() if k.startswith(key) for i in ids})
        if prefixed:
            return self._result(prefixed)
        scored: dict[int, float] = {}
        for match, score, _ in process.extract(
            key, list(self._index), scorer=fuzz.ratio, score_cutoff=FUZZY_CUTOFF, limit=8
        ):
            for hero_id in self._index[match]:
                scored.setdefault(hero_id, score)
        ranked = sorted(scored, key=lambda i: -scored[i])
        if len(ranked) > 1 and scored[ranked[0]] - scored[ranked[1]] < FUZZY_CLEAR_GAP:
            return self._result(ranked[:3])
        return self._result(ranked[:1])

    def _result(self, ids: list[int]) -> Resolution:
        heroes = [self._by_id[i] for i in ids]
        if len(heroes) == 1:
            return Resolution(hero=heroes[0])
        return Resolution(candidates=heroes)
