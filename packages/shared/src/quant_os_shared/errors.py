"""Exception hierarchy for AI Quant Research OS."""

from __future__ import annotations


class QuantOSError(Exception):
    """Base exception for all platform errors."""
    def __init__(self, message: str, code: str | None = None, details: dict | None = None) -> None:
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(message)


# --- Data Layer Errors ---

class DataError(QuantOSError):
    """Base error for data operations."""
    pass


class DataProviderError(DataError):
    """Error from external data provider (AKShare, Tushare)."""
    pass


class DataValidationError(DataError):
    """Data validation failed."""
    pass


class DataNotFoundError(DataError):
    """Requested data not found."""
    pass


class DataSyncError(DataError):
    """Data synchronization failed."""
    pass


# --- Factor Errors ---

class FactorError(QuantOSError):
    """Base error for factor operations."""
    pass


class FactorNotFoundError(FactorError):
    """Factor not found in registry."""
    pass


class FactorComputeError(FactorError):
    """Factor computation failed."""
    pass


class FactorRegistrationError(FactorError):
    """Factor registration failed."""
    pass


# --- Backtest Errors ---

class BacktestError(QuantOSError):
    """Base error for backtest operations."""
    pass


class BacktestConfigError(BacktestError):
    """Invalid backtest configuration."""
    pass


class BacktestExecutionError(BacktestError):
    """Backtest execution failed."""
    pass


class BacktestEngineError(BacktestError):
    """Backtest engine internal error."""
    pass


# --- Agent Errors ---

class AgentError(QuantOSError):
    """Base error for agent operations."""
    pass


class LLMError(AgentError):
    """LLM provider error."""
    pass


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""
    pass


class LLMContextLengthError(LLMError):
    """Input exceeds model context length."""
    pass


class ToolError(AgentError):
    """Tool execution error."""
    pass


class ToolNotFoundError(ToolError):
    """Tool not found in registry."""
    pass


class ToolTimeoutError(ToolError):
    """Tool execution timed out."""
    pass


class WorkflowError(AgentError):
    """Workflow execution error."""
    pass


class WorkflowCycleError(WorkflowError):
    """Cycle detected in workflow DAG."""
    pass


class WorkflowTimeoutError(WorkflowError):
    """Workflow execution timed out."""
    pass


class MaxIterationsError(WorkflowError):
    """Maximum iterations exceeded."""
    pass


# --- Infrastructure Errors ---

class InfraError(QuantOSError):
    """Base error for infrastructure operations."""
    pass


class DatabaseError(InfraError):
    """Database operation failed."""
    pass


class CacheError(InfraError):
    """Cache operation failed."""
    pass


class VectorStoreError(InfraError):
    """Vector store operation failed."""
    pass
