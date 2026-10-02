# Commands

- `uv sync` - install deps
- `make test` - pytest
- `make lint` - ruff check, ruff format --check, mypy
- `make fmt` - auto-fix and format
- `make up` / `make down` / `make logs` - Docker Compose
- `make migrate` - `alembic upgrade head` (the bot container also runs it on start; needs the db up)
- `uv run python -m dota_coach.main` - run the bot locally

Docker may not be available inside WSL; verify with `uv run` when it isn't.
