"""Transition log domain models for state transition audit trail.

Story: consent-gov-9.4: State Transition Logging

Domain models for logging all state transitions in the governance system.
All transitions are logged with full context for audit purposes.

Constitutional Requirements:
- FR59: System can log all state transitions with timestamp and actor
- FR60: System can prevent ledger modification (append-only enforcement)
- NFR-AUDIT-04: Transitions include triggering event reference

Key Design Decisions:
- All logs are frozen dataclasses (immutable)
- No modification or deletion methods exist
- Append-only by design
- All entity types use same TransitionLog structure
- Triggering event reference enables cause-effect tracing
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class EntityType(Enum):
    """Type of entity being transitioned.

    Defines all entity types that can have state transitions logged.
    All entity types use the same TransitionLog structure for consistency.
    """

    TASK = "task"
    LEGITIMACY_BAND = "legitimacy_band"
    SYSTEM = "system"
    CLUSTER = "cluster"
    MOTION = "motion"
    PANEL = "panel"
    PARTICIPANT = "participant"


@dataclass(frozen=True)
class TransitionLog:
    """Immutable log of a state transition.

    This is an append-only record of a state change. Once created,
    it cannot be modified. This is enforced by the frozen dataclass
    and by the absence of any update/delete methods in the port.

    Attributes:
        log_id: Unique identifier for this log entry.
        entity_type: Type of entity that transitioned.
        entity_id: ID of the entity that transitioned.
        from_state: State before the transition.
        to_state: State after the transition.
        timestamp: When the transition occurred (millisecond precision).
        actor: Who/what caused the transition (UUID or "system").
        reason: Human-readable reason for the transition.
        triggering_event_id: Optional reference to the event that triggered this.

    Constitutional Alignment:
        - FR59: timestamp and actor captured
        - NFR-AUDIT-04: triggering_event_id for tracing

    Note: The following are INTENTIONALLY NOT included:
        - modified_at: datetime (immutable, cannot be modified)
        - modified_by: UUID (immutable, cannot be modified)
        - deleted_at: datetime (append-only, cannot be deleted)
    """

    log_id: UUID
    entity_type: EntityType
    entity_id: UUID
    from_state: str
    to_state: str
    timestamp: datetime
    actor: str
    reason: str
    triggering_event_id: UUID | None = None

    def __post_init__(self) -> None:
        """Validate transition log fields."""
        if not self.from_state:
            raise ValueError("from_state cannot be empty")
        if not self.to_state:
            raise ValueError("to_state cannot be empty")
        if not self.actor:
            raise ValueError("actor cannot be empty")
        if not self.reason:
            raise ValueError("reason cannot be empty")

    @property
    def is_system_initiated(self) -> bool:
        """Check if this transition was initiated by the system."""
        return self.actor == "system"

    @property
    def has_triggering_event(self) -> bool:
        """Check if this transition has a linked triggering event."""
        return self.triggering_event_id is not None


@dataclass(frozen=True)
class TransitionQuery:
    """Query parameters for retrieving transition logs.

    All parameters are optional. When multiple are specified,
    they are combined with AND logic.

    Attributes:
        entity_type: Filter by entity type.
        entity_id: Filter by specific entity.
        actor: Filter by actor who triggered the transition.
        from_timestamp: Include transitions at or after this time.
        to_timestamp: Include transitions at or before this time.
        from_state: Filter by the source state.
        to_state: Filter by the target state.
    """

    entity_type: EntityType | None = None
    entity_id: UUID | None = None
    actor: str | None = None
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    from_state: str | None = None
    to_state: str | None = None

    def matches(self, log: TransitionLog) -> bool:
        """Check if a transition log matches this query.

        Args:
            log: The transition log to check.

        Returns:
            True if the log matches all specified criteria.
        """
        if self.entity_type is not None and log.entity_type != self.entity_type:
            return False
        if self.entity_id is not None and log.entity_id != self.entity_id:
            return False
        if self.actor is not None and log.actor != self.actor:
            return False
        if self.from_timestamp is not None and log.timestamp < self.from_timestamp:
            return False
        if self.to_timestamp is not None and log.timestamp > self.to_timestamp:
            return False
        if self.from_state is not None and log.from_state != self.from_state:
            return False
        return not (self.to_state is not None and log.to_state != self.to_state)


class TransitionLogError(ValueError):
    """Base error for transition log operations."""

    pass


class TransitionLogModificationError(TransitionLogError):
    """Raised when log modification is attempted.

    This error should never actually be raised in production because
    modification methods don't exist. It exists to document the
    design constraint and catch any accidental implementation of
    modification methods.
    """

    pass


class TransitionLogNotFoundError(TransitionLogError):
    """Raised when a requested transition log is not found."""

    pass
