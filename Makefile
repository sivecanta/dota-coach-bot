.PHONY: up down logs test lint fmt migrate

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f bot

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src

fmt:
	uv run ruff check --fix . && uv run ruff format .

migrate:
	uv run alembic upgrade head
