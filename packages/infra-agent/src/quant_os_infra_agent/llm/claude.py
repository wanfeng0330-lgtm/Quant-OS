"""Claude (Anthropic) LLM Provider implementation."""

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
    MessageRole,
    StreamChunk,
    ToolCall,
    ToolDefinition,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API provider implementation."""

    provider_name = "claude"
    default_model = "claude-3-5-sonnet-20241022"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        default_model: str | None = None,
    ) -> None:
        super().__init__(api_key, base_url, default_model or self.default_model)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
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
        """Send a chat completion request to Claude."""
        merged_config = self._merge_config(config)
        self._log_request(messages, tools, merged_config)

        payload = self._build_payload(messages, tools, merged_config, stream=False)

        try:
            response = await self._client.post("/v1/messages", json=payload)
            response.raise_for_status()
            data = response.json()

            llm_response = self._parse_response(data)
            self._log_response(llm_response)
            return llm_response

        except httpx.HTTPStatusError as e:
            logger.error("Claude API error: %s - %s", e.response.status_code, e.response.text)
            if e.response.status_code == 429:
                from quant_os_shared.errors import LLMRateLimitError
                raise LLMRateLimitError("Claude rate limit exceeded") from e
            elif e.response.status_code == 400:
                error_data = e.response.json()
                if "context_length" in str(error_data):
                    from quant_os_shared.errors import LLMContextLengthError
                    raise LLMContextLengthError("Context length exceeded") from e
            from quant_os_shared.errors import LLMError
            raise LLMError(f"Claude API error: {e}") from e

        except Exception as e:
            logger.error("Claude request failed: %s", e)
            from quant_os_shared.errors import LLMError
            raise LLMError(f"Claude request failed: {e}") from e

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        config: LLMConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming chat completion request to Claude."""
        merged_config = self._merge_config(config)
        self._log_request(messages, tools, merged_config)

        payload = self._build_payload(messages, tools, merged_config, stream=True)

        try:
            async with self._client.stream(
                "POST", "/v1/messages", json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]

                        try:
                            data = json.loads(data_str)
                            chunk = self._parse_stream_chunk(data)
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse stream chunk: %s", data_str)

        except Exception as e:
            logger.error("Claude stream request failed: %s", e)
            from quant_os_shared.errors import LLMError
            raise LLMError(f"Claude stream request failed: {e}") from e

    async def validate_connection(self) -> bool:
        """Validate Claude API connection."""
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
        """Build the API request payload for Claude."""
        # Extract system message
        system_message = None
        chat_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_message = msg.content
            else:
                chat_messages.append(self._convert_message(msg))

        payload: dict[str, Any] = {
            "model": config.model or self.default_model,
            "messages": chat_messages,
            "max_tokens": config.max_tokens,
            "stream": stream,
        }

        if system_message:
            payload["system"] = system_message

        if config.temperature != 0.7:
            payload["temperature"] = config.temperature

        if config.top_p != 1.0:
            payload["top_p"] = config.top_p

        if config.stop:
            payload["stop_sequences"] = config.stop

        if tools:
            payload["tools"] = [self._convert_tool(t) for t in tools]

        return payload

    def _convert_message(self, message: Message) -> dict[str, Any]:
        """Convert a Message to Claude format."""
        if message.role == MessageRole.TOOL:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id,
                        "content": message.content,
                    }
                ],
            }
        
        if message.role == MessageRole.ASSISTANT and message.tool_calls:
            content = []
            if message.content:
                content.append({"type": "text", "text": message.content})
            for tc in message.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": tc.get("function", {}).get("name", ""),
                    "input": tc.get("function", {}).get("arguments", {}),
                })
            return {"role": "assistant", "content": content}

        return {"role": message.role.value, "content": message.content}

    def _convert_tool(self, tool: ToolDefinition) -> dict[str, Any]:
        """Convert a ToolDefinition to Claude format."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse the Claude API response."""
        content = ""
        tool_calls = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    arguments=block.get("input", {}),
                ))

        # Parse usage
        usage = None
        if "usage" in data:
            usage_data = data["usage"]
            usage = TokenUsage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            )

        return LLMResponse(
            content=content if content else None,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=data.get("stop_reason"),
            usage=usage,
            model=data.get("model"),
            raw_response=data,
        )

    def _parse_stream_chunk(self, data: dict[str, Any]) -> StreamChunk | None:
        """Parse a Claude streaming chunk."""
        event_type = data.get("type")

        if event_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return StreamChunk(content=delta.get("text"))
            elif delta.get("type") == "input_json_delta":
                return StreamChunk(tool_calls=[delta])

        elif event_type == "message_delta":
            delta = data.get("delta", {})
            return StreamChunk(finish_reason=delta.get("stop_reason"))

        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
