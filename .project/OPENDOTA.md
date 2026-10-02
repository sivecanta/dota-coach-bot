# OpenDota data gotchas

- `player_slot` 0-127 Radiant, 128-255 Dire; combine with `radiant_win`.
- `rank_tier`: tens = rank, ones = stars. `lane_role` / `position_est` may be null.
- Response schemas in the OpenDota spec are partly wrong; parse defensively and test against recorded fixtures in `tests/fixtures/opendota/`.
- Unparsed matches lack `purchase_log`, `gold_t`, `radiant_gold_adv`; degrade to summary-only.
