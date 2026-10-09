"""Drives the real dispatcher (middlewares, filters, handlers, Postgres) with a fake Telegram and
recorded OpenDota data."""

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from aiogram import Dispatcher
from aiogram.methods import SendMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from dota_coach.bot.app import build_dispatcher
from dota_coach.bot.handlers import basic, link, roster, stats
from dota_coach.services.heroes import CatalogProvider
from dota_coach.storage.repositories import TgUserRepository
from tests.bot_helpers import Chatter, FakeSession, make_bot
from tests.helpers import FakeClient

GROUP = -1001


@pytest.fixture
async def sessions(migrated_db_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_db_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:  # flows commit for real, so clean up after
        for table in ("chat_players", "tg_users", "chats"):
            await conn.exec_driver_sql(f"DELETE FROM {table}")
    await engine.dispose()


@pytest.fixture
def dp(sessions: async_sessionmaker[AsyncSession]) -> Dispatcher:
    # Module-level routers can join only one dispatcher; detach them so each test builds its own.
    for module in (basic, link, roster, stats):
        module.router._parent_router = None
    dispatcher = build_dispatcher(sessions, throttle_interval=0)
    client = FakeClient()
    dispatcher.workflow_data.update(client=client, catalogs=CatalogProvider(cast(Any, client)))
    return dispatcher


@pytest.fixture
def telegram() -> tuple[Any, FakeSession]:
    return make_bot()


def button_data(session: FakeSession, index: int = 0) -> str:
    markup = session.last().reply_markup
    return str(markup.inline_keyboard[index][0].callback_data)


async def sent_messages(session: FakeSession) -> list[Any]:
    return [c for c in session.calls if isinstance(c, SendMessage)]


async def test_help_in_private_and_group(dp: Dispatcher, telegram: tuple[Any, FakeSession]) -> None:
    bot, fake = telegram
    await Chatter(dp, bot, user_id=1).say("/help")
    assert "/link" in fake.texts()[-1]
    await Chatter(dp, bot, user_id=1, chat_id=GROUP).say("/help@coach_bot")
    assert len(fake.texts()) == 2
    await Chatter(dp, bot, user_id=1, chat_id=GROUP).say("/help@other_bot")
    assert len(fake.texts()) == 2  # commands for other bots are ignored


async def test_link_flow_with_search(dp: Dispatcher, telegram: tuple[Any, FakeSession]) -> None:
    bot, fake = telegram
    user = Chatter(dp, bot, user_id=7)
    await user.say("/link")
    assert "Send your Dota name" in fake.texts()[-1]
    await user.say("miracle")
    assert "Which one is you?" in fake.texts()[-1]
    data = button_data(fake)

    stranger = Chatter(dp, bot, user_id=8)
    await stranger.press(data, on=_as_message(fake))  # someone else pressing is refused
    assert not any("Linked" in t for t in fake.texts())

    await user.press(data, on=_as_message(fake))
    assert "Linked" in fake.texts()[-1]

    await user.say("/me")
    assert "Linked account" in fake.texts()[-1]
    await user.say("/unlink")
    assert fake.texts()[-1] == "Unlinked."


async def test_link_by_id_in_dm_and_deeplink_from_group(
    dp: Dispatcher, telegram: tuple[Any, FakeSession], sessions: async_sessionmaker[AsyncSession]
) -> None:
    bot, fake = telegram
    await Chatter(dp, bot, user_id=7, chat_id=GROUP).say("/link")
    button = fake.last().reply_markup.inline_keyboard[0][0]
    assert button.url == "https://t.me/coach_bot?start=link"

    dm = Chatter(dp, bot, user_id=7)
    await dm.say("/start link")
    assert "Send your Dota name" in fake.texts()[-1]
    await dm.say("https://www.opendota.com/players/123456")
    assert "Linked" in fake.texts()[-1]
    async with sessions() as s:
        row = await TgUserRepository(s).get(7)
    assert row is not None
    assert row.account_id == 123456


async def test_stats_commands_for_linked_user(
    dp: Dispatcher, telegram: tuple[Any, FakeSession]
) -> None:
    bot, fake = telegram
    user = Chatter(dp, bot, user_id=7)
    await user.say("/last")
    assert "haven't linked" in fake.texts()[-1]

    await user.say("/link 123456")
    await user.say("/last")
    assert "last match" in fake.texts()[-1]
    assert "KDA" in fake.texts()[-1]
    await user.say("/heroes")
    assert "hero pool" in fake.texts()[-1]
    await user.say("/heroes am")
    assert "Anti-Mage" in fake.texts()[-1]
    await user.say("/form")
    assert "recent form" in fake.texts()[-1]
    await user.say("/heroes nonsensehero")
    assert "don't know a hero" in fake.texts()[-1]


async def test_group_roster(dp: Dispatcher, telegram: tuple[Any, FakeSession]) -> None:
    bot, fake = telegram
    owner = Chatter(dp, bot, user_id=7, chat_id=GROUP)
    await owner.say("/roster")
    assert "empty" in fake.texts()[-1]

    await owner.say("/add 111")
    assert "Added" in fake.texts()[-1]
    await owner.say("/add 111")
    assert "Already" in fake.texts()[-1]
    await owner.say("/roster")
    assert "111" in fake.texts()[-1]

    nickname = fake.texts()[-1].split("•")[1].split("</b>")[0].replace("<b>", "").strip()
    await owner.say(f"/nick {nickname} Dima")
    await owner.say("/role Dima 3")
    assert "3 (offlane)" in fake.texts()[-1]
    await owner.say("/last Dima")
    assert "Dima" in fake.texts()[-1]

    # another group has its own roster
    await Chatter(dp, bot, user_id=7, chat_id=-1002).say("/roster")
    assert "empty" in fake.texts()[-1]

    await owner.say("/remove Dima")
    assert "Removed" in fake.texts()[-1]
    await owner.say("/remove Dima")
    assert "No such nickname" in fake.texts()[-1]


async def test_errors_become_friendly_messages(
    dp: Dispatcher, telegram: tuple[Any, FakeSession]
) -> None:
    bot, fake = telegram
    await Chatter(dp, bot, user_id=7).say("/last nobody")
    assert "don't know" in fake.texts()[-1]


def _as_message(fake: FakeSession) -> Any:
    from aiogram.types import Chat, Message

    from tests.bot_helpers import BOT, NOW

    sent = fake.last()
    return Message(
        message_id=500, date=NOW, chat=Chat(id=7, type="private"), text=sent.text, from_user=BOT
    )
