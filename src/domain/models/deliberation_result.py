"""Deliberation result domain models (Story 2A.4, FR-11.4).

This module defines the result models for the Three Fates deliberation
protocol orchestration. PhaseResult captures individual phase outcomes,
while DeliberationResult captures the complete deliberation outcome.

Constitutional Constraints:
- CT-14: Results capture witnessed fate assignment
- AT-1: Every petition terminates in exactly one fate
- AT-6: Deliberation is collective judgment - outcome reflects consensus
- FR-11.4: Structured protocol execution tracked via phase results
- NFR-10.4: Witness completeness - transcript hashes enable verification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
)


@dataclass(frozen=True, eq=True)
class PhaseResult:
    """Result of a single deliberation phase execution (Story 2A.4, FR-11.4).

    Captures the transcript and metadata for each phase of the deliberation
    protocol (ASSESS, POSITION, CROSS_EXAMINE, VOTE). Phase results are
    immutable to preserve witness integrity.

    Constitutional Constraints:
    - CT-12: transcript_hash enables witness verification
    - NFR-10.4: Complete transcript captured for each phase

    Attributes:
        phase: The phase that was executed.
        transcript: Full text transcript of the phase.
        transcript_hash: Blake3 hash of transcript (32 bytes).
        participants: Ordered tuple of participating archon IDs.
        started_at: Phase start timestamp (UTC).
        completed_at: Phase completion timestamp (UTC).
        phase_metadata: Phase-specific metadata dict.

    Example:
        >>> result = PhaseResult(
        ...     phase=DeliberationPhase.ASSESS,
        ...     transcript="Archon 1 assessment...",
        ...     transcript_hash=blake3_hash,
        ...     participants=(archon1_id, archon2_id, archon3_id),
        ...     started_at=start_time,
        ...     completed_at=end_time,
        ... )
        >>> assert result.duration_ms > 0
    """

    phase: DeliberationPhase
    transcript: str
    transcript_hash: bytes
    participants: tuple[UUID, ...]
    started_at: datetime
    completed_at: datetime
    phase_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate phase result invariants."""
        # Validate transcript hash length (Blake3 = 32 bytes)
        if len(self.transcript_hash) != 32:
            raise ValueError(
                f"transcript_hash must be 32 bytes (Blake3), got {len(self.transcript_hash)}"
            )

        # Validate timestamps
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")

        # Validate participants
        if len(self.participants) == 0:
            raise ValueError("At least one participant required")

        # Check for duplicate participants
        if len(set(self.participants)) != len(self.participants):
            raise ValueError("Duplicate participant IDs not allowed")

    @property
    def duration_ms(self) -> int:
        """Get phase duration in milliseconds.

        Returns:
            Duration of the phase in milliseconds.
        """
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key.

        Args:
            key: Metadata key.
            default: Default value if key not found.

        Returns:
            Metadata value or default.
        """
        return self.phase_metadata.get(key, default)


@dataclass(frozen=True, eq=True)
class DeliberationResult:
    """Complete result of a deliberation session (Story 2A.4, FR-11.4, FR-11.5).

    Captures the outcome and all phase results for a completed Three Fates
    deliberation. The result is immutable to preserve witness integrity.

    Constitutional Constraints:
    - AT-1: outcome is one of the Five Fates
    - AT-6: outcome reflects 2-of-3 consensus (collective judgment)
    - CT-12: phase_results contain transcript hashes for witness verification
    - FR-11.5: outcome requires supermajority consensus

    Attributes:
        session_id: UUID of the deliberation session.
        petition_id: UUID of the petition deliberated.
        outcome: The resolved outcome (ACKNOWLEDGE, REFER, ESCALATE, DEFER, NO_RESPONSE).
        votes: Map of archon_id to their final vote.
        dissent_archon_id: UUID of dissenting archon (if 2-1 vote, else None).
        phase_results: Ordered tuple of all phase results.
        started_at: Deliberation start timestamp (UTC).
        completed_at: Deliberation completion timestamp (UTC).
        is_aborted: True if deliberation was aborted due to failures.
        abort_reason: Reason for abort (if aborted).

    Example:
        >>> result = DeliberationResult(
        ...     session_id=session.session_id,
        ...     petition_id=petition.id,
        ...     outcome=DeliberationOutcome.ACKNOWLEDGE,
        ...     votes={a1: ACKNOWLEDGE, a2: ACKNOWLEDGE, a3: REFER},
        ...     dissent_archon_id=a3,
        ...     phase_results=(assess, position, cross_examine, vote),
        ...     started_at=start_time,
        ...     completed_at=end_time,
        ... )
        >>> assert result.is_unanimous is False
        >>> assert result.total_duration_ms > 0
    """

    session_id: UUID
    petition_id: UUID
    outcome: DeliberationOutcome
    votes: dict[UUID, DeliberationOutcome]
    dissent_archon_id: UUID | None
    phase_results: tuple[PhaseResult, ...]
    started_at: datetime
    completed_at: datetime
    is_aborted: bool = False
    abort_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate deliberation result invariants."""
        # Validate timestamps
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")

        if self.is_aborted:
            if self.outcome != DeliberationOutcome.ESCALATE:
                raise ValueError("Aborted deliberation must ESCALATE")
            if self.abort_reason is None:
                raise ValueError("abort_reason required for aborted deliberation")
            return

        # Validate vote count (must be exactly 3)
        if len(self.votes) != 3:
            raise ValueError(f"Exactly 3 votes required, got {len(self.votes)}")

        vote_counts = self._count_votes()
        is_deadlock_escalation = self._is_deadlock_escalation(vote_counts)
        self._validate_outcome_consensus(vote_counts, is_deadlock_escalation)
        self._validate_dissent(vote_counts, is_deadlock_escalation)

        self._validate_phase_results()

    def _count_votes(self) -> dict[DeliberationOutcome, int]:
        vote_counts: dict[DeliberationOutcome, int] = {}
        for vote in self.votes.values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1
        return vote_counts

    def _is_deadlock_escalation(
        self, vote_counts: dict[DeliberationOutcome, int]
    ) -> bool:
        return (
            self.outcome == DeliberationOutcome.ESCALATE
            and len(vote_counts) == 3
            and all(count == 1 for count in vote_counts.values())
        )

    def _validate_outcome_consensus(
        self,
        vote_counts: dict[DeliberationOutcome, int],
        is_deadlock_escalation: bool,
    ) -> None:
        outcome_votes = vote_counts.get(self.outcome, 0)
        if outcome_votes < 2 and not is_deadlock_escalation:
            raise ValueError(
                f"Outcome {self.outcome.value} does not have 2-of-3 consensus "
                f"(got {outcome_votes} votes)"
            )

    def _validate_dissent(
        self,
        vote_counts: dict[DeliberationOutcome, int],
        is_deadlock_escalation: bool,
    ) -> None:
        if is_deadlock_escalation and self.dissent_archon_id is not None:
            raise ValueError("dissent_archon_id must be None for deadlock escalation")

        if self.is_unanimous and self.dissent_archon_id is not None:
            raise ValueError("dissent_archon_id must be None for unanimous vote")

        if (
            not self.is_unanimous
            and self.dissent_archon_id is None
            and not is_deadlock_escalation
        ):
            raise ValueError("dissent_archon_id required for 2-1 vote")

        if self.dissent_archon_id is not None:
            dissent_vote = self.votes.get(self.dissent_archon_id)
            if dissent_vote == self.outcome:
                raise ValueError(
                    f"Dissenting archon {self.dissent_archon_id} voted for outcome"
                )

    def _validate_phase_results(self) -> None:
        if len(self.phase_results) < 4:
            raise ValueError(
                "Phase results must include ASSESS, POSITION, and at least one "
                f"CROSS_EXAMINE/VOTE pair, got {len(self.phase_results)}"
            )

        if self.phase_results[0].phase != DeliberationPhase.ASSESS:
            raise ValueError(
                f"Phase 0 should be ASSESS, got {self.phase_results[0].phase.value}"
            )
        if self.phase_results[1].phase != DeliberationPhase.POSITION:
            raise ValueError(
                f"Phase 1 should be POSITION, got {self.phase_results[1].phase.value}"
            )

        remaining = self.phase_results[2:]
        if len(remaining) % 2 != 0:
            raise ValueError(
                "Phase results must include CROSS_EXAMINE/VOTE pairs after POSITION, got "
                f"{len(self.phase_results)}"
            )

        for offset, actual in enumerate(remaining):
            expected = (
                DeliberationPhase.CROSS_EXAMINE
                if offset % 2 == 0
                else DeliberationPhase.VOTE
            )
            if actual.phase != expected:
                phase_index = offset + 2
                raise ValueError(
                    f"Phase {phase_index} should be {expected.value}, got {actual.phase.value}"
                )

    @property
    def total_duration_ms(self) -> int:
        """Get total deliberation duration in milliseconds.

        Returns:
            Total duration of deliberation in milliseconds.
        """
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)

    @property
    def is_unanimous(self) -> bool:
        """Check if deliberation was unanimous (3-0 vote).

        Returns:
            True if all 3 archons voted for the same outcome.
        """
        return len(set(self.votes.values())) == 1

    def get_phase_result(self, phase: DeliberationPhase) -> PhaseResult | None:
        """Get result for a specific phase.

        Args:
            phase: The phase to get result for.

        Returns:
            PhaseResult for the phase, or None if not found.
        """
        for result in self.phase_results:
            if result.phase == phase:
                return result
        return None

    def get_archon_vote(self, archon_id: UUID) -> DeliberationOutcome | None:
        """Get an archon's vote.

        Args:
            archon_id: UUID of the archon.

        Returns:
            The archon's vote, or None if archon did not vote.
        """
        return self.votes.get(archon_id)

    @property
    def majority_archons(self) -> tuple[UUID, ...]:
        """Get UUIDs of archons who voted for the outcome.

        Returns:
            Tuple of archon UUIDs who voted for the winning outcome.
        """
        return tuple(
            archon_id for archon_id, vote in self.votes.items() if vote == self.outcome
        )
