"""Two-phase event domain models for Knight observability.

Story: consent-gov-1.6: Two-Phase Event Emission

This module defines the event types for two-phase emission that enables
Knight observation of all governance operations:

1. IntentEmittedEvent - Published BEFORE operation begins
2. CommitConfirmedEvent - Published on successful operation completion
3. FailureRecordedEvent - Published on operation failure

Constitutional Guarantees:
- Intent is ALWAYS emitted before operation begins
- Outcome (commit/failure) is ALWAYS emitted after operation
- No orphaned intents - auto-resolved after timeout
- Knight can observe intent immediately upon action initiation

Event Type Naming Convention (per governance-architecture.md):
- Intent: {branch}.intent.emitted
- Commit: {branch}.commit.confirmed
- Failure: {branch}.failure.recorded

Where {branch} is derived from operation_type (e.g., "executive.task.accept" -> "executive")

References:
- AD-3: Two-phase event emission
- NFR-CONST-07: Witness statements cannot be suppressed
- NFR-OBS-01: Events observable within ≤1 second
- NFR-AUDIT-01: All branch actions logged
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


class TwoPhaseEventTypeError(Exception):
    """Raised when two-phase event validation fails.

    This error indicates that a two-phase event could not be created
    due to invalid field values (wrong type, empty string, etc.).
    """

    pass


def _derive_branch_from_operation_type(operation_type: str) -> str:
    """Derive the governance branch from an operation type.

    Args:
        operation_type: Operation type in format "branch.noun.verb"
                       (e.g., "executive.task.accept")

    Returns:
        The branch component (first segment).

    Raises:
        TwoPhaseEventTypeError: If operation_type is malformed.
    """
    if not operation_type or "." not in operation_type:
        raise TwoPhaseEventTypeError(
            f"operation_type must be in format 'branch.noun.verb', got '{operation_type}'"
        )
    return operation_type.split(".")[0]


def _validate_uuid(value: Any, field_name: str) -> None:
    """Validate that a value is a UUID instance.

    Args:
        value: Value to validate.
        field_name: Name of the field for error messages.

    Raises:
        TwoPhaseEventTypeError: If value is not a UUID.
    """
    if not isinstance(value, UUID):
        raise TwoPhaseEventTypeError(
            f"{field_name} must be UUID, got {type(value).__name__}"
        )


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    """Validate that a value is a non-empty string.

    Args:
        value: Value to validate.
        field_name: Name of the field for error messages.

    Raises:
        TwoPhaseEventTypeError: If value is not a non-empty string.
    """
    if not isinstance(value, str):
        raise TwoPhaseEventTypeError(
            f"{field_name} must be string, got {type(value).__name__}"
        )
    if not value.strip():
        raise TwoPhaseEventTypeError(f"{field_name} must be non-empty string")


@dataclass(frozen=True, eq=True)
class IntentEmittedEvent:
    """Published BEFORE operation begins.

    This event is emitted immediately when an actor initiates a governance
    operation. The Knight can observe this event to know that an action
    has been attempted, even if the operation later fails.

    Attributes:
        correlation_id: Links intent to outcome (UUID v4).
        operation_type: Operation being attempted (e.g., "executive.task.accept").
        actor_id: ID of the archon or officer initiating the action.
        target_entity_id: ID of the entity being acted upon.
        intent_payload: Operation-specific intent data.

    Event Type: {branch}.intent.emitted
        - Example: "executive.intent.emitted", "judicial.intent.emitted"
    """

    correlation_id: UUID
    operation_type: str
    actor_id: str
    target_entity_id: str
    intent_payload: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate all fields on creation.

        Raises:
            TwoPhaseEventTypeError: If any field fails validation.
        """
        _validate_uuid(self.correlation_id, "correlation_id")
        _validate_non_empty_string(self.operation_type, "operation_type")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_non_empty_string(self.target_entity_id, "target_entity_id")
        # Validate operation_type format by deriving branch
        _derive_branch_from_operation_type(self.operation_type)

    @property
    def event_type(self) -> str:
        """Generate the event type for this intent event.

        Returns:
            Event type in format "{branch}.intent.emitted".
        """
        branch = _derive_branch_from_operation_type(self.operation_type)
        return f"{branch}.intent.emitted"

    @property
    def branch(self) -> str:
        """Get the governance branch for this event.

        Returns:
            Branch derived from operation_type (e.g., "executive").
        """
        return _derive_branch_from_operation_type(self.operation_type)

    def __hash__(self) -> int:
        """Hash based on correlation_id."""
        return hash(self.correlation_id)


@dataclass(frozen=True, eq=True)
class CommitConfirmedEvent:
    """Published on successful operation completion.

    This event is emitted when an operation that was previously announced
    via IntentEmittedEvent completes successfully. The correlation_id links
    this event to the original intent.

    Attributes:
        correlation_id: Links to intent (same UUID as IntentEmittedEvent).
        intent_event_id: UUID of the IntentEmittedEvent in the ledger.
        operation_type: Operation that was completed.
        result_payload: Operation-specific result data.

    Event Type: {branch}.commit.confirmed
        - Example: "executive.commit.confirmed"
    """

    correlation_id: UUID
    intent_event_id: UUID
    operation_type: str
    result_payload: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate all fields on creation.

        Raises:
            TwoPhaseEventTypeError: If any field fails validation.
        """
        _validate_uuid(self.correlation_id, "correlation_id")
        _validate_uuid(self.intent_event_id, "intent_event_id")
        _validate_non_empty_string(self.operation_type, "operation_type")
        # Validate operation_type format by deriving branch
        _derive_branch_from_operation_type(self.operation_type)

    @property
    def event_type(self) -> str:
        """Generate the event type for this commit event.

        Returns:
            Event type in format "{branch}.commit.confirmed".
        """
        branch = _derive_branch_from_operation_type(self.operation_type)
        return f"{branch}.commit.confirmed"

    @property
    def branch(self) -> str:
        """Get the governance branch for this event.

        Returns:
            Branch derived from operation_type.
        """
        return _derive_branch_from_operation_type(self.operation_type)

    def __hash__(self) -> int:
        """Hash based on correlation_id."""
        return hash(self.correlation_id)


@dataclass(frozen=True, eq=True)
class FailureRecordedEvent:
    """Published on operation failure.

    This event is emitted when an operation that was previously announced
    via IntentEmittedEvent fails. The correlation_id links this event to
    the original intent. Failures include both exceptions during execution
    and intentional rejections.

    Attributes:
        correlation_id: Links to intent (same UUID as IntentEmittedEvent).
        intent_event_id: UUID of the IntentEmittedEvent in the ledger.
        operation_type: Operation that failed.
        failure_reason: Short reason code (e.g., "VALIDATION_FAILED", "ORPHAN_TIMEOUT").
        failure_details: Detailed error information.
        was_orphan: True if this failure was auto-generated for an orphaned intent.

    Event Type: {branch}.failure.recorded
        - Example: "executive.failure.recorded"
    """

    correlation_id: UUID
    intent_event_id: UUID
    operation_type: str
    failure_reason: str
    failure_details: dict[str, Any]
    was_orphan: bool = False

    def __post_init__(self) -> None:
        """Validate all fields on creation.

        Raises:
            TwoPhaseEventTypeError: If any field fails validation.
        """
        _validate_uuid(self.correlation_id, "correlation_id")
        _validate_uuid(self.intent_event_id, "intent_event_id")
        _validate_non_empty_string(self.operation_type, "operation_type")
        _validate_non_empty_string(self.failure_reason, "failure_reason")
        # Validate operation_type format by deriving branch
        _derive_branch_from_operation_type(self.operation_type)

    @property
    def event_type(self) -> str:
        """Generate the event type for this failure event.

        Returns:
            Event type in format "{branch}.failure.recorded".
        """
        branch = _derive_branch_from_operation_type(self.operation_type)
        return f"{branch}.failure.recorded"

    @property
    def branch(self) -> str:
        """Get the governance branch for this event.

        Returns:
            Branch derived from operation_type.
        """
        return _derive_branch_from_operation_type(self.operation_type)

    def __hash__(self) -> int:
        """Hash based on correlation_id."""
        return hash(self.correlation_id)
