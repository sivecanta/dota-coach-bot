"""Turns service results into Telegram HTML messages. Pure functions: no Telegram objects."""

from datetime import UTC, datetime
from html import escape

from dota_coach.domain.formatting import (
    format_duration,
    format_kda,
    format_winrate,
)
from dota_coach.domain.models import Role
from dota_coach.services.match_review import MatchReview
from dota_coach.services.players import Candidate, ProfileStatus
from dota_coach.services.trends import (
    MIN_SAMPLE,
    FormReport,
    FormWindow,
    HeroDetail,
    HeroPoolReport,
    HeroRecord,
)

STALE_NOTE = "⚠️ OpenDota is unreachable; this may be outdated."
HIDDEN_PROFILE_HELP = (
    "I can't see any matches for this account. In Dota 2 open Settings → Options → Social and "
    "enable <b>Expose Public Match Data</b>, play a game, then press Re-check."
)

HELP = """<b>Dota coach</b>
/link — link your Dota account (in a private chat)
/me — show your linked account
/unlink — forget your account
/last [who] — review of the latest match
/heroes [who] [hero] — hero pool, or stats on one hero
/form [who] — last 10 games vs. the 10 before

<b>Group roster</b>
/roster — players of this chat
/add &lt;name or id&gt; — add a player (friends without Telegram too)
/join — add yourself
/remove &lt;nick&gt;, /nick &lt;old&gt; &lt;new&gt;, /role &lt;nick&gt; &lt;1-5&gt;

<i>who</i> = <code>me</code>, a roster nickname, an account id, or reply to someone's message.
Hero names can be English or Russian: <code>/heroes pa</code>, <code>/heroes магина</code>."""

_ROLE_NAMES = {
    Role.CARRY: "carry",
    Role.MID: "mid",
    Role.OFFLANE: "offlane",
    Role.SOFT_SUPPORT: "soft support",
    Role.HARD_SUPPORT: "hard support",
}


def role_label(role: int | None) -> str:
    if role is None:
        return "no role"
    try:
        return f"{role} ({_ROLE_NAMES[Role(role)]})"
    except ValueError:
        return str(role)


def _stale(stale: bool) -> str:
    return f"\n{STALE_NOTE}" if stale else ""


def _date(timestamp: int | None) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")


def _stat(value: int | None, percentile: int | None) -> str:
    text = "-" if value is None else f"{value:,}"
    return f"{text} (top {100 - percentile}%)" if percentile is not None else text


def candidates(found: list[Candidate], question: str) -> str:
    """A numbered list with enough detail to tell similar accounts apart."""
    lines = [f"<b>{question}</b>"]
    for i, c in enumerate(found, start=1):
        rank = str(c.rank) if c.rank else "unranked"
        games = f"{c.games} games" if c.games is not None else "games unknown"
        when = c.last_match_time
        last = f"last match {when:%Y-%m-%d}" if when else "no recent match"
        lines.append(f"{i}. <b>{escape(c.name)}</b> — {rank} · {games}")
        lines.append(f"    {last} · id <code>{c.account_id}</code>")
    return "\n".join(lines)


def profile(
    status: ProfileStatus, *, title: str = "Account", top: list[HeroRecord] | None = None
) -> str:
    rank = str(status.rank) if status.rank else "not shown by OpenDota"
    lines = [
        f"<b>{title}:</b> {escape(status.name)} (<code>{status.account_id}</code>)",
        f"Rank: {rank}",
        f"All time: {format_winrate(status.wins, status.wins + status.losses)}",
    ]
    if status.recent_games:
        lines.append(
            f"Last {status.recent_games} games: "
            f"{format_winrate(status.recent_wins, status.recent_games)} · "
            f"last match {_date(status.last_match_time)}"
        )
    if top:
        lines.append("Most played: " + ", ".join(f"{escape(r.hero)} ({r.games})" for r in top))
    return "\n".join(lines) + _stale(status.stale)


def review(r: MatchReview, who: str) -> str:
    result = {True: "🟢 Won", False: "🔴 Lost", None: "⚪ Result unknown"}[r.won]
    lane = f" · {r.lane}" if r.lane else ""
    score = ""
    if r.radiant_score is not None and r.dire_score is not None:
        score = f" · score {r.radiant_score}:{r.dire_score}"
    p = r.percentiles
    lines = [
        f"<b>{escape(who)} — last match</b>",
        f"{result} as <b>{escape(r.hero)}</b>{lane}",
        f"{format_duration(r.duration)} · {_date(r.started_at)}{score}",
        f"KDA {format_kda(r.kills, r.deaths, r.assists)}",
        f"GPM {_stat(r.gpm, p.get('gpm'))} · XPM {_stat(r.xpm, p.get('xpm'))}",
        f"Last hits {_stat(r.last_hits, p.get('last_hits'))} · "
        f"Hero damage {_stat(r.hero_damage, p.get('hero_damage'))}",
        f"Tower damage {_stat(r.tower_damage, None)} · Healing {_stat(r.hero_healing, None)}",
    ]
    if p:
        lines.append("<i>top N% = compared with players on this hero</i>")
    if not r.is_parsed:
        lines.append("<i>Replay not parsed: no timelines or item data for this match.</i>")
    lines.append(f"Match <code>{r.match_id}</code>")
    return "\n".join(lines) + _stale(r.stale)


def _record_line(r: HeroRecord) -> str:
    return f"{escape(r.hero)} — {format_winrate(r.wins, r.games)}"


def hero_pool(report: HeroPoolReport, who: str) -> str:
    if not report.top:
        return f"<b>{escape(who)}</b>: no hero games found." + _stale(report.stale)
    lines = [f"<b>{escape(who)} — hero pool</b> ({report.total_games} games)"]
    lines += [f"{i}. {_record_line(r)}" for i, r in enumerate(report.top, start=1)]
    if report.best and report.worst and report.best != report.worst:
        lines.append(f"\nBest ({MIN_SAMPLE}+ games): {_record_line(report.best)}")
        lines.append(f"Worst ({MIN_SAMPLE}+ games): {_record_line(report.worst)}")
    return "\n".join(lines) + _stale(report.stale)


def hero_detail(d: HeroDetail, who: str) -> str:
    if d.games == 0:
        return f"<b>{escape(who)}</b> has no games on {escape(d.hero)}." + _stale(d.stale)
    lines = [
        f"<b>{escape(who)} on {escape(d.hero)}</b>",
        f"Played: {format_winrate(d.wins, d.games)} · last on {_date(d.last_played)}",
    ]
    if d.with_games:
        lines.append(f"With this hero on the team: {format_winrate(d.with_wins, d.with_games)}")
    if d.against_games:
        lines.append(f"Against this hero: {format_winrate(d.against_wins, d.against_games)}")
    if d.small_sample:
        lines.append(f"<i>Only {d.games} games: take it with a grain of salt.</i>")
    return "\n".join(lines) + _stale(d.stale)


def _window(w: FormWindow) -> str:
    return (
        f"{format_winrate(w.wins, w.games)} · KDA {w.avg_kills:.1f}/{w.avg_deaths:.1f}/"
        f"{w.avg_assists:.1f} · GPM {w.avg_gpm:.0f} · XPM {w.avg_xpm:.0f}"
    )


_DIRECTION = {
    "improving": "📈 improving",
    "flat": "➡️ flat",
    "declining": "📉 declining",
    "unknown": "not enough games to call a trend",
}


def form(f: FormReport, who: str) -> str:
    lines = [f"<b>{escape(who)} — recent form</b>", f"Last {f.recent.games}: {_window(f.recent)}"]
    if f.previous:
        lines.append(f"Before that ({f.previous.games}): {_window(f.previous)}")
    lines.append(f"Trend: {_DIRECTION[f.direction]}")
    return "\n".join(lines) + _stale(f.stale)


def roster(entries: list[tuple[str, int, int | None, bool]]) -> str:
    """Rows are (nickname, account_id, default_role, has_linked_telegram_user)."""
    if not entries:
        return "The roster is empty. Add players with /add &lt;name or id&gt; or /join."
    lines = ["<b>Roster</b>"]
    for nickname, account_id, role, linked in entries:
        mark = " 🔗" if linked else ""
        lines.append(
            f"• <b>{escape(nickname)}</b>{mark} — <code>{account_id}</code> · {role_label(role)}"
        )
    lines.append("<i>🔗 = linked Telegram user</i>")
    return "\n".join(lines)
