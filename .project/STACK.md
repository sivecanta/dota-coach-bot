# Stack

- Python 3.12, `uv` for deps and running
- Telegram: aiogram 3 (async, FSM, inline keyboards)
- LLM: `openai` SDK (`AsyncOpenAI`) with custom `base_url`; Gemma 4 served by LM Studio (OpenAI-compatible)
- HTTP: httpx (async), used by the OpenDota client
- Config: pydantic / pydantic-settings
- DB: PostgreSQL 17, SQLAlchemy 2 async + asyncpg, Alembic migrations
- Charts: matplotlib (`Agg` backend)
- Hero alias matching: rapidfuzz, aliases in YAML
- Tests/quality: pytest, pytest-asyncio, respx, ruff, mypy (strict)
- Runtime: Docker Compose runs `bot` + `db`; LM Studio runs outside Docker on the LAN
