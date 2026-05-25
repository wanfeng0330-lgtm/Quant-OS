"""DeepSeek LLM Provider implementation."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from .base import (
    BaseLLMProvider,
    LLMConfig,
    LLMResponse,
    Message,
    StreamChunk,
    ToolCall,
    ToolDefinition,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API provider implementation."""

    provider_name = "deepseek"
    default_model = "deepseek-chat"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        default_model: str | None = None,
    ) -> None:
        super().__init__(api_key, base_url, default_model or self.default_model)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        config: LLMConfig | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to DeepSeek."""
        merged_config = self._merge_config(config)
        self._log_request(messages, tools, merged_config)

        payload = self._build_payload(messages, tools, merged_config, stream=False)

        try:
            response = await self._client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            llm_response = self._parse_response(data)
            self._log_response(llm_response)
            return llm_response

        except httpx.HTTPStatusError as e:
            logger.error("DeepSeek API error: %s - %s", e.response.status_code, e.response.text)
            if e.response.status_code == 429:
                from quant_os_shared.errors import LLMRateLimitError
                raise LLMRateLimitError("DeepSeek rate limit exceeded") from e
            elif e.response.status_code == 400 and "context_length" in e.response.text:
                from quant_os_shared.errors import LLMContextLengthError
                raise LLMContextLengthError("Context length exceeded") from e
            from quant_os_shared.errors import LLMError
            raise LLMError(f"DeepSeek API error: {e}") from e

        except Exception as e:
            logger.error("DeepSeek request failed: %s", e)
            from quant_os_shared.errors import LLMError
            raise LLMError(f"DeepSeek request failed: {e}") from e

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        config: LLMConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming chat completion request to DeepSeek."""
        merged_config = self._merge_config(config)
        merged_config.stream = True
        self._log_request(messages, tools, merged_config)

        payload = self._build_payload(messages, tools, merged_config, stream=True)

        try:
            async with self._client.stream(
                "POST", "/v1/chat/completions", json=payload
            ) as response:
                response.raise_for_status()

                buffer = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            chunk = self._parse_stream_chunk(data)
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse stream chunk: %s", data_str)

        except Exception as e:
            logger.error("DeepSeek stream request failed: %s", e)
            from quant_os_shared.errors import LLMError
            raise LLMError(f"DeepSeek stream request failed: {e}") from e

    async def validate_connection(self) -> bool:
        """Validate DeepSeek API connection."""
        try:
            response = await self.chat(
                [Message(role="user", content="Hello")],
                config=LLMConfig(max_tokens=10),
            )
            return response.content is not None
        except Exception:
            return False

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        config: LLMConfig,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build the API request payload."""
        payload: dict[str, Any] = {
            "model": config.model or self.default_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "stream": stream,
        }

        if config.frequency_penalty != 0:
            payload["frequency_penalty"] = config.frequency_penalty
        if config.presence_penalty != 0:
            payload["presence_penalty"] = config.presence_penalty
        if config.stop:
            payload["stop"] = config.stop

        if tools:
            payload["tools"] = [t.to_dict() for t in tools]
            payload["tool_choice"] = "auto"

        return payload

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse the API response."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Parse tool calls
        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = []
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                arguments = func.get("arguments", "{}")
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=arguments,
                ))

        # Parse usage
        usage = None
        if "usage" in data:
            usage_data = data["usage"]
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            model=data.get("model"),
            raw_response=data,
        )

    def _parse_stream_chunk(self, data: dict[str, Any]) -> StreamChunk | None:
        """Parse a streaming chunk."""
        choices = data.get("choices", [])
        if not choices:
            return None

        choice = choices[0]
        delta = choice.get("delta", {})

        content = delta.get("content")
        tool_calls = delta.get("tool_calls")
        finish_reason = choice.get("finish_reason")

        if content is None and tool_calls is None and finish_reason is None:
            return None

        return StreamChunk(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
