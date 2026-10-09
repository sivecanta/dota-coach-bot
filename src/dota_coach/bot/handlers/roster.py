"""Per-chat roster: linked members and friends added by hand."""

from aiogram import Bot, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from dota_coach.bot import presenter
from dota_coach.bot.handlers.common import (
    AddPick,
    Reply,
    candidates_keyboard,
    is_private,
    lookup,
    roster_entries,
    typing,
)
from dota_coach.clients.opendota import OpenDotaClient
from dota_coach.domain.models import Role
from dota_coach.services.players import check_profile
from dota_coach.services.targets import (
    clean_nickname,
    find_by_nickname,
    unique_nickname,
)
from dota_coach.storage.repositories import ChatPlayerRepository, TgUserRepository

router = Router(name="roster")


@router.message(Command("roster"))
async def show_roster(message: Message, session: AsyncSession) -> None:
    players = await ChatPlayerRepository(session).list(message.chat.id)
    linked = await TgUserRepository(session).linked_accounts([p.account_id for p in players])
    rows = [
        (p.nickname or str(p.account_id), p.account_id, p.default_role, p.account_id in linked)
        for p in players
    ]
    await message.answer(presenter.roster(rows))


@router.message(Command("add"))
async def add_command(
    message: Message, command: CommandObject, client: OpenDotaClient, session: AsyncSession
) -> None:
    assert message.from_user is not None
    if not command.args:
        await message.answer(
            "Usage: /add &lt;name, account id or profile link&gt;. "
            "To add yourself, link your account and use /join."
        )
        return
    user_id = message.from_user.id
    async with typing(message):
        found = await lookup(client, command.args)
        if found.account_id is not None:
            await add_player(
                message.answer, session, client, message.chat.id, user_id, found.account_id
            )
            return
    if not found.results:
        await message.answer("Nobody found with that name. Try another spelling or send an id.")
        return
    await message.answer(
        presenter.candidates(found.results, "Who do you mean? Press the number."),
        reply_markup=candidates_keyboard(
            found.results, lambda a: AddPick(user_id=user_id, account_id=a)
        ),
    )


@router.callback_query(AddPick.filter())
async def add_pick(
    callback: CallbackQuery,
    callback_data: AddPick,
    client: OpenDotaClient,
    session: AsyncSession,
) -> None:
    if callback.from_user.id != callback_data.user_id:
        await callback.answer("This menu belongs to someone else.", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer("This menu has expired. Send /add again.", show_alert=True)
        return
    await callback.answer()
    message = callback.message
    await add_player(
        message.edit_text,
        session,
        client,
        message.chat.id,
        callback.from_user.id,
        callback_data.account_id,
    )


async def add_player(
    send: Reply,
    session: AsyncSession,
    client: OpenDotaClient,
    chat_id: int,
    added_by: int,
    account_id: int,
) -> None:
    repo = ChatPlayerRepository(session)
    existing = await repo.get(chat_id, account_id)
    if existing:
        await send(f"Already in the roster as <b>{existing.nickname}</b>.")
        return
    status = await check_profile(client, account_id)
    nickname = unique_nickname(status.name, [p.nickname for p in await repo.list(chat_id)])
    await repo.add(chat_id, account_id, nickname, None, added_by)
    note = "" if status.has_matches else "\n\n" + presenter.HIDDEN_PROFILE_HELP.split(". ")[0] + "."
    await send(f"Added <b>{nickname}</b> (<code>{account_id}</code>).{note}")


@router.message(Command("join"))
async def join(message: Message, client: OpenDotaClient, session: AsyncSession) -> None:
    assert message.from_user is not None
    row = await TgUserRepository(session).get(message.from_user.id)
    if row is None or row.account_id is None:
        await message.answer("Link your account first: /link (in a private chat).")
        return
    await add_player(
        message.answer, session, client, message.chat.id, message.from_user.id, row.account_id
    )


async def _can_remove(
    message: Message, bot: Bot, session: AsyncSession, added_by: int | None, account_id: int
) -> bool:
    assert message.from_user is not None
    user_id = message.from_user.id
    if is_private(message) or added_by == user_id:
        return True
    me = await TgUserRepository(session).get(user_id)
    if me is not None and me.account_id == account_id:
        return True
    member = await bot.get_chat_member(message.chat.id, user_id)
    return member.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR)


@router.message(Command("remove"))
async def remove(message: Message, command: CommandObject, bot: Bot, session: AsyncSession) -> None:
    if not command.args:
        await message.answer("Usage: /remove &lt;nickname&gt;")
        return
    entries = await roster_entries(session, message.chat.id)
    entry = find_by_nickname(command.args, entries)
    if entry is None:
        await message.answer("No such nickname. See /roster.")
        return
    repo = ChatPlayerRepository(session)
    row = await repo.get(message.chat.id, entry.account_id)
    added_by = row.added_by if row else None
    if not await _can_remove(message, bot, session, added_by, entry.account_id):
        await message.answer("Only who added them, they themselves, or a chat admin can remove.")
        return
    await repo.remove(message.chat.id, entry.account_id)
    await message.answer(f"Removed <b>{entry.nickname}</b>.")


@router.message(Command("nick"))
async def nick(message: Message, command: CommandObject, session: AsyncSession) -> None:
    parts = (command.args or "").split()
    if len(parts) != 2:
        await message.answer("Usage: /nick &lt;old&gt; &lt;new&gt;")
        return
    old, new = parts
    entries = await roster_entries(session, message.chat.id)
    entry = find_by_nickname(old, entries)
    if entry is None:
        await message.answer("No such nickname. See /roster.")
        return
    new = clean_nickname(new)
    taken = find_by_nickname(new, entries)
    if taken is not None and taken.account_id != entry.account_id:
        await message.answer("That nickname is already used in this chat.")
        return
    await ChatPlayerRepository(session).rename(message.chat.id, entry.account_id, new)
    await message.answer(f"Renamed to <b>{new}</b>.")


@router.message(Command("role"))
async def role(message: Message, command: CommandObject, session: AsyncSession) -> None:
    parts = (command.args or "").split()
    if len(parts) != 2 or parts[1] not in {str(r.value) for r in Role}:
        await message.answer("Usage: /role &lt;nickname&gt; &lt;1-5&gt;")
        return
    entry = find_by_nickname(parts[0], await roster_entries(session, message.chat.id))
    if entry is None:
        await message.answer("No such nickname. See /roster.")
        return
    await ChatPlayerRepository(session).set_role(message.chat.id, entry.account_id, int(parts[1]))
    await message.answer(f"<b>{entry.nickname}</b> plays {presenter.role_label(int(parts[1]))}.")
