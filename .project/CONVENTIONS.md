# Conventions

- Async everywhere; blocking work (matplotlib) runs in an executor.
- Ruff line length 100; mypy strict.
- Tests in `tests/{unit,integration,contract,scenarios}`; DB tests (`tests/integration/`) use real Postgres, not mocks: a separate `dota_test` database on the compose `db`, each test in a rolled-back transaction. They skip with a message when Postgres is unreachable, so start it with `make up` first.
- Schema changes: edit `storage/models.py`, then use the `migration` skill.
- The OpenAI SDK runs on `httpx2`, which `respx` cannot patch. Test LLM code by passing `http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))` to `LLMClient`; keep `respx` for the OpenDota client (plain `httpx`).
