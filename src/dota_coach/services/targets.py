"""Resolving who a command is about: "me", a nickname, an account id or a replied-to user."""

from collections.abc import Sequence
from dataclasses import dataclass

from dota_coach.services.players import parse_account_id

MAX_NICKNAME = 20
_ME_WORDS = {"me", "я", "my"}


class TargetError(Exception):
    """The message is safe to show to the user."""


@dataclass(frozen=True)
class RosterEntry:
    account_id: int
    nickname: str | None


@dataclass(frozen=True)
class Target:
    account_id: int
    label: str


def clean_nickname(text: str) -> str:
    """Nicknames are single tokens so commands like `/nick old new` stay unambiguous."""
    return "_".join(text.split())[:MAX_NICKNAME]


def unique_nickname(base: str, taken: Sequence[str | None]) -> str:
    used = {t.casefold() for t in taken if t}
    base = clean_nickname(base) or "player"
    candidate, n = base, 2
    while candidate.casefold() in used:
        candidate = f"{base[: MAX_NICKNAME - len(str(n)) - 1]}_{n}"
        n += 1
    return candidate


def find_by_nickname(text: str, players: Sequence[RosterEntry]) -> RosterEntry | None:
    wanted = text.strip().casefold()
    return next((p for p in players if p.nickname and p.nickname.casefold() == wanted), None)


def resolve_target(
    text: str,
    *,
    me: int | None,
    replied: int | None,
    players: Sequence[RosterEntry],
) -> Target:
    """`text` empty means the replied-to user if any, otherwise the caller.

    `replied` is the linked account of the user whose message was replied to, if known.
    """
    text = text.strip()
    if not text:
        if replied is not None:
            return Target(replied, _label(replied, players))
        return _me(me)
    if text.casefold() in _ME_WORDS:
        return _me(me)
    if entry := find_by_nickname(text, players):
        return Target(entry.account_id, entry.nickname or str(entry.account_id))
    if (account_id := parse_account_id(text)) is not None:
        return Target(account_id, _label(account_id, players))
    raise TargetError(f"I don't know «{text}». Use /roster for nicknames, or give an account id.")


def looks_like_target(text: str, players: Sequence[RosterEntry]) -> bool:
    """Whether `text` names a person (as opposed to, say, a hero)."""
    text = text.strip()
    return (
        text.casefold() in _ME_WORDS
        or find_by_nickname(text, players) is not None
        or parse_account_id(text) is not None
    )


def _me(me: int | None) -> Target:
    if me is None:
        raise TargetError("You haven't linked a Dota account yet. Use /link in a private chat.")
    return Target(me, "you")


def _label(account_id: int, players: Sequence[RosterEntry]) -> str:
    entry = next((p for p in players if p.account_id == account_id), None)
    return entry.nickname if entry and entry.nickname else str(account_id)
