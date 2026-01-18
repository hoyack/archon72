"""State transition validator for governance events.

Story: consent-gov-1.4: Write-Time Validation

Validates that state machine transitions are legal before allowing
events to be appended to the ledger.

Performance Target: ≤10ms (NFR-PERF-05)

References:
    - AD-12: Write-time prevention
    - NFR-CONST-09: No mutation except state machine
    - NFR-PERF-05: State machine resolution ≤10ms
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from src.domain.governance.errors.validation_errors import IllegalStateTransitionError
from src.domain.governance.events.event_envelope import GovernanceEvent


class TaskState(str, Enum):
    """Task lifecycle states per governance-architecture.md."""

    PENDING = "pending"
    AUTHORIZED = "authorized"
    ACTIVATED = "activated"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class LegitimacyBand(str, Enum):
    """Legitimacy band states per governance-architecture.md."""

    FULL = "full"
    PROVISIONAL = "provisional"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


# State machine transition rules (immutable)
# Maps current_state -> allowed_next_states
TASK_STATE_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.PENDING: frozenset({TaskState.AUTHORIZED, TaskState.CANCELLED}),
    TaskState.AUTHORIZED: frozenset(
        {TaskState.ACTIVATED, TaskState.EXPIRED, TaskState.CANCELLED}
    ),
    TaskState.ACTIVATED: frozenset(
        {TaskState.ACCEPTED, TaskState.DECLINED, TaskState.EXPIRED}
    ),
    TaskState.ACCEPTED: frozenset({TaskState.COMPLETED, TaskState.EXPIRED}),
    TaskState.DECLINED: frozenset(),  # Terminal state
    TaskState.COMPLETED: frozenset(),  # Terminal state
    TaskState.EXPIRED: frozenset(),  # Terminal state
    TaskState.CANCELLED: frozenset(),  # Terminal state
}

LEGITIMACY_BAND_TRANSITIONS: dict[LegitimacyBand, frozenset[LegitimacyBand]] = {
    # Downward transitions are automatic (decay)
    # Upward transitions require explicit restoration
    LegitimacyBand.FULL: frozenset({LegitimacyBand.PROVISIONAL}),
    LegitimacyBand.PROVISIONAL: frozenset(
        {LegitimacyBand.FULL, LegitimacyBand.SUSPENDED}
    ),
    LegitimacyBand.SUSPENDED: frozenset(
        {LegitimacyBand.PROVISIONAL, LegitimacyBand.REVOKED}
    ),
    LegitimacyBand.REVOKED: frozenset(
        {LegitimacyBand.SUSPENDED}
    ),  # Requires explicit restoration
}


@dataclass(frozen=True)
class AggregateState:
    """Current state of an aggregate."""

    aggregate_type: str
    aggregate_id: str
    current_state: str


@runtime_checkable
class StateProjectionPort(Protocol):
    """Port for querying current state of aggregates.

    This port provides access to projections that track aggregate state.
    """

    async def get_current_state(
        self,
        aggregate_type: str,
        aggregate_id: str,
    ) -> AggregateState | None:
        """Get current state of an aggregate.

        Args:
            aggregate_type: Type of aggregate (e.g., 'task', 'legitimacy').
            aggregate_id: ID of the specific aggregate.

        Returns:
            Current state of the aggregate, or None if not found.
        """
        ...


class InMemoryStateProjection:
    """In-memory implementation of StateProjectionPort.

    Used for testing and as a cache layer.
    """

    def __init__(self) -> None:
        """Initialize empty state projection."""
        self._states: dict[tuple[str, str], AggregateState] = {}

    async def get_current_state(
        self,
        aggregate_type: str,
        aggregate_id: str,
    ) -> AggregateState | None:
        """Get current state of an aggregate."""
        return self._states.get((aggregate_type, aggregate_id))

    def set_state(
        self,
        aggregate_type: str,
        aggregate_id: str,
        current_state: str,
    ) -> None:
        """Set state of an aggregate (for testing)."""
        self._states[(aggregate_type, aggregate_id)] = AggregateState(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            current_state=current_state,
        )

    def clear(self) -> None:
        """Clear all states (for testing)."""
        self._states.clear()


# Event type to state mapping
# Maps event_type -> (aggregate_type, state_field_in_payload, resulting_state)
EVENT_STATE_MAPPINGS: dict[str, tuple[str, str, str]] = {
    # Task lifecycle events
    "executive.task.activated": ("task", "task_id", TaskState.ACTIVATED.value),
    "executive.task.accepted": ("task", "task_id", TaskState.ACCEPTED.value),
    "executive.task.declined": ("task", "task_id", TaskState.DECLINED.value),
    "executive.task.completed": ("task", "task_id", TaskState.COMPLETED.value),
    "executive.task.expired": ("task", "task_id", TaskState.EXPIRED.value),
    "consent.task.requested": ("task", "task_id", TaskState.PENDING.value),
    "consent.task.granted": ("task", "task_id", TaskState.AUTHORIZED.value),
    "consent.task.refused": ("task", "task_id", TaskState.CANCELLED.value),
    "consent.task.withdrawn": ("task", "task_id", TaskState.CANCELLED.value),
    # Legitimacy band events
    "legitimacy.band.decayed": ("legitimacy", "entity_id", ""),  # State in payload
    "legitimacy.band.restored": ("legitimacy", "entity_id", ""),  # State in payload
    "legitimacy.band.assessed": ("legitimacy", "entity_id", ""),  # State in payload
}


class StateTransitionValidator:
    """Validates that state machine transitions are legal.

    Uses projections to get current state, then validates against
    state machine rules. Rejects illegal transitions.

    Constitutional Constraint:
        Illegal state transitions are rejected at write-time to
        prevent ledger corruption. Policy violations (Golden Rules)
        are detected at observer-time.

    Performance:
        - State lookup: ~5ms (cached projection)
        - Transition validation: ~1ms (in-memory rules)
        - Total: ≤10ms (NFR-PERF-05)

    Attributes:
        skip_validation: If True, skip validation (admin replay only).
    """

    def __init__(
        self,
        state_projection: StateProjectionPort,
        *,
        skip_validation: bool = False,
    ) -> None:
        """Initialize the state transition validator.

        Args:
            state_projection: Port for querying aggregate states.
            skip_validation: If True, skip validation (admin replay only).
        """
        self._projection = state_projection
        self._skip_validation = skip_validation

    def _get_transition_rules(
        self,
        aggregate_type: str,
    ) -> dict[str, frozenset[str]] | None:
        """Get transition rules for an aggregate type.

        Args:
            aggregate_type: Type of aggregate.

        Returns:
            Transition rules dict, or None if no rules for this type.
        """
        if aggregate_type == "task":
            return {
                k.value: frozenset(v.value for v in vs)
                for k, vs in TASK_STATE_TRANSITIONS.items()
            }
        elif aggregate_type == "legitimacy":
            return {
                k.value: frozenset(v.value for v in vs)
                for k, vs in LEGITIMACY_BAND_TRANSITIONS.items()
            }
        return None

    def _extract_state_info(
        self,
        event: GovernanceEvent,
    ) -> tuple[str, str, str] | None:
        """Extract aggregate info from event.

        Args:
            event: The event to extract info from.

        Returns:
            Tuple of (aggregate_type, aggregate_id, new_state), or None if
            this event is not a state machine event.
        """
        mapping = EVENT_STATE_MAPPINGS.get(event.event_type)
        if not mapping:
            return None

        aggregate_type, id_field, explicit_state = mapping

        # Get aggregate ID from payload
        aggregate_id = event.payload.get(id_field)
        if not aggregate_id:
            return None

        # Get new state - either explicit or from payload
        if explicit_state:
            new_state = explicit_state
        else:
            # State is in payload (e.g., legitimacy events)
            new_state = event.payload.get("new_band") or event.payload.get("band")
            if not new_state:
                return None

        return aggregate_type, str(aggregate_id), str(new_state)

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate that the state transition is legal.

        Args:
            event: The GovernanceEvent to validate.

        Raises:
            IllegalStateTransitionError: If transition is not allowed.
        """
        if self._skip_validation:
            return

        # Extract state info from event
        state_info = self._extract_state_info(event)
        if not state_info:
            # Not a state machine event - nothing to validate
            return

        aggregate_type, aggregate_id, new_state = state_info

        # Get transition rules for this aggregate type
        rules = self._get_transition_rules(aggregate_type)
        if not rules:
            # No rules for this aggregate type - allow
            return

        # Get current state from projection
        current = await self._projection.get_current_state(aggregate_type, aggregate_id)

        if current is None:
            # New aggregate - check if new_state is a valid initial state
            # For tasks, PENDING is the only valid initial state
            # For legitimacy, FULL is the only valid initial state
            if aggregate_type == "task" and new_state != TaskState.PENDING.value:
                raise IllegalStateTransitionError(
                    event_id=event.event_id,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    current_state="(new)",
                    attempted_state=new_state,
                    allowed_states=[TaskState.PENDING.value],
                )
            if (
                aggregate_type == "legitimacy"
                and new_state != LegitimacyBand.FULL.value
            ):
                raise IllegalStateTransitionError(
                    event_id=event.event_id,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    current_state="(new)",
                    attempted_state=new_state,
                    allowed_states=[LegitimacyBand.FULL.value],
                )
            return

        current_state = current.current_state

        # Check if transition is allowed
        allowed_states = rules.get(current_state, frozenset())

        if new_state not in allowed_states:
            raise IllegalStateTransitionError(
                event_id=event.event_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                current_state=current_state,
                attempted_state=new_state,
                allowed_states=list(allowed_states),
            )

    async def is_valid_transition(
        self,
        event: GovernanceEvent,
    ) -> bool:
        """Check if a transition is valid without raising.

        Args:
            event: The event to check.

        Returns:
            True if the transition is valid, False otherwise.
        """
        try:
            await self.validate(event)
            return True
        except IllegalStateTransitionError:
            return False
