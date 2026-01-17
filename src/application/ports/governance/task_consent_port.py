"""TaskConsentPort - Interface for Cluster consent operations on tasks.

Story: consent-gov-2.3: Task Consent Operations

This port defines the contract for Cluster consent operations:
- View pending task activation requests
- Accept task activation requests
- Decline task activation requests (no justification required)
- Halt in-progress tasks (no penalty)

Constitutional Guarantees:
- Declining is ALWAYS penalty-free (FR4)
- Halting is ALWAYS penalty-free (FR5)
- No standing/reputation tracking exists in schema
- Justification is NEVER required for decline or halt

References:
- [Source: governance-architecture.md#Golden Rules]
- FR2: Cluster can view pending requests
- FR3: Cluster can accept request
- FR4: Cluster can decline without justification
- FR5: Cluster can halt without penalty
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.task.task_state import TaskState


@dataclass(frozen=True)
class PendingTaskView:
    """View model for pending task activation requests.

    Provides Cluster with information needed to decide on acceptance.

    Attributes:
        task_id: Unique identifier for the task.
        earl_id: ID of the Earl who created this task.
        description_preview: First 200 chars of task description.
        ttl_remaining: Time remaining to accept/decline.
        routed_at: When the task was routed to this Cluster.
    """

    task_id: UUID
    earl_id: str
    description_preview: str  # First 200 chars
    ttl_remaining: timedelta
    routed_at: datetime


@dataclass(frozen=True)
class TaskConsentResult:
    """Result of a consent operation.

    Attributes:
        success: Whether the operation succeeded.
        task_state: Updated task state after operation.
        operation: Operation type ("accepted", "declined", "halted").
        message: Optional message about the operation.
    """

    success: bool
    task_state: TaskState
    operation: str  # "accepted", "declined", "halted"
    message: str = ""


class UnauthorizedConsentError(Exception):
    """Raised when Cluster tries to consent on task not addressed to them.

    Per FR3/FR4/FR5: Only the intended Cluster can perform consent operations.
    """

    def __init__(self, cluster_id: str, task_id: UUID, message: str | None = None):
        self.cluster_id = cluster_id
        self.task_id = task_id
        super().__init__(
            message
            or f"Cluster {cluster_id} is not authorized to consent on task {task_id}"
        )


class InvalidTaskStateError(Exception):
    """Raised when consent operation attempted on invalid task state.

    Per FR13: State machine transitions are enforced.
    """

    def __init__(self, task_id: UUID, current_state: str, operation: str):
        self.task_id = task_id
        self.current_state = current_state
        self.operation = operation
        super().__init__(
            f"Cannot {operation} task {task_id} in {current_state} state"
        )


@runtime_checkable
class TaskConsentPort(Protocol):
    """Port for Cluster consent operations on tasks.

    Constitutional Guarantees:
    - Declining is ALWAYS penalty-free
    - No standing/reputation tracking exists
    - Halting in-progress tasks incurs no penalty
    - Justification is NEVER required for decline or halt

    This interface defines the contract for Cluster consent operations.
    Implementations must ensure:
    1. No penalty tracking on decline/halt
    2. No standing/reputation schema
    3. Event emission via two-phase pattern
    """

    async def get_pending_requests(
        self,
        cluster_id: str,
        limit: int = 100,
    ) -> list[PendingTaskView]:
        """Get pending task activation requests for a Cluster.

        Returns tasks in ROUTED state addressed to this Cluster,
        excluding expired requests.

        Per FR2: Cluster can view pending requests.

        Args:
            cluster_id: ID of the Cluster requesting pending tasks.
            limit: Maximum number of results (default 100).

        Returns:
            List of PendingTaskView objects for pending tasks.
        """
        ...

    async def accept_task(
        self,
        task_id: UUID,
        cluster_id: str,
    ) -> TaskConsentResult:
        """Accept a task activation request.

        Per FR3: Cluster can accept a task activation request.

        Transitions: ROUTED -> ACCEPTED

        Emits: executive.task.accepted event

        Args:
            task_id: ID of the task to accept.
            cluster_id: ID of the Cluster accepting.

        Returns:
            TaskConsentResult with new task state.

        Raises:
            UnauthorizedConsentError: If Cluster is not the recipient.
            InvalidTaskStateError: If task is not in ROUTED state.
        """
        ...

    async def decline_task(
        self,
        task_id: UUID,
        cluster_id: str,
        # NOTE: No justification parameter - intentionally omitted (FR4)
    ) -> TaskConsentResult:
        """Decline a task activation request.

        Constitutional Guarantee:
        - NO justification required (FR4 explicit)
        - NO penalty incurred
        - NO standing reduction
        - NO negative attribution recorded

        Per FR4: Cluster can decline without justification.

        Transitions: ROUTED -> DECLINED or ACCEPTED -> DECLINED

        Emits: executive.task.declined event with reason "explicit_decline"

        Args:
            task_id: ID of the task to decline.
            cluster_id: ID of the Cluster declining.

        Returns:
            TaskConsentResult with new task state.

        Raises:
            UnauthorizedConsentError: If Cluster is not the recipient.
            InvalidTaskStateError: If task is not in valid state for decline.
        """
        ...

    async def halt_task(
        self,
        task_id: UUID,
        cluster_id: str,
        # NOTE: No justification required - halting is penalty-free (FR5)
    ) -> TaskConsentResult:
        """Halt an in-progress task.

        Constitutional Guarantee:
        - Halting incurs NO penalty (FR5)
        - Task transitions to QUARANTINED (safe state)
        - NO negative attribution recorded
        - NO justification required

        Per FR5: Cluster can halt without penalty.

        Transitions: IN_PROGRESS -> QUARANTINED

        Emits: executive.task.halted event with penalty_incurred=false

        Args:
            task_id: ID of the task to halt.
            cluster_id: ID of the Cluster halting.

        Returns:
            TaskConsentResult with new task state.

        Raises:
            UnauthorizedConsentError: If Cluster is not the worker.
            InvalidTaskStateError: If task is not IN_PROGRESS.
        """
        ...
