"""Tool Registry for managing and discovering tools."""

from __future__ import annotations

import logging
from typing import Any, Callable, Type

from .base import BaseTool, Tool, ToolParameter, ToolParameterType, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Singleton registry for tools."""

    _instance: ToolRegistry | None = None
    _tools: dict[str, BaseTool] = {}

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._tools = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> ToolRegistry:
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the registry (for testing)."""
        cls._instance = None
        cls._tools = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool name already registered
        """
        if tool.name in self._tools:
            logger.warning("Tool '%s' already registered, overwriting", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def register_function(
        self,
        name: str,
        description: str,
        parameters: list[ToolParameter],
        func: Callable[..., Any],
    ) -> None:
        """Register a function as a tool.

        Args:
            name: Tool name
            description: Tool description
            parameters: Tool parameters
            func: Function to execute
        """
        from .base import FunctionTool
        tool = FunctionTool(name, description, parameters, func)
        self.register(tool)

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in LLM-compatible format.

        Returns:
            List of tool definitions for LLM
        """
        return [tool.to_definition() for tool in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            ToolResult from execution

        Raises:
            ValueError: If tool not found
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found",
            )

        return await tool.safe_execute(**kwargs)

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        logger.debug("Cleared all tools")


# Global registry instance
tool_registry = ToolRegistry.get_instance()


def register_tool(tool_class: Type[BaseTool]) -> Type[BaseTool]:
    """Decorator to register a tool class.

    Usage:
        @register_tool
        class MyTool(BaseTool):
            ...
    """
    instance = tool_class()
    tool_registry.register(instance)
    return tool_class


def register_tool_function(
    name: str,
    description: str,
    parameters: list[ToolParameter],
) -> Callable:
    """Decorator to register a function as a tool.

    Usage:
        @register_tool_function(
            name="my_tool",
            description="Does something",
            parameters=[
                ToolParameter(name="arg1", type=ToolParameterType.STRING, description="First arg"),
            ]
        )
        async def my_tool(arg1: str) -> ToolResult:
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_registry.register_function(name, description, parameters, func)
        return func
    return decorator


# Convenience functions for common parameter types
def string_param(name: str, description: str, required: bool = True) -> ToolParameter:
    """Create a string parameter."""
    return ToolParameter(
        name=name,
        type=ToolParameterType.STRING,
        description=description,
        required=required,
    )


def number_param(name: str, description: str, required: bool = True) -> ToolParameter:
    """Create a number parameter."""
    return ToolParameter(
        name=name,
        type=ToolParameterType.NUMBER,
        description=description,
        required=required,
    )


def integer_param(name: str, description: str, required: bool = True) -> ToolParameter:
    """Create an integer parameter."""
    return ToolParameter(
        name=name,
        type=ToolParameterType.INTEGER,
        description=description,
        required=required,
    )


def boolean_param(name: str, description: str, required: bool = True) -> ToolParameter:
    """Create a boolean parameter."""
    return ToolParameter(
        name=name,
        type=ToolParameterType.BOOLEAN,
        description=description,
        required=required,
    )


def array_param(
    name: str,
    description: str,
    items_type: ToolParameterType = ToolParameterType.STRING,
    required: bool = True,
) -> ToolParameter:
    """Create an array parameter."""
    return ToolParameter(
        name=name,
        type=ToolParameterType.ARRAY,
        description=description,
        required=required,
        items={"type": items_type.value},
    )