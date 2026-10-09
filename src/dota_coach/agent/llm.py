import logging
import time
from dataclasses import dataclass
from typing import Any, cast

import openai
from openai import AsyncOpenAI, DefaultAsyncHttpxClient
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base class. Messages are safe to show to users and never contain the API key."""


class LLMUnavailable(LLMError):
    """The server cannot be reached (connection refused, host down)."""


class LLMTimeout(LLMError):
    """The server did not answer within the timeout."""


class LLMModelNotLoaded(LLMError):
    """The requested model is not loaded (or not known) on the server."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text exactly as the model produced it; may be malformed


@dataclass(frozen=True)
class ChatReply:
    content: str | None
    tool_calls: list[ToolCall]
    finish_reason: str | None
    latency: float  # seconds
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def message(self) -> dict[str, Any]:
        """The assistant message, ready to append to the conversation history."""
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in self.tool_calls
            ]
        return message


class LLMClient:
    """Thin wrapper over an OpenAI-compatible server (LM Studio) with mapped errors."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 120.0,
        max_retries: int = 2,
        http_client: DefaultAsyncHttpxClient | None = None,  # tests inject a mock transport
    ) -> None:
        self._base_url = base_url
        self._model = model
        # The SDK retries connection errors, 408/409/429 and 5xx with backoff.
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )

    @property
    def model(self) -> str:
        return self._model

    async def aclose(self) -> None:
        await self._client.close()

    def _map_error(self, exc: openai.OpenAIError) -> LLMError:
        if isinstance(exc, openai.APITimeoutError):
            return LLMTimeout(f"LLM did not answer in time ({self._base_url})")
        if isinstance(exc, openai.APIConnectionError):
            return LLMUnavailable(f"cannot reach the LLM server at {self._base_url}")
        if isinstance(exc, openai.APIStatusError):
            text = str(exc.message).lower()
            if isinstance(exc, openai.NotFoundError) or "model" in text:
                return LLMModelNotLoaded(f"model {self._model!r} is not loaded: {exc.message}")
            return LLMError(f"LLM server error {exc.status_code}: {exc.message}")
        return LLMError(str(exc))

    async def list_models(self) -> list[str]:
        try:
            page = await self._client.models.list()
        except openai.OpenAIError as exc:
            raise self._map_error(exc) from exc
        return [model.id for model in page.data]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatReply:
        started = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                tools=cast(list[ChatCompletionToolParam], tools) if tools else openai.omit,
                temperature=temperature,
                max_tokens=max_tokens if max_tokens is not None else openai.omit,
            )
        except openai.OpenAIError as exc:
            raise self._map_error(exc) from exc
        latency = time.perf_counter() - started
        choice = response.choices[0]
        calls = [
            ToolCall(call.id, call.function.name, call.function.arguments)
            for call in choice.message.tool_calls or []
            if call.type == "function"
        ]
        usage = response.usage
        return ChatReply(
            content=choice.message.content,
            tool_calls=calls,
            finish_reason=choice.finish_reason,
            latency=latency,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )
