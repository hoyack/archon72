"""TaskResultService - Service for task result and problem report submission.

Story: consent-gov-2.4: Task Result Submission

This service implements the TaskResultPort interface for submitting
task results and problem reports.

Key Behaviors:
- Result submission: IN_PROGRESS → REPORTED (state transition)
- Problem report: IN_PROGRESS → IN_PROGRESS (no state change)

Constitutional Guarantees:
- Only assigned Cluster can submit (AC9)
- Result submission transitions to REPORTED (AC3)
- Problem reports do NOT change state (AC4)
- All operations use two-phase event emission

References:
- FR6: Cluster can submit task result report
- FR7: Cluster can submit problem report for in-progress task
- AC5: Event 'executive.task.reported' emitted on result submission
- AC6: Event 'executive.task.problem_reported' emitted on problem report
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.governance.task_activation_port import TaskStatePort
from src.application.ports.governance.task_result_port import (
    InvalidResultStateError,
    ProblemCategory,
    ProblemReportValue,
    ResultSubmissionResult,
    TaskResultPort,
    TaskResultValue,
    UnauthorizedResultError,
)
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.application.services.governance.two_phase_execution import TwoPhaseExecution
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.task.task_state import TaskStatus
from src.domain.ports.time_authority import TimeAuthorityProtocol


class TaskResultService(TaskResultPort):
    """Service for task result and problem report submissions.

    Implements the TaskResultPort interface for:
    1. Submitting task results (completed work)
    2. Submitting problem reports (issues during work)

    Key Behaviors:
    - Result submission transitions IN_PROGRESS → REPORTED
    - Problem reports do NOT change state (task remains IN_PROGRESS)
    - All operations use two-phase event emission
    - Only assigned Cluster can submit

    Constitutional Guarantees:
    - Only assigned Cluster can submit (AC9)
    - Results transition to REPORTED (AC3)
    - Problem reports preserve state (AC4)
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        ledger_port: GovernanceLedgerPort,
        two_phase_emitter: TwoPhaseEventEmitterPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the TaskResultService.

        Args:
            task_state_port: Port for task state persistence.
            ledger_port: Port for event ledger operations.
            two_phase_emitter: Port for two-phase event emission.
            time_authority: Time authority for timestamps.
        """
        self._task_state = task_state_port
        self._ledger = ledger_port
        self._emitter = two_phase_emitter
        self._time = time_authority

    async def submit_result(
        self,
        task_id: UUID,
        cluster_id: str,
        output: dict[str, Any],
    ) -> ResultSubmissionResult:
        """Submit a task result for completed work.

        Per FR6: Cluster can submit task result report.
        Per AC1: Cluster can submit task result report for completed work.
        Per AC3: Result submission transitions task from IN_PROGRESS to REPORTED.
        Per AC5: Event 'executive.task.reported' emitted on result submission.
        Per AC7: Result includes structured output matching task spec.
        Per AC9: Only assigned Cluster can submit results.

        Args:
            task_id: ID of the task to submit result for.
            cluster_id: ID of the Cluster submitting (must be assigned worker).
            output: Structured output matching task spec expectations.

        Returns:
            ResultSubmissionResult with the created TaskResultValue.

        Raises:
            UnauthorizedResultError: If Cluster is not the assigned worker.
            InvalidResultStateError: If task is not in IN_PROGRESS state.
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.result",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={"output_keys": list(output.keys())},
        ) as execution:
            # 1. Get task and validate
            task = await self._task_state.get_task(task_id)

            # 2. Validate Cluster is assigned worker
            if task.cluster_id != cluster_id:
                raise UnauthorizedResultError(
                    cluster_id=cluster_id,
                    task_id=task_id,
                    message=f"Cluster {cluster_id} is not the assigned worker for task {task_id}",
                )

            # 3. Validate task is in IN_PROGRESS state
            if task.current_status != TaskStatus.IN_PROGRESS:
                raise InvalidResultStateError(
                    task_id=task_id,
                    current_state=task.current_status.value,
                    operation="submit_result",
                )

            # 4. Create result value
            now = self._time.now()
            result_value = TaskResultValue(
                task_id=task_id,
                cluster_id=cluster_id,
                output=output,
                submitted_at=now,
            )

            # 5. Transition task to REPORTED
            new_task = task.transition(
                new_status=TaskStatus.REPORTED,
                transition_time=now,
                actor_id=cluster_id,
            )
            await self._task_state.save_task(new_task)

            # 6. Emit event
            await self._emit_result_event(
                task_id=task_id,
                cluster_id=cluster_id,
                output=output,
                timestamp=now,
            )

            # 7. Set execution result for commit
            execution.set_result({"new_status": "reported"})

            return ResultSubmissionResult(
                success=True,
                result=result_value,
                new_status="reported",
                message="Task result submitted successfully",
            )

        raise RuntimeError("Task result submission failed")

    async def submit_problem_report(
        self,
        task_id: UUID,
        cluster_id: str,
        category: ProblemCategory,
        description: str,
    ) -> ResultSubmissionResult:
        """Submit a problem report for an in-progress task.

        Per FR7: Cluster can submit problem report for in-progress task.
        Per AC2: Cluster can submit problem report for in-progress task.
        Per AC4: Problem report records issue WITHOUT state transition.
        Per AC6: Event 'executive.task.problem_reported' emitted.
        Per AC8: Problem report includes categorized issue type and description.
        Per AC9: Only assigned Cluster can submit problem reports.

        IMPORTANT: Problem reports do NOT trigger state transitions.
        The task remains IN_PROGRESS.

        Args:
            task_id: ID of the task to report problem for.
            cluster_id: ID of the Cluster reporting (must be assigned worker).
            category: Category of the problem.
            description: Description of the problem.

        Returns:
            ResultSubmissionResult with the created ProblemReportValue.

        Raises:
            UnauthorizedResultError: If Cluster is not the assigned worker.
            InvalidResultStateError: If task is not in IN_PROGRESS state.
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.problem_report",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={"category": category.value},
        ) as execution:
            # 1. Get task and validate
            task = await self._task_state.get_task(task_id)

            # 2. Validate Cluster is assigned worker
            if task.cluster_id != cluster_id:
                raise UnauthorizedResultError(
                    cluster_id=cluster_id,
                    task_id=task_id,
                    message=f"Cluster {cluster_id} is not the assigned worker for task {task_id}",
                )

            # 3. Validate task is in IN_PROGRESS state
            if task.current_status != TaskStatus.IN_PROGRESS:
                raise InvalidResultStateError(
                    task_id=task_id,
                    current_state=task.current_status.value,
                    operation="submit_problem_report",
                )

            # 4. Create problem report value
            now = self._time.now()
            report_value = ProblemReportValue(
                task_id=task_id,
                cluster_id=cluster_id,
                category=category,
                description=description,
                reported_at=now,
            )

            # 5. NO state transition - task remains IN_PROGRESS
            # This is intentional per AC4

            # 6. Emit event
            await self._emit_problem_report_event(
                task_id=task_id,
                cluster_id=cluster_id,
                category=category,
                description=description,
                timestamp=now,
            )

            # 7. Set execution result for commit
            execution.set_result({"reported": True, "category": category.value})

            return ResultSubmissionResult(
                success=True,
                result=report_value,
                new_status="in_progress",  # Unchanged per AC4
                message="Problem report submitted successfully",
            )

        raise RuntimeError("Problem report submission failed")

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _emit_result_event(
        self,
        task_id: UUID,
        cluster_id: str,
        output: dict[str, Any],
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.reported event.

        Per AC5: Event 'executive.task.reported' emitted on result submission.

        Args:
            task_id: ID of the task.
            cluster_id: ID of the Cluster submitting.
            output: Structured output.
            timestamp: Event timestamp.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.reported",
            timestamp=timestamp,
            actor_id=cluster_id,
            trace_id=str(task_id),
            payload={
                "task_id": str(task_id),
                "cluster_id": cluster_id,
                "output": output,
                "submitted_at": timestamp.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)

    async def _emit_problem_report_event(
        self,
        task_id: UUID,
        cluster_id: str,
        category: ProblemCategory,
        description: str,
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.problem_reported event.

        Per AC6: Event 'executive.task.problem_reported' emitted on problem report.

        IMPORTANT: This does NOT trigger state transition.

        Args:
            task_id: ID of the task.
            cluster_id: ID of the Cluster reporting.
            category: Category of the problem.
            description: Description of the problem.
            timestamp: Event timestamp.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.problem_reported",
            timestamp=timestamp,
            actor_id=cluster_id,
            trace_id=str(task_id),
            payload={
                "task_id": str(task_id),
                "cluster_id": cluster_id,
                "category": category.value,
                "description": description,
                "reported_at": timestamp.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)
