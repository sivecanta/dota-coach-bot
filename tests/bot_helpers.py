"""A fake Telegram: records every API call the bot makes so flows can be asserted end to end."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    GetMe,
    SendChatAction,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import CallbackQuery, Chat, Message, Update, User

BOT = User(id=999, is_bot=True, first_name="Coach", username="coach_bot")
NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []
        self._next_id = 1000

    async def close(self) -> None:
        pass

    async def stream_content(  # type: ignore[override,empty-body]
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,  # noqa: ASYNC109 - signature is fixed by aiogram's BaseSession
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: int | None = None,  # noqa: ASYNC109 - signature is fixed by aiogram's BaseSession
    ) -> Any:
        self.calls.append(method)
        if isinstance(method, GetMe):
            return BOT
        if isinstance(method, SendMessage | EditMessageText):
            self._next_id += 1
            chat_id = getattr(method, "chat_id", 0) or 0
            return Message(
                message_id=self._next_id,
                date=NOW,
                chat=Chat(id=int(chat_id), type="private" if int(chat_id) > 0 else "supergroup"),
                text=method.text,
                from_user=BOT,
            )
        if isinstance(method, SendChatAction | AnswerCallbackQuery):
            return True
        return True

    def texts(self) -> list[str]:
        """Text of every message sent or edited, in order."""
        return [m.text for m in self.calls if isinstance(m, SendMessage | EditMessageText)]

    def last(self) -> Any:
        return next(m for m in reversed(self.calls) if isinstance(m, SendMessage | EditMessageText))


def make_bot() -> tuple[Bot, FakeSession]:
    session = FakeSession()
    return Bot("123456:TESTTOKEN", session=session), session


class Chatter:
    """Feeds updates from one user in one chat into a dispatcher."""

    def __init__(self, dp: Any, bot: Bot, *, user_id: int = 1, chat_id: int | None = None) -> None:
        self.dp, self.bot = dp, bot
        self.user = User(id=user_id, is_bot=False, first_name=f"User{user_id}")
        self.chat_id = user_id if chat_id is None else chat_id
        self._update_id = 0

    @property
    def chat(self) -> Chat:
        return Chat(id=self.chat_id, type="private" if self.chat_id > 0 else "supergroup")

    def _message(self, text: str, reply_to: Message | None = None) -> Message:
        self._update_id += 1
        entities = None
        if text.startswith("/"):
            from aiogram.types import MessageEntity

            entities = [MessageEntity(type="bot_command", offset=0, length=len(text.split()[0]))]
        return Message(
            message_id=self._update_id,
            date=NOW,
            chat=self.chat,
            from_user=self.user,
            text=text,
            entities=entities,
            reply_to_message=reply_to,
        )

    async def say(self, text: str, reply_to: Message | None = None) -> None:
        self._update_id += 1
        update = Update(update_id=self._update_id, message=self._message(text, reply_to))
        await self.dp.feed_update(self.bot, update)

    async def press(self, data: str, on: Message) -> None:
        self._update_id += 1
        query = CallbackQuery(
            id=str(self._update_id),
            from_user=self.user,
            chat_instance="x",
            message=on,
            data=data,
        )
        await self.dp.feed_update(self.bot, Update(update_id=self._update_id, callback_query=query))
