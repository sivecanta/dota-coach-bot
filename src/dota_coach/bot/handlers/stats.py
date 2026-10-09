"""Read-only stats commands: /last, /heroes, /form."""

from collections.abc import Sequence

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from dota_coach.bot import presenter
from dota_coach.bot.handlers.common import roster_entries, target_from_message, typing, who
from dota_coach.clients.opendota import OpenDotaClient
from dota_coach.services.heroes import CatalogProvider
from dota_coach.services.match_review import review_last_match
from dota_coach.services.targets import RosterEntry, looks_like_target
from dota_coach.services.trends import hero_detail, hero_pool, recent_form

router = Router(name="stats")

NO_MATCHES = "No visible matches for {who}.\n\n" + presenter.HIDDEN_PROFILE_HELP


@router.message(Command("last"))
async def last(
    message: Message,
    command: CommandObject,
    client: OpenDotaClient,
    catalogs: CatalogProvider,
    session: AsyncSession,
) -> None:
    target = await target_from_message(session, message, command.args or "")
    async with typing(message):
        review = await review_last_match(client, await catalogs.get(), target.account_id)
    if review is None:
        await message.answer(NO_MATCHES.format(who=who(target)))
        return
    await message.answer(presenter.review(review, who(target)))


@router.message(Command("form"))
async def form(
    message: Message,
    command: CommandObject,
    client: OpenDotaClient,
    session: AsyncSession,
) -> None:
    target = await target_from_message(session, message, command.args or "")
    async with typing(message):
        report = await recent_form(client, target.account_id)
    if report is None:
        await message.answer(NO_MATCHES.format(who=who(target)))
        return
    await message.answer(presenter.form(report, who(target)))


def split_heroes_args(args: str, roster_players: Sequence[RosterEntry]) -> tuple[str, str]:
    """Splits "[who] [hero]" into (who, hero). Either may be empty.

    The first word is a target if it names a person (me, a nickname, an id); otherwise the whole
    text is a hero name, which may contain spaces ("anti mage").
    """
    words = args.split()
    if not words:
        return "", ""
    if looks_like_target(words[0], roster_players):
        return words[0], " ".join(words[1:])
    return "", " ".join(words)


@router.message(Command("heroes"))
async def heroes(
    message: Message,
    command: CommandObject,
    client: OpenDotaClient,
    catalogs: CatalogProvider,
    session: AsyncSession,
) -> None:
    players = await roster_entries(session, message.chat.id)
    target_text, hero_text = split_heroes_args(command.args or "", players)
    target = await target_from_message(session, message, target_text)
    catalog = await catalogs.get()
    resolution = catalog.resolve(hero_text) if hero_text else None
    if resolution is not None and resolution.hero is None:
        if resolution.candidates:
            names = ", ".join(h.localized_name for h in resolution.candidates)
            await message.answer(f"Which hero: {names}?")
        else:
            await message.answer(f"I don't know a hero called «{hero_text}».")
        return
    async with typing(message):
        if resolution is not None and resolution.hero is not None:
            detail = await hero_detail(client, catalog, target.account_id, resolution.hero.id)
            text = presenter.hero_detail(detail, who(target))
        else:
            text = presenter.hero_pool(
                await hero_pool(client, catalog, target.account_id), who(target)
            )
    await message.answer(text)
