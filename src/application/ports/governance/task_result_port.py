"""TaskResultPort - Abstract interface for task result submission.

Story: consent-gov-2.4: Task Result Submission

This port defines the contract for submitting task results and problem reports.
Per FR6/FR7, only the assigned Cluster can submit results for a task.

Constitutional Guarantees:
- Only assigned Cluster can submit results (AC9)
- Results transition task to REPORTED state (AC3)
- Problem reports do NOT change state (AC4)

Result vs Problem Report:
- Result Submission: IN_PROGRESS → REPORTED (state transition)
- Problem Report: IN_PROGRESS → IN_PROGRESS (no state change)

References:
- FR6: Cluster can submit a task result report
- FR7: Cluster can submit a problem report for an in-progress task
- governance-architecture.md: Task State Machine
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError

# Import ProblemCategory from canonical domain location to avoid duplication
from src.domain.governance.task.problem_report import ProblemCategory


@dataclass(frozen=True)
class TaskResultValue:
    """Immutable value object for task result submission.

    Per AC7: Result includes structured output matching task spec.
    Per AC1: Cluster can submit task result for completed work.

    Attributes:
        task_id: ID of the task this result is for.
        cluster_id: ID of the Cluster submitting the result.
        output: Structured output matching task spec expectations.
        submitted_at: Timestamp when result was submitted.
    """

    task_id: UUID
    cluster_id: str
    output: dict[str, Any]
    submitted_at: datetime


@dataclass(frozen=True)
class ProblemReportValue:
    """Immutable value object for problem report submission.

    Per AC8: Problem report includes categorized issue type and description.
    Per AC2: Cluster can submit problem report for in-progress task.

    Attributes:
        task_id: ID of the task this report is for.
        cluster_id: ID of the Cluster reporting the problem.
        category: Categorized issue type.
        description: Description of the problem.
        reported_at: Timestamp when report was submitted.
    """

    task_id: UUID
    cluster_id: str
    category: ProblemCategory
    description: str
    reported_at: datetime


@dataclass(frozen=True)
class ResultSubmissionResult:
    """Result of a result/problem submission operation.

    Attributes:
        success: Whether the submission was successful.
        result: The TaskResultValue or ProblemReportValue that was created.
        new_status: New task status after submission (if applicable).
        message: Human-readable result message.
    """

    success: bool
    result: TaskResultValue | ProblemReportValue
    new_status: str
    message: str


class UnauthorizedResultError(ConstitutionalViolationError):
    """Raised when unauthorized Cluster attempts result submission.

    Per AC9: Only assigned Cluster can submit results for a task.

    Attributes:
        cluster_id: ID of the Cluster that attempted submission.
        task_id: ID of the task.
        message: Error description.
    """

    def __init__(
        self,
        cluster_id: str,
        task_id: UUID,
        message: str,
    ) -> None:
        self.cluster_id = cluster_id
        self.task_id = task_id
        super().__init__(f"FR6: {message}")


class InvalidResultStateError(ConstitutionalViolationError):
    """Raised when result submission attempted from invalid state.

    Per FR6/FR7: Results can only be submitted from IN_PROGRESS state.

    Attributes:
        task_id: ID of the task.
        current_state: Current state of the task.
        operation: Operation that was attempted.
    """

    def __init__(
        self,
        task_id: UUID,
        current_state: str,
        operation: str,
    ) -> None:
        self.task_id = task_id
        self.current_state = current_state
        self.operation = operation
        super().__init__(
            f"FR6: Cannot {operation} - task {task_id} is in {current_state} state"
        )


class TaskResultPort(ABC):
    """Abstract port for task result and problem report submission.

    This port defines the contract for:
    1. Submitting task results (completed work)
    2. Submitting problem reports (issues during work)

    Constitutional Constraints:
    - Only assigned Cluster can submit (AC9)
    - Results transition to REPORTED (AC3)
    - Problem reports preserve state (AC4)

    Implementations must:
    - Validate Cluster is assigned worker
    - Validate task is in IN_PROGRESS state
    - Emit appropriate events
    - Use two-phase event emission
    """

    @abstractmethod
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
        ...

    @abstractmethod
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

        Note: Problem reports do NOT transition task state. Task remains
        IN_PROGRESS. This allows the Cluster to continue working or for
        escalation to occur.

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
        ...
