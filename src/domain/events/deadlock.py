"""Deliberation deadlock events (Story 2B.3, FR-11.10).

This module defines events for deliberation deadlock detection and resolution.
Deadlock occurs when 3 consecutive voting rounds produce no supermajority (1-1-1 splits).

Constitutional Constraints:
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority (deadlock)
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- CT-14: Silence must be expensive - every petition terminates in witnessed fate
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment - deadlock is still collective conclusion
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: 100% witness completeness
- NFR-6.5: Audit trail completeness - complete reconstruction possible
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationPhase

# =============================================================================
# Event Type Constants
# =============================================================================

# Event emitted when a voting round fails to reach consensus (3-way split)
# and the deliberation returns to CROSS_EXAMINE for another round
CROSS_EXAMINE_ROUND_TRIGGERED_EVENT_TYPE: str = "deliberation.round.triggered"

# Event emitted when deadlock is detected (3 rounds without supermajority)
# This triggers auto-ESCALATE per FR-11.10
DEADLOCK_DETECTED_EVENT_TYPE: str = "deliberation.deadlock.detected"

# Schema version for forward/backward compatibility (D2 requirement)
DEADLOCK_EVENT_SCHEMA_VERSION: int = 1


@dataclass(frozen=True, eq=True)
class CrossExamineRoundTriggeredEvent:
    """Event emitted when deliberation returns to CROSS_EXAMINE due to no consensus.

    This occurs when a 3-way split (1-1-1) happens in the VOTE phase and
    the deliberation has not yet reached the maximum allowed rounds.

    Constitutional Constraints:
    - FR-11.10: Tracks rounds toward deadlock detection
    - CT-11: Silent failure destroys legitimacy - event MUST be emitted
    - NFR-10.4: 100% witness completeness

    Attributes:
        event_id: UUIDv7 for this event.
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        round_number: The new round being started (2 or 3).
        previous_vote_distribution: How votes were split in the previous round.
        participating_archons: Tuple of 3 archon UUIDs assigned to session.
        schema_version: Event schema version for compatibility (D2).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    petition_id: UUID
    round_number: int
    previous_vote_distribution: dict[str, int]
    participating_archons: tuple[UUID, UUID, UUID]
    schema_version: int = field(default=DEADLOCK_EVENT_SCHEMA_VERSION)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_round_number()
        self._validate_archon_count()
        self._validate_vote_distribution()
        self._validate_schema_version()

    def _validate_round_number(self) -> None:
        """Validate round_number is valid (2 or 3 for new rounds)."""
        if self.round_number < 2:
            raise ValueError(
                f"round_number must be >= 2 for a new round, got {self.round_number}"
            )

    def _validate_archon_count(self) -> None:
        """Validate exactly 3 archons were participating."""
        if len(self.participating_archons) != 3:
            raise ValueError(
                f"participating_archons must contain exactly 3 UUIDs, "
                f"got {len(self.participating_archons)}"
            )

    def _validate_vote_distribution(self) -> None:
        """Validate vote distribution shows a 3-way split."""
        total_votes = sum(self.previous_vote_distribution.values())
        if total_votes != 3:
            raise ValueError(
                f"previous_vote_distribution must sum to 3 votes, got {total_votes}"
            )

    def _validate_schema_version(self) -> None:
        """Validate schema version is current."""
        if self.schema_version != DEADLOCK_EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {DEADLOCK_EVENT_SCHEMA_VERSION}, "
                f"got {self.schema_version}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (D2 pattern).

        Uses explicit to_dict() per project-context.md, NOT asdict().

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_type": CROSS_EXAMINE_ROUND_TRIGGERED_EVENT_TYPE,
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "round_number": self.round_number,
            "previous_vote_distribution": self.previous_vote_distribution,
            "participating_archons": [str(a) for a in self.participating_archons],
            "schema_version": self.schema_version,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class DeadlockDetectedEvent:
    """Event emitted when deliberation deadlocks (FR-11.10).

    This event is witnessed in the hash chain. Deadlock triggers
    automatic ESCALATE disposition per constitutional requirements.

    Constitutional Constraints:
    - FR-11.10: Auto-ESCALATE after 3 rounds without supermajority
    - CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
    - CT-14: Silence must be expensive - every petition terminates in witnessed fate
    - AT-1: Every petition terminates in exactly one of Three Fates
    - AT-6: Deliberation is collective judgment - deadlock is collective conclusion
    - NFR-10.3: Consensus determinism - 100% reproducible
    - NFR-10.4: 100% witness completeness
    - NFR-6.5: Audit trail completeness - complete reconstruction possible

    Attributes:
        event_id: UUIDv7 for this deadlock event.
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        round_count: Total rounds attempted (always MAX_ROUNDS on deadlock).
        votes_by_round: Vote distribution for each round.
        final_vote_distribution: The final round's vote split.
        phase_at_deadlock: The phase when deadlock was detected (always VOTE).
        reason: Reason code (always "DEADLOCK_MAX_ROUNDS_EXCEEDED").
        participating_archons: Tuple of 3 archon UUIDs assigned to session.
        schema_version: Event schema version for compatibility (D2).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    petition_id: UUID
    round_count: int
    votes_by_round: tuple[dict[str, int], ...]
    final_vote_distribution: dict[str, int]
    phase_at_deadlock: DeliberationPhase
    participating_archons: tuple[UUID, UUID, UUID]
    reason: str = field(default="DEADLOCK_MAX_ROUNDS_EXCEEDED")
    schema_version: int = field(default=DEADLOCK_EVENT_SCHEMA_VERSION)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate deadlock event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_round_count()
        self._validate_archon_count()
        self._validate_votes_by_round()
        self._validate_final_distribution()
        self._validate_reason()
        self._validate_schema_version()

    def _validate_round_count(self) -> None:
        """Validate round_count is positive."""
        if self.round_count < 1:
            raise ValueError(f"round_count must be >= 1, got {self.round_count}")

    def _validate_archon_count(self) -> None:
        """Validate exactly 3 archons were participating."""
        if len(self.participating_archons) != 3:
            raise ValueError(
                f"participating_archons must contain exactly 3 UUIDs, "
                f"got {len(self.participating_archons)}"
            )

    def _validate_votes_by_round(self) -> None:
        """Validate votes_by_round matches round_count."""
        if len(self.votes_by_round) != self.round_count:
            raise ValueError(
                f"votes_by_round must have {self.round_count} entries, "
                f"got {len(self.votes_by_round)}"
            )
        # Validate each round has 3 votes
        for i, round_votes in enumerate(self.votes_by_round):
            total = sum(round_votes.values())
            if total != 3:
                raise ValueError(
                    f"votes_by_round[{i}] must sum to 3 votes, got {total}"
                )

    def _validate_final_distribution(self) -> None:
        """Validate final_vote_distribution sums to 3."""
        total = sum(self.final_vote_distribution.values())
        if total != 3:
            raise ValueError(
                f"final_vote_distribution must sum to 3 votes, got {total}"
            )

    def _validate_reason(self) -> None:
        """Validate reason is the expected deadlock reason."""
        if self.reason != "DEADLOCK_MAX_ROUNDS_EXCEEDED":
            raise ValueError(
                f"reason must be 'DEADLOCK_MAX_ROUNDS_EXCEEDED', got '{self.reason}'"
            )

    def _validate_schema_version(self) -> None:
        """Validate schema version is current."""
        if self.schema_version != DEADLOCK_EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {DEADLOCK_EVENT_SCHEMA_VERSION}, "
                f"got {self.schema_version}"
            )

    @property
    def was_three_way_split_every_round(self) -> bool:
        """Check if every round was a 3-way split (1-1-1).

        Returns:
            True if all rounds had 3 different outcomes with 1 vote each.
        """
        for round_votes in self.votes_by_round:
            # 3-way split means max vote count is 1
            if max(round_votes.values()) > 1:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (D2 pattern).

        Uses explicit to_dict() per project-context.md, NOT asdict().

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_type": DEADLOCK_DETECTED_EVENT_TYPE,
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "round_count": self.round_count,
            "votes_by_round": list(self.votes_by_round),
            "final_vote_distribution": self.final_vote_distribution,
            "phase_at_deadlock": self.phase_at_deadlock.value,
            "reason": self.reason,
            "participating_archons": [str(a) for a in self.participating_archons],
            "schema_version": self.schema_version,
            "created_at": self.created_at.isoformat(),
        }
