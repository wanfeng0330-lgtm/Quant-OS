"""LLM Provider Protocol and base types."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single message in a conversation."""
    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-compatible dictionary."""
        d = {"role": self.role.value, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by the LLM."""
    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-compatible dictionary."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


@dataclass
class ToolCall:
    """A tool call made by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    model: str | None = None
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class TokenUsage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def cost_estimate(self) -> float:
        """Estimate cost in USD (rough estimate)."""
        # Rough estimate: $0.01 per 1K tokens
        return self.total_tokens / 1000 * 0.01


@dataclass
class LLMConfig:
    """Configuration for LLM calls."""
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: list[str] | None = None
    stream: bool = False
    tool_choice: str | None = None


@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all LLM providers must implement."""

    @property
    def provider_name(self) -> str:
        """Return the name of this provider."""
        ...

    @property
    def default_model(self) -> str:
        """Return the default model for this provider."""
        ...

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        config: LLMConfig | None = None,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tools available to the LLM
            config: Optional configuration overrides

        Returns:
            LLMResponse with the model's response
        """
        ...

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        config: LLMConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming chat completion request.

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tools available to the LLM
            config: Optional configuration overrides

        Yields:
            StreamChunk objects as they arrive
        """
        ...

    async def validate_connection(self) -> bool:
        """Validate that the connection to the LLM provider is working.

        Returns:
            True if connection is valid
        """
        ...


class BaseLLMProvider(ABC):
    """Base class for LLM providers with common functionality."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._default_model = default_model

    @property
    def default_model(self) -> str:
        return self._default_model or "default"

    def _merge_config(self, config: LLMConfig | None) -> LLMConfig:
        """Merge provided config with defaults."""
        if config is None:
            return LLMConfig()
        return config

    def _extract_usage(self, response: Any) -> TokenUsage | None:
        """Extract token usage from response. Override in subclasses."""
        return None

    def _log_request(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        config: LLMConfig,
    ) -> None:
        """Log the request for debugging."""
        logger.debug(
            "LLM Request: model=%s, messages=%d, tools=%d",
            config.model or self.default_model,
            len(messages),
            len(tools) if tools else 0,
        )

    def _log_response(self, response: LLMResponse) -> None:
        """Log the response for debugging."""
        logger.debug(
            "LLM Response: finish_reason=%s, tool_calls=%d, tokens=%s",
            response.finish_reason,
            len(response.tool_calls) if response.tool_calls else 0,
            response.usage.total_tokens if response.usage else "unknown",
        )
