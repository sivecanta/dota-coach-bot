# Conventions

- Async everywhere; blocking work (matplotlib) runs in an executor.
- Ruff line length 100; mypy strict.
- Tests in `tests/{unit,contract,scenarios}`; DB tests use real Postgres, not mocks.
