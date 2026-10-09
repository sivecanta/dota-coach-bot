import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dota_coach.bot.app import COMMANDS, build_dispatcher
from dota_coach.clients.opendota import OpenDotaClient, PostgresCache
from dota_coach.config import ConfigError, Settings, load_settings
from dota_coach.logging import setup_logging
from dota_coach.services.heroes import CatalogProvider
from dota_coach.storage.db import create_engine, create_session_factory

logger = logging.getLogger("dota_coach")


async def run(settings: Settings) -> None:
    engine = create_engine(settings.database_url.get_secret_value())
    sessions = create_session_factory(engine)
    api_key = settings.opendota_api_key.get_secret_value() if settings.opendota_api_key else None
    client = OpenDotaClient(PostgresCache(sessions), api_key)
    bot = Bot(
        settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(sessions)
    dp.workflow_data.update(client=client, catalogs=CatalogProvider(client))
    try:
        await bot.set_my_commands(COMMANDS)
        logger.info("started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await client.aclose()
        await bot.session.close()
        await engine.dispose()
        logger.info("stopped")


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        sys.exit(str(exc))
    setup_logging(settings.log_level, settings.log_format)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
