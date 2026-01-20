"""Consensus result domain models (Story 2A.6, FR-11.5, FR-11.6).

This module defines the domain models for the supermajority consensus
resolution system. A ConsensusResult represents the outcome of applying
2-of-3 supermajority logic to archon votes.

Constitutional Constraints:
- AT-6: Deliberation is collective judgment, not unilateral decision
- NFR-10.3: Consensus determinism - 100% reproducible
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass

# Algorithm version for determinism verification (NFR-10.3)
CONSENSUS_ALGORITHM_VERSION = 1

# Consensus threshold: 2-of-3 supermajority
SUPERMAJORITY_THRESHOLD = 2

# Required number of votes for consensus resolution
REQUIRED_VOTE_COUNT = 3


class ConsensusStatus(Enum):
    """Status of consensus resolution attempt.

    Statuses:
        ACHIEVED: 2-of-3 supermajority reached for one outcome
        UNANIMOUS: All 3 archons agreed on the outcome
        NOT_REACHED: No outcome achieved supermajority (edge case)
        INVALID: Votes are invalid (missing votes, unauthorized voters)
    """

    ACHIEVED = "ACHIEVED"
    UNANIMOUS = "UNANIMOUS"
    NOT_REACHED = "NOT_REACHED"
    INVALID = "INVALID"


class VoteValidationStatus(Enum):
    """Status of vote validation.

    Statuses:
        VALID: All votes are valid and can be counted
        MISSING_VOTES: Not all 3 archons have voted
        UNAUTHORIZED_VOTER: Vote from non-assigned archon
        DUPLICATE_VOTE: Same archon voted twice
        INVALID_OUTCOME: Vote references invalid outcome type
    """

    VALID = "VALID"
    MISSING_VOTES = "MISSING_VOTES"
    UNAUTHORIZED_VOTER = "UNAUTHORIZED_VOTER"
    DUPLICATE_VOTE = "DUPLICATE_VOTE"
    INVALID_OUTCOME = "INVALID_OUTCOME"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class VoteValidationResult:
    """Result of validating votes before consensus resolution (FR-11.5).

    This model captures the validation state of votes before attempting
    to resolve consensus. All validation must pass before consensus
    resolution can proceed.

    Attributes:
        is_valid: True if all votes are valid and consensus can be resolved.
        status: Specific validation status indicating success or failure type.
        missing_archon_ids: List of archon IDs that have not voted (if applicable).
        unauthorized_archon_ids: List of archon IDs that voted but weren't assigned.
        error_message: Human-readable description of validation failure.
        validated_at: Timestamp when validation was performed.
    """

    is_valid: bool
    status: VoteValidationStatus
    missing_archon_ids: tuple[UUID, ...] = field(default_factory=tuple)
    unauthorized_archon_ids: tuple[UUID, ...] = field(default_factory=tuple)
    error_message: str | None = field(default=None)
    validated_at: datetime = field(default_factory=_utc_now)

    @classmethod
    def valid(cls) -> VoteValidationResult:
        """Create a valid validation result.

        Returns:
            VoteValidationResult indicating all votes are valid.
        """
        return cls(
            is_valid=True,
            status=VoteValidationStatus.VALID,
        )

    @classmethod
    def missing_votes(
        cls, missing_archon_ids: tuple[UUID, ...]
    ) -> VoteValidationResult:
        """Create validation result for missing votes.

        Args:
            missing_archon_ids: IDs of archons who have not voted.

        Returns:
            VoteValidationResult indicating missing votes.
        """
        return cls(
            is_valid=False,
            status=VoteValidationStatus.MISSING_VOTES,
            missing_archon_ids=missing_archon_ids,
            error_message=f"Missing votes from {len(missing_archon_ids)} archon(s)",
        )

    @classmethod
    def unauthorized_voter(
        cls, unauthorized_archon_ids: tuple[UUID, ...]
    ) -> VoteValidationResult:
        """Create validation result for unauthorized voters.

        Args:
            unauthorized_archon_ids: IDs of archons who voted but weren't assigned.

        Returns:
            VoteValidationResult indicating unauthorized voters.
        """
        return cls(
            is_valid=False,
            status=VoteValidationStatus.UNAUTHORIZED_VOTER,
            unauthorized_archon_ids=unauthorized_archon_ids,
            error_message=f"Unauthorized vote(s) from {len(unauthorized_archon_ids)} archon(s)",
        )

    @classmethod
    def invalid_outcome(cls, error_message: str) -> VoteValidationResult:
        """Create validation result for invalid outcome type.

        Args:
            error_message: Description of the invalid outcome.

        Returns:
            VoteValidationResult indicating invalid outcome.
        """
        return cls(
            is_valid=False,
            status=VoteValidationStatus.INVALID_OUTCOME,
            error_message=error_message,
        )


@dataclass(frozen=True, eq=True)
class ConsensusResult:
    """Result of 2-of-3 supermajority consensus resolution (FR-11.5, FR-11.6).

    This model represents the deterministic output of applying the
    supermajority algorithm to archon votes. The result includes
    complete attribution for witness verification.

    Constitutional Constraints:
    - AT-6: Collective judgment requires 2-of-3 agreement
    - NFR-10.3: Algorithm version enables determinism verification
    - CT-12: Full attribution for witnessing

    Attributes:
        session_id: ID of the deliberation session.
        petition_id: ID of the petition being deliberated.
        status: Whether consensus was achieved.
        winning_outcome: The outcome that achieved supermajority (None if not reached).
        vote_distribution: Map of outcome to count of votes for that outcome.
        majority_archon_ids: IDs of archons who voted for winning outcome.
        dissent_archon_id: ID of dissenting archon in 2-1 vote (None if unanimous).
        algorithm_version: Version of consensus algorithm for reproducibility.
        resolved_at: Timestamp when consensus was resolved.
    """

    session_id: UUID
    petition_id: UUID
    status: ConsensusStatus
    vote_distribution: dict[str, int]
    majority_archon_ids: tuple[UUID, ...] = field(default_factory=tuple)
    dissent_archon_id: UUID | None = field(default=None)
    winning_outcome: str | None = field(default=None)
    algorithm_version: int = field(default=CONSENSUS_ALGORITHM_VERSION)
    resolved_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate consensus result invariants."""
        self._validate_consistency()

    def _validate_consistency(self) -> None:
        """Validate internal consistency of consensus result.

        Raises:
            ValueError: If result state is inconsistent.
        """
        # If consensus achieved, must have winning outcome
        if self.status in (ConsensusStatus.ACHIEVED, ConsensusStatus.UNANIMOUS):
            if self.winning_outcome is None:
                raise ValueError(
                    f"ConsensusResult with status {self.status.value} "
                    "must have a winning_outcome"
                )
            if len(self.majority_archon_ids) < SUPERMAJORITY_THRESHOLD:
                raise ValueError(
                    f"ConsensusResult with status {self.status.value} "
                    f"must have at least {SUPERMAJORITY_THRESHOLD} majority archons"
                )

        # Unanimous must have no dissenter
        if self.status == ConsensusStatus.UNANIMOUS:
            if self.dissent_archon_id is not None:
                raise ValueError(
                    "ConsensusResult with UNANIMOUS status cannot have dissent_archon_id"
                )

        # 2-1 split (ACHIEVED but not UNANIMOUS) must identify dissenter
        if (
            self.status == ConsensusStatus.ACHIEVED
            and len(self.majority_archon_ids) == SUPERMAJORITY_THRESHOLD
        ):
            if self.dissent_archon_id is None:
                raise ValueError(
                    "ConsensusResult with 2-1 split must identify dissent_archon_id"
                )

    @property
    def is_consensus_reached(self) -> bool:
        """Check if consensus was successfully reached.

        Returns:
            True if status is ACHIEVED or UNANIMOUS.
        """
        return self.status in (ConsensusStatus.ACHIEVED, ConsensusStatus.UNANIMOUS)

    @property
    def is_unanimous(self) -> bool:
        """Check if consensus was unanimous (3-0).

        Returns:
            True if all archons voted for the same outcome.
        """
        return self.status == ConsensusStatus.UNANIMOUS

    @property
    def has_dissent(self) -> bool:
        """Check if there was a dissenting vote.

        Returns:
            True if consensus was 2-1 (not unanimous).
        """
        return self.dissent_archon_id is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for event serialization.

        Returns:
            Dictionary representation suitable for event payloads.
        """
        return {
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "status": self.status.value,
            "winning_outcome": self.winning_outcome,
            "vote_distribution": dict(self.vote_distribution),
            "majority_archon_ids": [str(aid) for aid in self.majority_archon_ids],
            "dissent_archon_id": str(self.dissent_archon_id) if self.dissent_archon_id else None,
            "algorithm_version": self.algorithm_version,
            "resolved_at": self.resolved_at.isoformat(),
            "schema_version": 1,
        }
