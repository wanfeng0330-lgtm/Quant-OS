"""Workflow base types and protocols."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class NodeStatus(str, Enum):
    """Node execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeType(str, Enum):
    """Types of workflow nodes."""
    START = "start"
    END = "end"
    TASK = "task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"


@dataclass
class NodeDefinition:
    """Definition of a workflow node."""
    id: str
    name: str
    type: NodeType
    config: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # Node IDs this depends on

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "config": self.config,
            "dependencies": self.dependencies,
        }


@dataclass
class NodeResult:
    """Result of a node execution."""
    node_id: str
    status: NodeStatus
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "node_id": self.node_id,
            "status": self.status.value,
        }
        if self.output is not None:
            result["output"] = self.output
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class WorkflowDefinition:
    """Definition of a workflow."""
    id: str
    name: str
    description: str = ""
    nodes: list[NodeDefinition] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "config": self.config,
        }

    def get_node(self, node_id: str) -> NodeDefinition | None:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_dependencies(self, node_id: str) -> list[NodeDefinition]:
        """Get all dependencies for a node."""
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.get_node(dep_id) for dep_id in node.dependencies if self.get_node(dep_id)]

    def get_dependents(self, node_id: str) -> list[NodeDefinition]:
        """Get all nodes that depend on this node."""
        return [
            node for node in self.nodes
            if node_id in node.dependencies
        ]


@dataclass
class WorkflowRun:
    """Runtime state of a workflow execution."""
    id: str
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: Any = None
    completed_at: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "node_results": {k: v.to_dict() for k, v in self.node_results.items()},
            "context": self.context,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return self.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED)


@runtime_checkable
class NodeExecutor(Protocol):
    """Protocol for node executors."""

    async def execute(
        self,
        node: NodeDefinition,
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a workflow node.

        Args:
            node: Node definition
            context: Workflow context with previous node outputs

        Returns:
            NodeResult with execution result
        """
        ...


class BaseNodeExecutor(ABC):
    """Base class for node executors."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"workflow.node.{self.__class__.__name__}")

    @abstractmethod
    async def execute(
        self,
        node: NodeDefinition,
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a workflow node. Must be implemented by subclasses."""
        ...

    def _create_success_result(self, node_id: str, output: Any) -> NodeResult:
        """Create a success result."""
        return NodeResult(
            node_id=node_id,
            status=NodeStatus.COMPLETED,
            output=output,
        )

    def _create_error_result(self, node_id: str, error: str) -> NodeResult:
        """Create an error result."""
        return NodeResult(
            node_id=node_id,
            status=NodeStatus.FAILED,
            error=error,
        )


class TaskNodeExecutor(BaseNodeExecutor):
    """Executor for task nodes that call tools or functions."""

    def __init__(self, tool_registry: Any = None) -> None:
        super().__init__()
        self._tool_registry = tool_registry

    async def execute(
        self,
        node: NodeDefinition,
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a task node."""
        try:
            config = node.config
            task_type = config.get("type", "tool")

            if task_type == "tool":
                return await self._execute_tool(node, config, context)
            elif task_type == "function":
                return await self._execute_function(node, config, context)
            elif task_type == "llm":
                return await self._execute_llm(node, config, context)
            else:
                return self._create_error_result(
                    node.id,
                    f"Unknown task type: {task_type}",
                )
        except Exception as e:
            self._logger.error("Task node %s failed: %s", node.id, e)
            return self._create_error_result(node.id, str(e))

    async def _execute_tool(
        self,
        node: NodeDefinition,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a tool call."""
        if not self._tool_registry:
            return self._create_error_result(node.id, "Tool registry not available")

        tool_name = config.get("tool")
        if not tool_name:
            return self._create_error_result(node.id, "Tool name not specified")

        # Resolve parameters from context
        params = self._resolve_params(config.get("parameters", {}), context)

        result = await self._tool_registry.execute(tool_name, **params)
        if result.success:
            return self._create_success_result(node.id, result.data)
        else:
            return self._create_error_result(node.id, result.error or "Tool execution failed")

    async def _execute_function(
        self,
        node: NodeDefinition,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a function."""
        func_path = config.get("function")
        if not func_path:
            return self._create_error_result(node.id, "Function path not specified")

        try:
            # Import and call the function
            module_path, func_name = func_path.rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)

            # Resolve parameters from context
            params = self._resolve_params(config.get("parameters", {}), context)

            import asyncio
            import inspect
            if inspect.iscoroutinefunction(func):
                output = await func(**params)
            else:
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(None, lambda: func(**params))

            return self._create_success_result(node.id, output)
        except Exception as e:
            return self._create_error_result(node.id, f"Function execution failed: {e}")

    async def _execute_llm(
        self,
        node: NodeDefinition,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute an LLM call."""
        # This will be implemented when integrating with LLM providers
        return self._create_error_result(node.id, "LLM execution not implemented yet")

    def _resolve_params(
        self,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve parameter values from context."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # Reference to context variable
                var_name = value[1:]
                resolved[key] = context.get(var_name)
            else:
                resolved[key] = value
        return resolved


class ConditionNodeExecutor(BaseNodeExecutor):
    """Executor for condition nodes."""

    async def execute(
        self,
        node: NodeDefinition,
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a condition node."""
        try:
            config = node.config
            condition_type = config.get("type", "expression")

            if condition_type == "expression":
                return await self._evaluate_expression(node, config, context)
            elif condition_type == "threshold":
                return await self._evaluate_threshold(node, config, context)
            else:
                return self._create_error_result(
                    node.id,
                    f"Unknown condition type: {condition_type}",
                )
        except Exception as e:
            self._logger.error("Condition node %s failed: %s", node.id, e)
            return self._create_error_result(node.id, str(e))

    async def _evaluate_expression(
        self,
        node: NodeDefinition,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> NodeResult:
        """Evaluate a Python expression."""
        expression = config.get("expression")
        if not expression:
            return self._create_error_result(node.id, "Expression not specified")

        try:
            # Create a safe evaluation context
            eval_context = {"context": context, "result": None}
            exec(f"result = {expression}", eval_context)
            result = eval_context["result"]

            return self._create_success_result(node.id, {
                "condition_result": bool(result),
                "value": result,
            })
        except Exception as e:
            return self._create_error_result(node.id, f"Expression evaluation failed: {e}")

    async def _evaluate_threshold(
        self,
        node: NodeDefinition,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> NodeResult:
        """Evaluate a threshold condition."""
        value_key = config.get("value")
        threshold = config.get("threshold")
        operator = config.get("operator", ">")

        if not value_key or threshold is None:
            return self._create_error_result(node.id, "Value or threshold not specified")

        value = context.get(value_key)
        if value is None:
            return self._create_error_result(node.id, f"Value '{value_key}' not found in context")

        try:
            value = float(value)
            threshold = float(threshold)

            if operator == ">":
                result = value > threshold
            elif operator == ">=":
                result = value >= threshold
            elif operator == "<":
                result = value < threshold
            elif operator == "<=":
                result = value <= threshold
            elif operator == "==":
                result = value == threshold
            elif operator == "!=":
                result = value != threshold
            else:
                return self._create_error_result(node.id, f"Unknown operator: {operator}")

            return self._create_success_result(node.id, {
                "condition_result": result,
                "value": value,
                "threshold": threshold,
                "operator": operator,
            })
        except ValueError as e:
            return self._create_error_result(node.id, f"Invalid value or threshold: {e}")