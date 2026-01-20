"""Archon deliberation metrics domain model (Story 3.6, FR-3.6).

This module defines the domain model for tracking acknowledgment rate
metrics per Archon during deliberations.

Constitutional Constraints:
- FR-3.6: System SHALL track acknowledgment rate metrics per Marquis
- FM-3.2: Source for acknowledgment rate metrics requirement
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ArchonDeliberationMetrics:
    """Metrics for an archon's participation in deliberations (FR-3.6).

    Tracks the total number of deliberations an archon participated in
    and how they voted, enabling calculation of acknowledgment rate.

    The acknowledgment rate is a key quality indicator - a very high
    rate might indicate rubber-stamping, while a very low rate might
    indicate an overly adversarial approach.

    Attributes:
        archon_id: UUID of the archon being tracked.
        total_participations: Number of deliberations participated in.
        acknowledge_votes: Number of ACKNOWLEDGE votes cast.
        refer_votes: Number of REFER votes cast.
        escalate_votes: Number of ESCALATE votes cast.
    """

    archon_id: UUID
    total_participations: int = 0
    acknowledge_votes: int = 0
    refer_votes: int = 0
    escalate_votes: int = 0

    def __post_init__(self) -> None:
        """Validate metrics invariants."""
        if self.total_participations < 0:
            raise ValueError("total_participations must be non-negative")
        if self.acknowledge_votes < 0:
            raise ValueError("acknowledge_votes must be non-negative")
        if self.refer_votes < 0:
            raise ValueError("refer_votes must be non-negative")
        if self.escalate_votes < 0:
            raise ValueError("escalate_votes must be non-negative")

        # Total votes should not exceed participations
        total_votes = self.acknowledge_votes + self.refer_votes + self.escalate_votes
        if total_votes > self.total_participations:
            raise ValueError(
                f"Total votes ({total_votes}) cannot exceed participations ({self.total_participations})"
            )

    @property
    def total_votes(self) -> int:
        """Get total number of votes cast.

        Returns:
            Sum of all vote types.
        """
        return self.acknowledge_votes + self.refer_votes + self.escalate_votes

    @property
    def acknowledgment_rate(self) -> float:
        """Calculate acknowledgment rate (FR-3.6).

        The acknowledgment rate is the ratio of ACKNOWLEDGE votes to
        total participations. This metric helps identify patterns in
        archon deliberation behavior.

        Returns:
            Acknowledgment rate as a float between 0.0 and 1.0,
            or 0.0 if no participations recorded.
        """
        if self.total_participations == 0:
            return 0.0
        return self.acknowledge_votes / self.total_participations

    @property
    def refer_rate(self) -> float:
        """Calculate referral rate.

        Returns:
            Refer rate as a float between 0.0 and 1.0,
            or 0.0 if no participations recorded.
        """
        if self.total_participations == 0:
            return 0.0
        return self.refer_votes / self.total_participations

    @property
    def escalate_rate(self) -> float:
        """Calculate escalation rate.

        Returns:
            Escalate rate as a float between 0.0 and 1.0,
            or 0.0 if no participations recorded.
        """
        if self.total_participations == 0:
            return 0.0
        return self.escalate_votes / self.total_participations

    def with_participation(self) -> ArchonDeliberationMetrics:
        """Create new metrics with incremented participation count.

        Returns:
            New ArchonDeliberationMetrics with participation incremented.
        """
        return ArchonDeliberationMetrics(
            archon_id=self.archon_id,
            total_participations=self.total_participations + 1,
            acknowledge_votes=self.acknowledge_votes,
            refer_votes=self.refer_votes,
            escalate_votes=self.escalate_votes,
        )

    def with_vote(self, outcome: str) -> ArchonDeliberationMetrics:
        """Create new metrics with vote recorded.

        Args:
            outcome: Vote outcome - must be ACKNOWLEDGE, REFER, or ESCALATE.

        Returns:
            New ArchonDeliberationMetrics with vote incremented.

        Raises:
            ValueError: If outcome is not a valid deliberation outcome.
        """
        if outcome == "ACKNOWLEDGE":
            return ArchonDeliberationMetrics(
                archon_id=self.archon_id,
                total_participations=self.total_participations,
                acknowledge_votes=self.acknowledge_votes + 1,
                refer_votes=self.refer_votes,
                escalate_votes=self.escalate_votes,
            )
        elif outcome == "REFER":
            return ArchonDeliberationMetrics(
                archon_id=self.archon_id,
                total_participations=self.total_participations,
                acknowledge_votes=self.acknowledge_votes,
                refer_votes=self.refer_votes + 1,
                escalate_votes=self.escalate_votes,
            )
        elif outcome == "ESCALATE":
            return ArchonDeliberationMetrics(
                archon_id=self.archon_id,
                total_participations=self.total_participations,
                acknowledge_votes=self.acknowledge_votes,
                refer_votes=self.refer_votes,
                escalate_votes=self.escalate_votes + 1,
            )
        else:
            raise ValueError(
                f"Invalid outcome '{outcome}'. Must be ACKNOWLEDGE, REFER, or ESCALATE."
            )

    @classmethod
    def create(cls, archon_id: UUID) -> ArchonDeliberationMetrics:
        """Create new metrics for an archon with zero counts.

        Factory method for creating initial metrics for an archon.

        Args:
            archon_id: UUID of the archon.

        Returns:
            New ArchonDeliberationMetrics with all counts at zero.
        """
        return cls(archon_id=archon_id)
