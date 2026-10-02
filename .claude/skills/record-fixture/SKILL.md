---
name: record-fixture
description: Record a real OpenDota API response as a test fixture and cover it with a contract test. Use when adding or changing an OpenDota endpoint, when a response shape surprises the code, or when the user asks to record or refresh a fixture.
---

# Record fixture

The OpenDota spec is partly wrong (see `.project/OPENDOTA.md`), so models are tested against recorded real responses in `tests/fixtures/opendota/`.

## Workflow
1. Fetch the real response. Use `scripts/record_fixtures.py` if it exists; otherwise a one-off `curl` against `https://api.opendota.com/api/...`. Never invent or hand-write a fixture.
2. Save it as `tests/fixtures/opendota/<endpoint>__<case>.json`, e.g. `matches__parsed.json`, `matches__unparsed.json`, `players_heroes__hidden_profile.json`. Pretty-printed JSON.
3. Record the edge cases the code must survive, not only the happy path: unparsed match, hidden profile (empty results), null `lane_role` / `position_est`, new player with few games.
4. Trim long lists to a few items when the test does not need them all. Do not otherwise edit values: the point is real data.
5. Add or update a contract test in `tests/contract/` that loads the fixture through the pydantic model in `clients/opendota/models.py` and asserts the fields the code relies on. Serve it with `respx`; contract tests never hit the network.
6. Run the `check` skill.

## Rules
- The API key must never reach a fixture, a test or the git history. Do not store request URLs with `api_key=` in them.
- Fixtures are committed to a public repo. Ask the user which account and match ids to record; do not use their own or their friends' accounts without asking.
- When refreshing a fixture, show what changed in shape (added, removed, retyped fields) so the model can be updated on purpose.
