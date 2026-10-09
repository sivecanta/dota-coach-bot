"""Turning raw stats into percentiles against OpenDota's per-hero benchmarks."""

from dota_coach.clients.opendota.models import BenchmarkPoint


def percentile_of(value: float, points: list[BenchmarkPoint]) -> int | None:
    """Percent of players this value beats (0-99), interpolated between benchmark points.

    OpenDota publishes values at fixed percentiles (0.1 ... 0.99); outside that range the result is
    clamped to the first/last point. None when no benchmark data exists.
    """
    ordered = sorted(points, key=lambda p: p.percentile)
    if not ordered:
        return None
    if value <= ordered[0].value:
        return round(ordered[0].percentile * 100)
    for low, high in zip(ordered, ordered[1:], strict=False):
        if value <= high.value:
            span = high.value - low.value
            fraction = (value - low.value) / span if span else 1.0
            return round((low.percentile + fraction * (high.percentile - low.percentile)) * 100)
    return round(ordered[-1].percentile * 100)
