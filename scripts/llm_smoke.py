"""Smoke test and benchmark for tool calling on the local LLM (LM Studio).

Usage:
    uv run python scripts/llm_smoke.py                  # connectivity + round trip + 20 prompts
    uv run python scripts/llm_smoke.py --bench 6        # fewer benchmark prompts
    uv run python scripts/llm_smoke.py --bench 0 --extras   # tool-count and context probes only
    uv run python scripts/llm_smoke.py --temperature 0 --json out.json

Exit code 0 when the benchmark passes the reliability thresholds, 1 otherwise.

Status: NOT FINISHED. The LLM is deferred (commands first, see the roadmap).
TODO:
- Set LM Studio CPU thread pool to 3 and reload the model (it ran on 1 thread, ~2 tokens/s).
- Run the full 20-prompt benchmark, `--temperature 0.2` vs `0`, and `--extras`.
- Write the findings file (chat template, temperature, max reliable tools, speed notes).
Partial result so far: 11/11 prompts passed, 0 malformed JSON, but ~30 s per model call.
"""

import argparse
import asyncio
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dota_coach.agent.llm import ChatReply, LLMClient, LLMError
from dota_coach.config import load_settings

MIN_SUCCESS_RATE = 0.9
MAX_MALFORMED_RATE = 0.05
MAX_ROUNDS = 4

SYSTEM = (
    "You are a Dota 2 coach assistant. Use the tools to look up data; never invent numbers. "
    "Answer in the language the user writes in, briefly."
)


def tool(name: str, description: str, props: dict[str, str], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
                "required": required,
            },
        },
    }


FIND_PLAYER = tool(
    "find_player", "Find a Dota 2 player by name.", {"name": "player nickname"}, ["name"]
)
GET_WINRATE = tool(
    "get_hero_winrate",
    "Win rate of a player on a hero.",
    {"hero": "hero name in English", "player": "player nickname"},
    ["hero", "player"],
)
TOOLS = [FIND_PLAYER, GET_WINRATE]
REQUIRED_ARGS = {"find_player": {"name"}, "get_hero_winrate": {"hero", "player"}}


def run_fake_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "find_player":
        return {"account_id": 105248644, "nickname": args.get("name", "?"), "rank": "Immortal"}
    if name == "get_hero_winrate":
        return {
            "hero": args.get("hero"),
            "player": args.get("player"),
            "winrate": "62%",
            "games": 14,
        }
    return {"error": f"unknown tool {name}"}


@dataclass
class Case:
    prompt: str
    expect_tools: set[str] = field(default_factory=set)
    expect_in_answer: list[str] = field(default_factory=list)
    tag: str = ""


CASES = [
    Case("Find the player Miracle.", {"find_player"}, tag="en-find"),
    Case("Who is Arteezy? Look him up.", {"find_player"}, tag="en-find"),
    Case("Can you find a player called Yatoro for me?", {"find_player"}, tag="en-find"),
    Case("Search for the player named Topson.", {"find_player"}, tag="en-find"),
    Case("What is Slava's win rate on Axe?", {"get_hero_winrate"}, ["62"], tag="en-winrate"),
    Case("How good is Miracle on Invoker?", {"get_hero_winrate"}, ["62"], tag="en-winrate"),
    Case(
        "Win rate of Arteezy on Phantom Assassin?", {"get_hero_winrate"}, ["62"], tag="en-winrate"
    ),
    Case("Tell me Topson's winrate with Pudge.", {"get_hero_winrate"}, ["62"], tag="en-winrate"),
    Case(
        "Look up Miracle and Arteezy.",
        {"find_player"},
        tag="en-parallel",
    ),
    Case(
        "Find Yatoro and tell me his win rate on Morphling.",
        {"find_player", "get_hero_winrate"},
        ["62"],
        tag="en-multistep",
    ),
    Case("Найди игрока Miracle.", {"find_player"}, tag="ru-find"),
    Case("Кто такой Arteezy? Найди его.", {"find_player"}, tag="ru-find"),
    Case("Какой винрейт у Slava на Axe?", {"get_hero_winrate"}, ["62"], tag="ru-winrate"),
    Case("Покажи винрейт Miracle на Invoker.", {"get_hero_winrate"}, ["62"], tag="ru-winrate"),
    Case(
        "Сколько игр у Topson на Pudge и какой винрейт?",
        {"get_hero_winrate"},
        ["62", "14"],
        tag="ru-winrate",
    ),
    Case("Hi! How are you?", set(), tag="no-tool"),
    Case("Thanks, that's all.", set(), tag="no-tool"),
    Case("What does a position 1 carry do in Dota?", set(), tag="no-tool"),
    Case("Привет! Что такое лайнинг?", set(), tag="no-tool-ru"),
    Case(
        "Find Miracle, then tell me his win rate on Storm Spirit.",
        {"find_player", "get_hero_winrate"},
        ["62"],
        tag="en-multistep",
    ),
]


@dataclass
class Trace:
    case: Case
    calls: list[tuple[str, dict[str, Any] | None]] = field(default_factory=list)
    malformed: int = 0
    answer: str = ""
    latencies: list[float] = field(default_factory=list)
    tokens: int = 0
    error: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and not self.error


async def converse(
    llm: LLMClient,
    prompt: str,
    tools: list[dict[str, Any]],
    temperature: float,
    history: list[dict[str, Any]] | None = None,
) -> Trace:
    trace = Trace(Case(prompt))
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}, *(history or [])]
    messages.append({"role": "user", "content": prompt})
    for _ in range(MAX_ROUNDS):
        try:
            reply: ChatReply = await llm.chat(messages, tools=tools, temperature=temperature)
        except LLMError as exc:
            trace.error = f"{type(exc).__name__}: {exc}"
            return trace
        trace.latencies.append(reply.latency)
        trace.tokens += reply.completion_tokens or 0
        if not reply.tool_calls:
            trace.answer = reply.content or ""
            return trace
        messages.append(reply.message)
        for call in reply.tool_calls:
            try:
                args = json.loads(call.arguments)
                if not isinstance(args, dict):
                    raise ValueError("arguments are not an object")
            except ValueError:
                trace.malformed += 1
                trace.calls.append((call.name, None))
                result: dict[str, Any] = {"error": "arguments were not valid JSON"}
            else:
                trace.calls.append((call.name, args))
                result = run_fake_tool(call.name, args)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
            )
    trace.problems.append(f"no final answer after {MAX_ROUNDS} rounds")
    return trace


def judge(trace: Trace, case: Case) -> None:
    trace.case = case
    names = {name for name, _ in trace.calls}
    if trace.malformed:
        trace.problems.append(f"{trace.malformed} malformed tool-call JSON")
    for name, args in trace.calls:
        if name not in REQUIRED_ARGS:
            trace.problems.append(f"unknown tool {name!r}")
        elif args is not None and not REQUIRED_ARGS[name] <= set(args):
            trace.problems.append(f"{name}: missing args {REQUIRED_ARGS[name] - set(args)}")
    missing = case.expect_tools - names
    if missing:
        trace.problems.append(f"expected tool(s) not called: {sorted(missing)}")
    extra = names - case.expect_tools
    if extra and not case.expect_tools:
        trace.problems.append(f"called tool(s) on a no-tool prompt: {sorted(extra)}")
    if not trace.answer.strip():
        trace.problems.append("empty final answer")
    for needle in case.expect_in_answer:
        if needle not in trace.answer:
            trace.problems.append(f"answer lacks {needle!r} (figure from the tool result)")


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * len(ordered)))]


async def benchmark(llm: LLMClient, count: int, temperature: float) -> tuple[bool, dict[str, Any]]:
    traces: list[Trace] = []
    for i, case in enumerate(CASES[:count], 1):
        trace = await converse(llm, case.prompt, TOOLS, temperature)
        judge(trace, case)
        traces.append(trace)
        status = "ok  " if trace.ok else "FAIL"
        detail = trace.error or "; ".join(trace.problems)
        calls = ",".join(n for n, _ in trace.calls) or "-"
        total = sum(trace.latencies)
        print(
            f"  [{i:2}/{count}] {status} {case.tag:<13} {total:6.1f}s calls={calls} {detail}",
            flush=True,
        )
    ok = sum(t.ok for t in traces)
    malformed = sum(t.malformed for t in traces)
    calls_total = sum(len(t.calls) for t in traces) or 1
    latencies = [x for t in traces for x in t.latencies]
    tokens = sum(t.tokens for t in traces)
    seconds = sum(latencies) or 1
    by_tag: dict[str, list[bool]] = {}
    for t in traces:
        by_tag.setdefault(t.case.tag, []).append(t.ok)
    summary = {
        "temperature": temperature,
        "prompts": len(traces),
        "success": ok,
        "success_rate": ok / len(traces),
        "malformed_calls": malformed,
        "malformed_rate": malformed / calls_total,
        "latency_per_call_s": {
            "mean": statistics.mean(latencies),
            "p50": percentile(latencies, 0.5),
            "max": max(latencies),
        },
        "tokens_per_s": tokens / seconds,
        "by_tag": {k: f"{sum(v)}/{len(v)}" for k, v in by_tag.items()},
        "failures": [
            {"prompt": t.case.prompt, "problems": t.problems, "error": t.error}
            for t in traces
            if not t.ok
        ],
    }
    passed = (
        summary["success_rate"] >= MIN_SUCCESS_RATE
        and summary["malformed_rate"] <= MAX_MALFORMED_RATE
    )
    return passed, summary


def dummy_tools(count: int) -> list[dict[str, Any]]:
    names = [
        ("get_recent_matches", "Recent matches of a player."),
        ("get_hero_pool", "Most played heroes of a player."),
        ("get_match", "Details of one match by id."),
        ("recommend_heroes", "Recommend heroes for a role."),
        ("compare_teams", "Compare two teams in a match."),
        ("request_parse", "Request a replay parse for a match."),
        ("get_benchmarks", "Benchmarks for a hero."),
        ("list_roster", "List the chat's saved players."),
        ("make_chart", "Render a chart image."),
        ("get_hero_stats", "Meta statistics of a hero."),
    ]
    out = []
    for name, description in names[:count]:
        out.append(tool(name, description, {"query": "free text"}, ["query"]))
    return out


async def extras(llm: LLMClient, temperature: float) -> None:
    print("\nTool-count probe (does the right tool still get picked?)")
    for extra in (0, 4, 10):
        tools = [FIND_PLAYER, GET_WINRATE, *dummy_tools(extra)]
        trace = await converse(llm, "What is Slava's win rate on Axe?", tools, temperature)
        names = [n for n, _ in trace.calls]
        ok = "get_hero_winrate" in names and "62" in trace.answer
        print(
            f"  {len(tools):2} tools: {'ok  ' if ok else 'FAIL'} calls={names} "
            f"{sum(trace.latencies):.1f}s {trace.error}",
            flush=True,
        )
    print("\nContext probe (padding before the question)")
    filler = [
        {
            "role": "user",
            "content": "Let's talk about Dota strategy. " + "Lanes matter a lot. " * 40,
        },
        {"role": "assistant", "content": "Sure. " + "Farm priority and map control matter. " * 40},
    ]
    for pairs in (1, 15, 40):
        trace = await converse(llm, "Find the player Miracle.", TOOLS, temperature, filler * pairs)
        names = [n for n, _ in trace.calls]
        print(
            f"  {pairs * 2:3} padded messages: {'ok  ' if 'find_player' in names else 'FAIL'} "
            f"calls={names} {sum(trace.latencies):.1f}s {trace.error}",
            flush=True,
        )


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--bench", type=int, default=len(CASES), help="number of benchmark prompts")
    parser.add_argument("--extras", action="store_true", help="tool-count and context probes")
    parser.add_argument("--json", help="write the benchmark summary to this file")
    args = parser.parse_args()

    settings = load_settings()
    llm = LLMClient(
        settings.llm_base_url,
        settings.llm_api_key.get_secret_value(),
        settings.llm_model,
        timeout=settings.llm_timeout,
    )
    try:
        models = await llm.list_models()
        print(f"models: {models}")
        print(f"configured model loaded: {llm.model in models}")
        plain = await llm.chat([{"role": "user", "content": "Reply with one word: ready?"}])
        print(f"plain completion: {plain.content!r} in {plain.latency:.1f}s")
        trace = await converse(llm, "Find the player Miracle.", TOOLS, args.temperature)
        print(
            f"round trip: calls={trace.calls} answer={trace.answer!r} "
            f"in {sum(trace.latencies):.1f}s"
        )

        passed = True
        if args.bench:
            print(
                f"\nBenchmark: {min(args.bench, len(CASES))} prompts "
                f"at temperature {args.temperature}"
            )
            passed, summary = await benchmark(llm, min(args.bench, len(CASES)), args.temperature)
            print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))
            if args.json:
                text = json.dumps(summary, indent=2, ensure_ascii=False)
                await asyncio.to_thread(Path(args.json).write_text, text)
            print(
                f"\n{'PASS' if passed else 'FAIL'}: success >= {MIN_SUCCESS_RATE:.0%} and "
                f"malformed <= {MAX_MALFORMED_RATE:.0%}"
            )
        if args.extras:
            await extras(llm, args.temperature)
        return 0 if passed else 1
    except LLMError as exc:
        print(f"LLM error: {type(exc).__name__}: {exc}")
        return 1
    finally:
        await llm.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
