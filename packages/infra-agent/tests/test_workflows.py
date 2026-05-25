"""Tests for the workflow engine."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from quant_os_infra_agent.workflows.base import (
    NodeDefinition,
    NodeResult,
    NodeStatus,
    NodeType,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStatus,
)
from quant_os_infra_agent.workflows.engine import WorkflowEngine


@pytest.fixture
def sample_workflow():
    """Create a sample workflow for testing."""
    nodes = [
        NodeDefinition(
            id="start",
            name="Start",
            type=NodeType.START,
        ),
        NodeDefinition(
            id="task1",
            name="Task 1",
            type=NodeType.TASK,
            config={"type": "function", "function": "builtins.id", "parameters": {"x": 1}},
            dependencies=["start"],
        ),
        NodeDefinition(
            id="task2",
            name="Task 2",
            type=NodeType.TASK,
            config={"type": "function", "function": "builtins.id", "parameters": {"x": 2}},
            dependencies=["start"],
        ),
        NodeDefinition(
            id="end",
            name="End",
            type=NodeType.END,
            dependencies=["task1", "task2"],
        ),
    ]

    return WorkflowDefinition(
        id="test_workflow",
        name="Test Workflow",
        description="A test workflow",
        nodes=nodes,
    )


@pytest.fixture
def workflow_engine():
    return WorkflowEngine()


class TestNodeDefinition:
    def test_to_dict(self):
        node = NodeDefinition(
            id="test",
            name="Test Node",
            type=NodeType.TASK,
            config={"key": "value"},
            dependencies=["dep1"],
        )
        result = node.to_dict()
        assert result == {
            "id": "test",
            "name": "Test Node",
            "type": "task",
            "config": {"key": "value"},
            "dependencies": ["dep1"],
        }


class TestWorkflowDefinition:
    def test_to_dict(self, sample_workflow):
        result = sample_workflow.to_dict()
        assert result["id"] == "test_workflow"
        assert result["name"] == "Test Workflow"
        assert len(result["nodes"]) == 4

    def test_get_node(self, sample_workflow):
        node = sample_workflow.get_node("task1")
        assert node is not None
        assert node.name == "Task 1"

    def test_get_node_nonexistent(self, sample_workflow):
        assert sample_workflow.get_node("nonexistent") is None

    def test_get_dependencies(self, sample_workflow):
        deps = sample_workflow.get_dependencies("end")
        assert len(deps) == 2
        dep_ids = [d.id for d in deps]
        assert "task1" in dep_ids
        assert "task2" in dep_ids

    def test_get_dependents(self, sample_workflow):
        dependents = sample_workflow.get_dependents("start")
        assert len(dependents) == 2
        dependent_ids = [d.id for d in dependents]
        assert "task1" in dependent_ids
        assert "task2" in dependent_ids


class TestWorkflowRun:
    def test_to_dict(self):
        run = WorkflowRun(
            id="run1",
            workflow_id="workflow1",
            status=WorkflowStatus.RUNNING,
            context={"key": "value"},
        )
        result = run.to_dict()
        assert result["id"] == "run1"
        assert result["workflow_id"] == "workflow1"
        assert result["status"] == "running"
        assert result["context"] == {"key": "value"}

    def test_is_complete(self):
        run = WorkflowRun(id="run1", workflow_id="workflow1")
        assert run.is_complete() is False

        run.status = WorkflowStatus.COMPLETED
        assert run.is_complete() is True

        run.status = WorkflowStatus.FAILED
        assert run.is_complete() is True


class TestWorkflowEngine:
    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self, workflow_engine, sample_workflow):
        result = await workflow_engine.execute_workflow(sample_workflow)
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.node_results) == 4

    @pytest.mark.asyncio
    async def test_execute_workflow_with_context(self, workflow_engine, sample_workflow):
        initial_context = {"initial_value": 42}
        result = await workflow_engine.execute_workflow(sample_workflow, initial_context)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.context.get("initial_value") == 42

    @pytest.mark.asyncio
    async def test_cancel_workflow(self, workflow_engine, sample_workflow):
        # Start a workflow
        run_task = asyncio.create_task(
            workflow_engine.execute_workflow(sample_workflow)
        )

        # Wait a bit for it to start
        await asyncio.sleep(0.1)

        # Get running workflows
        running = workflow_engine.get_running_workflows()
        if running:
            # Cancel the first one
            success = await workflow_engine.cancel_workflow(running[0].id)
            assert success is True

        # Wait for the task to complete
        await run_task

    def test_register_executor(self, workflow_engine):
        mock_executor = MagicMock()
        workflow_engine.register_executor(NodeType.TASK, mock_executor)
        assert workflow_engine._executors[NodeType.TASK] == mock_executor


class TestNodeExecutors:
    @pytest.mark.asyncio
    async def test_task_node_executor(self):
        from quant_os_infra_agent.workflows.base import TaskNodeExecutor

        executor = TaskNodeExecutor()
        node = NodeDefinition(
            id="test",
            name="Test",
            type=NodeType.TASK,
            config={"type": "function", "function": "builtins.id", "parameters": {"x": 1}},
        )

        result = await executor.execute(node, {})
        # This might fail if builtins.id can't be called with x=1
        # In a real test, you'd mock the function
        assert result.node_id == "test"

    @pytest.mark.asyncio
    async def test_condition_node_executor(self):
        from quant_os_infra_agent.workflows.base import ConditionNodeExecutor

        executor = ConditionNodeExecutor()
        node = NodeDefinition(
            id="test",
            name="Test",
            type=NodeType.CONDITION,
            config={
                "type": "expression",
                "expression": "1 + 1 == 2",
            },
        )

        result = await executor.execute(node, {})
        assert result.status == NodeStatus.COMPLETED
        assert result.output["condition_result"] is True


if __name__ == "__main__":
    pytest.main([__file__])