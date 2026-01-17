"""Governance State Machine Adapter (Epic 8).

This module implements the GovernanceStateMachineProtocol for enforcing
the 7-step canonical governance flow.

Per Government PRD FR-GOV-23: Governance Flow - 7 canonical steps:
King→Conclave→President→Duke/Earl→Prince→Knight→Conclave.
No step may be skipped, no role may be collapsed.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.governance_state_machine import (
    ForceSkipAttemptError,
    GovernanceState,
    GovernanceStateMachineProtocol,
    InvalidTransitionError,
    MotionStateRecord,
    SkipAttemptAuditEntry,
    SkipAttemptError,
    SkipAttemptType,
    SkipAttemptViolation,
    StateTransition,
    TERMINAL_STATES,
    TerminalStateError,
    TransitionRejection,
    TransitionRequest,
    TransitionResult,
    get_valid_next_states,
    is_terminal_state,
    is_valid_transition,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatementType,
)

logger = get_logger(__name__)


class GovernanceStateMachineAdapter(GovernanceStateMachineProtocol):
    """Implementation of the 7-step governance state machine.

    This adapter enforces the canonical governance flow per FR-GOV-23:
    1. INTRODUCED (King introduces motion)
    2. DELIBERATING (Conclave deliberates)
    3. RATIFIED/REJECTED/TABLED (Conclave decision)
    4. PLANNING (President plans execution)
    5. EXECUTING (Duke/Earl execute)
    6. JUDGING (Prince judges compliance)
    7. WITNESSING (Knight witnesses)
    8. ACKNOWLEDGED (Conclave acknowledges completion)

    No step may be skipped. All transitions are witnessed.
    """

    def __init__(
        self,
        knight_witness: KnightWitnessProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the Governance State Machine.

        Args:
            knight_witness: Knight witness for recording transitions (optional)
            verbose: Enable verbose logging
        """
        self._knight_witness = knight_witness
        self._verbose = verbose

        # In-memory storage (would be repository in production)
        self._motion_states: dict[UUID, GovernanceState] = {}
        self._transition_history: dict[UUID, list[StateTransition]] = {}
        self._state_entered_at: dict[UUID, datetime] = {}

        # Skip attempt audit trail (per AC6)
        self._skip_attempt_audit: list[SkipAttemptAuditEntry] = []

        if self._verbose:
            logger.debug("governance_state_machine_initialized")

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
        if self._verbose:
            logger.debug(
                "transition_requested",
                motion_id=str(request.motion_id),
                to_state=request.to_state.value,
                triggered_by=request.triggered_by,
            )

        # Get current state
        current_state = self._motion_states.get(request.motion_id)
        if current_state is None:
            return TransitionResult(
                success=False,
                error=f"Motion {request.motion_id} not found",
            )

        # Check if current state is terminal
        if is_terminal_state(current_state):
            rejection = TransitionRejection.create(
                motion_id=request.motion_id,
                current_state=current_state,
                attempted_state=request.to_state,
                reason=f"Motion is in terminal state {current_state.value}",
            )

            # Witness the rejection
            await self._witness_rejection(request, rejection)

            return TransitionResult(
                success=False,
                rejection=rejection,
                error=f"Motion is in terminal state {current_state.value}",
            )

        # Check if transition is valid (AC1: Skip Detection)
        if not is_valid_transition(current_state, request.to_state):
            # Calculate skipped states
            skipped_states = self._find_skipped_states(current_state, request.to_state)

            # Determine skip attempt type (AC2, AC3)
            attempt_type = self._classify_skip_attempt(skipped_states)

            # Create skip attempt violation (AC3: Violation Recording)
            violation = SkipAttemptViolation.create(
                motion_id=request.motion_id,
                current_state=current_state,
                attempted_state=request.to_state,
                skipped_states=skipped_states,
                attempt_type=attempt_type,
                attempted_by=request.triggered_by,
                source="api",
                escalate=False,
            )

            # Record in audit trail (AC6)
            await self._record_skip_attempt(violation)

            rejection = TransitionRejection.create(
                motion_id=request.motion_id,
                current_state=current_state,
                attempted_state=request.to_state,
                reason=f"Invalid transition: {current_state.value} → {request.to_state.value}. "
                       f"No step may be skipped per FR-GOV-23.",
                skipped_states=skipped_states,
            )

            # Witness the rejection - this is a skip attempt
            await self._witness_rejection(request, rejection, violation)

            return TransitionResult(
                success=False,
                rejection=rejection,
                error=f"Invalid transition from {current_state.value} to {request.to_state.value}",
            )

        # Transition is valid - execute it
        transition = StateTransition.create(
            motion_id=request.motion_id,
            from_state=current_state,
            to_state=request.to_state,
            triggered_by=request.triggered_by,
            reason=request.reason,
        )

        # Update state
        self._motion_states[request.motion_id] = request.to_state
        self._state_entered_at[request.motion_id] = datetime.now(timezone.utc)

        # Record history
        if request.motion_id not in self._transition_history:
            self._transition_history[request.motion_id] = []
        self._transition_history[request.motion_id].append(transition)

        # Witness the successful transition
        await self._witness_transition(transition)

        if self._verbose:
            logger.info(
                "transition_completed",
                motion_id=str(request.motion_id),
                from_state=current_state.value,
                to_state=request.to_state.value,
                triggered_by=request.triggered_by,
            )

        return TransitionResult(
            success=True,
            transition=transition,
        )

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
        # Get current state
        current_state = self._motion_states.get(request.motion_id)
        if current_state is None:
            raise InvalidTransitionError(
                motion_id=request.motion_id,
                current_state=GovernanceState.INTRODUCED,  # Placeholder
                attempted_state=request.to_state,
                reason=f"Motion {request.motion_id} not found",
            )

        # Check terminal state
        if is_terminal_state(current_state):
            raise TerminalStateError(
                motion_id=request.motion_id,
                current_state=current_state,
            )

        # Check valid transition
        if not is_valid_transition(current_state, request.to_state):
            skipped_states = self._find_skipped_states(current_state, request.to_state)
            raise InvalidTransitionError(
                motion_id=request.motion_id,
                current_state=current_state,
                attempted_state=request.to_state,
                reason=f"Invalid transition. No step may be skipped per FR-GOV-23.",
                skipped_states=skipped_states,
            )

        # Perform transition (reuse transition method logic)
        result = await self.transition(request)
        if not result.success or not result.transition:
            raise InvalidTransitionError(
                motion_id=request.motion_id,
                current_state=current_state,
                attempted_state=request.to_state,
                reason=result.error or "Unknown error",
            )

        return result.transition

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
        return self._motion_states.get(motion_id)

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
        current_state = self._motion_states.get(motion_id)
        if current_state is None:
            return None

        entered_at = self._state_entered_at.get(
            motion_id, datetime.now(timezone.utc)
        )
        history = tuple(self._transition_history.get(motion_id, []))

        return MotionStateRecord(
            motion_id=motion_id,
            current_state=current_state,
            history=history,
            entered_state_at=entered_at,
            is_terminal=is_terminal_state(current_state),
        )

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
        current_state = self._motion_states.get(motion_id)
        if current_state is None:
            return []

        if is_terminal_state(current_state):
            return []

        return get_valid_next_states(current_state)

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
        current_state = self._motion_states.get(motion_id)
        if current_state is None:
            return False

        if is_terminal_state(current_state):
            return False

        return is_valid_transition(current_state, to_state)

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
        if self._verbose:
            logger.debug(
                "motion_initialization_requested",
                motion_id=str(motion_id),
                introduced_by=introduced_by,
            )

        # Check if motion already exists
        if motion_id in self._motion_states:
            return TransitionResult(
                success=False,
                error=f"Motion {motion_id} already exists",
            )

        # Initialize in INTRODUCED state
        self._motion_states[motion_id] = GovernanceState.INTRODUCED
        self._state_entered_at[motion_id] = datetime.now(timezone.utc)
        self._transition_history[motion_id] = []

        # Create initial transition record
        transition = StateTransition.create(
            motion_id=motion_id,
            from_state=GovernanceState.INTRODUCED,  # Self-transition for initialization
            to_state=GovernanceState.INTRODUCED,
            triggered_by=introduced_by,
            reason="Motion introduced",
        )

        self._transition_history[motion_id].append(transition)

        # Witness the initialization
        await self._witness_transition(transition)

        if self._verbose:
            logger.info(
                "motion_initialized",
                motion_id=str(motion_id),
                introduced_by=introduced_by,
            )

        return TransitionResult(
            success=True,
            transition=transition,
        )

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
        return [
            motion_id
            for motion_id, current_state in self._motion_states.items()
            if current_state == state
        ]

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
        return self._transition_history.get(motion_id, [])

    async def force_transition(
        self,
        request: TransitionRequest,
    ) -> TransitionResult:
        """Attempt to force a transition (privileged operation).

        Per AC4: Force skip attempts are rejected regardless of privilege
        and escalated to Conclave review.

        Args:
            request: Transition request

        Returns:
            TransitionResult (always failure for skip attempts)

        Raises:
            ForceSkipAttemptError: If force skip is attempted
        """
        if self._verbose:
            logger.warning(
                "force_transition_attempted",
                motion_id=str(request.motion_id),
                to_state=request.to_state.value,
                triggered_by=request.triggered_by,
            )

        # Get current state
        current_state = self._motion_states.get(request.motion_id)
        if current_state is None:
            return TransitionResult(
                success=False,
                error=f"Motion {request.motion_id} not found",
            )

        # If valid transition, just execute normally
        if is_valid_transition(current_state, request.to_state):
            return await self.transition(request)

        # Force skip attempt detected (AC4)
        skipped_states = self._find_skipped_states(current_state, request.to_state)

        # Create violation with FORCE_SKIP type and escalation
        violation = SkipAttemptViolation.create(
            motion_id=request.motion_id,
            current_state=current_state,
            attempted_state=request.to_state,
            skipped_states=skipped_states,
            attempt_type=SkipAttemptType.FORCE_SKIP,
            attempted_by=request.triggered_by,
            source="force_api",
            escalate=True,  # Escalate to Conclave per AC4
        )

        # Record in audit trail
        await self._record_skip_attempt(violation)

        # Witness as violation
        rejection = TransitionRejection.create(
            motion_id=request.motion_id,
            current_state=current_state,
            attempted_state=request.to_state,
            reason=f"FORCED_SKIP_ATTEMPT: {current_state.value} → {request.to_state.value}. "
                   f"Rejected and escalated to Conclave per AC4.",
            skipped_states=skipped_states,
        )

        await self._witness_rejection(request, rejection, violation)

        logger.critical(
            "force_skip_rejected_and_escalated",
            motion_id=str(request.motion_id),
            current_state=current_state.value,
            attempted_state=request.to_state.value,
            skipped_states=[s.value for s in skipped_states],
            triggered_by=request.triggered_by,
            violation_id=str(violation.violation_id),
        )

        # Raise ForceSkipAttemptError per AC4
        raise ForceSkipAttemptError(violation)

    async def validate_transition(
        self,
        motion_id: UUID,
        to_state: GovernanceState,
    ) -> tuple[bool, list[GovernanceState]]:
        """Validate a transition without attempting it (AC5: API-Level Enforcement).

        Args:
            motion_id: UUID of the motion
            to_state: Proposed target state

        Returns:
            Tuple of (is_valid, skipped_states_if_invalid)
        """
        current_state = self._motion_states.get(motion_id)
        if current_state is None:
            return False, []

        if is_terminal_state(current_state):
            return False, []

        if is_valid_transition(current_state, to_state):
            return True, []

        # Skip detected
        skipped_states = self._find_skipped_states(current_state, to_state)
        return False, skipped_states

    async def get_skip_attempts(
        self,
        motion_id: UUID | None = None,
    ) -> list[SkipAttemptAuditEntry]:
        """Get skip attempt audit entries (AC6: Audit Trail).

        Args:
            motion_id: Optional filter by motion ID

        Returns:
            List of skip attempt audit entries
        """
        if motion_id is None:
            return self._skip_attempt_audit.copy()

        return [
            entry
            for entry in self._skip_attempt_audit
            if entry.violation.motion_id == motion_id
        ]

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _classify_skip_attempt(
        self,
        skipped_states: list[GovernanceState],
    ) -> SkipAttemptType:
        """Classify the type of skip attempt.

        Args:
            skipped_states: States that would be skipped

        Returns:
            SkipAttemptType classification
        """
        if len(skipped_states) > 1:
            return SkipAttemptType.BULK_SKIP
        return SkipAttemptType.SIMPLE_SKIP

    async def _record_skip_attempt(
        self,
        violation: SkipAttemptViolation,
    ) -> SkipAttemptAuditEntry:
        """Record a skip attempt in the audit trail (AC6).

        Args:
            violation: The skip attempt violation

        Returns:
            Created audit entry
        """
        audit_entry = SkipAttemptAuditEntry.create(violation=violation)
        self._skip_attempt_audit.append(audit_entry)

        if self._verbose:
            logger.warning(
                "skip_attempt_recorded",
                violation_id=str(violation.violation_id),
                motion_id=str(violation.motion_id),
                attempt_type=violation.attempt_type.value,
                skipped_states=[s.value for s in violation.skipped_states],
                severity=violation.severity.value,
                escalated=violation.escalated_to_conclave,
            )

        return audit_entry

    def _find_skipped_states(
        self,
        from_state: GovernanceState,
        to_state: GovernanceState,
    ) -> list[GovernanceState]:
        """Find states that would be skipped in an invalid transition.

        Args:
            from_state: Current state
            to_state: Attempted target state

        Returns:
            List of states that would be skipped
        """
        # Define the canonical order
        canonical_order = [
            GovernanceState.INTRODUCED,
            GovernanceState.DELIBERATING,
            GovernanceState.RATIFIED,
            GovernanceState.PLANNING,
            GovernanceState.EXECUTING,
            GovernanceState.JUDGING,
            GovernanceState.WITNESSING,
            GovernanceState.ACKNOWLEDGED,
        ]

        try:
            from_idx = canonical_order.index(from_state)
            to_idx = canonical_order.index(to_state)

            if to_idx > from_idx + 1:
                return canonical_order[from_idx + 1:to_idx]
        except ValueError:
            pass

        return []

    async def _witness_transition(
        self,
        transition: StateTransition,
    ) -> None:
        """Witness a successful state transition.

        Args:
            transition: The transition to witness
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            session_id="governance_state_machine",
            statement_type=WitnessStatementType.OBSERVATION,
            trigger_source="governance_state_machine_adapter",
        )

        await self._knight_witness.witness_observation(
            observation={
                "event": "state_transition",
                "motion_id": str(transition.motion_id),
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "triggered_by": transition.triggered_by,
                "transition_id": str(transition.transition_id),
            },
            context=context,
        )

    async def _witness_rejection(
        self,
        request: TransitionRequest,
        rejection: TransitionRejection,
        skip_violation: SkipAttemptViolation | None = None,
    ) -> None:
        """Witness a rejected transition attempt.

        Per FR-GOV-23: All skip attempts must be witnessed.
        Per AC3: Violation recording with full details.

        Args:
            request: The original transition request
            rejection: The rejection record
            skip_violation: Optional SkipAttemptViolation for enhanced tracking
        """
        if not self._knight_witness:
            if self._verbose:
                logger.warning(
                    "rejection_not_witnessed_no_knight",
                    motion_id=str(request.motion_id),
                    attempted_state=request.to_state.value,
                )
            return

        # Build violation type based on skip_violation if available
        if skip_violation:
            violation_type = f"STEP_SKIP_ATTEMPT:{skip_violation.attempt_type.value}"
        else:
            violation_type = "skip_attempt" if rejection.skipped_states else "invalid_transition"

        # Build evidence with enhanced details per AC3
        evidence: dict[str, Any] = {
            "motion_id": str(request.motion_id),
            "current_state": rejection.current_state.value,
            "attempted_state": rejection.attempted_state.value,
            "skipped_states": [s.value for s in rejection.skipped_states],
        }

        # Add skip violation details if available
        if skip_violation:
            evidence["violation_id"] = str(skip_violation.violation_id)
            evidence["attempt_type"] = skip_violation.attempt_type.value
            evidence["severity"] = skip_violation.severity.value
            evidence["source"] = skip_violation.source
            evidence["escalated_to_conclave"] = skip_violation.escalated_to_conclave
            evidence["attempted_at"] = skip_violation.attempted_at.isoformat()

        violation = ViolationRecord(
            archon_id=request.triggered_by,
            violation_type=violation_type,
            description=rejection.reason,
            prd_reference=rejection.prd_reference,
            evidence=evidence,
        )

        context = ObservationContext(
            session_id="governance_state_machine",
            statement_type=WitnessStatementType.VIOLATION,
            trigger_source="governance_state_machine_adapter",
        )

        await self._knight_witness.witness_violation(
            violation=violation,
            context=context,
        )
