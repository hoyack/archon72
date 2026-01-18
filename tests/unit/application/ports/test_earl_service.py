"""Unit tests for Earl Service port (Epic 4, Story 4.2).

Tests:
- ExecutionResult model creation
- AgentAssignment model creation
- AgentCoordination model creation
- OptimizationReport model creation
- ExecutionStatus and AgentRole enums
- Immutability of frozen dataclasses

Constitutional Constraints:
- FR-GOV-12: Earl Authority - Execute tasks, coordinate agents, optimize within constraints
- FR-GOV-13: No reinterpretation of intent, no suppression of failure signals
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestExecutionStatusEnum:
    """Test ExecutionStatus enum."""

    def test_all_statuses_defined(self) -> None:
        """All execution statuses are defined."""
        from src.application.ports.earl_service import ExecutionStatus

        expected = {
            "pending",
            "assigned",
            "executing",
            "completed",
            "failed",
            "blocked",
            "cancelled",
        }
        actual = {s.value for s in ExecutionStatus}
        assert actual == expected


class TestAgentRoleEnum:
    """Test AgentRole enum."""

    def test_all_agent_roles_defined(self) -> None:
        """All agent roles are defined."""
        from src.application.ports.earl_service import AgentRole

        expected = {"primary", "coordinator", "validator", "monitor", "support"}
        actual = {r.value for r in AgentRole}
        assert actual == expected


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_create_successful_result(self) -> None:
        """ExecutionResult.create() for successful execution."""
        from src.application.ports.earl_service import ExecutionResult, ExecutionStatus

        task_id = uuid4()
        now = datetime.now(timezone.utc)
        result = ExecutionResult.create(
            task_id=task_id,
            status=ExecutionStatus.COMPLETED,
            outputs={"result": "value", "artifacts": ["file1"]},
            metrics={"duration_ms": 1500.0, "accuracy": 0.95},
            success=True,
            executed_by="earl-archon-001",
            timestamp=now,
            domain_id="domain-001",
        )

        assert result.task_id == task_id
        assert result.status == ExecutionStatus.COMPLETED
        assert result.success is True
        assert result.outputs["result"] == "value"
        assert result.metrics["accuracy"] == 0.95
        assert result.executed_by == "earl-archon-001"
        assert result.executed_at == now

    def test_create_failed_result(self) -> None:
        """ExecutionResult.create() for failed execution with error."""
        from src.application.ports.earl_service import ExecutionResult, ExecutionStatus

        task_id = uuid4()
        result = ExecutionResult.create(
            task_id=task_id,
            status=ExecutionStatus.FAILED,
            outputs={},
            metrics={},
            success=False,
            executed_by="earl-archon-001",
            timestamp=datetime.now(timezone.utc),
            error="Task execution failed due to resource exhaustion",
            error_details={
                "resource": "memory",
                "required": "16GB",
                "available": "8GB",
            },
        )

        assert result.status == ExecutionStatus.FAILED
        assert result.success is False
        assert result.error is not None
        assert "resource exhaustion" in result.error
        assert result.error_details is not None

    def test_execution_result_is_frozen(self) -> None:
        """ExecutionResult is immutable."""
        from src.application.ports.earl_service import ExecutionResult, ExecutionStatus

        result = ExecutionResult.create(
            task_id=uuid4(),
            status=ExecutionStatus.COMPLETED,
            outputs={},
            metrics={},
            success=True,
            executed_by="earl-001",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            result.success = False  # type: ignore

    def test_execution_result_to_dict(self) -> None:
        """ExecutionResult serializes to dictionary."""
        from src.application.ports.earl_service import ExecutionResult, ExecutionStatus

        task_id = uuid4()
        result = ExecutionResult.create(
            task_id=task_id,
            status=ExecutionStatus.COMPLETED,
            outputs={"key": "value"},
            metrics={"m1": 1.0},
            success=True,
            executed_by="earl-001",
            timestamp=datetime.now(timezone.utc),
        )

        d = result.to_dict()

        assert d["task_id"] == str(task_id)
        assert d["status"] == "completed"
        assert d["success"] is True
        assert d["executed_by"] == "earl-001"


class TestAgentAssignment:
    """Test AgentAssignment dataclass."""

    def test_create_agent_assignment(self) -> None:
        """AgentAssignment.create() produces valid assignment."""
        from src.application.ports.earl_service import AgentAssignment, AgentRole

        task_id = uuid4()
        now = datetime.now(timezone.utc)
        assignment = AgentAssignment.create(
            agent_id="agent-001",
            task_id=task_id,
            role=AgentRole.PRIMARY,
            subtasks=["subtask-1", "subtask-2"],
            assigned_by="earl-archon-001",
            timestamp=now,
        )

        assert assignment.agent_id == "agent-001"
        assert assignment.task_id == task_id
        assert assignment.role == AgentRole.PRIMARY
        assert assignment.subtasks == ("subtask-1", "subtask-2")
        assert assignment.assigned_by == "earl-archon-001"
        assert assignment.assigned_at == now

    def test_agent_assignment_is_frozen(self) -> None:
        """AgentAssignment is immutable."""
        from src.application.ports.earl_service import AgentAssignment, AgentRole

        assignment = AgentAssignment.create(
            agent_id="agent-001",
            task_id=uuid4(),
            role=AgentRole.SUPPORT,
            subtasks=[],
            assigned_by="earl-001",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            assignment.role = AgentRole.PRIMARY  # type: ignore


class TestAgentCoordination:
    """Test AgentCoordination dataclass."""

    def test_create_agent_coordination(self) -> None:
        """AgentCoordination.create() produces valid coordination."""
        from src.application.ports.earl_service import (
            AgentAssignment,
            AgentCoordination,
            AgentRole,
        )

        task_id = uuid4()
        now = datetime.now(timezone.utc)
        assignment1 = AgentAssignment.create(
            agent_id="agent-001",
            task_id=task_id,
            role=AgentRole.PRIMARY,
            subtasks=["main-work"],
            assigned_by="earl-001",
            timestamp=now,
        )
        assignment2 = AgentAssignment.create(
            agent_id="agent-002",
            task_id=task_id,
            role=AgentRole.VALIDATOR,
            subtasks=["validate-output"],
            assigned_by="earl-001",
            timestamp=now,
        )

        coordination = AgentCoordination.create(
            task_id=task_id,
            agent_assignments=[assignment1, assignment2],
            coordinated_by="earl-archon-001",
            timestamp=now,
            coordinator_agent="agent-001",
        )

        assert coordination.task_id == task_id
        assert len(coordination.agent_assignments) == 2
        assert coordination.coordinator_agent == "agent-001"
        assert coordination.coordinated_by == "earl-archon-001"
        assert coordination.created_at == now

    def test_agent_coordination_is_frozen(self) -> None:
        """AgentCoordination is immutable."""
        from src.application.ports.earl_service import AgentCoordination

        coordination = AgentCoordination.create(
            task_id=uuid4(),
            agent_assignments=[],
            coordinated_by="earl-001",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            coordination.coordinator_agent = "new-agent"  # type: ignore


class TestOptimizationAction:
    """Test OptimizationAction dataclass."""

    def test_optimization_action_creation(self) -> None:
        """OptimizationAction can be created with all fields."""
        from src.application.ports.earl_service import OptimizationAction

        now = datetime.now(timezone.utc)
        action = OptimizationAction.create(
            description="Batch processing enabled",
            impact="30% reduction in API calls",
            constraints_honored=["max-rate-limit", "resource-cap"],
            taken_by="earl-archon-001",
            timestamp=now,
        )

        assert "Batch processing" in action.description
        assert len(action.constraints_honored) == 2
        assert action.taken_at == now

    def test_optimization_action_to_dict(self) -> None:
        """OptimizationAction serializes to dictionary."""
        from src.application.ports.earl_service import OptimizationAction

        now = datetime.now(timezone.utc)
        action = OptimizationAction.create(
            description="Cache enabled",
            impact="50% latency reduction",
            constraints_honored=["memory-limit"],
            taken_by="earl-001",
            timestamp=now,
        )

        d = action.to_dict()

        assert d["description"] == "Cache enabled"
        assert d["impact"] == "50% latency reduction"


class TestOptimizationReport:
    """Test OptimizationReport dataclass."""

    def test_create_optimization_report(self) -> None:
        """OptimizationReport.create() produces valid report."""
        from src.application.ports.earl_service import (
            OptimizationAction,
            OptimizationReport,
        )

        task_id = uuid4()
        now = datetime.now(timezone.utc)
        action = OptimizationAction.create(
            description="Parallel processing",
            impact="2x throughput",
            constraints_honored=["thread-limit"],
            taken_by="earl-001",
            timestamp=now,
        )

        report = OptimizationReport.create(
            task_id=task_id,
            actions_taken=[action],
            improvements={"throughput": 100.0, "latency": -50.0},
            constraints_enforced=["thread-limit", "memory-cap"],
            reported_by="earl-archon-001",
            timestamp=now,
        )

        assert report.task_id == task_id
        assert len(report.actions_taken) == 1
        assert report.improvements["throughput"] == 100.0
        assert "thread-limit" in report.constraints_enforced
        assert report.reported_by == "earl-archon-001"
        assert report.reported_at == now

    def test_optimization_report_is_frozen(self) -> None:
        """OptimizationReport is immutable."""
        from src.application.ports.earl_service import OptimizationReport

        report = OptimizationReport.create(
            task_id=uuid4(),
            actions_taken=[],
            improvements={},
            constraints_enforced=[],
            reported_by="earl-001",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            report.reported_by = "someone-else"  # type: ignore


class TestTaskExecutionRequest:
    """Test TaskExecutionRequest dataclass."""

    def test_task_execution_request(self) -> None:
        """TaskExecutionRequest holds all required fields."""
        from src.application.ports.earl_service import TaskExecutionRequest

        task_id = uuid4()
        request = TaskExecutionRequest(
            earl_id="earl-archon-001",
            task_id=task_id,
            task_spec={"type": "analysis", "input": "data"},
            domain_id="domain-001",
            constraints=["max-time-60s", "no-external-calls"],
        )

        assert request.earl_id == "earl-archon-001"
        assert request.task_id == task_id
        assert request.task_spec["type"] == "analysis"
        assert len(request.constraints) == 2
