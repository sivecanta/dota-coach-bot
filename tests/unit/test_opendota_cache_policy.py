from datetime import timedelta

import pytest

from dota_coach.clients.opendota.cache import cache_key, is_hot, ttl_for


@pytest.mark.parametrize(
    ("path", "payload", "ttl"),
    [
        ("/heroes", [], timedelta(days=7)),
        ("/constants/items", {}, timedelta(days=7)),
        ("/heroStats", [], timedelta(hours=12)),
        ("/benchmarks", {}, timedelta(hours=12)),
        ("/players/1", {}, timedelta(minutes=3)),
        ("/players/1/recentMatches", [], timedelta(minutes=3)),
        ("/matches/5", {"version": 22}, timedelta(days=3650)),
        ("/matches/5", {"match_id": 5}, timedelta(minutes=10)),
        ("/search", [], timedelta(minutes=5)),
    ],
)
def test_ttl_policy(path: str, payload: object, ttl: timedelta) -> None:
    assert ttl_for(path, payload) == ttl


def test_hot_entries_are_constants_only() -> None:
    assert is_hot("/heroes")
    assert is_hot("/constants/heroes")
    assert not is_hot("/matches/5")


def test_cache_key_ignores_param_order() -> None:
    assert cache_key("/x", {"b": 2, "a": 1}) == cache_key("/x", {"a": 1, "b": 2})
    assert cache_key("/x", {}) == "opendota:/x"
