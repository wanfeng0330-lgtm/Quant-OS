"""AI Quant Research OS - Agent infrastructure."""

from .llm import (
    LLMProvider,
    LLMProviderFactory,
    Message,
    MessageRole,
    ToolDefinition,
    ToolCall,
    LLMResponse,
    TokenUsage,
    LLMConfig,
    StreamChunk,
    get_llm_provider,
)
from .tools import (
    Tool,
    BaseTool,
    FunctionTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
    ToolRegistry,
    tool_registry,
    register_tool,
    register_tool_function,
    # Stock tools
    GetStockInfoTool,
    SearchStocksTool,
    ListStocksTool,
    GetStockPriceTool,
    # Factor tools
    ComputeFactorTool,
    ListFactorsTool,
    AnalyzeFactorTool,
    # Backtest tools
    RunBacktestTool,
    GetBacktestResultTool,
    ListBacktestsTool,
)
from .workflows import (
    WorkflowStatus,
    NodeStatus,
    NodeType,
    NodeDefinition,
    NodeResult,
    WorkflowDefinition,
    WorkflowRun,
    NodeExecutor,
    BaseNodeExecutor,
    TaskNodeExecutor,
    ConditionNodeExecutor,
    ParallelNodeExecutor,
    LoopNodeExecutor,
    WorkflowEngine,
)

__version__ = "0.1.0"

__all__ = [
    # LLM
    "LLMProvider",
    "LLMProviderFactory",
    "Message",
    "MessageRole",
    "ToolDefinition",
    "ToolCall",
    "LLMResponse",
    "TokenUsage",
    "LLMConfig",
    "StreamChunk",
    "get_llm_provider",
    # Tools
    "Tool",
    "BaseTool",
    "FunctionTool",
    "ToolParameter",
    "ToolParameterType",
    "ToolResult",
    "ToolRegistry",
    "tool_registry",
    "register_tool",
    "register_tool_function",
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
    # Workflows
    "WorkflowStatus",
    "NodeStatus",
    "NodeType",
    "NodeDefinition",
    "NodeResult",
    "WorkflowDefinition",
    "WorkflowRun",
    "NodeExecutor",
    "BaseNodeExecutor",
    "TaskNodeExecutor",
    "ConditionNodeExecutor",
    "ParallelNodeExecutor",
    "LoopNodeExecutor",
    "WorkflowEngine",
]