FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy MPLBACKEND=Agg PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev

RUN useradd --create-home app && chown -R app /app
USER app

ENV PATH="/app/.venv/bin:$PATH"
CMD ["sh", "-c", "alembic upgrade head && python -m dota_coach.main"]
