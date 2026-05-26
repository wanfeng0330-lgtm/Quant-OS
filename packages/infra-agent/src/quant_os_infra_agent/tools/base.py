"""Tool Protocol and base types for Agent tool system."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class ToolParameterType(str, Enum):
    """Supported tool parameter types."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: ToolParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: list[Any] | None = None
    items: dict[str, Any] | None = None  # For array type
    properties: dict[str, Any] | None = None  # For object type

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON Schema property format."""
        result: dict[str, Any] = {
            "type": self.type.value,
            "description": self.description,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.enum:
            result["enum"] = self.enum
        if self.items:
            result["items"] = self.items
        if self.properties:
            result["properties"] = self.properties
        return result


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def to_llm_content(self) -> str:
        """Convert to content string for LLM response."""
        if self.success:
            if isinstance(self.data, str):
                return self.data
            import json
            return json.dumps(self.data, ensure_ascii=False, indent=2)
        else:
            return f"Error: {self.error}"


@runtime_checkable
class Tool(Protocol):
    """Protocol that all tools must implement."""

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        ...

    @property
    def description(self) -> str:
        """Return a description of what the tool does."""
        ...

    @property
    def parameters(self) -> list[ToolParameter]:
        """Return the list of parameters for this tool."""
        ...

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with the execution result
        """
        ...

    def to_definition(self) -> dict[str, Any]:
        """Convert to LLM tool definition format."""
        ...


class BaseTool(ABC):
    """Base class for tools with common functionality."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"tool.{self.name}")

    @property
    def required_parameters(self) -> list[ToolParameter]:
        """Return only required parameters."""
        return [p for p in self.parameters if p.required]

    @property
    def optional_parameters(self) -> list[ToolParameter]:
        """Return only optional parameters."""
        return [p for p in self.parameters if not p.required]

    def validate_parameters(self, **kwargs: Any) -> tuple[bool, str | None]:
        """Validate provided parameters against definition.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for param in self.required_parameters:
            if param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"

        # Check parameter types (basic validation)
        for param in self.parameters:
            if param.name in kwargs:
                value = kwargs[param.name]
                if param.type == ToolParameterType.STRING and not isinstance(value, str):
                    return False, f"Parameter '{param.name}' must be a string"
                elif param.type == ToolParameterType.NUMBER and not isinstance(value, (int, float)):
                    return False, f"Parameter '{param.name}' must be a number"
                elif param.type == ToolParameterType.INTEGER and not isinstance(value, int):
                    return False, f"Parameter '{param.name}' must be an integer"
                elif param.type == ToolParameterType.BOOLEAN and not isinstance(value, bool):
                    return False, f"Parameter '{param.name}' must be a boolean"

        return True, None

    def to_definition(self) -> dict[str, Any]:
        """Convert to LLM tool definition format (OpenAI compatible)."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_dict()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        }

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool. Must be implemented by subclasses."""
        ...

    async def safe_execute(self, **kwargs: Any) -> ToolResult:
        """Execute with validation and error handling."""
        # Validate parameters
        is_valid, error_msg = self.validate_parameters(**kwargs)
        if not is_valid:
            return ToolResult(success=False, error=error_msg)

        try:
            self._logger.info("Executing tool %s with args: %s", self.name, kwargs.keys())
            result = await self.execute(**kwargs)
            self._logger.info("Tool %s completed: success=%s", self.name, result.success)
            return result
        except Exception as e:
            self._logger.error("Tool %s failed: %s", self.name, str(e), exc_info=True)
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                metadata={"exception_type": type(e).__name__}
            )


class FunctionTool(BaseTool):
    """Tool wrapper for simple functions."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: list[ToolParameter],
        func: Callable[..., Any],
    ) -> None:
        self._name = name
        self._description = description
        self._parameters = parameters
        self._func = func
        super().__init__()

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> list[ToolParameter]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the wrapped function."""
        import asyncio
        import inspect

        try:
            if inspect.iscoroutinefunction(self._func):
                result = await self._func(**kwargs)
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: self._func(**kwargs))

            if isinstance(result, ToolResult):
                return result
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))