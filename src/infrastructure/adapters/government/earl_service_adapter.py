"""Earl Service Adapter (Administrative Branch - Junior).

This module implements the EarlServiceProtocol for task execution,
agent coordination, and optimization within Duke-assigned constraints.

Per Government PRD FR-GOV-12: Earls execute tasks, coordinate agents,
optimize within constraints.
Per Government PRD FR-GOV-13: No reinterpretation of intent, no suppression
of failure signals. Execute within Duke-assigned constraints.

HARDENING-1: TimeAuthorityProtocol injection required for all timestamps.
"""

from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.earl_service import (
    AgentAssignment,
    AgentCoordination,
    AgentCoordinationRequest,
    AgentCoordinationResult,
    AgentRole,
    EarlServiceProtocol,
    ExecutionResult,
    ExecutionStatus,
    OptimizationAction,
    OptimizationReport,
    OptimizationRequest,
    OptimizationResult,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatementType,
)
from src.application.ports.permission_enforcer import (
    GovernanceAction,
    PermissionContext,
    PermissionEnforcerProtocol,
)
from src.application.ports.time_authority import TimeAuthorityProtocol

logger = get_logger(__name__)


class RankViolationError(Exception):
    """Raised when an Archon attempts an action outside their rank authority."""

    def __init__(
        self,
        archon_id: str,
        action: str,
        reason: str,
        prd_reference: str = "FR-GOV-12",
    ) -> None:
        self.archon_id = archon_id
        self.action = action
        self.reason = reason
        self.prd_reference = prd_reference
        super().__init__(
            f"Rank violation by {archon_id} on {action}: {reason} (per {prd_reference})"
        )


class ConstraintViolationError(Exception):
    """Raised when Earl violates Duke-assigned constraints."""

    def __init__(
        self,
        earl_id: str,
        constraint: str,
        action: str,
    ) -> None:
        self.earl_id = earl_id
        self.constraint = constraint
        self.action = action
        super().__init__(
            f"Earl {earl_id} violated constraint '{constraint}' during {action} "
            "(per FR-GOV-13)"
        )


class EarlServiceAdapter(EarlServiceProtocol):
    """Implementation of Earl-rank administrative functions.

    This service allows Earl-rank Archons to:
    - Execute tasks within Duke's domain
    - Coordinate agents for task execution
    - Optimize within Duke-assigned constraints

    Per FR-GOV-13:
    - No reinterpretation of intent
    - No suppression of failure signals
    - Execute within Duke-assigned constraints

    All operations are witnessed by Knight per FR-GOV-20.
    """

    def __init__(
        self,
        time_authority: TimeAuthorityProtocol,
        permission_enforcer: PermissionEnforcerProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the Earl Service.

        HARDENING-1: time_authority is required for all timestamp operations.

        Args:
            time_authority: TimeAuthorityProtocol for consistent timestamps
            permission_enforcer: Permission enforcement (optional for testing)
            knight_witness: Knight witness for recording events (optional)
            verbose: Enable verbose logging
        """
        self._time = time_authority
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness
        self._verbose = verbose

        # In-memory storage (would be repository in production)
        self._execution_results: dict[UUID, ExecutionResult] = {}
        self._coordinations: dict[UUID, AgentCoordination] = {}
        self._optimization_reports: dict[UUID, OptimizationReport] = {}

        if self._verbose:
            logger.debug("earl_service_initialized")

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
        """
        if self._verbose:
            logger.debug(
                "task_execution_requested",
                earl_id=request.earl_id,
                task_id=str(request.task_id),
                domain_id=request.domain_id,
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource=f"task:{request.task_id}",
                action_details={
                    "domain_id": request.domain_id,
                    "task_spec": request.task_spec,
                },
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.earl_id,
                action=GovernanceAction.EXECUTE_TASK,
                context=context,
            )

            if not permission_result.allowed:
                await self._witness_violation(
                    archon_id=request.earl_id,
                    violation_type="rank_violation",
                    description=f"Attempted task execution without Earl rank: {permission_result.violation_reason}",
                )

                raise RankViolationError(
                    archon_id=request.earl_id,
                    action="execute_task",
                    reason=permission_result.violation_reason or "Not authorized",
                    prd_reference="FR-GOV-12",
                )

        # Execute the task (simulated - real implementation would delegate to agents)
        try:
            # Validate constraints are being honored
            for constraint in request.constraints:
                if not await self._validate_constraint(constraint, request.task_spec):
                    # Per FR-GOV-13: Report constraint violations, don't suppress
                    await self._witness_violation(
                        archon_id=request.earl_id,
                        violation_type="constraint_violation",
                        description=f"Earl violated constraint: {constraint}",
                    )
                    raise ConstraintViolationError(
                        earl_id=request.earl_id,
                        constraint=constraint,
                        action="execute_task",
                    )

            # Create successful execution result
            result = ExecutionResult.create(
                task_id=request.task_id,
                status=ExecutionStatus.COMPLETED,
                outputs={"execution_complete": True},
                metrics={"duration_ms": 0.0},  # Simulated
                success=True,
                executed_by=request.earl_id,
                timestamp=self._time.now(),
                domain_id=request.domain_id,
            )

            self._execution_results[result.result_id] = result

            # Witness successful execution
            await self._witness_action(
                archon_id=request.earl_id,
                action="task_executed",
                details={
                    "result_id": str(result.result_id),
                    "task_id": str(request.task_id),
                    "status": result.status.value,
                },
            )

            if self._verbose:
                logger.info(
                    "task_execution_completed",
                    earl_id=request.earl_id,
                    task_id=str(request.task_id),
                    result_id=str(result.result_id),
                )

            return TaskExecutionResult(
                success=True,
                result=result,
            )

        except ConstraintViolationError:
            raise
        except Exception as e:
            # Per FR-GOV-13: Failures MUST be reported, NEVER suppressed
            result = ExecutionResult.create(
                task_id=request.task_id,
                status=ExecutionStatus.FAILED,
                outputs={},
                metrics={},
                success=False,
                executed_by=request.earl_id,
                timestamp=self._time.now(),
                domain_id=request.domain_id,
                error=str(e),
                error_details={"exception_type": type(e).__name__},
            )

            self._execution_results[result.result_id] = result

            # Witness the failure - per FR-GOV-13 this MUST happen
            await self._witness_action(
                archon_id=request.earl_id,
                action="task_execution_failed",
                details={
                    "result_id": str(result.result_id),
                    "task_id": str(request.task_id),
                    "error": str(e),
                },
            )

            logger.warning(
                "task_execution_failed",
                earl_id=request.earl_id,
                task_id=str(request.task_id),
                error=str(e),
            )

            return TaskExecutionResult(
                success=False,
                result=result,
                error=str(e),
            )

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
        if self._verbose:
            logger.debug(
                "agent_coordination_requested",
                earl_id=request.earl_id,
                task_id=str(request.task_id),
                agent_count=len(request.agent_ids),
            )

        # Create agent assignments
        assignments: list[AgentAssignment] = []
        coordinator_agent: str | None = None

        for i, agent_id in enumerate(request.agent_ids):
            subtasks = request.subtask_allocation.get(agent_id, [])

            # First agent with subtasks becomes coordinator
            role = AgentRole.SUPPORT
            if i == 0 and subtasks:
                role = AgentRole.PRIMARY
                coordinator_agent = agent_id
            elif subtasks:
                role = AgentRole.SUPPORT

            assignment = AgentAssignment.create(
                agent_id=agent_id,
                task_id=request.task_id,
                role=role,
                subtasks=subtasks,
                assigned_by=request.earl_id,
                timestamp=self._time.now(),
            )
            assignments.append(assignment)

        # Create coordination
        coordination = AgentCoordination.create(
            task_id=request.task_id,
            agent_assignments=assignments,
            coordinated_by=request.earl_id,
            timestamp=self._time.now(),
            coordinator_agent=coordinator_agent,
        )

        self._coordinations[coordination.coordination_id] = coordination

        # Witness coordination
        await self._witness_action(
            archon_id=request.earl_id,
            action="agents_coordinated",
            details={
                "coordination_id": str(coordination.coordination_id),
                "task_id": str(request.task_id),
                "agent_count": len(assignments),
                "coordinator": coordinator_agent,
            },
        )

        if self._verbose:
            logger.info(
                "agent_coordination_created",
                earl_id=request.earl_id,
                coordination_id=str(coordination.coordination_id),
            )

        return AgentCoordinationResult(
            success=True,
            coordination=coordination,
        )

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
        if self._verbose:
            logger.debug(
                "optimization_requested",
                earl_id=request.earl_id,
                task_id=str(request.task_id),
                constraint_count=len(request.constraints),
            )

        # Identify possible optimizations within constraints
        actions: list[OptimizationAction] = []
        improvements: dict[str, float] = {}

        # Simulated optimization actions that honor constraints
        for constraint in request.constraints:
            action = OptimizationAction.create(
                description=f"Optimized within constraint: {constraint}",
                impact="Improved efficiency while honoring constraint",
                constraints_honored=[constraint],
                taken_by=request.earl_id,
                timestamp=self._time.now(),
            )
            actions.append(action)

        # Create optimization report
        report = OptimizationReport.create(
            task_id=request.task_id,
            actions_taken=actions,
            improvements=improvements,
            constraints_enforced=request.constraints,
            reported_by=request.earl_id,
            timestamp=self._time.now(),
        )

        self._optimization_reports[report.report_id] = report

        # Witness optimization
        await self._witness_action(
            archon_id=request.earl_id,
            action="optimization_completed",
            details={
                "report_id": str(report.report_id),
                "task_id": str(request.task_id),
                "action_count": len(actions),
                "constraints_honored": request.constraints,
            },
        )

        if self._verbose:
            logger.info(
                "optimization_completed",
                earl_id=request.earl_id,
                report_id=str(report.report_id),
            )

        return OptimizationResult(
            success=True,
            report=report,
        )

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
        self._execution_results[result.result_id] = result

        # Witness the report - failures prominently
        details = {
            "result_id": str(result.result_id),
            "task_id": str(task_id),
            "status": result.status.value,
            "success": result.success,
        }

        if not result.success:
            # Per FR-GOV-13: Failures MUST be prominently reported
            details["error"] = result.error
            logger.warning(
                "execution_failure_reported",
                result_id=str(result.result_id),
                error=result.error,
            )

        await self._witness_action(
            archon_id=result.executed_by,
            action="execution_result_reported",
            details=details,
        )

        return True

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
        return self._execution_results.get(result_id)

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
        return [
            result
            for result in self._execution_results.values()
            if result.task_id == task_id
        ]

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
        return [
            result
            for result in self._execution_results.values()
            if result.executed_by == earl_id
        ]

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
        return self._coordinations.get(coordination_id)

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _validate_constraint(
        self,
        constraint: str,
        task_spec: dict[str, Any],
    ) -> bool:
        """Validate that a constraint is being honored.

        Args:
            constraint: Constraint to validate
            task_spec: Task specification

        Returns:
            True if constraint is honored
        """
        # Simple validation - real implementation would be more sophisticated
        return True

    async def _witness_violation(
        self,
        archon_id: str,
        violation_type: str,
        description: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Witness a violation through Knight.

        Args:
            archon_id: Archon who committed violation
            violation_type: Type of violation
            description: Description of violation
            evidence: Supporting evidence
        """
        if not self._knight_witness:
            if self._verbose:
                logger.warning(
                    "violation_not_witnessed_no_knight",
                    archon_id=archon_id,
                    violation_type=violation_type,
                )
            return

        violation = ViolationRecord(
            archon_id=archon_id,
            violation_type=violation_type,
            description=description,
            prd_reference="FR-GOV-12/FR-GOV-13",
            evidence=evidence or {},
        )

        context = ObservationContext(
            session_id="earl_service",
            statement_type=WitnessStatementType.VIOLATION,
            trigger_source="earl_service_adapter",
        )

        await self._knight_witness.witness_violation(
            violation=violation,
            context=context,
        )

    async def _witness_action(
        self,
        archon_id: str,
        action: str,
        details: dict[str, Any],
    ) -> None:
        """Witness an action through Knight.

        Args:
            archon_id: Archon who performed action
            action: Action performed
            details: Action details
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            session_id="earl_service",
            statement_type=WitnessStatementType.OBSERVATION,
            trigger_source="earl_service_adapter",
        )

        await self._knight_witness.witness_observation(
            observation={
                "archon_id": archon_id,
                "action": action,
                "details": details,
            },
            context=context,
        )
