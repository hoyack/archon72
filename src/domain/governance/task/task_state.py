"""Task state domain model for consent-based governance.

Story: consent-gov-2.1: Task State Machine Domain Model

This module defines the TaskStatus enumeration and TaskState frozen dataclass
for the task state machine. All state transitions are validated and immutable.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Invalid transitions raise errors
- Golden Rule: No silent assignment → Explicit accept/decline transitions

Task States (11 total):
| State | Category | Description |
|-------|----------|-------------|
| authorized | Pre-consent | Task created by system, not yet offered |
| activated | Pre-consent | Task offered to Cluster via Earl |
| routed | Pre-consent | Task routed to Cluster (async delivery) |
| accepted | Post-consent | Cluster explicitly accepted |
| in_progress | Post-consent | Work actively being done |
| reported | Post-consent | Result submitted by Cluster |
| aggregated | Post-consent | Results aggregated (multi-cluster) |
| completed | Terminal | Task successfully finished |
| declined | Terminal | Cluster declined (or TTL expired) |
| quarantined | Terminal | Task isolated due to issue |
| nullified | Terminal | Task cancelled (pre-consent halt) |

References:
- [Source: governance-architecture.md#Task State Projection]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


class TaskStatus(str, Enum):
    """All possible task states in the consent-based governance system.

    Task states are organized into three categories:
    - Pre-consent: Task has been created but not yet accepted by a Cluster
    - Post-consent: Cluster has explicitly accepted the task
    - Terminal: Task lifecycle has ended

    The state machine enforces that tasks can only transition through
    legal states, ensuring consent-based coordination.
    """

    # Pre-consent states (Cluster has not agreed to work)
    AUTHORIZED = "authorized"
    """Task created by system, not yet offered to any Cluster."""

    ACTIVATED = "activated"
    """Task offered to Cluster via Earl, awaiting routing."""

    ROUTED = "routed"
    """Task routed to specific Cluster, awaiting acceptance."""

    # Post-consent states (Cluster has agreed to work)
    ACCEPTED = "accepted"
    """Cluster explicitly accepted the task."""

    IN_PROGRESS = "in_progress"
    """Work actively being done by Cluster."""

    REPORTED = "reported"
    """Result submitted by Cluster, awaiting aggregation."""

    AGGREGATED = "aggregated"
    """Results aggregated (for multi-cluster tasks)."""

    # Terminal states (no further transitions)
    COMPLETED = "completed"
    """Task successfully finished."""

    DECLINED = "declined"
    """Cluster declined task (or TTL expired without acceptance)."""

    QUARANTINED = "quarantined"
    """Task isolated due to issue (post-consent halt)."""

    NULLIFIED = "nullified"
    """Task cancelled (pre-consent halt)."""

    @property
    def is_pre_consent(self) -> bool:
        """Check if this is a pre-consent state.

        Pre-consent states are before explicit acceptance.
        Halt in pre-consent → nullified.
        """
        return self in _PRE_CONSENT_STATES

    @property
    def is_post_consent(self) -> bool:
        """Check if this is a post-consent state.

        Post-consent states are after explicit acceptance.
        Halt in post-consent → quarantined.
        """
        return self in _POST_CONSENT_STATES

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state.

        Terminal states have no further transitions.
        """
        return self in _TERMINAL_STATES


# State category sets for fast lookup
_PRE_CONSENT_STATES: frozenset[TaskStatus] = frozenset({
    TaskStatus.AUTHORIZED,
    TaskStatus.ACTIVATED,
    TaskStatus.ROUTED,
})

_POST_CONSENT_STATES: frozenset[TaskStatus] = frozenset({
    TaskStatus.ACCEPTED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.REPORTED,
    TaskStatus.AGGREGATED,
})

_TERMINAL_STATES: frozenset[TaskStatus] = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.DECLINED,
    TaskStatus.QUARANTINED,
    TaskStatus.NULLIFIED,
})


class IllegalStateTransitionError(ConstitutionalViolationError):
    """Raised when an illegal state transition is attempted.

    This is a constitutional violation - the state machine
    must not allow invalid transitions.

    Per FR13: State machine transitions are enforced.
    Per Golden Rule: No silent assignment.

    Attributes:
        current_state: The state the task is currently in.
        attempted_state: The state transition that was attempted.
        allowed_states: The set of states that are allowed transitions.
    """

    def __init__(
        self,
        current_state: TaskStatus,
        attempted_state: TaskStatus,
        allowed_states: frozenset[TaskStatus],
    ) -> None:
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.allowed_states = allowed_states
        super().__init__(
            f"FR13: Task cannot transition from {current_state.value} to "
            f"{attempted_state.value}. Allowed transitions: "
            f"{sorted(s.value for s in allowed_states)}"
        )


@dataclass(frozen=True)
class TaskState:
    """Immutable task state with transition capabilities.

    Per governance-architecture.md, tasks move through a defined state machine
    with explicit consent gates. This dataclass captures the current state
    and provides validated transition methods.

    Constitutional Guarantees:
    - Transitions are validated against rules
    - Invalid transitions raise IllegalStateTransitionError
    - All transitions can emit events to ledger via event generation
    - State is immutable (frozen dataclass)

    Attributes:
        task_id: Unique identifier for this task (UUID).
        earl_id: ID of the Earl who owns/manages this task.
        cluster_id: ID of the Cluster assigned (None until routed).
        current_status: Current state from TaskStatus enum.
        created_at: When the task was first created.
        state_entered_at: When the current state was entered.
        ttl: Time-to-live for acceptance (default 72h).
        inactivity_timeout: Max time between progress updates (default 48h).
        reporting_timeout: Max time to submit result (default 7 days).
    """

    task_id: UUID
    earl_id: str
    cluster_id: str | None  # None until routed
    current_status: TaskStatus
    created_at: datetime
    state_entered_at: datetime
    ttl: timedelta = timedelta(hours=72)  # Default 72h per NFR-CONSENT-01
    inactivity_timeout: timedelta = timedelta(hours=48)
    reporting_timeout: timedelta = timedelta(days=7)

    def __post_init__(self) -> None:
        """Validate all TaskState fields.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_task_id()
        self._validate_earl_id()
        self._validate_current_status()
        self._validate_timestamps()
        self._validate_timeouts()

    def _validate_task_id(self) -> None:
        """Validate task_id is UUID."""
        if not isinstance(self.task_id, UUID):
            raise ConstitutionalViolationError(
                f"FR13: TaskState validation failed - "
                f"task_id must be UUID, got {type(self.task_id).__name__}"
            )

    def _validate_earl_id(self) -> None:
        """Validate earl_id is non-empty string."""
        if not isinstance(self.earl_id, str):
            raise ConstitutionalViolationError(
                f"FR13: TaskState validation failed - "
                f"earl_id must be string, got {type(self.earl_id).__name__}"
            )
        if not self.earl_id.strip():
            raise ConstitutionalViolationError(
                "FR13: TaskState validation failed - "
                "earl_id must be non-empty string"
            )

    def _validate_current_status(self) -> None:
        """Validate current_status is TaskStatus."""
        if not isinstance(self.current_status, TaskStatus):
            raise ConstitutionalViolationError(
                f"FR13: TaskState validation failed - "
                f"current_status must be TaskStatus, got {type(self.current_status).__name__}"
            )

    def _validate_timestamps(self) -> None:
        """Validate timestamps are datetime."""
        if not isinstance(self.created_at, datetime):
            raise ConstitutionalViolationError(
                f"FR13: TaskState validation failed - "
                f"created_at must be datetime, got {type(self.created_at).__name__}"
            )
        if not isinstance(self.state_entered_at, datetime):
            raise ConstitutionalViolationError(
                f"FR13: TaskState validation failed - "
                f"state_entered_at must be datetime, got {type(self.state_entered_at).__name__}"
            )

    def _validate_timeouts(self) -> None:
        """Validate timeouts are positive timedelta."""
        if not isinstance(self.ttl, timedelta) or self.ttl <= timedelta(0):
            raise ConstitutionalViolationError(
                "FR13: TaskState validation failed - "
                "ttl must be positive timedelta"
            )
        if not isinstance(self.inactivity_timeout, timedelta) or self.inactivity_timeout <= timedelta(0):
            raise ConstitutionalViolationError(
                "FR13: TaskState validation failed - "
                "inactivity_timeout must be positive timedelta"
            )
        if not isinstance(self.reporting_timeout, timedelta) or self.reporting_timeout <= timedelta(0):
            raise ConstitutionalViolationError(
                "FR13: TaskState validation failed - "
                "reporting_timeout must be positive timedelta"
            )

    def transition(
        self,
        new_status: TaskStatus,
        transition_time: datetime,
        actor_id: str,
        reason: str = "",
    ) -> TaskState:
        """Transition to new state if valid.

        This is the core state machine operation. Validates that the
        transition is allowed before creating a new TaskState.

        Per FR13: State machine transitions are enforced.
        Per AC6: Returns new TaskState (immutable pattern).

        Args:
            new_status: The target state to transition to.
            transition_time: When the transition occurs.
            actor_id: ID of the actor performing the transition.
            reason: Optional reason for the transition.

        Returns:
            New TaskState with updated status and state_entered_at.

        Raises:
            IllegalStateTransitionError: If transition is not allowed.
        """
        # Import here to avoid circular dependency
        from src.domain.governance.task.task_state_rules import TaskTransitionRules

        if not TaskTransitionRules.is_valid_transition(
            self.current_status, new_status
        ):
            raise IllegalStateTransitionError(
                current_state=self.current_status,
                attempted_state=new_status,
                allowed_states=TaskTransitionRules.get_allowed_transitions(
                    self.current_status
                ),
            )

        return TaskState(
            task_id=self.task_id,
            earl_id=self.earl_id,
            cluster_id=self.cluster_id,
            current_status=new_status,
            created_at=self.created_at,
            state_entered_at=transition_time,
            ttl=self.ttl,
            inactivity_timeout=self.inactivity_timeout,
            reporting_timeout=self.reporting_timeout,
        )

    def with_cluster(self, cluster_id: str) -> TaskState:
        """Create new TaskState with cluster assigned.

        Used when routing a task to a specific cluster.

        Args:
            cluster_id: ID of the cluster to assign.

        Returns:
            New TaskState with cluster_id set.

        Raises:
            ConstitutionalViolationError: If cluster_id is invalid.
        """
        if not isinstance(cluster_id, str) or not cluster_id.strip():
            raise ConstitutionalViolationError(
                "FR13: cluster_id must be non-empty string"
            )

        return TaskState(
            task_id=self.task_id,
            earl_id=self.earl_id,
            cluster_id=cluster_id,
            current_status=self.current_status,
            created_at=self.created_at,
            state_entered_at=self.state_entered_at,
            ttl=self.ttl,
            inactivity_timeout=self.inactivity_timeout,
            reporting_timeout=self.reporting_timeout,
        )

    @property
    def is_pre_consent(self) -> bool:
        """Check if task is in pre-consent state.

        Pre-consent: Cluster has not yet agreed to work.
        Halt in pre-consent → nullified.
        """
        return self.current_status.is_pre_consent

    @property
    def is_post_consent(self) -> bool:
        """Check if task is in post-consent state.

        Post-consent: Cluster has agreed to work.
        Halt in post-consent → quarantined.
        """
        return self.current_status.is_post_consent

    @property
    def is_terminal(self) -> bool:
        """Check if task is in terminal state.

        Terminal: No further transitions possible.
        """
        return self.current_status.is_terminal

    def is_ttl_expired(self, current_time: datetime) -> bool:
        """Check if TTL has expired for acceptance.

        Only applies to pre-consent states (authorized, activated, routed).
        Per NFR-CONSENT-01: TTL expiration = declined.

        Args:
            current_time: Current time to check against.

        Returns:
            True if task is pre-consent and TTL has expired.
        """
        if not self.is_pre_consent:
            return False
        return current_time > self.state_entered_at + self.ttl

    def is_inactive(self, current_time: datetime) -> bool:
        """Check if task has exceeded inactivity timeout.

        Only applies to in_progress state.

        Args:
            current_time: Current time to check against.

        Returns:
            True if task is in_progress and inactive timeout exceeded.
        """
        if self.current_status != TaskStatus.IN_PROGRESS:
            return False
        return current_time > self.state_entered_at + self.inactivity_timeout

    def is_reporting_expired(self, current_time: datetime) -> bool:
        """Check if reporting timeout has expired.

        Only applies to accepted/in_progress states.

        Args:
            current_time: Current time to check against.

        Returns:
            True if task should have reported by now.
        """
        if self.current_status not in {TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS}:
            return False
        return current_time > self.state_entered_at + self.reporting_timeout

    @classmethod
    def create(
        cls,
        *,
        task_id: UUID,
        earl_id: str,
        created_at: datetime,
        ttl: timedelta | None = None,
        inactivity_timeout: timedelta | None = None,
        reporting_timeout: timedelta | None = None,
    ) -> TaskState:
        """Factory method to create a new task in AUTHORIZED state.

        All tasks start in AUTHORIZED state (pre-consent).

        Args:
            task_id: Unique identifier for this task.
            earl_id: ID of the Earl who owns this task.
            created_at: When the task is created.
            ttl: Time-to-live for acceptance (optional, default 72h).
            inactivity_timeout: Max inactivity time (optional, default 48h).
            reporting_timeout: Max reporting time (optional, default 7 days).

        Returns:
            New TaskState in AUTHORIZED status.
        """
        kwargs: dict[str, Any] = {
            "task_id": task_id,
            "earl_id": earl_id,
            "cluster_id": None,
            "current_status": TaskStatus.AUTHORIZED,
            "created_at": created_at,
            "state_entered_at": created_at,
        }
        if ttl is not None:
            kwargs["ttl"] = ttl
        if inactivity_timeout is not None:
            kwargs["inactivity_timeout"] = inactivity_timeout
        if reporting_timeout is not None:
            kwargs["reporting_timeout"] = reporting_timeout

        return cls(**kwargs)
