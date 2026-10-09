"""Dispatcher wiring: middlewares, routers and the global error handler."""

import logging

from aiogram import Dispatcher, Router
from aiogram.types import BotCommand, ChatMemberUpdated, ErrorEvent
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dota_coach.bot.handlers import basic, link, roster, stats
from dota_coach.bot.middlewares import (
    DbSessionMiddleware,
    EnsureChatMiddleware,
    LogContextMiddleware,
    ThrottleMiddleware,
)
from dota_coach.clients.opendota import OpenDotaError, OpenDotaNotFound
from dota_coach.services.targets import TargetError

logger = logging.getLogger("dota_coach.bot")

COMMANDS = [
    BotCommand(command="link", description="Link your Dota account"),
    BotCommand(command="me", description="Your linked account"),
    BotCommand(command="last", description="Review of the latest match"),
    BotCommand(command="heroes", description="Hero pool or stats on one hero"),
    BotCommand(command="form", description="Recent form and trend"),
    BotCommand(command="roster", description="Players of this chat"),
    BotCommand(command="add", description="Add a player to the roster"),
    BotCommand(command="join", description="Add yourself to the roster"),
    BotCommand(command="help", description="What I can do"),
]


def user_message(exc: Exception) -> str:
    """The text a user sees for an exception that escaped a handler."""
    if isinstance(exc, TargetError):
        return str(exc)
    if isinstance(exc, OpenDotaNotFound):
        return "OpenDota doesn't know that player or match."
    if isinstance(exc, OpenDotaError):
        return "OpenDota is not answering right now. Try again in a minute."
    return "Something went wrong on my side. Try again later."


def build_dispatcher(
    sessions: async_sessionmaker[AsyncSession], throttle_interval: float = 1.0
) -> Dispatcher:
    dp = Dispatcher()
    dp.update.outer_middleware(DbSessionMiddleware(sessions))
    dp.update.outer_middleware(LogContextMiddleware())
    dp.message.outer_middleware(ThrottleMiddleware(throttle_interval))
    dp.message.outer_middleware(EnsureChatMiddleware())
    dp.callback_query.outer_middleware(EnsureChatMiddleware())

    # link's FSM text handler is registered before the commands so a name is not mistaken for one
    dp.include_routers(basic.router, link.router, roster.router, stats.router, _events())
    dp.errors.register(on_error)
    return dp


def _events() -> Router:
    router = Router(name="events")

    @router.my_chat_member()
    async def membership(event: ChatMemberUpdated, session: AsyncSession) -> None:
        logger.info(
            "bot membership changed",
            extra={"new_status": event.new_chat_member.status, "chat_type": event.chat.type},
        )

    return router


async def on_error(event: ErrorEvent) -> bool:
    exc = event.exception
    if isinstance(exc, Exception):
        if isinstance(exc, TargetError | OpenDotaError):
            logger.warning("handled error: %s", type(exc).__name__)
        else:
            logger.error("unhandled error", exc_info=exc)
        text = user_message(exc)
    else:
        text = user_message(Exception())
    update = event.update
    if update.message:
        await update.message.answer(text)
    elif update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
    return True
