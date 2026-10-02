from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dota_coach.storage.models import CacheEntry, Chat, ChatPlayer, TgUser


class TgUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tg_user_id: int) -> TgUser | None:
        return await self._session.get(TgUser, tg_user_id)

    async def link(self, tg_user_id: int, account_id: int, nickname: str | None) -> None:
        stmt = insert(TgUser).values(
            tg_user_id=tg_user_id, account_id=account_id, nickname=nickname
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[TgUser.tg_user_id],
            set_={"account_id": stmt.excluded.account_id, "nickname": stmt.excluded.nickname},
        )
        await self._session.execute(stmt)


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, chat_id: int) -> Chat | None:
        return await self._session.get(Chat, chat_id)

    async def ensure(self, chat_id: int, chat_type: str) -> None:
        stmt = insert(Chat).values(chat_id=chat_id, type=chat_type).on_conflict_do_nothing()
        await self._session.execute(stmt)


class ChatPlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        chat_id: int,
        account_id: int,
        nickname: str | None,
        default_role: int | None,
        added_by: int | None,
    ) -> None:
        stmt = insert(ChatPlayer).values(
            chat_id=chat_id,
            account_id=account_id,
            nickname=nickname,
            default_role=default_role,
            added_by=added_by,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ChatPlayer.chat_id, ChatPlayer.account_id],
            set_={"nickname": stmt.excluded.nickname, "default_role": stmt.excluded.default_role},
        )
        await self._session.execute(stmt)

    async def list(self, chat_id: int) -> list[ChatPlayer]:
        result = await self._session.scalars(
            select(ChatPlayer).where(ChatPlayer.chat_id == chat_id).order_by(ChatPlayer.id)
        )
        return list(result)

    async def remove(self, chat_id: int, account_id: int) -> bool:
        result = await self._session.execute(
            delete(ChatPlayer).where(
                ChatPlayer.chat_id == chat_id, ChatPlayer.account_id == account_id
            )
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]


class CacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str, *, include_expired: bool = False) -> CacheEntry | None:
        stmt = select(CacheEntry).where(CacheEntry.key == key)
        if not include_expired:
            stmt = stmt.where(CacheEntry.expires_at > func.now())
        return await self._session.scalar(stmt)

    async def set(self, key: str, payload: Any, expires_at: datetime) -> None:
        stmt = insert(CacheEntry).values(key=key, payload=payload, expires_at=expires_at)
        stmt = stmt.on_conflict_do_update(
            index_elements=[CacheEntry.key],
            set_={"payload": stmt.excluded.payload, "expires_at": stmt.excluded.expires_at},
        )
        await self._session.execute(stmt)

    async def delete_expired(self) -> int:
        result = await self._session.execute(
            delete(CacheEntry).where(CacheEntry.expires_at <= func.now())
        )
        return int(result.rowcount)  # type: ignore[attr-defined]
