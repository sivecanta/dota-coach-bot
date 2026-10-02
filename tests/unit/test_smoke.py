from dota_coach.config import Settings
from dota_coach.main import run


async def test_run_starts() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        telegram_bot_token="t",  # type: ignore[arg-type]
        database_url="postgresql+asyncpg://u:p@localhost/db",  # type: ignore[arg-type]
        llm_model="m",
    )
    await run(settings)
