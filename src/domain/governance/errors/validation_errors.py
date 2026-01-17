"""Write-time validation errors for governance ledger.

Story: consent-gov-1.4: Write-Time Validation

This module defines the error hierarchy for write-time validation failures.
Each error type provides specific context for debugging and includes
the architectural decision reference.

Constitutional Constraint:
    Write-time prevention is for ledger corruption. Policy violations are
    detected at observer-time (Knight-Witness).

Error Hierarchy:
    WriteTimeValidationError (base)
    ├── IllegalStateTransitionError - State machine violation
    ├── HashChainBreakError - Hash chain integrity violation
    ├── UnknownEventTypeError - Unregistered event type
    └── UnknownActorError - Unregistered actor

References:
    - [Source: _bmad-output/planning-artifacts/governance-architecture.md#Write-Time Prevention (Locked)]
    - AD-12: Write-time prevention
    - NFR-PERF-05: State machine ≤10ms
    - NFR-CONST-09: No mutation except state machine
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


class WriteTimeValidationError(Exception):
    """Base exception for write-time validation failures.

    All write-time validation errors inherit from this class.
    Each subclass provides specific context for debugging.

    Write-time validation protects ledger integrity by rejecting:
    - Illegal state transitions
    - Hash chain breaks
    - Unknown event types
    - Unknown actors

    NOTE: This is for STRUCTURAL integrity. Policy violations
    (Golden Rule, legitimacy decay) are observer-time concerns.
    """

    pass


@dataclass(frozen=True)
class IllegalStateTransitionError(WriteTimeValidationError):
    """State machine transition is not allowed.

    Raised when an event attempts a state transition that violates
    the state machine rules. For example, transitioning a task
    directly from 'authorized' to 'completed' without 'activated'.

    Attributes:
        event_id: The ID of the event that failed validation.
        aggregate_type: The type of aggregate (e.g., 'task', 'legitimacy').
        aggregate_id: The ID of the specific aggregate instance.
        current_state: The current state of the aggregate.
        attempted_state: The state transition attempted by the event.
        allowed_states: List of valid states that can be transitioned to.

    References:
        - AD-12: Write-time prevention
        - NFR-CONST-09: No mutation except state machine
    """

    event_id: UUID
    aggregate_type: str
    aggregate_id: str
    current_state: str
    attempted_state: str
    allowed_states: list[str]

    def __str__(self) -> str:
        """Format error message with full context."""
        allowed_str = ", ".join(self.allowed_states) if self.allowed_states else "none"
        return (
            f"AD-12: Illegal state transition for {self.aggregate_type}:{self.aggregate_id} "
            f"(event {self.event_id}): cannot transition from '{self.current_state}' "
            f"to '{self.attempted_state}'. Allowed transitions: [{allowed_str}]"
        )

    def __hash__(self) -> int:
        """Hash based on event_id."""
        return hash(self.event_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on event_id."""
        if not isinstance(other, IllegalStateTransitionError):
            return NotImplemented
        return self.event_id == other.event_id


@dataclass(frozen=True)
class HashChainBreakError(WriteTimeValidationError):
    """Hash chain integrity violation.

    Raised when an event's prev_hash does not match the hash of the
    previous event in the ledger. This indicates potential tampering
    or a bug in hash chain construction.

    This is an EXISTENTIAL threat to ledger integrity and must
    result in immediate rejection.

    Attributes:
        event_id: The ID of the event that failed validation.
        expected_prev_hash: The hash of the latest event in the ledger.
        actual_prev_hash: The prev_hash provided by the event.
        latest_sequence: The sequence number of the latest event (for debugging).

    References:
        - AD-6: Hash chain implementation
        - NFR-CONST-02: Event integrity verification
    """

    event_id: UUID
    expected_prev_hash: str
    actual_prev_hash: str
    latest_sequence: int = 0

    def __str__(self) -> str:
        """Format error message with truncated hashes for readability."""
        expected_short = self.expected_prev_hash[:24] + "..." if len(self.expected_prev_hash) > 24 else self.expected_prev_hash
        actual_short = self.actual_prev_hash[:24] + "..." if len(self.actual_prev_hash) > 24 else self.actual_prev_hash
        seq_info = f" (after sequence {self.latest_sequence})" if self.latest_sequence > 0 else ""
        return (
            f"AD-6: Hash chain break detected for event {self.event_id}{seq_info}: "
            f"expected prev_hash='{expected_short}', actual prev_hash='{actual_short}'"
        )

    def __hash__(self) -> int:
        """Hash based on event_id."""
        return hash(self.event_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on event_id."""
        if not isinstance(other, HashChainBreakError):
            return NotImplemented
        return self.event_id == other.event_id


@dataclass(frozen=True)
class UnknownEventTypeError(WriteTimeValidationError):
    """Event type is not registered in the governance vocabulary.

    Raised when an event uses an event_type that is not in the
    registered set of governance event types.

    Attributes:
        event_id: The ID of the event that failed validation.
        event_type: The unrecognized event type string.
        suggestion: Optional suggestion for the correct event type.

    References:
        - AD-5: Event type validation
        - governance-architecture.md Event Naming Convention
    """

    event_id: UUID
    event_type: str
    suggestion: str = ""

    def __str__(self) -> str:
        """Format error message with optional suggestion."""
        base_msg = (
            f"AD-5: Unknown event type '{self.event_type}' for event {self.event_id}"
        )
        if self.suggestion:
            return f"{base_msg}. Did you mean '{self.suggestion}'?"
        return base_msg

    def __hash__(self) -> int:
        """Hash based on event_id."""
        return hash(self.event_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on event_id."""
        if not isinstance(other, UnknownEventTypeError):
            return NotImplemented
        return self.event_id == other.event_id


@dataclass(frozen=True)
class UnknownActorError(WriteTimeValidationError):
    """Actor is not registered in the actor registry.

    Raised when an event references an actor_id that is not
    registered in the governance actor registry.

    Attributes:
        event_id: The ID of the event that failed validation.
        actor_id: The unrecognized actor ID string.

    References:
        - CT-12: Witnessing creates accountability
        - All actors must be attributable
    """

    event_id: UUID
    actor_id: str

    def __str__(self) -> str:
        """Format error message."""
        return (
            f"CT-12: Unknown actor '{self.actor_id}' for event {self.event_id}. "
            f"All actors must be registered before emitting events."
        )

    def __hash__(self) -> int:
        """Hash based on event_id."""
        return hash(self.event_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on event_id."""
        if not isinstance(other, UnknownActorError):
            return NotImplemented
        return self.event_id == other.event_id
