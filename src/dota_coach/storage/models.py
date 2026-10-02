from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TgUser(Base):
    __tablename__ = "tg_users"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(BigInteger)
    nickname: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chat(Base):
    __tablename__ = "chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatPlayer(Base):
    __tablename__ = "chat_players"
    __table_args__ = (UniqueConstraint("chat_id", "account_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.chat_id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(BigInteger)
    nickname: Mapped[str | None] = mapped_column(String)
    default_role: Mapped[int | None] = mapped_column(SmallInteger)
    added_by: Mapped[int | None] = mapped_column(BigInteger)


class CacheEntry(Base):
    __tablename__ = "cache"
    __table_args__ = (Index("ix_cache_expires_at", "expires_at"),)

    key: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[Any] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
