"""Tool system for Agent."""

from .base import (
    BaseTool,
    FunctionTool,
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)
from .registry import (
    ToolRegistry,
    array_param,
    boolean_param,
    integer_param,
    number_param,
    register_tool,
    register_tool_function,
    string_param,
    tool_registry,
)

# Import tools to trigger registration
from .stock_tools import (
    GetStockInfoTool,
    SearchStocksTool,
    ListStocksTool,
    GetStockPriceTool,
)
from .factor_tools import (
    ComputeFactorTool,
    ListFactorsTool,
    AnalyzeFactorTool,
)
from .backtest_tools import (
    RunBacktestTool,
    GetBacktestResultTool,
    ListBacktestsTool,
)

__all__ = [
    # Base types
    "Tool",
    "BaseTool",
    "FunctionTool",
    "ToolParameter",
    "ToolParameterType",
    "ToolResult",
    # Registry
    "ToolRegistry",
    "tool_registry",
    "register_tool",
    "register_tool_function",
    # Parameter helpers
    "string_param",
    "number_param",
    "integer_param",
    "boolean_param",
    "array_param",
    # Stock tools
    "GetStockInfoTool",
    "SearchStocksTool",
    "ListStocksTool",
    "GetStockPriceTool",
    # Factor tools
    "ComputeFactorTool",
    "ListFactorsTool",
    "AnalyzeFactorTool",
    # Backtest tools
    "RunBacktestTool",
    "GetBacktestResultTool",
    "ListBacktestsTool",
]