"""LLMClient against a mocked server.

The OpenAI SDK runs on httpx2, which respx cannot patch, so tests inject a MockTransport.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from openai import DefaultAsyncHttpxClient

from dota_coach.agent.llm import (
    LLMClient,
    LLMError,
    LLMModelNotLoaded,
    LLMTimeout,
    LLMUnavailable,
)

BASE = "http://lm.test/v1"
Handler = Callable[[httpx2.Request], httpx2.Response]


def make_llm(handler: Handler, api_key: str = "dummy") -> LLMClient:
    transport = httpx2.MockTransport(handler)
    http_client = DefaultAsyncHttpxClient(transport=transport)
    return LLMClient(BASE, api_key, "m", timeout=2, max_retries=0, http_client=http_client)


def completion(message: dict[str, Any], finish: str = "stop") -> dict[str, Any]:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def raises(exc: Exception) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise exc

    return handler


async def test_plain_completion() -> None:
    llm = make_llm(
        lambda r: httpx2.Response(200, json=completion({"role": "assistant", "content": "hi"}))
    )
    reply = await llm.chat([{"role": "user", "content": "hello"}])
    assert reply.content == "hi"
    assert reply.tool_calls == []
    assert (reply.prompt_tokens, reply.completion_tokens) == (10, 5)
    assert reply.message == {"role": "assistant", "content": "hi"}


async def test_tool_call_keeps_raw_arguments() -> None:
    bad_json = '{"name": "Miracle"'  # malformed on purpose: the client must not parse it
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "find_player", "arguments": bad_json},
            }
        ],
    }
    llm = make_llm(lambda r: httpx2.Response(200, json=completion(message, "tool_calls")))
    reply = await llm.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
    assert [(c.id, c.name, c.arguments) for c in reply.tool_calls] == [
        ("c1", "find_player", bad_json)
    ]
    assert reply.message["tool_calls"][0]["function"]["arguments"] == bad_json


async def test_request_carries_model_tools_and_temperature() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.update(json.loads(request.content))
        return httpx2.Response(200, json=completion({"role": "assistant", "content": "ok"}))

    tool = {"type": "function", "function": {"name": "t", "parameters": {"type": "object"}}}
    await make_llm(handler).chat([{"role": "user", "content": "x"}], tools=[tool], temperature=0.7)
    assert seen["model"] == "m"
    assert seen["temperature"] == 0.7
    assert seen["tools"] == [tool]


async def test_list_models() -> None:
    body = {"object": "list", "data": [{"id": "gemma", "object": "model", "owned_by": "x"}]}
    llm = make_llm(lambda r: httpx2.Response(200, json=body))
    assert await llm.list_models() == ["gemma"]


async def test_connection_refused() -> None:
    llm = make_llm(raises(httpx2.ConnectError("refused")))
    with pytest.raises(LLMUnavailable, match="lm.test"):
        await llm.chat([{"role": "user", "content": "x"}])


async def test_timeout() -> None:
    llm = make_llm(raises(httpx2.ReadTimeout("slow")))
    with pytest.raises(LLMTimeout):
        await llm.chat([{"role": "user", "content": "x"}])


async def test_model_not_loaded() -> None:
    llm = make_llm(
        lambda r: httpx2.Response(404, json={"error": {"message": "model 'm' not found"}})
    )
    with pytest.raises(LLMModelNotLoaded):
        await llm.chat([{"role": "user", "content": "x"}])


async def test_other_server_error_is_mapped_without_the_key() -> None:
    llm = make_llm(
        lambda r: httpx2.Response(500, json={"error": {"message": "boom"}}), api_key="secret-key"
    )
    with pytest.raises(LLMError) as exc:
        await llm.chat([{"role": "user", "content": "x"}])
    assert "secret-key" not in str(exc.value)
    assert not isinstance(exc.value, LLMModelNotLoaded)
