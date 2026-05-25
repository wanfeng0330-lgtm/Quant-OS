"""Workflow DAG execution engine."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from .base import (
    BaseNodeExecutor,
    ConditionNodeExecutor,
    NodeDefinition,
    NodeExecutor,
    NodeResult,
    NodeStatus,
    NodeType,
    TaskNodeExecutor,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """DAG-based workflow execution engine."""

    def __init__(self, tool_registry: Any = None) -> None:
        self._executors: dict[NodeType, NodeExecutor] = {
            NodeType.TASK: TaskNodeExecutor(tool_registry),
            NodeType.CONDITION: ConditionNodeExecutor(),
        }
        self._running_workflows: dict[str, WorkflowRun] = {}

    def register_executor(self, node_type: NodeType, executor: NodeExecutor) -> None:
        """Register a custom node executor.

        Args:
            node_type: Type of node this executor handles
            executor: Executor instance
        """
        self._executors[node_type] = executor

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        initial_context: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Execute a workflow.

        Args:
            workflow: Workflow definition to execute
            initial_context: Initial context variables

        Returns:
            WorkflowRun with execution results
        """
        run_id = str(uuid.uuid4())
        run = WorkflowRun(
            id=run_id,
            workflow_id=workflow.id,
            status=WorkflowStatus.RUNNING,
            context=initial_context or {},
            started_at=datetime.now(),
        )

        self._running_workflows[run_id] = run
        logger.info("Starting workflow %s (run %s)", workflow.id, run_id)

        try:
            # Build execution graph
            graph = self._build_graph(workflow)

            # Execute nodes in topological order
            await self._execute_graph(workflow, run, graph)

            # Check final status
            if run.status == WorkflowStatus.RUNNING:
                run.status = WorkflowStatus.COMPLETED
                run.completed_at = datetime.now()
                logger.info("Workflow %s completed successfully", workflow.id)

        except Exception as e:
            run.status = WorkflowStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()
            logger.error("Workflow %s failed: %s", workflow.id, e)

        finally:
            self._running_workflows.pop(run_id, None)

        return run

    async def execute_node(
        self,
        node: NodeDefinition,
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a single node.

        Args:
            node: Node definition to execute
            context: Current workflow context

        Returns:
            NodeResult with execution result
        """
        executor = self._executors.get(node.type)
        if not executor:
            return NodeResult(
                node_id=node.id,
                status=NodeStatus.FAILED,
                error=f"No executor registered for node type: {node.type}",
            )

        return await executor.execute(node, context)

    def _build_graph(self, workflow: WorkflowDefinition) -> dict[str, list[str]]:
        """Build execution graph from workflow definition.

        Returns:
            Adjacency list representation of the graph
        """
        graph: dict[str, list[str]] = {}

        for node in workflow.nodes:
            graph[node.id] = []

        # Add edges from dependencies
        for node in workflow.nodes:
            for dep_id in node.dependencies:
                if dep_id in graph:
                    graph[dep_id].append(node.id)

        return graph

    async def _execute_graph(
        self,
        workflow: WorkflowDefinition,
        run: WorkflowRun,
        graph: dict[str, list[str]],
    ) -> None:
        """Execute workflow graph.

        This implements a simple topological sort execution with parallel support.
        """
        # Find start nodes (nodes with no dependencies)
        start_nodes = [
            node for node in workflow.nodes
            if not node.dependencies
        ]

        if not start_nodes:
            raise ValueError("Workflow has no start nodes")

        # Execute nodes level by level
        executed = set()
        current_level = [node.id for node in start_nodes]

        while current_level and run.status == WorkflowStatus.RUNNING:
            # Execute current level nodes in parallel
            tasks = []
            for node_id in current_level:
                node = workflow.get_node(node_id)
                if node:
                    tasks.append(self._execute_node_with_context(workflow, run, node))

            # Wait for all nodes in current level to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for node_id, result in zip(current_level, results):
                if isinstance(result, Exception):
                    run.node_results[node_id] = NodeResult(
                        node_id=node_id,
                        status=NodeStatus.FAILED,
                        error=str(result),
                    )
                    run.status = WorkflowStatus.FAILED
                    run.error = f"Node {node_id} failed: {result}"
                    return
                else:
                    run.node_results[node_id] = result
                    executed.add(node_id)

                    # Update context with node output
                    if result.output is not None:
                        run.context[f"node_{node_id}_output"] = result.output

            # Find next level nodes
            next_level = []
            for node_id in current_level:
                for dependent_id in graph.get(node_id, []):
                    # Check if all dependencies are satisfied
                    dependent_node = workflow.get_node(dependent_id)
                    if dependent_node:
                        all_deps_met = all(
                            dep_id in executed
                            for dep_id in dependent_node.dependencies
                        )
                        if all_deps_met and dependent_id not in executed:
                            next_level.append(dependent_id)

            current_level = next_level

    async def _execute_node_with_context(
        self,
        workflow: WorkflowDefinition,
        run: WorkflowRun,
        node: NodeDefinition,
    ) -> NodeResult:
        """Execute a node with proper context preparation."""
        # Prepare context with dependencies' outputs
        context = dict(run.context)

        # Add dependency outputs to context
        for dep_id in node.dependencies:
            dep_result = run.node_results.get(dep_id)
            if dep_result and dep_result.output is not None:
                context[f"dep_{dep_id}_output"] = dep_result.output

        # Execute the node
        result = await self.execute_node(node, context)

        # Handle condition nodes - determine which branch to take
        if node.type == NodeType.CONDITION and result.status == NodeStatus.COMPLETED:
            await self._handle_condition_result(workflow, run, node, result)

        return result

    async def _handle_condition_result(
        self,
        workflow: WorkflowDefinition,
        run: WorkflowRun,
        node: NodeDefinition,
        result: NodeResult,
    ) -> None:
        """Handle condition node result to determine branch execution."""
        if not result.output or not isinstance(result.output, dict):
            return

        condition_result = result.output.get("condition_result", False)
        config = node.config

        # Get true/false branch node IDs
        true_branch = config.get("true_branch")
        false_branch = config.get("false_branch")

        # Mark the non-taken branch as skipped
        if condition_result and false_branch:
            false_node = workflow.get_node(false_branch)
            if false_node:
                run.node_results[false_branch] = NodeResult(
                    node_id=false_branch,
                    status=NodeStatus.SKIPPED,
                    output=None,
                )
        elif not condition_result and true_branch:
            true_node = workflow.get_node(true_branch)
            if true_node:
                run.node_results[true_branch] = NodeResult(
                    node_id=true_branch,
                    status=NodeStatus.SKIPPED,
                    output=None,
                )

    async def cancel_workflow(self, run_id: str) -> bool:
        """Cancel a running workflow.

        Args:
            run_id: Workflow run ID to cancel

        Returns:
            True if cancelled successfully
        """
        run = self._running_workflows.get(run_id)
        if not run:
            return False

        run.status = WorkflowStatus.CANCELLED
        run.completed_at = datetime.now()
        return True

    def get_running_workflows(self) -> list[WorkflowRun]:
        """Get list of currently running workflows."""
        return list(self._running_workflows.values())

    def get_workflow_status(self, run_id: str) -> WorkflowRun | None:
        """Get status of a workflow run."""
        return self._running_workflows.get(run_id)


class ParallelNodeExecutor(BaseNodeExecutor):
    """Executor for parallel node groups."""

    async def execute(
        self,
        node: NodeDefinition,
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a parallel node group."""
        try:
            config = node.config
            nodes = config.get("nodes", [])

            if not nodes:
                return self._create_error_result(node.id, "No nodes specified for parallel execution")

            # Execute all nodes in parallel
            tasks = []
            for sub_node_config in nodes:
                # This is a simplified version - in practice, you'd create actual node objects
                tasks.append(self._execute_sub_node(sub_node_config, context))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect results
            outputs = []
            errors = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    errors.append(f"Node {i}: {result}")
                else:
                    outputs.append(result)

            if errors:
                return self._create_error_result(
                    node.id,
                    f"Parallel execution failed: {'; '.join(errors)}",
                )

            return self._create_success_result(node.id, outputs)

        except Exception as e:
            self._logger.error("Parallel node %s failed: %s", node.id, e)
            return self._create_error_result(node.id, str(e))

    async def _execute_sub_node(
        self,
        node_config: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """Execute a sub-node in parallel."""
        # This is a placeholder - implement based on your specific needs
        node_type = node_config.get("type", "task")
        if node_type == "task":
            # Execute a task
            tool_name = node_config.get("tool")
            if tool_name:
                # Execute tool
                pass
        return None


class LoopNodeExecutor(BaseNodeExecutor):
    """Executor for loop nodes."""

    async def execute(
        self,
        node: NodeDefinition,
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a loop node."""
        try:
            config = node.config
            loop_type = config.get("type", "for")

            if loop_type == "for":
                return await self._execute_for_loop(node, config, context)
            elif loop_type == "while":
                return await self._execute_while_loop(node, config, context)
            else:
                return self._create_error_result(node.id, f"Unknown loop type: {loop_type}")

        except Exception as e:
            self._logger.error("Loop node %s failed: %s", node.id, e)
            return self._create_error_result(node.id, str(e))

    async def _execute_for_loop(
        self,
        node: NodeDefinition,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a for loop."""
        items = config.get("items", [])
        if not items:
            return self._create_error_result(node.id, "No items to iterate")

        results = []
        for i, item in enumerate(items):
            # Update context with loop variable
            loop_context = dict(context)
            loop_context["loop_item"] = item
            loop_context["loop_index"] = i

            # Execute loop body
            body_result = await self._execute_loop_body(config, loop_context)
            results.append(body_result)

            # Check for early termination
            if config.get("break_on_error") and isinstance(body_result, Exception):
                return self._create_error_result(
                    node.id,
                    f"Loop failed at iteration {i}: {body_result}",
                )

        return self._create_success_result(node.id, results)

    async def _execute_while_loop(
        self,
        node: NodeDefinition,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> NodeResult:
        """Execute a while loop."""
        condition = config.get("condition")
        if not condition:
            return self._create_error_result(node.id, "No condition specified")

        max_iterations = config.get("max_iterations", 100)
        results = []

        for i in range(max_iterations):
            # Evaluate condition
            try:
                eval_context = {"context": context, "result": None}
                exec(f"result = {condition}", eval_context)
                should_continue = eval_context["result"]
            except Exception as e:
                return self._create_error_result(node.id, f"Condition evaluation failed: {e}")

            if not should_continue:
                break

            # Execute loop body
            body_result = await self._execute_loop_body(config, context)
            results.append(body_result)

            # Update context with result
            context[f"loop_iteration_{i}"] = body_result

        return self._create_success_result(node.id, results)

    async def _execute_loop_body(
        self,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """Execute loop body."""
        # This is a placeholder - implement based on your specific needs
        return None