"""Deliberation Summary domain model (Story 7.4, FR-7.4, Ruling-2).

This module defines the DeliberationSummary model for mediated access to
deliberation outcomes. Per Ruling-2 (Tiered Transcript Access), Observers
receive summarized views that hide sensitive details while proving immutability.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - Observers see summaries, not raw transcripts
- FR-7.4: System SHALL provide mediated deliberation summary to Observer
- CT-12: Witnessing creates accountability - hash references prove immutability
- PRD Section 13A.8: Observers receive phase-level summaries + final disposition

What Observers CAN see:
- Outcome (ACKNOWLEDGE, REFER, ESCALATE)
- Vote breakdown string (e.g., "2-1" or "3-0")
- Dissent presence indicator (boolean only)
- Phase summaries (metadata, not content)
- Duration and timestamps
- Hash references (proving transcripts exist and are immutable)

What Observers CANNOT see:
- Raw transcript text
- Individual Archon identities (UUIDs)
- Verbatim utterances
- Who voted for what
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationOutcome, DeliberationPhase


class EscalationTrigger(Enum):
    """Trigger reason for escalation (Story 7.4, AC-2, AC-6, AC-7).

    Indicates why a petition was escalated to King-level consideration.

    Values:
        DELIBERATION: Normal 2-of-3 vote resulted in ESCALATE outcome
        AUTO_ESCALATED: Co-signer threshold triggered automatic escalation
        TIMEOUT: Deliberation timed out (HC-7)
        DEADLOCK: Maximum rounds exceeded without consensus (FR-11.10)
    """

    DELIBERATION = "DELIBERATION"
    AUTO_ESCALATED = "AUTO_ESCALATED"
    TIMEOUT = "TIMEOUT"
    DEADLOCK = "DEADLOCK"


@dataclass(frozen=True, eq=True)
class PhaseSummaryItem:
    """Summary of a single deliberation phase (Story 7.4, AC-1).

    Provides high-level phase information without exposing transcript content.
    Hash references prove transcript immutability without revealing content.

    Constitutional Constraints:
    - Ruling-2: No raw transcript exposure
    - CT-12: Hash proves witnessing occurred

    Attributes:
        phase: The deliberation phase (ASSESS, POSITION, CROSS_EXAMINE, VOTE).
        duration_seconds: How long the phase took.
        transcript_hash_hex: Hex-encoded Blake3 hash of transcript (proves existence).
        themes: Optional list of high-level themes discussed (metadata, not content).
        convergence_reached: Optional indicator if archons converged on position.
    """

    phase: DeliberationPhase
    duration_seconds: int
    transcript_hash_hex: str
    themes: tuple[str, ...] = field(default_factory=tuple)
    convergence_reached: bool | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API serialization.

        Per D2 (Schema Versioning), includes schema_version.

        Returns:
            Dictionary with serializable values.
        """
        result: dict[str, Any] = {
            "phase": self.phase.value,
            "duration_seconds": self.duration_seconds,
            "transcript_hash_hex": self.transcript_hash_hex,
            "schema_version": 1,
        }
        if self.themes:
            result["themes"] = list(self.themes)
        if self.convergence_reached is not None:
            result["convergence_reached"] = self.convergence_reached
        return result


@dataclass(frozen=True, eq=True)
class DeliberationSummary:
    """Mediated summary of deliberation for Observer access (Story 7.4, FR-7.4).

    This model provides the Observer tier of transcript access per Ruling-2.
    It reveals deliberation outcomes without exposing sensitive details like
    individual Archon identities or raw transcript content.

    Constitutional Constraints:
    - Ruling-2: Tiered transcript access - mediated view
    - FR-7.4: System SHALL provide deliberation summary
    - CT-12: Hash references prove witnessing occurred
    - PRD Section 13A.8: Observer tier access

    Attributes:
        petition_id: UUID of the deliberated petition.
        outcome: Deliberation outcome (ACKNOWLEDGE, REFER, ESCALATE).
        vote_breakdown: Vote breakdown string (e.g., "2-1", "3-0").
        has_dissent: Whether there was a dissenting vote (boolean, not identity).
        phase_summaries: List of phase summaries with metadata.
        duration_seconds: Total deliberation duration in seconds.
        completed_at: When deliberation completed (UTC).
        escalation_trigger: Why escalated (if outcome is ESCALATE).
        escalation_reason: Additional escalation context.
        timed_out: True if terminated by timeout.
        rounds_attempted: Number of voting rounds attempted (for deadlock).
    """

    petition_id: UUID
    outcome: DeliberationOutcome
    vote_breakdown: str
    has_dissent: bool
    phase_summaries: tuple[PhaseSummaryItem, ...]
    duration_seconds: int
    completed_at: datetime
    escalation_trigger: EscalationTrigger | None = field(default=None)
    escalation_reason: str | None = field(default=None)
    timed_out: bool = field(default=False)
    rounds_attempted: int = field(default=1)

    def __post_init__(self) -> None:
        """Validate deliberation summary invariants."""
        self._validate_vote_breakdown()
        self._validate_escalation_consistency()
        self._validate_completed_at()

    def _validate_vote_breakdown(self) -> None:
        """Validate vote breakdown format.

        Must be in format "X-Y" where X >= Y and X + Y == 3.
        Valid values: "3-0", "2-1".

        Raises:
            ValueError: If vote breakdown format is invalid.
        """
        if not self.vote_breakdown:
            return  # Empty is valid for auto-escalation with no deliberation

        parts = self.vote_breakdown.split("-")
        if len(parts) != 2:
            raise ValueError(
                f"vote_breakdown must be in format 'X-Y', got '{self.vote_breakdown}'"
            )

        try:
            majority, minority = int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError(
                f"vote_breakdown must contain integers, got '{self.vote_breakdown}'"
            )

        if majority < minority:
            raise ValueError(
                f"vote_breakdown majority must be >= minority, got '{self.vote_breakdown}'"
            )

        if majority + minority != 3 and majority + minority != 0:
            raise ValueError(
                f"vote_breakdown must sum to 3 (or 0 for no deliberation), "
                f"got {majority + minority}"
            )

    def _validate_escalation_consistency(self) -> None:
        """Validate escalation fields are consistent with outcome.

        If outcome is ESCALATE, escalation_trigger should be set.

        Raises:
            ValueError: If escalation fields are inconsistent.
        """
        if self.outcome == DeliberationOutcome.ESCALATE:
            if self.escalation_trigger is None:
                raise ValueError(
                    "escalation_trigger is required when outcome is ESCALATE"
                )
        else:
            if self.escalation_trigger is not None:
                raise ValueError(
                    "escalation_trigger should be None when outcome is not ESCALATE"
                )

    def _validate_completed_at(self) -> None:
        """Validate completed_at is timezone-aware.

        Raises:
            ValueError: If completed_at is not timezone-aware.
        """
        if self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware (UTC)")

    @classmethod
    def from_auto_escalation(
        cls,
        petition_id: UUID,
        escalation_reason: str,
        completed_at: datetime | None = None,
    ) -> DeliberationSummary:
        """Create summary for auto-escalated petition (AC-2).

        When a petition bypasses deliberation via co-signer threshold,
        no deliberation session exists.

        Args:
            petition_id: UUID of the petition.
            escalation_reason: Why auto-escalation occurred.
            completed_at: When escalation occurred (defaults to now).

        Returns:
            DeliberationSummary for auto-escalated petition.
        """
        if completed_at is None:
            completed_at = datetime.now(timezone.utc)

        return cls(
            petition_id=petition_id,
            outcome=DeliberationOutcome.ESCALATE,
            vote_breakdown="0-0",  # No deliberation votes
            has_dissent=False,
            phase_summaries=tuple(),  # No phases
            duration_seconds=0,
            completed_at=completed_at,
            escalation_trigger=EscalationTrigger.AUTO_ESCALATED,
            escalation_reason=escalation_reason,
            timed_out=False,
            rounds_attempted=0,
        )

    @classmethod
    def from_timeout(
        cls,
        petition_id: UUID,
        phase_summaries: tuple[PhaseSummaryItem, ...],
        duration_seconds: int,
        completed_at: datetime,
    ) -> DeliberationSummary:
        """Create summary for timeout-triggered escalation (AC-6).

        Args:
            petition_id: UUID of the petition.
            phase_summaries: Partial phase data up to timeout.
            duration_seconds: Total duration before timeout.
            completed_at: When timeout occurred.

        Returns:
            DeliberationSummary for timed-out petition.
        """
        return cls(
            petition_id=petition_id,
            outcome=DeliberationOutcome.ESCALATE,
            vote_breakdown="0-0",  # No consensus reached
            has_dissent=False,
            phase_summaries=phase_summaries,
            duration_seconds=duration_seconds,
            completed_at=completed_at,
            escalation_trigger=EscalationTrigger.TIMEOUT,
            escalation_reason="Deliberation timeout exceeded",
            timed_out=True,
            rounds_attempted=1,
        )

    @classmethod
    def from_deadlock(
        cls,
        petition_id: UUID,
        phase_summaries: tuple[PhaseSummaryItem, ...],
        duration_seconds: int,
        completed_at: datetime,
        rounds_attempted: int,
    ) -> DeliberationSummary:
        """Create summary for deadlock-triggered escalation (AC-7).

        Args:
            petition_id: UUID of the petition.
            phase_summaries: Full phase data through all rounds.
            duration_seconds: Total duration of all rounds.
            completed_at: When deadlock was declared.
            rounds_attempted: Number of voting rounds attempted.

        Returns:
            DeliberationSummary for deadlocked petition.
        """
        return cls(
            petition_id=petition_id,
            outcome=DeliberationOutcome.ESCALATE,
            vote_breakdown="0-0",  # No consensus achieved
            has_dissent=False,
            phase_summaries=phase_summaries,
            duration_seconds=duration_seconds,
            completed_at=completed_at,
            escalation_trigger=EscalationTrigger.DEADLOCK,
            escalation_reason=f"Maximum rounds ({rounds_attempted}) exceeded without supermajority",
            timed_out=False,
            rounds_attempted=rounds_attempted,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API serialization.

        Per D2 (Schema Versioning), includes schema_version.

        Returns:
            Dictionary with serializable values.
        """
        result: dict[str, Any] = {
            "petition_id": str(self.petition_id),
            "outcome": self.outcome.value,
            "vote_breakdown": self.vote_breakdown,
            "has_dissent": self.has_dissent,
            "phase_summaries": [ps.to_dict() for ps in self.phase_summaries],
            "duration_seconds": self.duration_seconds,
            "completed_at": self.completed_at.isoformat(),
            "timed_out": self.timed_out,
            "rounds_attempted": self.rounds_attempted,
            "schema_version": 1,
        }

        if self.escalation_trigger is not None:
            result["escalation_trigger"] = self.escalation_trigger.value
        if self.escalation_reason is not None:
            result["escalation_reason"] = self.escalation_reason

        return result
