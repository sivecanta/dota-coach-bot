# dota-coach-bot
Dota 2 coaching bot: hero picks, match reviews and team vs. enemy analytics via the OpenDota API.

## Quickstart

```bash
cp .env.example .env      # fill in TELEGRAM_BOT_TOKEN, POSTGRES_PASSWORD
make up                   # docker compose: bot + postgres
make logs
```

Local dev without Docker: `uv sync && uv run python -m dota_coach.main`. Checks: `make lint`, `make test`.

The bot is commands-first and needs no LLM. In groups, keep BotFather privacy mode ON.
The `LLM_*` settings (any OpenAI-compatible server, e.g. LM Studio) are only for the optional agent, roadmap phase 6.

## Commands

| Command | What it does |
|---|---|
| `/link`, `/me`, `/unlink` | link your Dota account (by name, id or profile link; done in a private chat) |
| `/last [who]` | latest match: result, KDA, GPM/XPM, percentiles vs. the hero's benchmarks |
| `/heroes [who] [hero]` | hero pool, or stats on one hero (English/Ukrainian names and abbreviations: `pa`, `антімаг`) |
| `/form [who]` | last 10 games vs. the 10 before, with a trend |
| `/roster`, `/add`, `/join`, `/remove`, `/nick`, `/role` | per-chat player list, incl. friends without Telegram |

`who` is `me`, a roster nickname, an account id, or a reply to someone's message.

## Project structure

```
.
├── src/dota_coach/         application package
│   ├── main.py             entry point / composition root
│   ├── config.py           typed settings from environment (pydantic-settings)
│   ├── logging.py          log formatters (text / JSON) and request context vars
│   ├── bot/                Telegram layer (aiogram): handlers, FSM, keyboards
│   ├── agent/              LLM client, tool-calling loop, prompts, tools
│   ├── services/           business logic; no Telegram or LLM knowledge
│   ├── clients/
│   │   └── opendota/       OpenDota API client: models, Postgres cache, retries, stale fallback
│   ├── storage/            async DB engine, models, repositories (SQLAlchemy)
│   ├── charts/             matplotlib chart rendering
│   └── domain/             shared pydantic models, constants, pure helpers
├── migrations/             Alembic migrations (env.py, versions/)
├── tests/
│   ├── unit/               pure logic tests
│   ├── integration/        tests against real Postgres (needs `make up`)
│   ├── contract/           tests against recorded OpenDota responses
│   ├── scenarios/          end-to-end flows (hidden profile, unparsed match, ...)
│   └── fixtures/           recorded API responses
├── scripts/                CLI utilities (fixture recorder, LLM smoke test, agent harness)
├── data/                   local runtime data (gitignored)
├── .project/               project docs: stack, commands, architecture, config, conventions
├── .github/workflows/      CI: lint, types and tests against Postgres
├── .claude/skills/         Claude Code skills for this repo
├── .plans/                 personal feature plans and roadmap (gitignored)
├── CLAUDE.md               instructions for Claude Code
├── plan.md                 product scope
├── alembic.ini             Alembic config (URL comes from DATABASE_URL)
├── pyproject.toml          dependencies and ruff / mypy / pytest config
├── uv.lock                 locked dependencies
├── .python-version         Python version used by uv (3.12)
├── Makefile                dev commands (up, down, logs, test, lint, fmt, migrate)
├── Dockerfile              bot image
├── docker-compose.yml      bot + postgres
├── docker-compose.override.yml   dev overrides (mounts src/)
└── .env.example            environment template
```

Layering rules: [.project/ARCHITECTURE.md](.project/ARCHITECTURE.md). Product scope: [plan.md](plan.md).
