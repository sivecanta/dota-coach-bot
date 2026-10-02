from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from dota_coach.storage.repositories import (
    CacheRepository,
    ChatPlayerRepository,
    ChatRepository,
    TgUserRepository,
)


async def test_tg_user_link_is_upsert(session: AsyncSession) -> None:
    repo = TgUserRepository(session)
    assert await repo.get(1) is None
    await repo.link(1, 111, "Slava")
    await repo.link(1, 222, "Slava2")
    user = await repo.get(1)
    assert user is not None
    assert (user.account_id, user.nickname) == (222, "Slava2")


async def test_chat_ensure_is_idempotent_with_defaults(session: AsyncSession) -> None:
    repo = ChatRepository(session)
    await repo.ensure(-100, "supergroup")
    await repo.ensure(-100, "group")
    chat = await repo.get(-100)
    assert chat is not None
    assert chat.type == "supergroup"
    assert chat.tracking_enabled is False
    assert chat.settings == {}


async def test_chat_players_add_list_remove(session: AsyncSession) -> None:
    await ChatRepository(session).ensure(-100, "group")
    repo = ChatPlayerRepository(session)
    await repo.add(-100, 111, "A", 1, 1)
    await repo.add(-100, 222, "B", None, 1)
    await repo.add(-100, 111, "A2", 3, 1)  # same account: updates, no duplicate
    players = await repo.list(-100)
    assert [(p.account_id, p.nickname, p.default_role) for p in players] == [
        (111, "A2", 3),
        (222, "B", None),
    ]
    assert await repo.remove(-100, 111) is True
    assert await repo.remove(-100, 111) is False
    assert len(await repo.list(-100)) == 1


async def test_cache_ttl(session: AsyncSession) -> None:
    repo = CacheRepository(session)
    now = datetime.now(UTC)
    await repo.set("fresh", {"a": 1}, now + timedelta(hours=1))
    await repo.set("old", [1, 2], now - timedelta(hours=1))

    fresh = await repo.get("fresh")
    assert fresh is not None
    assert fresh.payload == {"a": 1}
    assert await repo.get("old") is None
    stale = await repo.get("old", include_expired=True)
    assert stale is not None
    assert stale.payload == [1, 2]

    assert await repo.delete_expired() == 1
    assert await repo.get("old", include_expired=True) is None
