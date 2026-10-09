"""Small text formatters used by presenters. All are null-safe."""

PLACEHOLDER = "-"


def format_duration(seconds: int | None) -> str:
    """2527 -> "42:07"; 3727 -> "1:02:07"."""
    if seconds is None or seconds < 0:
        return PLACEHOLDER
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_kda(kills: int | None, deaths: int | None, assists: int | None) -> str:
    if kills is None or deaths is None or assists is None:
        return PLACEHOLDER
    return f"{kills}/{deaths}/{assists}"


def format_percent(ratio: float | None, digits: int = 0) -> str:
    """0.617 -> "62%"."""
    if ratio is None:
        return PLACEHOLDER
    return f"{ratio * 100:.{digits}f}%"


def format_winrate(wins: int, games: int) -> str:
    """ "62% (8/13)"; "-" when there are no games."""
    if games <= 0:
        return PLACEHOLDER
    return f"{format_percent(wins / games)} ({wins}/{games})"
