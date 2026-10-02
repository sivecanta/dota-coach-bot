---
name: migration
description: Create and verify an Alembic database migration. Use when SQLAlchemy models in storage/ are added or changed, when the user asks for a migration, or when a schema change is needed.
---

# Migration

Postgres 17, SQLAlchemy 2 async, Alembic. Migrations are verified against real Postgres, not mocks.

## Workflow
1. Change the models in `src/dota_coach/storage/` first.
2. Generate: `uv run alembic revision --autogenerate -m "<imperative summary>"`.
3. Read the generated file; autogenerate is a draft. Check for:
   - missed changes: renames (shown as drop + add, which loses data), server defaults, JSONB and enum changes, indexes, constraints;
   - a `downgrade()` that really reverses `upgrade()`;
   - new `NOT NULL` columns on existing tables: add a server default or backfill in the same migration.
4. Verify the round trip: `make migrate`, then `uv run alembic downgrade -1`, then `make migrate` again.
5. Confirm models and schema agree: `uv run alembic check` reports no pending changes.
6. Run the `check` skill.

## Rules
- One migration per logical change. Never edit a migration that is already committed; add a new one.
- Destructive steps (drop table or column, type change that loses data): stop and confirm with the user first.
- If Postgres is not reachable (Docker may be unavailable in WSL), say the migration is unverified. Do not report it as working.
