import asyncio
import logging

logger = logging.getLogger("dota_coach")


async def run() -> None:
    logger.info("started")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
