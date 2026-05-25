"""Tests for the tool system."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from quant_os_infra_agent.tools.base import (
    BaseTool,
    FunctionTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)
from quant_os_infra_agent.tools.registry import ToolRegistry, tool_registry


class MockTool(BaseTool):
    """Mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="input",
                type=ToolParameterType.STRING,
                description="Input string",
                required=True,
            ),
            ToolParameter(
                name="count",
                type=ToolParameterType.INTEGER,
                description="Number of times to repeat",
                required=False,
                default=1,
            ),
        ]

    async def execute(self, input: str, count: int = 1) -> ToolResult:
        return ToolResult(success=True, data=input * count)


@pytest.fixture
def mock_tool():
    return MockTool()


@pytest.fixture
def tool_registry_instance():
    registry = ToolRegistry()
    registry.clear()
    return registry


class TestToolParameter:
    def test_to_dict(self):
        param = ToolParameter(
            name="test",
            type=ToolParameterType.STRING,
            description="Test parameter",
        )
        result = param.to_dict()
        assert result == {
            "type": "string",
            "description": "Test parameter",
        }

    def test_to_dict_with_enum(self):
        param = ToolParameter(
            name="test",
            type=ToolParameterType.STRING,
            description="Test parameter",
            enum=["a", "b", "c"],
        )
        result = param.to_dict()
        assert result["enum"] == ["a", "b", "c"]


class TestToolResult:
    def test_to_dict_success(self):
        result = ToolResult(success=True, data="test data")
        assert result.to_dict() == {
            "success": True,
            "data": "test data",
        }

    def test_to_dict_error(self):
        result = ToolResult(success=False, error="test error")
        assert result.to_dict() == {
            "success": False,
            "error": "test error",
        }

    def test_to_llm_content_success(self):
        result = ToolResult(success=True, data="test data")
        assert result.to_llm_content() == "test data"

    def test_to_llm_content_error(self):
        result = ToolResult(success=False, error="test error")
        assert result.to_llm_content() == "Error: test error"


class TestBaseTool:
    def test_validate_parameters_valid(self, mock_tool):
        is_valid, error = mock_tool.validate_parameters(input="test")
        assert is_valid is True
        assert error is None

    def test_validate_parameters_missing_required(self, mock_tool):
        is_valid, error = mock_tool.validate_parameters()
        assert is_valid is False
        assert "Missing required parameter: input" in error

    def test_validate_parameters_wrong_type(self, mock_tool):
        is_valid, error = mock_tool.validate_parameters(input=123)
        assert is_valid is False
        assert "must be a string" in error

    def test_to_definition(self, mock_tool):
        definition = mock_tool.to_definition()
        assert definition["type"] == "function"
        assert definition["function"]["name"] == "mock_tool"
        assert "input" in definition["function"]["parameters"]["properties"]
        assert "input" in definition["function"]["parameters"]["required"]

    @pytest.mark.asyncio
    async def test_safe_execute_success(self, mock_tool):
        result = await mock_tool.safe_execute(input="test", count=2)
        assert result.success is True
        assert result.data == "testtest"

    @pytest.mark.asyncio
    async def test_safe_execute_validation_error(self, mock_tool):
        result = await mock_tool.safe_execute()
        assert result.success is False
        assert "Missing required parameter" in result.error


class TestFunctionTool:
    @pytest.mark.asyncio
    async def test_execute_sync_function(self):
        def sync_func(x: int, y: int) -> int:
            return x + y

        tool = FunctionTool(
            name="add",
            description="Add two numbers",
            parameters=[
                ToolParameter(name="x", type=ToolParameterType.INTEGER, description="First number"),
                ToolParameter(name="y", type=ToolParameterType.INTEGER, description="Second number"),
            ],
            func=sync_func,
        )

        result = await tool.safe_execute(x=5, y=3)
        assert result.success is True
        assert result.data == 8

    @pytest.mark.asyncio
    async def test_execute_async_function(self):
        async def async_func(x: int, y: int) -> int:
            return x * y

        tool = FunctionTool(
            name="multiply",
            description="Multiply two numbers",
            parameters=[
                ToolParameter(name="x", type=ToolParameterType.INTEGER, description="First number"),
                ToolParameter(name="y", type=ToolParameterType.INTEGER, description="Second number"),
            ],
            func=async_func,
        )

        result = await tool.safe_execute(x=5, y=3)
        assert result.success is True
        assert result.data == 15


class TestToolRegistry:
    def test_register_tool(self, tool_registry_instance, mock_tool):
        tool_registry_instance.register(mock_tool)
        assert tool_registry_instance.get("mock_tool") == mock_tool

    def test_register_duplicate_tool(self, tool_registry_instance, mock_tool):
        tool_registry_instance.register(mock_tool)
        # Should not raise, just log warning
        tool_registry_instance.register(mock_tool)

    def test_get_nonexistent_tool(self, tool_registry_instance):
        assert tool_registry_instance.get("nonexistent") is None

    def test_list_tools(self, tool_registry_instance, mock_tool):
        tool_registry_instance.register(mock_tool)
        tools = tool_registry_instance.list_tools()
        assert "mock_tool" in tools

    def test_get_definitions(self, tool_registry_instance, mock_tool):
        tool_registry_instance.register(mock_tool)
        definitions = tool_registry_instance.get_definitions()
        assert len(definitions) == 1
        assert definitions[0]["function"]["name"] == "mock_tool"

    @pytest.mark.asyncio
    async def test_execute_tool(self, tool_registry_instance, mock_tool):
        tool_registry_instance.register(mock_tool)
        result = await tool_registry_instance.execute("mock_tool", input="test")
        assert result.success is True
        assert result.data == "test"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, tool_registry_instance):
        result = await tool_registry_instance.execute("nonexistent")
        assert result.success is False
        assert "not found" in result.error

    def test_clear(self, tool_registry_instance, mock_tool):
        tool_registry_instance.register(mock_tool)
        tool_registry_instance.clear()
        assert tool_registry_instance.get("mock_tool") is None


if __name__ == "__main__":
    pytest.main([__file__])