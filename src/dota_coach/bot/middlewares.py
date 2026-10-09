"""Per-update plumbing: DB session, chat row, logging context, throttling."""

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Chat, TelegramObject, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dota_coach import logging as log_context
from dota_coach.storage.repositories import ChatRepository

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware(BaseMiddleware):
    """One transaction per update: committed when the handler succeeds, rolled back otherwise."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self._sessions() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                raise
            await session.commit()
            return result


class LogContextMiddleware(BaseMiddleware):
    """Puts chat, user and a request id on every log line of this update."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        chat: Chat | None = data.get("event_chat")
        user: User | None = data.get("event_from_user")
        tokens = (
            log_context.chat_id.set(chat.id if chat else None),
            log_context.user_id.set(user.id if user else None),
            log_context.request_id.set(uuid.uuid4().hex[:8]),
        )
        try:
            return await handler(event, data)
        finally:
            log_context.chat_id.reset(tokens[0])
            log_context.user_id.reset(tokens[1])
            log_context.request_id.reset(tokens[2])


class EnsureChatMiddleware(BaseMiddleware):
    """Makes sure a `chats` row exists before handlers touch per-chat data."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        chat: Chat | None = data.get("event_chat")
        session: AsyncSession | None = data.get("session")
        if chat and session:
            await ChatRepository(session).ensure(chat.id, chat.type)
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Drops messages from a user who sends faster than one per `interval` seconds."""

    def __init__(self, interval: float = 1.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._interval = interval
        self._clock = clock
        self._last: dict[int, float] = {}

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        now = self._clock()
        if now - self._last.get(user.id, float("-inf")) < self._interval:
            return None
        self._last[user.id] = now
        if len(self._last) > 10_000:  # keep memory bounded
            cutoff = now - self._interval
            self._last = {k: v for k, v in self._last.items() if v > cutoff}
        return await handler(event, data)


__all__ = [
    "DbSessionMiddleware",
    "EnsureChatMiddleware",
    "LogContextMiddleware",
    "ThrottleMiddleware",
]
