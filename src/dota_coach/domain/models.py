"""Core domain types shared by every layer."""

from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Team(StrEnum):
    RADIANT = "radiant"
    DIRE = "dire"


class Role(IntEnum):
    """Dota positions 1-5."""

    CARRY = 1
    MID = 2
    OFFLANE = 3
    SOFT_SUPPORT = 4
    HARD_SUPPORT = 5


class Bracket(IntEnum):
    """Rank brackets, numbered as in OpenDota's heroStats (`1_pick` ... `8_pick`)."""

    HERALD = 1
    GUARDIAN = 2
    CRUSADER = 3
    ARCHON = 4
    LEGEND = 5
    ANCIENT = 6
    DIVINE = 7
    IMMORTAL = 8


class Hero(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str  # internal name, e.g. "npc_dota_hero_antimage"
    localized_name: str  # display name, e.g. "Anti-Mage"
    primary_attr: str | None = None
    attack_type: str | None = None
    roles: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def short_name(self) -> str:
        return self.name.removeprefix("npc_dota_hero_")


class RankTier(BaseModel):
    model_config = ConfigDict(frozen=True)

    bracket: Bracket
    stars: int  # 0-5 (Immortal has none)

    def __str__(self) -> str:
        label = self.bracket.name.capitalize()
        return f"{label} {self.stars}" if self.stars else label
