import asyncio
import logging
import sys

from dota_coach.config import ConfigError, Settings, load_settings
from dota_coach.logging import setup_logging

logger = logging.getLogger("dota_coach")


async def run(settings: Settings) -> None:
    logger.info("started")


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        sys.exit(str(exc))
    setup_logging(settings.log_level, settings.log_format)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
