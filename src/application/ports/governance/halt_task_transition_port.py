"""Halt Task Transition Port - Interface for task state transitions on halt.

Story: consent-gov-4.3: Task State Transitions on Halt

This port defines the contract for transitioning all tasks to deterministic
states when a system halt is triggered. Tasks are categorized by their
consent state and transitioned accordingly:

- Pre-consent tasks → nullified (Cluster never agreed)
- Post-consent tasks → quarantined (preserve work for review)
- Terminal tasks → unchanged (already finished)

Constitutional Context:
- FR24: Pre-consent tasks transition to nullified
- FR25: Post-consent tasks transition to quarantined
- FR26: Completed tasks remain unchanged
- FR27: State transitions are atomic (no partial transitions)
- NFR-ATOMIC-01: Atomic transitions
- NFR-REL-03: In-flight tasks resolve deterministically

Event Types Emitted:
- executive.task.nullified_on_halt: Pre-consent task nullified
- executive.task.quarantined_on_halt: Post-consent task quarantined
- executive.task.preserved_on_halt: Terminal task preserved (audit only)

References:
- [Source: governance-architecture.md#Task State Projection]
- [Source: governance-prd.md#FR22-FR27]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class TaskStateCategory(str, Enum):
    """Categories for halt handling based on consent boundary.

    The consent boundary determines how tasks are treated on halt:
    - PRE_CONSENT: Cluster never agreed to work → nullified
    - POST_CONSENT: Cluster agreed to work → quarantined
    - TERMINAL: Task already finished → unchanged

    Per FR24-FR26: Different treatment based on consent state.
    """

    PRE_CONSENT = "pre_consent"
    """Task has not been accepted by Cluster. Can be nullified safely."""

    POST_CONSENT = "post_consent"
    """Cluster accepted and may have started work. Must preserve."""

    TERMINAL = "terminal"
    """Task lifecycle has ended. No changes needed."""


class HaltTransitionType(str, Enum):
    """Types of transitions applied during halt.

    Per FR24-FR26: Each category has a specific transition type.
    """

    NULLIFIED = "nullified"
    """Pre-consent task cancelled (no penalty to Cluster)."""

    QUARANTINED = "quarantined"
    """Post-consent task isolated for review."""

    PRESERVED = "preserved"
    """Terminal task unchanged (audit record only)."""

    FAILED = "failed"
    """Transition failed (concurrent modification or error)."""


@dataclass(frozen=True)
class TaskTransitionRecord:
    """Record of a single task's halt transition.

    Immutable record capturing the before/after state of a task
    during halt processing. Used for audit trail and event emission.

    Attributes:
        task_id: Unique identifier of the task.
        previous_status: Task status before halt transition.
        new_status: Task status after halt transition (or same if terminal).
        category: Task's consent category (pre/post/terminal).
        transition_type: Type of transition applied.
        transitioned_at: When the transition occurred.
        halt_correlation_id: Links to the halt event that triggered this.
        error_message: Error message if transition failed.
    """

    task_id: UUID
    previous_status: str
    new_status: str
    category: TaskStateCategory
    transition_type: HaltTransitionType
    transitioned_at: datetime
    halt_correlation_id: UUID
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        """Check if transition was successful."""
        return self.transition_type != HaltTransitionType.FAILED


@dataclass(frozen=True)
class HaltTransitionResult:
    """Result of halt task transitions.

    Aggregated result of transitioning all active tasks during halt.
    Provides counts and details for each category.

    Attributes:
        halt_correlation_id: Links all transitions to the triggering halt.
        triggered_at: When the halt was triggered.
        completed_at: When all transitions completed.
        nullified_count: Number of pre-consent tasks nullified.
        quarantined_count: Number of post-consent tasks quarantined.
        preserved_count: Number of terminal tasks preserved.
        failed_count: Number of failed transitions.
        total_processed: Total number of tasks processed.
        transition_records: Individual records for each task.
    """

    halt_correlation_id: UUID
    triggered_at: datetime
    completed_at: datetime
    nullified_count: int
    quarantined_count: int
    preserved_count: int
    failed_count: int
    total_processed: int
    transition_records: tuple[TaskTransitionRecord, ...] = field(default_factory=tuple)

    @property
    def execution_ms(self) -> float:
        """Calculate execution time in milliseconds."""
        return (self.completed_at - self.triggered_at).total_seconds() * 1000

    @property
    def is_complete_success(self) -> bool:
        """Check if all transitions succeeded."""
        return self.failed_count == 0

    @property
    def failed_task_ids(self) -> list[UUID]:
        """Get IDs of tasks that failed to transition."""
        return [
            record.task_id
            for record in self.transition_records
            if not record.is_success
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary for event payload.

        Returns:
            Dictionary representation for event emission.
        """
        return {
            "halt_correlation_id": str(self.halt_correlation_id),
            "triggered_at": self.triggered_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "execution_ms": self.execution_ms,
            "nullified_count": self.nullified_count,
            "quarantined_count": self.quarantined_count,
            "preserved_count": self.preserved_count,
            "failed_count": self.failed_count,
            "total_processed": self.total_processed,
            "is_complete_success": self.is_complete_success,
            "failed_task_ids": [str(tid) for tid in self.failed_task_ids],
        }


class ConcurrentModificationError(Exception):
    """Raised when task state changed between read and write.

    Per NFR-ATOMIC-01: Atomic transitions use optimistic locking.
    If the task state changes during transition, this error is raised.

    Attributes:
        task_id: ID of the task that was modified.
        expected_status: Status we expected the task to be in.
        actual_status: Status the task was actually in.
    """

    def __init__(
        self,
        task_id: UUID,
        expected_status: str,
        actual_status: str,
    ) -> None:
        self.task_id = task_id
        self.expected_status = expected_status
        self.actual_status = actual_status
        super().__init__(
            f"Task {task_id} state changed: expected {expected_status}, got {actual_status}"
        )


class HaltTaskTransitionPort(ABC):
    """Abstract interface for task state transitions on halt.

    This port defines the contract for transitioning all active tasks
    to deterministic states when a system halt is triggered.

    Per FR22-FR27:
    - Pre-consent tasks → nullified (safe to cancel)
    - Post-consent tasks → quarantined (preserve work)
    - Terminal tasks → unchanged (already finished)

    Per NFR-ATOMIC-01: Each task transition is atomic.
    Per NFR-REL-03: In-flight tasks resolve deterministically.

    Event Correlation:
    All transitions include halt_correlation_id linking back to the
    halt event that triggered them. This enables audit trail reconstruction.

    Example Usage:
        >>> halt_transition = get_halt_transition_port()
        >>> result = await halt_transition.transition_all_tasks_on_halt(
        ...     halt_correlation_id=halt_status.correlation_id,
        ... )
        >>> if not result.is_complete_success:
        ...     logger.error("Some tasks failed to transition", failed=result.failed_task_ids)
    """

    @abstractmethod
    async def transition_all_tasks_on_halt(
        self,
        halt_correlation_id: UUID,
    ) -> HaltTransitionResult:
        """Transition all active tasks to halt states.

        This is the primary method for halt task transitions. It:
        1. Queries all non-terminal tasks
        2. Categorizes each by consent state
        3. Applies appropriate transition atomically
        4. Emits events with halt correlation
        5. Returns aggregated result

        Per FR24: Pre-consent → nullified
        Per FR25: Post-consent → quarantined
        Per FR26: Terminal → unchanged
        Per FR27: Each transition is atomic

        Args:
            halt_correlation_id: ID linking to the halt event.

        Returns:
            HaltTransitionResult with counts and individual records.

        Note:
            This method does not raise on individual task failures.
            Failures are recorded in the result for audit purposes.
        """
        ...

    @abstractmethod
    async def get_active_tasks(self) -> list[tuple[UUID, str]]:
        """Get all active (non-terminal) tasks.

        Returns:
            List of (task_id, current_status) tuples.
        """
        ...

    @abstractmethod
    async def atomic_transition(
        self,
        task_id: UUID,
        from_status: str,
        to_status: str,
        halt_correlation_id: UUID,
        transitioned_at: datetime,
    ) -> None:
        """Atomically transition a single task.

        Uses optimistic locking to ensure no partial transitions.
        If the task's current status doesn't match from_status,
        raises ConcurrentModificationError.

        Per FR27: Each task transitions atomically.
        Per NFR-ATOMIC-01: No partial state changes.

        Args:
            task_id: ID of task to transition.
            from_status: Expected current status (for optimistic lock).
            to_status: Target status.
            halt_correlation_id: ID linking to halt event.
            transitioned_at: Timestamp of transition.

        Raises:
            ConcurrentModificationError: If task state changed.
        """
        ...
