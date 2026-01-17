"""Governance State Machine Port.

This module defines the abstract protocol for the governance state machine
that enforces the 7-step canonical flow.

Per Government PRD FR-GOV-23: Governance Flow - 7 canonical steps:
King→Conclave→President→Duke/Earl→Prince→Knight→Conclave.
No step may be skipped, no role may be collapsed.

HARDENING-1: All timestamps must be provided via TimeAuthorityProtocol injection.
Factory methods require explicit timestamp parameters - no datetime.now() calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class GovernanceState(Enum):
    """States in the 7-step governance flow.

    Per PRD §6: No step may be skipped.
    """

    # Step 1: King introduces motion
    INTRODUCED = "introduced"

    # Step 2: Conclave deliberates
    DELIBERATING = "deliberating"

    # Step 2b: Conclave outcomes
    RATIFIED = "ratified"
    REJECTED = "rejected"  # Terminal
    TABLED = "tabled"  # Paused for later consideration

    # Step 3: President plans
    PLANNING = "planning"

    # Step 4: Duke/Earl execute
    EXECUTING = "executing"

    # Step 5: Prince judges
    JUDGING = "judging"

    # Step 6: Knight witnesses
    WITNESSING = "witnessing"

    # Step 7: Conclave acknowledges
    ACKNOWLEDGED = "acknowledged"  # Terminal


# Terminal states where no further transitions are allowed
TERMINAL_STATES = {GovernanceState.REJECTED, GovernanceState.ACKNOWLEDGED}

# Valid transitions in the governance flow
VALID_TRANSITIONS: list[tuple[GovernanceState, GovernanceState]] = [
    (GovernanceState.INTRODUCED, GovernanceState.DELIBERATING),
    (GovernanceState.DELIBERATING, GovernanceState.RATIFIED),
    (GovernanceState.DELIBERATING, GovernanceState.REJECTED),
    (GovernanceState.DELIBERATING, GovernanceState.TABLED),
    (GovernanceState.TABLED, GovernanceState.DELIBERATING),  # Return from tabled
    (GovernanceState.RATIFIED, GovernanceState.PLANNING),
    (GovernanceState.PLANNING, GovernanceState.EXECUTING),
    (GovernanceState.EXECUTING, GovernanceState.JUDGING),
    (GovernanceState.JUDGING, GovernanceState.WITNESSING),
    (GovernanceState.WITNESSING, GovernanceState.ACKNOWLEDGED),
]


def is_valid_transition(
    from_state: GovernanceState,
    to_state: GovernanceState,
) -> bool:
    """Check if a transition is valid.

    Args:
        from_state: Current state
        to_state: Proposed next state

    Returns:
        True if transition is valid, False otherwise
    """
    return (from_state, to_state) in VALID_TRANSITIONS


def get_valid_next_states(state: GovernanceState) -> list[GovernanceState]:
    """Get valid next states from current state.

    Args:
        state: Current state

    Returns:
        List of valid next states
    """
    return [to_state for from_state, to_state in VALID_TRANSITIONS if from_state == state]


def is_terminal_state(state: GovernanceState) -> bool:
    """Check if a state is terminal.

    Args:
        state: State to check

    Returns:
        True if terminal, False otherwise
    """
    return state in TERMINAL_STATES


@dataclass(frozen=True)
class StateTransition:
    """Record of a state transition.

    Immutable to ensure transition integrity.
    """

    transition_id: UUID
    motion_id: UUID
    from_state: GovernanceState
    to_state: GovernanceState
    triggered_by: str  # Archon ID who triggered
    transitioned_at: datetime
    witnessed_by: str | None = None  # Knight who witnessed
    reason: str | None = None

    @classmethod
    def create(
        cls,
        motion_id: UUID,
        from_state: GovernanceState,
        to_state: GovernanceState,
        triggered_by: str,
        timestamp: datetime,
        witnessed_by: str | None = None,
        reason: str | None = None,
    ) -> "StateTransition":
        """Create a new state transition.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            motion_id: Motion being transitioned
            from_state: State transitioning from
            to_state: State transitioning to
            triggered_by: Archon ID
            timestamp: Current time from TimeAuthorityProtocol
            witnessed_by: Knight who witnessed
            reason: Reason for transition

        Returns:
            New immutable StateTransition
        """
        return cls(
            transition_id=uuid4(),
            motion_id=motion_id,
            from_state=from_state,
            to_state=to_state,
            triggered_by=triggered_by,
            transitioned_at=timestamp,
            witnessed_by=witnessed_by,
            reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "transition_id": str(self.transition_id),
            "motion_id": str(self.motion_id),
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "triggered_by": self.triggered_by,
            "transitioned_at": self.transitioned_at.isoformat(),
            "witnessed_by": self.witnessed_by,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MotionStateRecord:
    """Complete state record for a motion."""

    motion_id: UUID
    current_state: GovernanceState
    history: tuple[StateTransition, ...]
    entered_state_at: datetime
    is_terminal: bool

    def time_in_state(self, current_time: datetime) -> timedelta:
        """Calculate time spent in current state.

        HARDENING-1: current_time must be provided via TimeAuthorityProtocol.

        Args:
            current_time: Current time from time_authority.now()

        Returns:
            Time spent in current state
        """
        return current_time - self.entered_state_at

    @property
    def available_transitions(self) -> list[GovernanceState]:
        """Get available next states."""
        if self.is_terminal:
            return []
        return get_valid_next_states(self.current_state)

    def to_dict(self, current_time: datetime | None = None) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Args:
            current_time: Current time for time_in_state calculation.
                         If None, time_in_state_seconds will be None.
        """
        time_in_state_seconds = (
            self.time_in_state(current_time).total_seconds()
            if current_time is not None
            else None
        )
        return {
            "motion_id": str(self.motion_id),
            "current_state": self.current_state.value,
            "history": [t.to_dict() for t in self.history],
            "entered_state_at": self.entered_state_at.isoformat(),
            "time_in_state_seconds": time_in_state_seconds,
            "is_terminal": self.is_terminal,
            "available_transitions": [s.value for s in self.available_transitions],
        }


@dataclass(frozen=True)
class TransitionRejection:
    """Record of a rejected transition attempt."""

    rejection_id: UUID
    motion_id: UUID
    current_state: GovernanceState
    attempted_state: GovernanceState
    rejected_at: datetime
    rejected_by_system: bool = True  # System rejected, not user
    reason: str = ""
    skipped_states: tuple[GovernanceState, ...] = field(default_factory=tuple)
    prd_reference: str = "FR-GOV-23"

    @classmethod
    def create(
        cls,
        motion_id: UUID,
        current_state: GovernanceState,
        attempted_state: GovernanceState,
        reason: str,
        timestamp: datetime,
        skipped_states: list[GovernanceState] | None = None,
    ) -> "TransitionRejection":
        """Create a new transition rejection.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            motion_id: Motion that was being transitioned
            current_state: Current state of motion
            attempted_state: State that was attempted
            reason: Reason for rejection
            timestamp: Current time from TimeAuthorityProtocol
            skipped_states: States that would have been skipped

        Returns:
            New immutable TransitionRejection
        """
        return cls(
            rejection_id=uuid4(),
            motion_id=motion_id,
            current_state=current_state,
            attempted_state=attempted_state,
            rejected_at=timestamp,
            reason=reason,
            skipped_states=tuple(skipped_states or []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rejection_id": str(self.rejection_id),
            "motion_id": str(self.motion_id),
            "current_state": self.current_state.value,
            "attempted_state": self.attempted_state.value,
            "rejected_at": self.rejected_at.isoformat(),
            "rejected_by_system": self.rejected_by_system,
            "reason": self.reason,
            "skipped_states": [s.value for s in self.skipped_states],
            "prd_reference": self.prd_reference,
        }


@dataclass
class TransitionRequest:
    """Request to transition a motion's state."""

    motion_id: UUID
    to_state: GovernanceState
    triggered_by: str  # Archon ID
    reason: str | None = None


@dataclass
class TransitionResult:
    """Result of a transition attempt."""

    success: bool
    transition: StateTransition | None = None
    rejection: TransitionRejection | None = None
    error: str | None = None


class SkipAttemptType(Enum):
    """Types of skip attempts per FR-GOV-23.

    Categorizes how skips are attempted for audit and response purposes.
    """

    SIMPLE_SKIP = "simple_skip"  # Normal API call attempting skip
    FORCE_SKIP = "force_skip"  # Privileged attempt to bypass
    BULK_SKIP = "bulk_skip"  # Attempting to skip multiple states


class SkipAttemptSeverity(Enum):
    """Severity levels for skip attempt violations."""

    CRITICAL = "critical"  # Must halt, cannot continue
    HIGH = "high"  # Requires escalation
    MEDIUM = "medium"  # Logged but may continue


@dataclass(frozen=True)
class SkipAttemptViolation:
    """A violation where a step skip was attempted.

    Per FR-GOV-23: No step may be skipped.
    Per CT-11: Silent failure destroys legitimacy -> all attempts recorded.
    """

    violation_id: UUID
    motion_id: UUID
    current_state: GovernanceState
    attempted_state: GovernanceState
    skipped_states: tuple[GovernanceState, ...]
    attempt_type: SkipAttemptType
    attempted_by: str  # Archon ID
    attempted_at: datetime
    source: str  # API, service, manual
    severity: SkipAttemptSeverity = SkipAttemptSeverity.CRITICAL
    rejected: bool = True
    escalated_to_conclave: bool = False
    prd_reference: str = "FR-GOV-23"

    @classmethod
    def create(
        cls,
        motion_id: UUID,
        current_state: GovernanceState,
        attempted_state: GovernanceState,
        skipped_states: list[GovernanceState],
        attempt_type: SkipAttemptType,
        attempted_by: str,
        timestamp: datetime,
        source: str = "api",
        escalate: bool = False,
    ) -> "SkipAttemptViolation":
        """Create a new skip attempt violation.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            motion_id: The motion being transitioned
            current_state: Current state of the motion
            attempted_state: State that was attempted (invalid)
            skipped_states: States that would have been skipped
            attempt_type: Type of skip attempt
            attempted_by: Archon ID who attempted
            timestamp: Current time from TimeAuthorityProtocol
            source: Source of the attempt (api, service, manual)
            escalate: Whether to escalate to Conclave

        Returns:
            New immutable SkipAttemptViolation
        """
        return cls(
            violation_id=uuid4(),
            motion_id=motion_id,
            current_state=current_state,
            attempted_state=attempted_state,
            skipped_states=tuple(skipped_states),
            attempt_type=attempt_type,
            attempted_by=attempted_by,
            attempted_at=timestamp,
            source=source,
            escalated_to_conclave=escalate,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization and audit logging."""
        return {
            "violation_id": str(self.violation_id),
            "violation_type": "STEP_SKIP_ATTEMPT",
            "motion_id": str(self.motion_id),
            "current_state": self.current_state.value,
            "attempted_state": self.attempted_state.value,
            "skipped_states": [s.value for s in self.skipped_states],
            "attempt_type": self.attempt_type.value,
            "attempted_by": self.attempted_by,
            "attempted_at": self.attempted_at.isoformat(),
            "source": self.source,
            "severity": self.severity.value,
            "rejected": self.rejected,
            "escalated_to_conclave": self.escalated_to_conclave,
            "prd_reference": self.prd_reference,
        }


@dataclass(frozen=True)
class SkipAttemptAuditEntry:
    """Audit trail entry for skip attempts.

    Per AC6: Full audit trail must be maintained.
    """

    audit_id: UUID
    violation: SkipAttemptViolation
    recorded_at: datetime
    witness_statement_id: UUID | None = None  # Knight witness reference

    @classmethod
    def create(
        cls,
        violation: SkipAttemptViolation,
        timestamp: datetime,
        witness_statement_id: UUID | None = None,
    ) -> "SkipAttemptAuditEntry":
        """Create a new audit entry.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            violation: The skip attempt violation
            timestamp: Current time from TimeAuthorityProtocol
            witness_statement_id: Optional Knight witness reference

        Returns:
            New immutable audit entry
        """
        return cls(
            audit_id=uuid4(),
            violation=violation,
            recorded_at=timestamp,
            witness_statement_id=witness_statement_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "audit_id": str(self.audit_id),
            "violation": self.violation.to_dict(),
            "recorded_at": self.recorded_at.isoformat(),
            "witness_statement_id": str(self.witness_statement_id)
            if self.witness_statement_id
            else None,
        }


class SkipAttemptError(Exception):
    """Raised when a step skip is attempted.

    Per FR-GOV-23: No step may be skipped.
    Per CT-11: Silent failure destroys legitimacy -> explicit error.
    """

    def __init__(
        self,
        violation: SkipAttemptViolation,
    ):
        self.violation = violation
        self.error_code = "STEP_SKIP_VIOLATION"
        self.prd_reference = "FR-GOV-23"
        super().__init__(
            f"Cannot skip from {violation.current_state.value} to "
            f"{violation.attempted_state.value}; must pass through "
            f"{', '.join(s.value for s in violation.skipped_states)}"
        )

    def to_error_response(self) -> dict[str, Any]:
        """Generate HTTP error response format per story requirements."""
        required_next = (
            self.violation.skipped_states[0].value
            if self.violation.skipped_states
            else None
        )
        return {
            "error_code": self.error_code,
            "prd_reference": self.prd_reference,
            "message": str(self),
            "current_state": self.violation.current_state.value,
            "attempted_state": self.violation.attempted_state.value,
            "required_next_state": required_next,
            "skipped_states": [s.value for s in self.violation.skipped_states],
            "motion_id": str(self.violation.motion_id),
            "severity": self.violation.severity.value,
        }


class ForceSkipAttemptError(SkipAttemptError):
    """Raised when a privileged user attempts to force skip.

    Per AC4: Force skip attempts are rejected regardless of privilege
    and escalated to Conclave review.
    """

    def __init__(
        self,
        violation: SkipAttemptViolation,
    ):
        super().__init__(violation)
        self.error_code = "FORCED_SKIP_ATTEMPT"
        self.escalated = True


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        motion_id: UUID,
        current_state: GovernanceState,
        attempted_state: GovernanceState,
        reason: str,
        skipped_states: list[GovernanceState] | None = None,
    ):
        self.motion_id = motion_id
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.reason = reason
        self.skipped_states = skipped_states or []
        super().__init__(
            f"Invalid transition for motion {motion_id}: "
            f"{current_state.value} → {attempted_state.value}. {reason}"
        )


class TerminalStateError(Exception):
    """Raised when a transition is attempted from a terminal state."""

    def __init__(
        self,
        motion_id: UUID,
        current_state: GovernanceState,
    ):
        self.motion_id = motion_id
        self.current_state = current_state
        super().__init__(
            f"Motion {motion_id} is in terminal state {current_state.value}. "
            "No further transitions allowed."
        )


class GovernanceStateMachineProtocol(ABC):
    """Abstract protocol for the governance state machine.

    Per Government PRD FR-GOV-23:
    - Enforces the 7-step canonical flow
    - No step may be skipped
    - No role may be collapsed
    - All transitions must be witnessed
    """

    @abstractmethod
    async def transition(
        self,
        request: TransitionRequest,
    ) -> TransitionResult:
        """Attempt to transition a motion to a new state.

        Per FR-GOV-23: Validates that the transition follows the canonical flow.

        Args:
            request: Transition request with motion_id and target state

        Returns:
            TransitionResult with success/failure and details

        Note:
            Invalid transitions are rejected, not raised.
            Callers should check TransitionResult.success.
        """
        ...

    @abstractmethod
    async def enforce_transition(
        self,
        request: TransitionRequest,
    ) -> StateTransition:
        """Transition a motion, raising on invalid.

        Per FR-GOV-23: Same as transition() but raises on invalid.

        Args:
            request: Transition request

        Returns:
            StateTransition if successful

        Raises:
            InvalidTransitionError: If transition is invalid
            TerminalStateError: If motion is in terminal state
        """
        ...

    @abstractmethod
    async def get_current_state(
        self,
        motion_id: UUID,
    ) -> GovernanceState | None:
        """Get the current state of a motion.

        Args:
            motion_id: UUID of the motion

        Returns:
            Current GovernanceState, or None if motion not found
        """
        ...

    @abstractmethod
    async def get_state_record(
        self,
        motion_id: UUID,
    ) -> MotionStateRecord | None:
        """Get the full state record for a motion.

        Args:
            motion_id: UUID of the motion

        Returns:
            MotionStateRecord with history, or None if not found
        """
        ...

    @abstractmethod
    async def get_available_transitions(
        self,
        motion_id: UUID,
    ) -> list[GovernanceState]:
        """Get valid next states for a motion.

        Args:
            motion_id: UUID of the motion

        Returns:
            List of valid next states (empty if terminal)
        """
        ...

    @abstractmethod
    async def can_transition(
        self,
        motion_id: UUID,
        to_state: GovernanceState,
    ) -> bool:
        """Check if a transition is valid without attempting it.

        Args:
            motion_id: UUID of the motion
            to_state: Proposed target state

        Returns:
            True if transition would be valid, False otherwise
        """
        ...

    @abstractmethod
    async def initialize_motion(
        self,
        motion_id: UUID,
        introduced_by: str,
    ) -> TransitionResult:
        """Initialize a new motion in INTRODUCED state.

        Args:
            motion_id: UUID of the new motion
            introduced_by: King Archon ID who introduced it

        Returns:
            TransitionResult for the initialization
        """
        ...

    @abstractmethod
    async def get_motions_by_state(
        self,
        state: GovernanceState,
    ) -> list[UUID]:
        """Get all motions currently in a given state.

        Args:
            state: State to filter by

        Returns:
            List of motion UUIDs in that state
        """
        ...

    @abstractmethod
    async def get_transition_history(
        self,
        motion_id: UUID,
    ) -> list[StateTransition]:
        """Get the transition history for a motion.

        Args:
            motion_id: UUID of the motion

        Returns:
            List of transitions in chronological order
        """
        ...
