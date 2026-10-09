# Config

Environment via `.env` (template: `.env.example`):

- `TELEGRAM_BOT_TOKEN`, `OPENDOTA_API_KEY`
- `LLM_BASE_URL` (include scheme and `/v1`, e.g. `http://192.168.1.146:1234/v1`), `LLM_MODEL`, `LLM_API_KEY` (dummy for LM Studio), `LLM_TIMEOUT`
- `DATABASE_URL` (`postgresql+asyncpg://` form), `POSTGRES_PASSWORD`
- `LOG_LEVEL`, `LOG_FORMAT` (`text` or `json`)

Required: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`. The `LLM_*` settings are optional until the LLM agent (roadmap phase 6) is built. Missing or invalid values stop startup with a readable error.

Never commit `.env` or log secrets.
