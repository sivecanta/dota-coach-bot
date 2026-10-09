"""Helpers shared by handlers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from dota_coach.bot import presenter
from dota_coach.clients.opendota import OpenDotaClient
from dota_coach.clients.opendota.models import SearchResult
from dota_coach.services.players import parse_account_id, search_players
from dota_coach.services.targets import RosterEntry, Target, resolve_target
from dota_coach.storage.repositories import ChatPlayerRepository, TgUserRepository

# Sends or edits a message: the same flow serves a command and a button press.
Reply = Callable[..., Awaitable[object]]  # called as send(text, reply_markup=...)


class LinkPick(CallbackData, prefix="lk"):
    user_id: int  # only this user may press the button
    account_id: int


class AddPick(CallbackData, prefix="ad"):
    user_id: int
    account_id: int


def typing(message: Message) -> ChatActionSender:
    assert message.bot is not None
    return ChatActionSender.typing(
        bot=message.bot, chat_id=message.chat.id, message_thread_id=message.message_thread_id
    )


def is_private(message: Message) -> bool:
    return message.chat.type == "private"


async def bot_username(bot: Bot) -> str:
    return (await bot.me()).username or ""


def candidates_keyboard(
    results: list[SearchResult], make_data: Callable[[int], CallbackData]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for result in results:
        builder.row(
            InlineKeyboardButton(
                text=presenter.candidate_label(result),
                callback_data=make_data(result.account_id).pack(),
            )
        )
    return builder.as_markup()


@dataclass(frozen=True)
class Lookup:
    account_id: int | None = None  # set when the input was an id or profile link
    results: list[SearchResult] = field(default_factory=list)  # otherwise: name search results


async def lookup(client: OpenDotaClient, text: str) -> Lookup:
    """An id or profile link resolves directly; anything else is searched by name."""
    if (account_id := parse_account_id(text)) is not None:
        return Lookup(account_id=account_id)
    return Lookup(results=await search_players(client, text.strip()))


async def roster_entries(session: AsyncSession, chat_id: int) -> list[RosterEntry]:
    players = await ChatPlayerRepository(session).list(chat_id)
    return [RosterEntry(p.account_id, p.nickname) for p in players]


async def target_from_message(session: AsyncSession, message: Message, text: str) -> Target:
    """Who a command is about. Raises TargetError with a user-facing message."""
    caller = message.from_user
    users = TgUserRepository(session)
    me = None
    if caller and (row := await users.get(caller.id)):
        me = row.account_id
    replied = None
    reply = message.reply_to_message
    if reply and reply.from_user and not reply.from_user.is_bot:
        if row := await users.get(reply.from_user.id):
            replied = row.account_id
    return resolve_target(
        text, me=me, replied=replied, players=await roster_entries(session, message.chat.id)
    )


def who(target: Target) -> str:
    return "You" if target.label == "you" else target.label
