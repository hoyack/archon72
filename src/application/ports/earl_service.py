"""Earl Service Port (Administrative Branch - Junior).

This module defines the abstract protocol for Earl-rank administrative functions.
Earls execute tasks, coordinate agents, and optimize within Duke-assigned constraints.

Per Government PRD FR-GOV-12: Earl Authority - Execute tasks, coordinate agents,
optimize within constraints.
Per Government PRD FR-GOV-13: Earl Constraints - No reinterpretation of intent,
no suppression of failure signals. Execute within Duke-assigned constraints.

HARDENING-1: All timestamps must be provided via TimeAuthorityProtocol injection.
Factory methods require explicit timestamp parameters - no datetime.now() calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ExecutionStatus(Enum):
    """Status of task execution by Earl."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class AgentRole(Enum):
    """Roles for agents in task execution."""

    PRIMARY = "primary"  # Main executor
    COORDINATOR = "coordinator"  # Coordinates other agents
    VALIDATOR = "validator"  # Validates outputs
    MONITOR = "monitor"  # Monitors progress
    SUPPORT = "support"  # Supporting role


@dataclass(frozen=True)
class ExecutionResult:
    """Result of task execution by an Earl.

    Per FR-GOV-12: Earls execute tasks and report results.
    Immutable to ensure execution integrity.
    """

    result_id: UUID
    task_id: UUID
    status: ExecutionStatus
    outputs: dict[str, Any]  # Task outputs mapped to success criteria
    metrics: dict[str, float]  # Execution metrics
    success: bool
    executed_by: str  # Earl's Archon ID
    executed_at: datetime
    domain_id: str | None = None
    error: str | None = None
    error_details: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        task_id: UUID,
        status: ExecutionStatus,
        outputs: dict[str, Any],
        metrics: dict[str, float],
        success: bool,
        executed_by: str,
        timestamp: datetime,
        domain_id: str | None = None,
        error: str | None = None,
        error_details: dict[str, Any] | None = None,
    ) -> "ExecutionResult":
        """Create a new execution result.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            task_id: Task that was executed
            status: Final execution status
            outputs: Task outputs
            metrics: Execution metrics
            success: Whether execution succeeded
            executed_by: Earl Archon ID
            timestamp: Current time from TimeAuthorityProtocol
            domain_id: Domain the task was in
            error: Error message if failed
            error_details: Detailed error information

        Returns:
            New immutable ExecutionResult
        """
        return cls(
            result_id=uuid4(),
            task_id=task_id,
            status=status,
            outputs=outputs,
            metrics=metrics,
            success=success,
            executed_by=executed_by,
            executed_at=timestamp,
            domain_id=domain_id,
            error=error,
            error_details=error_details,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "result_id": str(self.result_id),
            "task_id": str(self.task_id),
            "status": self.status.value,
            "outputs": self.outputs,
            "metrics": self.metrics,
            "success": self.success,
            "executed_by": self.executed_by,
            "executed_at": self.executed_at.isoformat(),
            "domain_id": self.domain_id,
            "error": self.error,
            "error_details": self.error_details,
        }


@dataclass(frozen=True)
class AgentAssignment:
    """Assignment of an agent to a task role."""

    assignment_id: UUID
    agent_id: str
    task_id: UUID
    role: AgentRole
    subtasks: tuple[str, ...]  # Subtasks assigned to this agent
    assigned_by: str  # Earl Archon ID
    assigned_at: datetime

    @classmethod
    def create(
        cls,
        agent_id: str,
        task_id: UUID,
        role: AgentRole,
        subtasks: list[str],
        assigned_by: str,
        timestamp: datetime,
    ) -> "AgentAssignment":
        """Create a new agent assignment.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            agent_id: Agent being assigned
            task_id: Task to work on
            role: Role in the task
            subtasks: Subtasks for this agent
            assigned_by: Earl Archon ID
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New immutable AgentAssignment
        """
        return cls(
            assignment_id=uuid4(),
            agent_id=agent_id,
            task_id=task_id,
            role=role,
            subtasks=tuple(subtasks),
            assigned_by=assigned_by,
            assigned_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "assignment_id": str(self.assignment_id),
            "agent_id": self.agent_id,
            "task_id": str(self.task_id),
            "role": self.role.value,
            "subtasks": list(self.subtasks),
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at.isoformat(),
        }


@dataclass(frozen=True)
class AgentCoordination:
    """Coordination specification for agents in task execution."""

    coordination_id: UUID
    task_id: UUID
    agent_assignments: tuple[AgentAssignment, ...]
    coordinator_agent: str | None  # Lead agent if any
    coordinated_by: str  # Earl Archon ID
    created_at: datetime

    @classmethod
    def create(
        cls,
        task_id: UUID,
        agent_assignments: list[AgentAssignment],
        coordinated_by: str,
        timestamp: datetime,
        coordinator_agent: str | None = None,
    ) -> "AgentCoordination":
        """Create a new agent coordination.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            task_id: Task being coordinated
            agent_assignments: List of agent assignments
            coordinated_by: Earl Archon ID
            timestamp: Current time from TimeAuthorityProtocol
            coordinator_agent: Lead agent if any

        Returns:
            New immutable AgentCoordination
        """
        return cls(
            coordination_id=uuid4(),
            task_id=task_id,
            agent_assignments=tuple(agent_assignments),
            coordinator_agent=coordinator_agent,
            coordinated_by=coordinated_by,
            created_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "coordination_id": str(self.coordination_id),
            "task_id": str(self.task_id),
            "agent_assignments": [a.to_dict() for a in self.agent_assignments],
            "coordinator_agent": self.coordinator_agent,
            "coordinated_by": self.coordinated_by,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class OptimizationAction:
    """An optimization action taken during execution."""

    action_id: UUID
    description: str
    impact: str
    constraints_honored: tuple[str, ...]
    taken_by: str  # Earl Archon ID
    taken_at: datetime

    @classmethod
    def create(
        cls,
        description: str,
        impact: str,
        constraints_honored: list[str],
        taken_by: str,
        timestamp: datetime,
    ) -> "OptimizationAction":
        """Create a new optimization action.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            description: What was optimized
            impact: Impact of the optimization
            constraints_honored: Constraints that were honored
            taken_by: Earl Archon ID
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New immutable OptimizationAction
        """
        return cls(
            action_id=uuid4(),
            description=description,
            impact=impact,
            constraints_honored=tuple(constraints_honored),
            taken_by=taken_by,
            taken_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action_id": str(self.action_id),
            "description": self.description,
            "impact": self.impact,
            "constraints_honored": list(self.constraints_honored),
            "taken_by": self.taken_by,
            "taken_at": self.taken_at.isoformat(),
        }


@dataclass(frozen=True)
class OptimizationReport:
    """Report of optimization actions during execution."""

    report_id: UUID
    task_id: UUID
    actions_taken: tuple[OptimizationAction, ...]
    improvements: dict[str, float]  # metric -> improvement %
    constraints_enforced: tuple[str, ...]
    reported_by: str  # Earl Archon ID
    reported_at: datetime

    @classmethod
    def create(
        cls,
        task_id: UUID,
        actions_taken: list[OptimizationAction],
        improvements: dict[str, float],
        constraints_enforced: list[str],
        reported_by: str,
        timestamp: datetime,
    ) -> "OptimizationReport":
        """Create a new optimization report.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            task_id: Task that was optimized
            actions_taken: List of optimization actions
            improvements: Metric improvements
            constraints_enforced: Constraints that were honored
            reported_by: Earl Archon ID
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New immutable OptimizationReport
        """
        return cls(
            report_id=uuid4(),
            task_id=task_id,
            actions_taken=tuple(actions_taken),
            improvements=improvements,
            constraints_enforced=tuple(constraints_enforced),
            reported_by=reported_by,
            reported_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "report_id": str(self.report_id),
            "task_id": str(self.task_id),
            "actions_taken": [a.to_dict() for a in self.actions_taken],
            "improvements": self.improvements,
            "constraints_enforced": list(self.constraints_enforced),
            "reported_by": self.reported_by,
            "reported_at": self.reported_at.isoformat(),
        }


@dataclass
class TaskExecutionRequest:
    """Request to execute a task."""

    earl_id: str  # Earl Archon ID
    task_id: UUID
    task_spec: dict[str, Any]  # AegisTaskSpec as dict
    domain_id: str
    constraints: list[str]


@dataclass
class TaskExecutionResult:
    """Result of task execution."""

    success: bool
    result: ExecutionResult | None = None
    error: str | None = None


@dataclass
class AgentCoordinationRequest:
    """Request to coordinate agents for a task."""

    earl_id: str  # Earl Archon ID
    task_id: UUID
    agent_ids: list[str]
    subtask_allocation: dict[str, list[str]]  # agent_id -> subtasks


@dataclass
class AgentCoordinationResult:
    """Result of agent coordination."""

    success: bool
    coordination: AgentCoordination | None = None
    error: str | None = None


@dataclass
class OptimizationRequest:
    """Request to optimize execution."""

    earl_id: str  # Earl Archon ID
    task_id: UUID
    constraints: list[str]


@dataclass
class OptimizationResult:
    """Result of optimization."""

    success: bool
    report: OptimizationReport | None = None
    error: str | None = None


class EarlServiceProtocol(ABC):
    """Abstract protocol for Earl-rank administrative functions.

    Per Government PRD:
    - FR-GOV-12: Execute tasks, coordinate agents, optimize within constraints
    - FR-GOV-13: No reinterpretation of intent, no suppression of failure signals,
                 execute within Duke-assigned constraints

    This protocol explicitly EXCLUDES:
    - Motion introduction (King function)
    - Execution definition (President function)
    - Intent interpretation (Constitutional prohibition)
    - Domain ownership (Duke function)
    - Compliance judgment (Prince function)
    - Witnessing (Knight function)

    The Earl operates within the Duke's domain and must honor all
    Duke-assigned constraints.
    """

    @abstractmethod
    async def execute_task(
        self,
        request: TaskExecutionRequest,
    ) -> TaskExecutionResult:
        """Execute a task within the Duke's domain.

        Per FR-GOV-12: Earls execute tasks.

        Args:
            request: Task execution request with spec and constraints

        Returns:
            TaskExecutionResult with execution outcome

        Raises:
            RankViolationError: If the Archon is not Earl-rank

        Note:
            Per FR-GOV-13: Failures MUST be reported, never suppressed.
            The task must be within a domain owned by a Duke.
        """
        ...

    @abstractmethod
    async def coordinate_agents(
        self,
        request: AgentCoordinationRequest,
    ) -> AgentCoordinationResult:
        """Coordinate agents for task execution.

        Per FR-GOV-12: Earls coordinate agents.

        Args:
            request: Agent coordination request

        Returns:
            AgentCoordinationResult with coordination details
        """
        ...

    @abstractmethod
    async def optimize_within_constraints(
        self,
        request: OptimizationRequest,
    ) -> OptimizationResult:
        """Optimize execution within approved constraints.

        Per FR-GOV-12: Earls optimize within constraints.

        Args:
            request: Optimization request with constraints

        Returns:
            OptimizationResult with optimization report

        Note:
            Optimization MUST stay within Duke-assigned constraints.
            Any constraint violation must be reported.
        """
        ...

    @abstractmethod
    async def report_execution_result(
        self,
        task_id: UUID,
        result: ExecutionResult,
    ) -> bool:
        """Report task execution result to the pipeline.

        Args:
            task_id: Task that was executed
            result: Execution result

        Returns:
            True if successfully reported

        Note:
            Per FR-GOV-13: This propagates to Prince for evaluation.
            Failures are NEVER suppressed.
        """
        ...

    @abstractmethod
    async def get_execution_result(
        self,
        result_id: UUID,
    ) -> ExecutionResult | None:
        """Retrieve an execution result by ID.

        Args:
            result_id: UUID of the result

        Returns:
            ExecutionResult if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_results_by_task(
        self,
        task_id: UUID,
    ) -> list[ExecutionResult]:
        """Get all execution results for a task.

        Args:
            task_id: Task UUID

        Returns:
            List of execution results
        """
        ...

    @abstractmethod
    async def get_results_by_earl(
        self,
        earl_id: str,
    ) -> list[ExecutionResult]:
        """Get all execution results by an Earl.

        Args:
            earl_id: Earl Archon ID

        Returns:
            List of execution results
        """
        ...

    @abstractmethod
    async def get_coordination(
        self,
        coordination_id: UUID,
    ) -> AgentCoordination | None:
        """Retrieve agent coordination by ID.

        Args:
            coordination_id: UUID of the coordination

        Returns:
            AgentCoordination if found, None otherwise
        """
        ...

    # =========================================================================
    # EXPLICITLY EXCLUDED METHODS
    # These methods are NOT part of the Earl Service per FR-GOV-12, FR-GOV-13
    # =========================================================================

    # def introduce_motion(self) -> None:  # PROHIBITED (King function)
    # def define_execution(self) -> None:  # PROHIBITED (President function)
    # def reinterpret_intent(self) -> None:  # PROHIBITED (FR-GOV-13)
    # def suppress_failure(self) -> None:  # PROHIBITED (FR-GOV-13)
    # def own_domain(self) -> None:  # PROHIBITED (Duke function)
    # def judge_compliance(self) -> None:  # PROHIBITED (Prince function)
    # def witness(self) -> None:  # PROHIBITED (Knight function)
