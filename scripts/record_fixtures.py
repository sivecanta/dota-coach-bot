"""Record real OpenDota responses into tests/fixtures/opendota/.

Usage: uv run python scripts/record_fixtures.py

Uses only public pro data (a pro account, recent pro and public matches). Values are never
edited; long lists and dicts are cut to a few items and heavy match sections are dropped to
keep files small.
The API key is read from OPENDOTA_API_KEY and never written to disk.
"""

import json
import sys
from pathlib import Path
from typing import Any

import httpx

from dota_coach.config import load_settings

BASE = "https://api.opendota.com/api"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "opendota"
PRO_ACCOUNT = 105248644  # public pro profile
EMPTY_ACCOUNT = 1  # exists, but has no public match data (hidden-profile case)
HEAVY_MATCH_KEYS = {
    "teamfights",
    "chat",
    "draft_timings",
    "cosmetics",
    "all_word_counts",
    "my_word_counts",
    "objectives",
    "kills_log",
    "buyback_log",
    "runes_log",
    "obs_log",
    "sen_log",
    "obs_left_log",
    "sen_left_log",
    "obs",
    "sen",
    "life_state",
    "damage_inflictor",
    "damage_inflictor_received",
    "damage_targets",
    "ability_targets",
    "item_uses",
    "ability_uses",
    "damage",
    "damage_taken",
    "healing",
    "killed",
    "killed_by",
    "lane_pos",
    "pings",
    "actions",
    "gold_reasons",
    "xp_reasons",
    "kill_streaks",
    "multi_kills",
    "benchmarks",
    "permanent_buffs",
    "pred_vict",
}


def trim(data: Any, limit: int | None, drop: set[str]) -> Any:
    if isinstance(data, dict):
        items = list(data.items())
        if limit is not None:
            items = items[:limit]
        return {k: trim(v, None, drop) for k, v in items if k not in drop}
    if isinstance(data, list):
        items = data if limit is None else data[:limit]
        return [trim(v, None, drop) for v in items]
    return data


def main() -> int:
    key = load_settings().opendota_api_key
    params_base = {"api_key": key.get_secret_value()} if key else {}
    OUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE, timeout=60, params=params_base) as http:

        def get(path: str, **params: Any) -> Any:
            resp = http.get(path, params=params)
            resp.raise_for_status()
            return resp.json()

        def save(name: str, data: Any) -> None:
            (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            print("recorded", name)

        pro = get("/proMatches")
        parsed_id = next(m["match_id"] for m in pro[10:] if m.get("version"))
        public = get("/publicMatches")
        unparsed_id = next(
            m["match_id"]
            for m in public
            if m["duration"] > 600 and "version" not in get(f"/matches/{m['match_id']}")
        )
        print("parsed match", parsed_id, "| unparsed match", unparsed_id)

        player = f"/players/{PRO_ACCOUNT}"
        empty = f"/players/{EMPTY_ACCOUNT}"
        save("health", get("/health"))
        save("search__pro", trim(get("/search", q="Miracle"), 5, set()))
        save("players__profile", get(player))
        save("players__hidden_profile", get(empty))
        save("players_wl__ok", get(f"{player}/wl"))
        save("players_wl__hidden", get(f"{empty}/wl"))
        save("players_recent_matches__ok", trim(get(f"{player}/recentMatches"), 5, set()))
        save("players_recent_matches__hidden", get(f"{empty}/recentMatches"))
        save("players_heroes__ok", trim(get(f"{player}/heroes"), 8, set()))
        save("matches__parsed", trim(get(f"/matches/{parsed_id}"), None, HEAVY_MATCH_KEYS))
        save("matches__unparsed", trim(get(f"/matches/{unparsed_id}"), None, HEAVY_MATCH_KEYS))
        save("heroes", trim(get("/heroes"), 10, set()))
        save("hero_stats", trim(get("/heroStats"), 5, set()))
        save("benchmarks__hero", get("/benchmarks", hero_id=1))
        save("constants_heroes", trim(get("/constants/heroes"), 5, set()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
