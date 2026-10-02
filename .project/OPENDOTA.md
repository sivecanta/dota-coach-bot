# OpenDota data gotchas

- `player_slot` 0-127 Radiant, 128-255 Dire; combine with `radiant_win`.
- `rank_tier`: tens = rank, ones = stars. `lane_role` / `position_est` may be null.
- Response schemas in the OpenDota spec are partly wrong; parse defensively and test against recorded fixtures in `tests/fixtures/opendota/`.
- Match `version` is present only once parsed (`Match.is_parsed`); an unparsed match may be parsed later, so it is cached 10 min while a parsed one is cached indefinitely.
- Anonymous players have `account_id: null` in matches. A hidden profile still returns a `profile` object (with `fh_unavailable`) but empty `recentMatches`, 0/0 win-loss and no rank; unknown ids give 404.
- The API key goes as the `api_key` query param, so never log request URLs: `setup_logging` silences the `httpx` logger below WARNING, and client errors carry the path only.
- Refresh fixtures with `uv run python scripts/record_fixtures.py` (public pro data only).
- Unparsed matches lack `purchase_log`, `gold_t`, `radiant_gold_adv`; degrade to summary-only.
