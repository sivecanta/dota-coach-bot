# Dota 2 Assistant Agent — Implementation Plan

Data source: OpenDota API (`https://api.opendota.com/api`, spec v31.1.0).
Goal: a chat bot/agent that remembers players, asks about the upcoming game (who plays, role, hero), recommends heroes, analyzes past games, and compares team vs. enemy with charts.

---

## 1. Scope

### In scope
1. Player setup: search by name, save, quick re-pick later.
2. Pre-game dialogue: who plays, which role, which hero, enemy picks (typed by user).
3. Hero recommendation based on personal history, meta, role fit and counters.
4. Last-game analysis and performance trends, compared to benchmarks.
5. Team analytics, and team vs. enemy comparison with charts.

### Out of scope (API limitations)
- Live draft or lobby data for normal matches (user must type picks).
- Scouting enemies before a game (accounts are anonymous unless user supplies IDs).
- Reliable ally-synergy data (only approximated via `/explorer`, optional).

### Open question
- The original request was cut off at "also when user says ..." — confirm the missing requirement and add it to section 3.

---

## 2. Architecture

```
Chat frontend (Telegram: groups and private chats)
        |
   Agent (LLM + tool calling)
        |
   Tool layer (Python)
     |-- OpenDota client (rate limiting, retries, cache)
     |-- Storage (PostgreSQL): players, preferences, cached responses
     |-- Analytics (scoring, benchmarks, percentiles)
     |-- Charts (matplotlib) -> images
```

### Components
- **OpenDota client**: one wrapper with API key support (query param or Bearer header), request queue, exponential backoff on 429/5xx, response cache with TTLs.
- **Storage (PostgreSQL)**:
  - `users(chat_id, created_at)`
  - `saved_players(chat_id, account_id, nickname, default_role, is_me)`
  - `cache(key, payload, fetched_at, ttl)`
  - `parse_jobs(match_id, job_id, status, requested_at)`
- **Agent**: system prompt with persona, tool definitions, and rules (see section 6).
- **Charts**: render to PNG and send as an image in chat.

### Stack
- Python 3.12, `httpx`, `pydantic`, PostgreSQL via SQLAlchemy (async), `matplotlib`.
- Frontend: Telegram (aiogram 3).
- LLM: Gemma 4 served locally by LM Studio (OpenAI-compatible API) with tool calling.
- Details: `.project/STACK.md`.

---

## 3. Features and API mapping

| Feature | Endpoints | Notes |
|---|---|---|
| Find player by name | `/search?q=` | Returns `account_id`, avatar, similarity. Let user confirm from a short list. |
| Save and recall players | local DB | Steam32 `account_id` is the key. Accept pasted friend ID too. |
| Check profile is usable | `/players/{id}`, `/players/{id}/wl` | Detect hidden match history (empty results). |
| Last game | `/players/{id}/recentMatches` -> `/matches/{match_id}` | Fall back gracefully if unparsed. |
| Performance vs. peers | `/benchmarks?hero_id=&bracket=` | Convert player GPM/XPM/etc. to percentile. |
| Trends | `/players/{id}/matches?project=...`, `/totals`, `/histograms/{field}` | Filter by hero, patch, date, lane_role. |
| Hero pool | `/players/{id}/heroes` | Games and win rate per hero. |
| Meta strength | `/heroStats` | Win rates per rank bracket. |
| Role fit | `/scenarios/laneRoles`, `/heroes` | Lane win rates and role tags. |
| Counters | `/heroes/{id}/matchups` | Use against typed enemy picks. |
| Party stats | `/players/{id}/peers`, `included_account_id` filter | |
| Parse request | `POST /request/{match_id}`, `GET /request/{jobId}` | Costs 10 calls. Poll and notify. |
| Names and icons | `/constants/heroes`, `/constants/items`, `/heroes` | Cache for days. |
| Charts | `/matches/{id}` (`radiant_gold_adv`, `radiant_xp_adv`, `players[].gold_t/xp_t/lh_t`) | Parsed matches only for time series. |

---

## 4. Conversation flows

### Flow A: Onboarding
1. "What's your Dota name?" -> `/search`.
2. Show up to 5 candidates (name, avatar, last match time) -> user confirms.
3. Verify data availability; if hidden, explain how to enable public match data.
4. Save as "me"; offer to add friends/teammates.

### Flow B: Pre-game helper
1. "Who is playing?" (pick from saved players).
2. "Which role for each?" (1-5, store as default).
3. "Which heroes are you considering / what has the enemy picked?"
4. Run recommendation (section 5) and present top 3 with short reasons.
5. Optional: show win rate vs. each enemy hero.

### Flow C: Last game review
1. Fetch most recent match; if unparsed, offer a parse request.
2. Summarize: result, hero, KDA, GPM/XPM, percentile vs. benchmarks.
3. Offer follow-ups as buttons: "Team comparison", "Gold/XP chart", "Item timings", "Compare to my average".

### Flow D: Team vs. enemy
1. Pull all 10 players from the match.
2. Show side-by-side table and charts:
   - Gold/XP advantage over time (line).
   - Per-player GPM, XPM, hero damage, tower damage (grouped bars).
   - Team totals (kills, net worth, damage).
3. Short written takeaways (biggest swing minute, best/worst performer).

---

## 5. Hero recommendation algorithm (v1)

Score per candidate hero `h` for player `p`, role `r`, enemy picks `E`:

```
score = w1 * personal(h)      # smoothed win rate and games from /players/{id}/heroes
      + w2 * meta(h, bracket) # win rate from /heroStats for player's bracket
      + w3 * role_fit(h, r)   # lane-role win rate and role tags
      + w4 * counter(h, E)    # mean matchup win rate vs. each enemy hero
```

- Smooth personal win rate with a prior: `(wins + k*meta_wr) / (games + k)`, with k around 10.
- Normalize each component to 0-1; start with weights 0.35 / 0.20 / 0.20 / 0.25 and tune.
- Exclude heroes already picked or banned (as told by user).
- Output top 3 with a one-line reason each (e.g. "62% in your last 14 games, strong vs. enemy carry").
- v2 (optional): ally synergy via `/explorer` SQL, with strict query limits and caching.

---

## 6. Agent design

### Tools (function calling)
- `search_player(name)`
- `save_player(chat_id, account_id, nickname, role?)` / `list_saved_players(chat_id)`
- `get_profile_status(account_id)`
- `get_recent_matches(account_id, limit)`
- `get_match(match_id)` / `request_parse(match_id)` / `get_parse_status(job_id)`
- `get_player_heroes(account_id, filters)`
- `get_hero_stats()` / `get_hero_matchups(hero_id)` / `get_lane_role_stats(hero_id?)`
- `get_benchmarks(hero_id, bracket?)`
- `recommend_heroes(account_id, role, enemy_hero_ids, banned_ids)`
- `make_chart(kind, match_id|account_id, options)`

### System prompt rules
- Never invent stats; every number must come from a tool result.
- State data limits (hidden profile, unparsed match, small sample) instead of guessing.
- Ask only one question at a time during setup.
- Offer next actions as short option lists after each answer.
- Use hero/item names, not IDs.

---

## 7. Technical considerations

1. **Rate limits**: not documented in the spec. Get an API key early, centralize calls in one client, queue and back off on 429.
2. **Caching TTLs**: constants and `/heroes` 7 days; `/heroStats` and benchmarks 6-24 hours; player recent matches 2-5 minutes; finished matches indefinitely.
3. **Parsed vs. unparsed**: check for presence of `purchase_log`, `gold_t`, `radiant_gold_adv`; degrade to summary-only mode if absent.
4. **Hidden profiles**: empty or null results trigger a clear explanation and instructions.
5. **Data mapping gotchas**:
   - `player_slot` 0-127 Radiant, 128-255 Dire; combine with `radiant_win`.
   - `rank_tier`: tens = rank, ones = stars.
   - Bitmask fields (towers/barracks) need decoding if shown.
   - `lane_role` and `position_est` can be null; infer role cautiously.
6. **Spec inconsistencies**: some response schemas are wrong (arrays typed as objects, duplicate `win`/`lose`, string-typed counts). Validate responses defensively and test against live data.
7. **Privacy**: store only `account_id` and nicknames the user provides; allow deleting saved data.
8. **Reliability**: handle API downtime via `/health`; return cached data with a "may be outdated" note.

---

## 8. Milestones

| # | Milestone | Deliverables | Done when |
|---|---|---|---|
| 0 | Setup | Repo, API key, config, OpenDota client with cache and backoff | Client passes smoke tests on key endpoints |
| 1 | Player setup | Search, confirm, save/recall, profile check | A user can register and return later |
| 2 | Last-game review | Recent match, parse request flow, summary and benchmark percentiles | Review works for parsed and unparsed matches |
| 3 | Trends | Hero pool, win rates, filtered history, simple trend text | Answers "how am I doing on hero X this month" |
| 4 | Charts and team comparison | Gold/XP line, per-player bars, team table | Charts render for a parsed match |
| 5 | Pre-game flow | Multi-player role/hero dialogue, state handling | Full conversation completes without errors |
| 6 | Recommendations | Scoring v1, explanation text, weight tuning | Top-3 picks look sensible on test cases |
| 7 | Polish | Error messages, rate-limit handling, logging, tests, deployment | Runs unattended on a server |

Rough effort: milestones 0-2 about 3-5 days, 3-4 about 3-4 days, 5-6 about 4-6 days, 7 about 2-3 days (one developer, part-time estimates will vary).

---

## 9. Testing

- Unit tests: scoring function, smoothing, slot/win mapping, rank decoding.
- Contract tests: record real API responses (fixtures) for matches, players, heroes; assert fields the code relies on.
- Scenario tests: hidden profile, unparsed match, new player with few games, API 429/timeout.
- Manual evaluation: 10-20 recommendation cases reviewed by an experienced player.

---

## 10. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Unknown rate limits | Throttling, failed answers | API key, caching, request queue, backoff |
| Hidden profiles | No data for user | Detect early, explain, suggest public setting |
| Unparsed matches | Missing charts and details | On-demand parse with polling, summary fallback |
| Weak recommendations | Low trust | Transparent reasons, small-sample smoothing, user feedback loop |
| Spec/schema drift | Breakage | Defensive parsing, fixtures, version check on startup |
| Role inference errors | Wrong advice | Ask the user for role; use inference only as a hint |

---

## 11. Future ideas
- Ally synergy and draft simulation via `/explorer`.
- Weekly digest of performance sent automatically.
- Pro-match comparisons using `/proMatches` and `/heroes/{id}/itemPopularity`.
- Item-timing advice via `/scenarios/itemTimings`.
- Web dashboard sharing the same tool layer.
