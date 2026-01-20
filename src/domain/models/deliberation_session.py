"""Deliberation session domain model (Story 2A.1, FR-11.1, FR-11.4, Story 2B.2, 2B.3, 2B.4).

This module defines the DeliberationSession aggregate for the Three Fates
mini-Conclave deliberation system. A deliberation session tracks the
structured protocol through which 3 Marquis-rank Archons assess a petition.

Constitutional Constraints:
- CT-14: Silence is expensive - every claim terminates in witnessed fate
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment, not unilateral decision
- FR-11.1: System SHALL assign exactly 3 Marquis-rank Archons
- FR-11.4: Deliberation SHALL follow structured protocol
- FR-11.9: System SHALL enforce deliberation timeout with auto-ESCALATE on expiry
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority (deadlock)
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: Witness completeness - 100% utterances witnessed
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- NFR-10.6: Archon substitution latency < 10 seconds on failure (Story 2B.4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from uuid6 import uuid7

if TYPE_CHECKING:
    pass


class DeliberationPhase(Enum):
    """Phase in the deliberation protocol (FR-11.4).

    The deliberation follows a strict protocol sequence:
    ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE -> COMPLETE

    Phases:
        ASSESS: Phase 1 - Independent assessment of petition
        POSITION: Phase 2 - State preferred disposition
        CROSS_EXAMINE: Phase 3 - Challenge positions
        VOTE: Phase 4 - Cast final votes
        COMPLETE: Terminal - Deliberation finished
    """

    ASSESS = "ASSESS"
    POSITION = "POSITION"
    CROSS_EXAMINE = "CROSS_EXAMINE"
    VOTE = "VOTE"
    COMPLETE = "COMPLETE"

    def is_terminal(self) -> bool:
        """Check if this phase is the terminal phase.

        Returns:
            True if this is the COMPLETE phase, False otherwise.
        """
        return self == DeliberationPhase.COMPLETE

    def next_phase(self) -> DeliberationPhase | None:
        """Get the next phase in the protocol sequence.

        Returns:
            The next phase, or None if this is the terminal phase.
        """
        return PHASE_TRANSITION_MATRIX.get(self)


class DeliberationOutcome(Enum):
    """Possible outcomes of deliberation (Three Fates).

    These map to the terminal PetitionState values:
    - ACKNOWLEDGE -> PetitionState.ACKNOWLEDGED
    - REFER -> PetitionState.REFERRED
    - ESCALATE -> PetitionState.ESCALATED

    Outcomes:
        ACKNOWLEDGE: Petition acknowledged, no further action
        REFER: Referred to Knight for review
        ESCALATE: Escalated to King for adoption consideration
    """

    ACKNOWLEDGE = "ACKNOWLEDGE"
    REFER = "REFER"
    ESCALATE = "ESCALATE"


# Phase transition matrix (FR-11.4)
# Maps each phase to its valid next phase (strict sequence)
PHASE_TRANSITION_MATRIX: dict[DeliberationPhase, DeliberationPhase | None] = {
    DeliberationPhase.ASSESS: DeliberationPhase.POSITION,
    DeliberationPhase.POSITION: DeliberationPhase.CROSS_EXAMINE,
    DeliberationPhase.CROSS_EXAMINE: DeliberationPhase.VOTE,
    DeliberationPhase.VOTE: DeliberationPhase.COMPLETE,
    DeliberationPhase.COMPLETE: None,  # Terminal
}

# Minimum votes needed for consensus (2-of-3 supermajority)
CONSENSUS_THRESHOLD = 2

# Required number of archons per deliberation (FR-11.1)
REQUIRED_ARCHON_COUNT = 3

# Maximum deliberation rounds before deadlock (FR-11.10)
# Note: This is also in config, but kept here as a domain constant
DEFAULT_MAX_ROUNDS = 3

# Maximum substitutions allowed per session (NFR-10.6, Story 2B.4)
MAX_SUBSTITUTIONS_PER_SESSION = 1


@dataclass(frozen=True, eq=True)
class ArchonSubstitution:
    """Record of an Archon substitution within a session (Story 2B.4, AC-9).

    Tracks substitution details for audit trail and context handoff.

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy - substitutions must be recorded
    - NFR-10.6: Substitution latency < 10 seconds

    Attributes:
        failed_archon_id: Original Archon that failed.
        substitute_archon_id: Replacement Archon.
        phase_at_failure: Phase when failure occurred.
        failure_reason: Why the original failed (RESPONSE_TIMEOUT, API_ERROR, INVALID_RESPONSE).
        substituted_at: When substitution occurred (UTC).
    """

    failed_archon_id: UUID
    substitute_archon_id: UUID
    phase_at_failure: DeliberationPhase
    failure_reason: str
    substituted_at: datetime

    def __post_init__(self) -> None:
        """Validate substitution record invariants."""
        if self.failed_archon_id == self.substitute_archon_id:
            raise ValueError(
                "failed_archon_id and substitute_archon_id must be different"
            )
        valid_reasons = ("RESPONSE_TIMEOUT", "API_ERROR", "INVALID_RESPONSE")
        if self.failure_reason not in valid_reasons:
            raise ValueError(
                f"failure_reason must be one of {valid_reasons}, got '{self.failure_reason}'"
            )


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class DeliberationSession:
    """A mini-Conclave deliberation session (Story 2A.1, FR-11.1, FR-11.4, 2B.2, 2B.3, 2B.4).

    This aggregate represents a Three Fates deliberation on a single petition.
    Exactly 3 Marquis-rank Archons are assigned to deliberate following a
    structured protocol: Assess -> Position -> Cross-Examine -> Vote.

    Constitutional Constraints:
    - CT-12: Frozen dataclass ensures immutability
    - FR-11.1: assigned_archons MUST contain exactly 3 unique archon IDs
    - FR-11.4: phase progression follows strict protocol sequence
    - FR-11.9: timeout_job_id tracks scheduled timeout for auto-ESCALATE
    - FR-11.10: round_count tracks rounds for deadlock detection
    - AT-6: outcome requires 2-of-3 consensus (collective judgment)
    - HC-7: timed_out flag indicates timeout-triggered escalation
    - CT-11: is_deadlocked flag indicates deadlock-triggered escalation
    - NFR-10.6: Archon substitution tracking for failure recovery (Story 2B.4)

    Attributes:
        session_id: UUIDv7 unique identifier.
        petition_id: Foreign key to petition_submissions.
        assigned_archons: Tuple of exactly 3 archon UUIDs (ordered).
        phase: Current deliberation phase.
        phase_transcripts: Map of phase to Blake3 transcript hash.
        votes: Map of archon_id to their vote.
        outcome: Final deliberation outcome (None until resolved).
        dissent_archon_id: UUID of dissenting archon in 2-1 vote (None if unanimous).
        created_at: Session creation timestamp (UTC).
        completed_at: Completion timestamp (None until complete).
        version: Optimistic locking version for concurrent access.
        timeout_job_id: UUID of scheduled timeout job (Story 2B.2, FR-11.9).
        timeout_at: Timestamp when timeout will fire (Story 2B.2, FR-11.9).
        timed_out: True if session terminated due to timeout (HC-7).
        round_count: Current voting round (starts at 1) (Story 2B.3, FR-11.10).
        votes_by_round: Vote distributions from each round (Story 2B.3, FR-11.10).
        is_deadlocked: True if session terminated due to deadlock (Story 2B.3, CT-11).
        deadlock_reason: Reason for deadlock (e.g., DEADLOCK_MAX_ROUNDS_EXCEEDED).
        substitutions: Tuple of substitution records (Story 2B.4, AC-9).
        is_aborted: True if session was aborted due to failures (Story 2B.4, AC-7).
        abort_reason: Reason for abort (INSUFFICIENT_ARCHONS or ARCHON_POOL_EXHAUSTED).
    """

    session_id: UUID
    petition_id: UUID
    assigned_archons: tuple[UUID, UUID, UUID]
    phase: DeliberationPhase = field(default=DeliberationPhase.ASSESS)
    phase_transcripts: dict[DeliberationPhase, bytes] = field(default_factory=dict)
    votes: dict[UUID, DeliberationOutcome] = field(default_factory=dict)
    outcome: DeliberationOutcome | None = field(default=None)
    dissent_archon_id: UUID | None = field(default=None)
    created_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | None = field(default=None)
    version: int = field(default=1)
    # Timeout tracking (Story 2B.2, FR-11.9, HC-7)
    timeout_job_id: UUID | None = field(default=None)
    timeout_at: datetime | None = field(default=None)
    timed_out: bool = field(default=False)
    # Round tracking for deadlock detection (Story 2B.3, FR-11.10, CT-11)
    round_count: int = field(default=1)
    votes_by_round: tuple[dict[str, int], ...] = field(default_factory=tuple)
    is_deadlocked: bool = field(default=False)
    deadlock_reason: str | None = field(default=None)
    # Substitution tracking (Story 2B.4, NFR-10.6, AC-9)
    substitutions: tuple[ArchonSubstitution, ...] = field(default_factory=tuple)
    is_aborted: bool = field(default=False)
    abort_reason: str | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate deliberation session invariants."""
        self._validate_archons()
        self._validate_phase_state()

    def _validate_archons(self) -> None:
        """Validate archon assignment invariants (FR-11.1).

        Raises:
            InvalidArchonAssignmentError: If archon assignment violates invariants.
        """
        from src.domain.errors.deliberation import InvalidArchonAssignmentError

        # Must have exactly 3 archons
        if len(self.assigned_archons) != REQUIRED_ARCHON_COUNT:
            raise InvalidArchonAssignmentError(
                message=f"Exactly {REQUIRED_ARCHON_COUNT} archons required, got {len(self.assigned_archons)}",
                archon_count=len(self.assigned_archons),
            )

        # Check for duplicates
        archon_set = set(self.assigned_archons)
        if len(archon_set) != REQUIRED_ARCHON_COUNT:
            raise InvalidArchonAssignmentError(
                message="Duplicate archon IDs not allowed",
                archon_count=len(self.assigned_archons),
            )

    def _validate_phase_state(self) -> None:
        """Validate phase-related state consistency."""
        from src.domain.errors.deliberation import ConsensusNotReachedError

        # If outcome is set, validate consensus was achieved
        if self.outcome is not None:
            # Skip validation if outcome was forced by timeout, deadlock, or abort
            if self.timed_out or self.is_deadlocked or self.is_aborted:
                return
            if len(self.votes) != REQUIRED_ARCHON_COUNT:
                raise ConsensusNotReachedError(
                    message=f"Outcome set without all {REQUIRED_ARCHON_COUNT} votes recorded",
                    votes_received=len(self.votes),
                    votes_required=REQUIRED_ARCHON_COUNT,
                )

            # Verify consensus matches outcome
            vote_counts: dict[DeliberationOutcome, int] = {}
            for vote in self.votes.values():
                vote_counts[vote] = vote_counts.get(vote, 0) + 1

            if vote_counts.get(self.outcome, 0) < CONSENSUS_THRESHOLD:
                raise ConsensusNotReachedError(
                    message=f"Outcome {self.outcome.value} does not have {CONSENSUS_THRESHOLD}-of-{REQUIRED_ARCHON_COUNT} consensus",
                    votes_received=vote_counts.get(self.outcome, 0),
                    votes_required=CONSENSUS_THRESHOLD,
                )

        # Validate round_count is within bounds
        if self.round_count < 1:
            raise ValueError(f"round_count must be >= 1, got {self.round_count}")

    @property
    def id(self) -> UUID:
        """Backward-compatible alias for session_id."""
        return self.session_id

    @property
    def archon_ids(self) -> tuple[UUID, UUID, UUID]:
        """Backward-compatible alias for assigned_archons."""
        return self.assigned_archons

    @classmethod
    def create(
        cls,
        petition_id: UUID,
        assigned_archons: tuple[UUID, UUID, UUID] | None = None,
        archon_ids: tuple[UUID, UUID, UUID] | None = None,
        session_id: UUID | None = None,
    ) -> DeliberationSession:
        """Create a new deliberation session.

        Factory method for creating a new session with validated archons.

        Args:
            petition_id: UUID of the petition being deliberated.
            assigned_archons: Tuple of exactly 3 archon UUIDs.
            archon_ids: Backward-compatible alias for assigned_archons.
            session_id: UUIDv7 for the session.

        Returns:
            New DeliberationSession in ASSESS phase.

        Raises:
            InvalidArchonAssignmentError: If archon assignment violates invariants.
        """
        if session_id is None:
            session_id = uuid7()

        if assigned_archons is None:
            if archon_ids is None:
                raise ValueError("assigned_archons is required")
            assigned_archons = archon_ids

        return cls(
            session_id=session_id,
            petition_id=petition_id,
            assigned_archons=assigned_archons,
        )

    def with_phase(self, new_phase: DeliberationPhase) -> DeliberationSession:
        """Create new session with updated phase (FR-11.4).

        Enforces strict phase progression: ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE -> COMPLETE.

        Args:
            new_phase: The phase to transition to.

        Returns:
            New DeliberationSession with updated phase.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            InvalidPhaseTransitionError: If transition violates protocol order.
        """
        from src.domain.errors.deliberation import (
            InvalidPhaseTransitionError,
            SessionAlreadyCompleteError,
        )

        # Cannot modify completed session
        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot modify completed deliberation session",
            )

        # Validate phase progression
        expected_next = self.phase.next_phase()
        if new_phase != expected_next:
            raise InvalidPhaseTransitionError(
                from_phase=self.phase,
                to_phase=new_phase,
                expected_phase=expected_next,
            )

        # If transitioning to COMPLETE, set completed_at
        completed_at = (
            _utc_now() if new_phase == DeliberationPhase.COMPLETE else self.completed_at
        )

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=new_phase,
            phase_transcripts=dict(self.phase_transcripts),
            votes=dict(self.votes),
            outcome=self.outcome,
            dissent_archon_id=self.dissent_archon_id,
            created_at=self.created_at,
            completed_at=completed_at,
            version=self.version + 1,
            timeout_job_id=self.timeout_job_id,
            timeout_at=self.timeout_at,
            timed_out=self.timed_out,
            round_count=self.round_count,
            votes_by_round=self.votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
            substitutions=self.substitutions,
            is_aborted=self.is_aborted,
            abort_reason=self.abort_reason,
        )

    def with_transcript(
        self, phase: DeliberationPhase, transcript_hash: bytes
    ) -> DeliberationSession:
        """Create new session with phase transcript recorded.

        Phase transcripts store Blake3 hashes of deliberation content
        for witness integrity verification (NFR-10.4).

        Args:
            phase: The phase whose transcript is being recorded.
            transcript_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            New DeliberationSession with transcript recorded.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If transcript hash is not 32 bytes.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot modify completed deliberation session",
            )

        if len(transcript_hash) != 32:
            raise ValueError("Transcript hash must be 32 bytes (Blake3)")

        new_transcripts = dict(self.phase_transcripts)
        new_transcripts[phase] = transcript_hash

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=self.phase,
            phase_transcripts=new_transcripts,
            votes=dict(self.votes),
            outcome=self.outcome,
            dissent_archon_id=self.dissent_archon_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            version=self.version + 1,
            timeout_job_id=self.timeout_job_id,
            timeout_at=self.timeout_at,
            timed_out=self.timed_out,
            round_count=self.round_count,
            votes_by_round=self.votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
            substitutions=self.substitutions,
            is_aborted=self.is_aborted,
            abort_reason=self.abort_reason,
        )

    def with_votes(self, votes: dict[UUID, DeliberationOutcome]) -> DeliberationSession:
        """Create new session with votes recorded.

        All 3 assigned archons must vote. Only assigned archons can vote.

        Args:
            votes: Map of archon_id to their vote. Must have exactly 3 entries.

        Returns:
            New DeliberationSession with votes recorded.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            InvalidArchonAssignmentError: If vote is from non-assigned archon.
            ValueError: If vote count doesn't match archon count.
        """
        from src.domain.errors.deliberation import (
            InvalidArchonAssignmentError,
            SessionAlreadyCompleteError,
        )

        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot modify completed deliberation session",
            )

        # Validate vote count
        if len(votes) != REQUIRED_ARCHON_COUNT:
            raise ValueError(
                f"Exactly {REQUIRED_ARCHON_COUNT} votes required, got {len(votes)}"
            )

        # Validate all voters are assigned archons
        assigned_set = set(self.assigned_archons)
        for archon_id in votes:
            if archon_id not in assigned_set:
                raise InvalidArchonAssignmentError(
                    message=f"Archon {archon_id} is not assigned to this session",
                    archon_count=len(votes),
                )

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=self.phase,
            phase_transcripts=dict(self.phase_transcripts),
            votes=dict(votes),
            outcome=self.outcome,
            dissent_archon_id=self.dissent_archon_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            version=self.version + 1,
            timeout_job_id=self.timeout_job_id,
            timeout_at=self.timeout_at,
            timed_out=self.timed_out,
            round_count=self.round_count,
            votes_by_round=self.votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
            substitutions=self.substitutions,
            is_aborted=self.is_aborted,
            abort_reason=self.abort_reason,
        )

    def with_outcome(self) -> DeliberationSession:
        """Create new session with outcome resolved from votes (AT-6).

        Resolves 2-of-3 supermajority consensus from recorded votes.
        Automatically identifies dissenting archon in 2-1 votes.
        Transitions phase to COMPLETE.

        Returns:
            New DeliberationSession with outcome set and phase COMPLETE.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ConsensusNotReachedError: If votes don't have 2-of-3 agreement.
        """
        from src.domain.errors.deliberation import (
            ConsensusNotReachedError,
            SessionAlreadyCompleteError,
        )

        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot modify completed deliberation session",
            )

        if len(self.votes) != REQUIRED_ARCHON_COUNT:
            raise ConsensusNotReachedError(
                message=f"Cannot resolve outcome without all {REQUIRED_ARCHON_COUNT} votes",
                votes_received=len(self.votes),
                votes_required=REQUIRED_ARCHON_COUNT,
            )

        # Count votes by outcome
        vote_counts: dict[DeliberationOutcome, list[UUID]] = {}
        for archon_id, vote in self.votes.items():
            if vote not in vote_counts:
                vote_counts[vote] = []
            vote_counts[vote].append(archon_id)

        # Find outcome with 2+ votes (supermajority)
        resolved_outcome: DeliberationOutcome | None = None
        dissent_archon: UUID | None = None

        for outcome, voters in vote_counts.items():
            if len(voters) >= CONSENSUS_THRESHOLD:
                resolved_outcome = outcome
                # Find dissenter (if any)
                for other_outcome, other_voters in vote_counts.items():
                    if other_outcome != outcome and len(other_voters) == 1:
                        dissent_archon = other_voters[0]
                        break
                break

        if resolved_outcome is None:
            # This can happen if all 3 archons vote differently (shouldn't be possible with 3 outcomes)
            raise ConsensusNotReachedError(
                message="No outcome achieved 2-of-3 consensus",
                votes_received=len(self.votes),
                votes_required=CONSENSUS_THRESHOLD,
            )

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=DeliberationPhase.COMPLETE,
            phase_transcripts=dict(self.phase_transcripts),
            votes=dict(self.votes),
            outcome=resolved_outcome,
            dissent_archon_id=dissent_archon,
            created_at=self.created_at,
            completed_at=_utc_now(),
            version=self.version + 1,
            timeout_job_id=self.timeout_job_id,
            timeout_at=self.timeout_at,
            timed_out=self.timed_out,
            round_count=self.round_count,
            votes_by_round=self.votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
            substitutions=self.substitutions,
            is_aborted=self.is_aborted,
            abort_reason=self.abort_reason,
        )

    def with_timeout_scheduled(
        self,
        job_id: UUID,
        timeout_at: datetime,
    ) -> DeliberationSession:
        """Create new session with timeout job scheduled (FR-11.9, HC-7).

        Records the scheduled timeout job ID and expiry time.

        Args:
            job_id: UUID of the scheduled timeout job.
            timeout_at: When the timeout will fire (UTC, timezone-aware).

        Returns:
            New DeliberationSession with timeout tracking.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If timeout_at is not timezone-aware.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot schedule timeout on completed session",
            )

        if timeout_at.tzinfo is None:
            raise ValueError("timeout_at must be timezone-aware (UTC)")

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=self.phase,
            phase_transcripts=dict(self.phase_transcripts),
            votes=dict(self.votes),
            outcome=self.outcome,
            dissent_archon_id=self.dissent_archon_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            version=self.version + 1,
            timeout_job_id=job_id,
            timeout_at=timeout_at,
            timed_out=self.timed_out,
            round_count=self.round_count,
            votes_by_round=self.votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
            substitutions=self.substitutions,
            is_aborted=self.is_aborted,
            abort_reason=self.abort_reason,
        )

    def with_timeout_cancelled(self) -> DeliberationSession:
        """Create new session with timeout job cleared (completion path).

        Clears timeout_job_id and timeout_at when deliberation completes
        normally before the timeout fires.

        Returns:
            New DeliberationSession with timeout tracking cleared.
        """
        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=self.phase,
            phase_transcripts=dict(self.phase_transcripts),
            votes=dict(self.votes),
            outcome=self.outcome,
            dissent_archon_id=self.dissent_archon_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            version=self.version + 1,
            timeout_job_id=None,
            timeout_at=None,
            timed_out=self.timed_out,
            round_count=self.round_count,
            votes_by_round=self.votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
        )

    def with_timeout_triggered(self) -> DeliberationSession:
        """Create new session marked as timed out with auto-ESCALATE (FR-11.9, HC-7).

        Marks the session as terminated due to timeout. The outcome is set
        to ESCALATE per constitutional constraint HC-7.

        Returns:
            New DeliberationSession with timed_out=True, outcome=ESCALATE, phase=COMPLETE.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot timeout already completed session",
            )

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=DeliberationPhase.COMPLETE,  # Terminal
            phase_transcripts=dict(self.phase_transcripts),
            votes=dict(self.votes),  # Keep any votes recorded so far
            outcome=DeliberationOutcome.ESCALATE,  # HC-7: auto-ESCALATE on timeout
            dissent_archon_id=None,  # No dissent - timeout forced outcome
            created_at=self.created_at,
            completed_at=_utc_now(),
            version=self.version + 1,
            timeout_job_id=self.timeout_job_id,
            timeout_at=self.timeout_at,
            timed_out=True,
            round_count=self.round_count,
            votes_by_round=self.votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
        )

    # =========================================================================
    # Round tracking methods for deadlock detection (Story 2B.3, FR-11.10)
    # =========================================================================

    def can_retry_cross_examine(self, max_rounds: int = DEFAULT_MAX_ROUNDS) -> bool:
        """Check if another CROSS_EXAMINE round is allowed (FR-11.10).

        Args:
            max_rounds: Maximum allowed rounds before deadlock (default: 3).

        Returns:
            True if round_count < max_rounds, False otherwise.
        """
        return self.round_count < max_rounds

    def with_new_round(
        self,
        previous_vote_distribution: dict[str, int],
    ) -> DeliberationSession:
        """Return session with incremented round and phase reset to CROSS_EXAMINE.

        Called when VOTE phase results in 3-way split (no consensus).

        Args:
            previous_vote_distribution: Vote distribution from failed consensus.

        Returns:
            Session in CROSS_EXAMINE phase with incremented round_count.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If already at max rounds (should use with_deadlock_outcome instead).
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot start new round on completed session",
            )

        # Store vote distribution from this round
        new_votes_by_round = self.votes_by_round + (previous_vote_distribution,)

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=DeliberationPhase.CROSS_EXAMINE,  # Return to CROSS_EXAMINE
            phase_transcripts=dict(self.phase_transcripts),
            votes={},  # Clear votes for new round
            outcome=self.outcome,
            dissent_archon_id=self.dissent_archon_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            version=self.version + 1,
            timeout_job_id=self.timeout_job_id,
            timeout_at=self.timeout_at,
            timed_out=self.timed_out,
            round_count=self.round_count + 1,
            votes_by_round=new_votes_by_round,
            is_deadlocked=self.is_deadlocked,
            deadlock_reason=self.deadlock_reason,
        )

    def with_deadlock_outcome(
        self,
        final_vote_distribution: dict[str, int],
    ) -> DeliberationSession:
        """Return session terminated due to deadlock (FR-11.10, CT-11).

        Args:
            final_vote_distribution: Vote distribution from final failed round.

        Returns:
            Session in COMPLETE phase with ESCALATE outcome and deadlock metadata.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if self.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(self.session_id),
                message="Cannot apply deadlock outcome to completed session",
            )

        # Include final vote distribution in history
        new_votes_by_round = self.votes_by_round + (final_vote_distribution,)

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            phase=DeliberationPhase.COMPLETE,  # Terminal
            phase_transcripts=dict(self.phase_transcripts),
            votes=dict(self.votes),  # Keep any votes recorded
            outcome=DeliberationOutcome.ESCALATE,  # FR-11.10: auto-ESCALATE on deadlock
            dissent_archon_id=None,  # No dissent - deadlock forced outcome
            created_at=self.created_at,
            completed_at=_utc_now(),
            version=self.version + 1,
            timeout_job_id=self.timeout_job_id,
            timeout_at=self.timeout_at,
            timed_out=self.timed_out,
            round_count=self.round_count,
            votes_by_round=new_votes_by_round,
            is_deadlocked=True,
            deadlock_reason="DEADLOCK_MAX_ROUNDS_EXCEEDED",
        )

    @property
    def has_timeout_scheduled(self) -> bool:
        """Check if a timeout job is currently scheduled.

        Returns:
            True if timeout_job_id is set, False otherwise.
        """
        return self.timeout_job_id is not None

    @property
    def is_timed_out(self) -> bool:
        """Check if session was terminated due to timeout.

        Returns:
            True if timed_out flag is set, False otherwise.
        """
        return self.timed_out

    def is_archon_assigned(self, archon_id: UUID) -> bool:
        """Check if an archon is assigned to this session.

        Args:
            archon_id: UUID of the archon to check.

        Returns:
            True if the archon is assigned, False otherwise.
        """
        return archon_id in self.assigned_archons

    def get_archon_vote(self, archon_id: UUID) -> DeliberationOutcome | None:
        """Get an archon's vote if recorded.

        Args:
            archon_id: UUID of the archon.

        Returns:
            The archon's vote, or None if not yet recorded.
        """
        return self.votes.get(archon_id)

    def has_transcript(self, phase: DeliberationPhase) -> bool:
        """Check if transcript is recorded for a phase.

        Args:
            phase: The phase to check.

        Returns:
            True if transcript hash is recorded, False otherwise.
        """
        return phase in self.phase_transcripts
