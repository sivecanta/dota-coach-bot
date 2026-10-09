"""Linking a Telegram user to a Dota account."""

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from dota_coach.bot import presenter
from dota_coach.bot.handlers.common import (
    LinkPick,
    Reply,
    bot_username,
    candidates_keyboard,
    is_private,
    lookup,
    typing,
)
from dota_coach.clients.opendota import OpenDotaClient, OpenDotaError
from dota_coach.services.heroes import CatalogProvider
from dota_coach.services.players import check_profile
from dota_coach.services.trends import HeroRecord, hero_pool
from dota_coach.storage.repositories import TgUserRepository

router = Router(name="link")

PROMPT = "Send your Dota name, Steam friend ID, or an OpenDota/Dotabuff profile link."


class LinkStates(StatesGroup):
    waiting_query = State()


async def begin_link(message: Message, state: FSMContext) -> None:
    """Start linking from /link or the group's «Continue in DM» button."""
    await state.set_state(LinkStates.waiting_query)
    await message.answer(PROMPT)


@router.message(Command("link"))
async def link_command(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    bot: Bot,
    client: OpenDotaClient,
    catalogs: CatalogProvider,
    session: AsyncSession,
) -> None:
    if not is_private(message):
        button = InlineKeyboardButton(
            text="Continue in private chat",
            url=f"https://t.me/{await bot_username(bot)}?start=link",
        )
        await message.answer(
            "Linking is done in a private chat, to keep this group clean.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
        )
        return
    if command.args:
        await state.clear()
        await search_and_offer(message, command.args, client, catalogs, session)
    else:
        await begin_link(message, state)


@router.message(StateFilter(LinkStates.waiting_query))
async def link_query(
    message: Message,
    state: FSMContext,
    client: OpenDotaClient,
    catalogs: CatalogProvider,
    session: AsyncSession,
) -> None:
    if not message.text or message.text.startswith("/"):
        return
    await state.clear()
    await search_and_offer(message, message.text, client, catalogs, session)


async def search_and_offer(
    message: Message,
    text: str,
    client: OpenDotaClient,
    catalogs: CatalogProvider,
    session: AsyncSession,
) -> None:
    assert message.from_user is not None
    user_id = message.from_user.id
    async with typing(message):
        found = await lookup(client, text)
        if found.account_id is not None:
            await finish_link(message.answer, session, client, catalogs, user_id, found.account_id)
            return
    if not found.results:
        await message.answer("Nobody found with that name. Try another spelling or send an id.")
        return
    await message.answer(
        presenter.candidates(found.results, "Which one is you? Press the number."),
        reply_markup=candidates_keyboard(
            found.results, lambda a: LinkPick(user_id=user_id, account_id=a)
        ),
    )


@router.callback_query(LinkPick.filter())
async def link_pick(
    callback: CallbackQuery,
    callback_data: LinkPick,
    client: OpenDotaClient,
    catalogs: CatalogProvider,
    session: AsyncSession,
) -> None:
    if callback.from_user.id != callback_data.user_id:
        await callback.answer("This menu belongs to someone else.", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer("This menu has expired. Send /link again.", show_alert=True)
        return
    await callback.answer()
    message = callback.message
    await finish_link(
        message.edit_text,
        session,
        client,
        catalogs,
        callback.from_user.id,
        callback_data.account_id,
    )


async def finish_link(
    send: Reply,
    session: AsyncSession,
    client: OpenDotaClient,
    catalogs: CatalogProvider,
    user_id: int,
    account_id: int,
) -> None:
    status = await check_profile(client, account_id)
    if not status.has_matches:
        builder = InlineKeyboardBuilder()
        pick = LinkPick(user_id=user_id, account_id=account_id)
        builder.button(text="Re-check", callback_data=pick)
        await send(
            f"{presenter.profile(status)}\n\n{presenter.HIDDEN_PROFILE_HELP}",
            reply_markup=builder.as_markup(),
        )
        return
    await TgUserRepository(session).link(user_id, account_id, status.name)
    top = await _top_heroes(client, catalogs, account_id)
    await send(f"✅ Linked.\n{presenter.profile(status, top=top)}")


async def _top_heroes(
    client: OpenDotaClient, catalogs: CatalogProvider, account_id: int
) -> list[HeroRecord] | None:
    """Nice-to-have extra: never let it block the answer."""
    try:
        return (await hero_pool(client, await catalogs.get(), account_id)).top[:3]
    except OpenDotaError:
        return None


@router.message(Command("me"))
async def me(
    message: Message, client: OpenDotaClient, catalogs: CatalogProvider, session: AsyncSession
) -> None:
    assert message.from_user is not None
    row = await TgUserRepository(session).get(message.from_user.id)
    if row is None or row.account_id is None:
        await message.answer("You haven't linked a Dota account. Use /link.")
        return
    async with typing(message):
        status = await check_profile(client, row.account_id)
        top = await _top_heroes(client, catalogs, row.account_id)
    await message.answer(presenter.profile(status, title="Linked account", top=top))


@router.message(Command("unlink"))
async def unlink(message: Message, session: AsyncSession) -> None:
    assert message.from_user is not None
    removed = await TgUserRepository(session).unlink(message.from_user.id)
    await message.answer("Unlinked." if removed else "You had no linked account.")
