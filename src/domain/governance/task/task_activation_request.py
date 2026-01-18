"""Task activation request domain models for consent-based governance.

Story: consent-gov-2.2: Task Activation Request

This module defines the TaskActivationRequest and TaskActivationResult
domain models for the task activation workflow.

Constitutional Guarantees:
- Content MUST pass through Coercion Filter (FR21)
- Cannot be sent without FilteredContent wrapper
- No bypass path exists for participant messages

References:
- [Source: governance-architecture.md#Filter Pipeline Placement (Locked)]
- [Source: governance-architecture.md#Routing Architecture (Locked)]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.governance.task.task_state import TaskState


class FilterOutcome(str, Enum):
    """Possible outcomes from the Coercion Filter.

    Per FR21, all content must pass through the Coercion Filter
    before routing to participants.
    """

    ACCEPTED = "accepted"
    """Content passed filter unchanged."""

    TRANSFORMED = "transformed"
    """Content was modified by filter to remove coercive elements."""

    REJECTED = "rejected"
    """Content was rejected - Earl may revise and resubmit."""

    BLOCKED = "blocked"
    """Content was blocked due to severe violation - logged to ledger."""


class RoutingStatus(str, Enum):
    """Status of the routing attempt to Cluster.

    Per NFR-INT-01, all Earl→Cluster communication uses async protocol.
    """

    ROUTED = "routed"
    """Successfully routed to Cluster via async protocol."""

    PENDING_REWRITE = "pending_rewrite"
    """Content rejected, awaiting Earl revision."""

    BLOCKED = "blocked"
    """Content blocked due to violation, not routable."""

    PENDING_FILTER = "pending_filter"
    """Awaiting filter decision."""


@dataclass(frozen=True)
class FilteredContent:
    """Wrapper for content that has passed through Coercion Filter.

    This type enforces at the type system level that only filtered
    content can be sent to participants. Raw strings cannot be sent.

    Constitutional Guarantee:
    - Only FilteredContent can be sent to participants
    - Type system prevents bypass of Coercion Filter

    Attributes:
        content: The filtered content text.
        filter_decision_id: UUID of the filter decision for audit.
        original_hash: BLAKE3 hash of original content (not stored raw).
        transformation_applied: True if content was modified by filter.
    """

    content: str
    filter_decision_id: UUID
    original_hash: str
    transformation_applied: bool = False


@dataclass(frozen=True)
class TaskActivationRequest:
    """Request to activate a task for a Cluster.

    Per governance-architecture.md, task activation must:
    1. Create task in AUTHORIZED state
    2. Transition to ACTIVATED
    3. Pass through Coercion Filter
    4. Route to Cluster via async protocol if accepted

    Constitutional Guarantee:
    - Content MUST pass through Coercion Filter
    - Cannot be sent without FilteredContent wrapper

    Attributes:
        request_id: Unique identifier for this activation request.
        task_id: The task being activated.
        earl_id: The Earl creating the activation request.
        cluster_id: The Cluster to receive the task.
        description: Task description (subject to filtering).
        requirements: List of requirements (subject to filtering).
        expected_outcomes: Expected deliverables (subject to filtering).
        ttl: Time-to-live for acceptance (default 72h per NFR-CONSENT-01).
        created_at: When this request was created.
        filtered_content: FilteredContent after filter processing (None initially).
        filter_decision_id: UUID of filter decision (None until filtered).
        filter_outcome: Result of filter processing (None until filtered).
    """

    request_id: UUID
    task_id: UUID
    earl_id: str
    cluster_id: str
    description: str
    requirements: list[str] = field(default_factory=list)
    expected_outcomes: list[str] = field(default_factory=list)
    ttl: timedelta = field(default_factory=lambda: timedelta(hours=72))
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Filter-related fields (set after filtering)
    filtered_content: FilteredContent | None = None
    filter_decision_id: UUID | None = None
    filter_outcome: FilterOutcome | None = None

    def __post_init__(self) -> None:
        """Validate activation request fields."""
        self._validate_ids()
        self._validate_description()
        self._validate_ttl()

    def _validate_ids(self) -> None:
        """Validate ID fields."""
        if not isinstance(self.request_id, UUID):
            raise ValueError(
                f"request_id must be UUID, got {type(self.request_id).__name__}"
            )
        if not isinstance(self.task_id, UUID):
            raise ValueError(f"task_id must be UUID, got {type(self.task_id).__name__}")
        if not isinstance(self.earl_id, str) or not self.earl_id.strip():
            raise ValueError("earl_id must be non-empty string")
        if not isinstance(self.cluster_id, str) or not self.cluster_id.strip():
            raise ValueError("cluster_id must be non-empty string")

    def _validate_description(self) -> None:
        """Validate description is non-empty."""
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be non-empty string")

    def _validate_ttl(self) -> None:
        """Validate TTL is positive duration."""
        if not isinstance(self.ttl, timedelta):
            raise ValueError(f"ttl must be timedelta, got {type(self.ttl).__name__}")
        if self.ttl.total_seconds() <= 0:
            raise ValueError("ttl must be positive duration")

    @property
    def is_filtered(self) -> bool:
        """Check if this request has been filtered."""
        return self.filter_outcome is not None

    @property
    def is_routable(self) -> bool:
        """Check if this request can be routed to Cluster.

        Only accepted or transformed content can be routed.
        """
        return self.filter_outcome in (
            FilterOutcome.ACCEPTED,
            FilterOutcome.TRANSFORMED,
        )


@dataclass(frozen=True)
class TaskActivationResult:
    """Result of task activation attempt.

    This captures the full outcome of attempting to activate a task,
    including filter decision and routing status.

    Attributes:
        success: True if task was successfully routed.
        task_state: Current TaskState after activation attempt.
        filter_outcome: Result from Coercion Filter.
        filter_decision_id: UUID of filter decision for audit.
        routing_status: Current routing status.
        message: Human-readable message about the result.
        rejection_reason: Reason for rejection (if rejected/blocked).
    """

    success: bool
    task_state: TaskState
    filter_outcome: FilterOutcome
    filter_decision_id: UUID
    routing_status: RoutingStatus
    message: str
    rejection_reason: str | None = None


@dataclass(frozen=True)
class TaskStateView:
    """View of task state for Earl visibility.

    Per FR12, Earl can view task state and history.
    This provides a read-only view of task status.

    Attributes:
        task_id: The task identifier.
        current_status: Current status from TaskStatus enum.
        cluster_id: The assigned Cluster (if any).
        created_at: When task was created.
        state_entered_at: When current state was entered.
        ttl: Time-to-live for acceptance.
        ttl_remaining: Time remaining until TTL expiry.
        is_pre_consent: True if task is in pre-consent state.
        is_post_consent: True if task is in post-consent state.
        is_terminal: True if task is in terminal state.
    """

    task_id: UUID
    current_status: str  # String to avoid circular import with TaskStatus
    cluster_id: str | None
    created_at: datetime
    state_entered_at: datetime
    ttl: timedelta
    ttl_remaining: timedelta | None
    is_pre_consent: bool
    is_post_consent: bool
    is_terminal: bool
