# Architecture rules

- Dependency direction: `bot -> agent -> services -> clients/storage/charts`. `bot` may also call `services` directly (deterministic commands). Lower layers never import upper ones.
- `domain/` is the bottom layer: pydantic models, constants, pure helpers. Any layer may import it; it imports nothing else from the package.
- `main.py` is the composition root: it loads config, configures logging and wires dependencies. `config.py` and `logging.py` sit at the package root; other modules receive settings as arguments and do not read env vars.
- The LLM client lives in `agent/llm.py`; only `agent/` talks to the LLM.
- `services/` know nothing about Telegram or the LLM: typed args in, pydantic models out.
- LLM tools in `agent/tools/` are thin wrappers over services and return small, pre-computed, already-named results (hero names, not ids).
- Structured flows (linking, lobby) are deterministic buttons/FSM; the LLM handles free text and prose. Deterministic commands must work when the LLM is down.
- All OpenDota calls go through `clients/opendota` (cache, rate limit, backoff). Never call it from handlers.
- The LLM must never invent numbers: every figure in a reply comes from a tool result.
- Bot runs with Telegram privacy mode ON in groups (sees commands, @mentions, replies only). State is keyed by chat, not just user; shared UI (lobby) is one edited message.

Product scope: `plan.md`. Roadmap: `.plans/roadmap/` (personal, gitignored).
