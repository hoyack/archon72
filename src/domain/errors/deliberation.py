"""Deliberation domain errors (Story 2A.1, FR-11.1, FR-11.4).

This module defines domain-specific exceptions for the Three Fates
deliberation system. All errors inherit from ConclaveError and include
constitutional references where applicable.

Constitutional Constraints:
- D7: All errors include trace_id and constitutional references
- CT-14: Silence is expensive - errors must be clear and actionable
- AT-6: Deliberation is collective judgment - consensus errors are domain errors
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.exceptions import ConclaveError

if TYPE_CHECKING:
    from src.domain.models.deliberation_session import DeliberationPhase


class DeliberationError(ConclaveError):
    """Base class for deliberation-related errors."""

    pass


class InvalidPhaseTransitionError(DeliberationError):
    """Raised when attempting invalid phase transition (FR-11.4).

    The deliberation protocol requires strict phase progression:
    ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE -> COMPLETE

    Skipping phases or going backwards is not permitted.

    Attributes:
        from_phase: Current phase.
        to_phase: Attempted target phase.
        expected_phase: The expected next phase in sequence.
    """

    def __init__(
        self,
        from_phase: DeliberationPhase,
        to_phase: DeliberationPhase,
        expected_phase: DeliberationPhase | None,
    ) -> None:
        """Initialize InvalidPhaseTransitionError.

        Args:
            from_phase: Current phase.
            to_phase: Attempted target phase.
            expected_phase: The expected next phase (None if terminal).
        """
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.expected_phase = expected_phase

        expected_str = expected_phase.value if expected_phase else "None (terminal)"
        message = (
            f"Invalid phase transition from {from_phase.value} to {to_phase.value}. "
            f"Expected next phase: {expected_str}. "
            "Deliberation protocol requires strict sequence: "
            "ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE -> COMPLETE (FR-11.4)"
        )
        super().__init__(message)


class ConsensusNotReachedError(DeliberationError):
    """Raised when setting outcome without 2-of-3 consensus (AT-6).

    Constitutional Truth AT-6: "Deliberation is collective judgment,
    not unilateral decision." This requires 2-of-3 supermajority
    for any outcome to be valid.

    Attributes:
        votes_received: Number of votes received.
        votes_required: Number of votes required.
        message: Descriptive error message.
    """

    def __init__(
        self,
        message: str,
        votes_received: int,
        votes_required: int,
    ) -> None:
        """Initialize ConsensusNotReachedError.

        Args:
            message: Descriptive error message.
            votes_received: Number of votes received.
            votes_required: Number of votes required for consensus.
        """
        self.votes_received = votes_received
        self.votes_required = votes_required

        full_message = (
            f"{message} "
            f"(votes_received={votes_received}, votes_required={votes_required}). "
            "Constitutional Truth AT-6: Deliberation is collective judgment."
        )
        super().__init__(full_message)


class SessionAlreadyCompleteError(DeliberationError):
    """Raised when modifying a completed session (AC-6).

    Once a deliberation session reaches COMPLETE phase, it becomes
    immutable. This preserves the integrity of the witnessed record.

    Attributes:
        session_id: ID of the completed session.
        message: Descriptive error message.
    """

    def __init__(
        self,
        session_id: str,
        message: str,
    ) -> None:
        """Initialize SessionAlreadyCompleteError.

        Args:
            session_id: ID of the completed session.
            message: Descriptive error message.
        """
        self.session_id = session_id

        full_message = (
            f"Session {session_id}: {message}. "
            "Completed sessions are immutable to preserve witness integrity (CT-12)."
        )
        super().__init__(full_message)


class InvalidArchonAssignmentError(DeliberationError):
    """Raised when archon assignment violates invariants (FR-11.1).

    FR-11.1 requires exactly 3 Marquis-rank Archons to be assigned
    to each deliberation. This error is raised when:
    - Fewer or more than 3 archons are assigned
    - Duplicate archon IDs are provided
    - An archon not in the assigned set attempts to vote

    Attributes:
        message: Descriptive error message.
        archon_count: Number of archons provided (if applicable).
    """

    def __init__(
        self,
        message: str,
        archon_count: int | None = None,
    ) -> None:
        """Initialize InvalidArchonAssignmentError.

        Args:
            message: Descriptive error message.
            archon_count: Number of archons provided.
        """
        self.archon_count = archon_count

        full_message = (
            f"{message}. FR-11.1: System SHALL assign exactly 3 Marquis-rank Archons."
        )
        super().__init__(full_message)


class InvalidPetitionStateError(DeliberationError):
    """Raised when petition is not in expected state for assignment (AC-4).

    Archon assignment requires the petition to be in RECEIVED state.
    This error is raised when attempting to assign archons to a petition
    that has already begun deliberation or reached a terminal fate.

    Attributes:
        petition_id: ID of the petition.
        current_state: Current state of the petition.
        expected_state: Expected state for the operation.
    """

    def __init__(
        self,
        petition_id: str,
        current_state: str,
        expected_state: str = "RECEIVED",
    ) -> None:
        """Initialize InvalidPetitionStateError.

        Args:
            petition_id: ID of the petition.
            current_state: Current state of the petition.
            expected_state: Expected state for the operation.
        """
        self.petition_id = petition_id
        self.current_state = current_state
        self.expected_state = expected_state

        message = (
            f"Petition {petition_id} is in state {current_state}, "
            f"expected {expected_state}. "
            "FR-11.2: Archon assignment initiates when petition enters RECEIVED state."
        )
        super().__init__(message)


class SessionAlreadyExistsError(DeliberationError):
    """Raised when trying to create duplicate session for petition.

    Each petition can only have one deliberation session. This error
    indicates idempotency - the existing session should be returned
    instead of creating a new one.

    Attributes:
        petition_id: ID of the petition.
        session_id: ID of the existing session.
    """

    def __init__(
        self,
        petition_id: str,
        session_id: str,
    ) -> None:
        """Initialize SessionAlreadyExistsError.

        Args:
            petition_id: ID of the petition.
            session_id: ID of the existing session.
        """
        self.petition_id = petition_id
        self.session_id = session_id

        message = (
            f"Deliberation session {session_id} already exists for "
            f"petition {petition_id}. Use idempotent return (AC-3)."
        )
        super().__init__(message)


class SessionNotFoundError(DeliberationError):
    """Raised when a session cannot be found (Story 2B.2, FR-11.9).

    This error is raised when attempting to operate on a session that
    does not exist, such as during timeout handling when the session
    has been deleted or was never created.

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy - missing session must error
    - FR-11.9: Timeout handling requires valid session reference

    Attributes:
        session_id: ID of the session that was not found.
        message: Descriptive error message.
    """

    def __init__(
        self,
        session_id: str,
        message: str,
    ) -> None:
        """Initialize SessionNotFoundError.

        Args:
            session_id: ID of the session that was not found.
            message: Descriptive error message.
        """
        self.session_id = session_id

        full_message = (
            f"Session {session_id}: {message}. "
            "CT-11: Silent failure destroys legitimacy."
        )
        super().__init__(full_message)


class ArchonPoolExhaustedError(DeliberationError):
    """Raised when archon pool has fewer than required archons.

    FR-11.1 requires exactly 3 Archons. If the pool has fewer,
    deliberation cannot proceed.

    Attributes:
        available_count: Number of archons available in pool.
        required_count: Number of archons required (3).
    """

    def __init__(
        self,
        available_count: int,
        required_count: int = 3,
    ) -> None:
        """Initialize ArchonPoolExhaustedError.

        Args:
            available_count: Number of archons available.
            required_count: Number of archons required.
        """
        self.available_count = available_count
        self.required_count = required_count

        message = (
            f"Archon pool has {available_count} archons, "
            f"but {required_count} are required. "
            "FR-11.1: System SHALL assign exactly 3 Marquis-rank Archons."
        )
        super().__init__(message)


class PhaseExecutionError(DeliberationError):
    """Raised when phase execution fails (Story 2A.5, NFR-10.2).

    Phase execution can fail due to:
    - Agent invocation timeout (NFR-10.2: 30s per archon)
    - Agent invocation error (LLM failure)
    - Transcript generation failure

    Attributes:
        phase: The phase that failed.
        archon_id: Optional ID of the archon that failed.
        reason: Description of why execution failed.
    """

    def __init__(
        self,
        phase: DeliberationPhase,
        reason: str,
        archon_id: UUID | None = None,
    ) -> None:
        """Initialize PhaseExecutionError.

        Args:
            phase: The phase that failed.
            reason: Description of why execution failed.
            archon_id: Optional ID of the archon that failed.
        """
        self.phase = phase
        self.reason = reason
        self.archon_id = archon_id

        archon_info = f" (archon {archon_id})" if archon_id else ""
        message = (
            f"Phase {phase.value} execution failed{archon_info}: {reason}. "
            "NFR-10.2: Individual Archon response time p95 < 30 seconds."
        )
        super().__init__(message)


class PetitionSessionMismatchError(DeliberationError):
    """Raised when session.petition_id doesn't match petition.id (Story 2A.3).

    Context package building requires the session to be associated with
    the provided petition. This error prevents building packages with
    mismatched petition/session pairs.

    Attributes:
        petition_id: ID of the petition provided.
        session_petition_id: ID of the petition in the session.
    """

    def __init__(
        self,
        petition_id: UUID,
        session_petition_id: UUID,
    ) -> None:
        """Initialize PetitionSessionMismatchError.

        Args:
            petition_id: ID of the petition provided.
            session_petition_id: ID of the petition in the session.
        """
        self.petition_id = petition_id
        self.session_petition_id = session_petition_id

        message = (
            f"Petition ID mismatch: provided petition {petition_id} "
            f"but session references petition {session_petition_id}. "
            "Context package requires matching petition and session."
        )
        super().__init__(message)


class IncompleteWitnessChainError(DeliberationError):
    """Raised when witness chain is incomplete for disposition emission (Story 2A.8).

    Disposition emission requires all 4 phase witnesses to be recorded
    before the outcome can be finalized and routed.

    Constitutional Constraints:
    - CT-14: Every claim terminates in witnessed fate
    - CT-12: All transitions must be witnessed
    - NFR-10.4: Witness completeness - 100% utterances witnessed

    Attributes:
        session_id: ID of the deliberation session.
        missing_phases: List of phases missing witnesses.
    """

    def __init__(
        self,
        session_id: UUID,
        missing_phases: list[DeliberationPhase],
    ) -> None:
        """Initialize IncompleteWitnessChainError.

        Args:
            session_id: ID of the deliberation session.
            missing_phases: List of phases missing witnesses.
        """
        self.session_id = session_id
        self.missing_phases = missing_phases

        phases_str = ", ".join(p.value for p in missing_phases)
        message = (
            f"Incomplete witness chain for session {session_id}: "
            f"missing witnesses for phases [{phases_str}]. "
            "CT-14: Every claim must terminate in witnessed fate. "
            "NFR-10.4: 100% witness completeness required."
        )
        super().__init__(message)


class PipelineRoutingError(DeliberationError):
    """Raised when pipeline routing fails (Story 2A.8, FR-11.11).

    Pipeline routing can fail due to:
    - Invalid outcome type
    - Queue unavailable
    - Pipeline configuration error

    Constitutional Constraints:
    - FR-11.11: System SHALL route to appropriate pipeline
    - CT-14: Claims must terminate in witnessed fate

    Attributes:
        petition_id: ID of the petition being routed.
        pipeline: Target pipeline that failed.
        reason: Description of why routing failed.
    """

    def __init__(
        self,
        petition_id: UUID,
        pipeline: str,
        reason: str,
    ) -> None:
        """Initialize PipelineRoutingError.

        Args:
            petition_id: ID of the petition being routed.
            pipeline: Target pipeline that failed.
            reason: Description of why routing failed.
        """
        self.petition_id = petition_id
        self.pipeline = pipeline
        self.reason = reason

        message = (
            f"Pipeline routing failed for petition {petition_id} "
            f"to pipeline {pipeline}: {reason}. "
            "FR-11.11: System SHALL route to appropriate pipeline."
        )
        super().__init__(message)


class DeliberationPendingError(DeliberationError):
    """Raised when deliberation has not yet completed (Story 7.4, AC-3).

    Deliberation summary is only available after deliberation has completed.
    This error indicates the petition is still in RECEIVED state or deliberation
    is actively in progress.

    Constitutional Constraints:
    - FR-7.4: System SHALL provide deliberation summary after completion
    - CT-14: Every claim terminates in witnessed fate - but not yet for this one

    Attributes:
        petition_id: ID of the petition.
        current_state: Current state of the petition.
    """

    def __init__(
        self,
        petition_id: str,
        current_state: str,
    ) -> None:
        """Initialize DeliberationPendingError.

        Args:
            petition_id: ID of the petition.
            current_state: Current state of the petition.
        """
        self.petition_id = petition_id
        self.current_state = current_state

        message = (
            f"Petition {petition_id} has not yet completed deliberation "
            f"(current state: {current_state}). "
            "FR-7.4: Deliberation summary available only after fate assignment."
        )
        super().__init__(message)
