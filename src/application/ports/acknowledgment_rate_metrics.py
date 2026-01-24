"""Acknowledgment rate metrics protocol (Story 3.6, FR-3.6).

This module defines the protocol for tracking acknowledgment rate metrics
per Archon during deliberations.

Constitutional Constraints:
- FR-3.6: System SHALL track acknowledgment rate metrics per Marquis
- FM-3.2: Source for acknowledgment rate metrics requirement
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AcknowledgmentRateMetricsProtocol(Protocol):
    """Protocol for tracking acknowledgment rate metrics per Archon (FR-3.6).

    Implementations collect metrics when archons participate in deliberations
    and cast votes. These metrics enable monitoring of deliberation patterns
    and quality.

    Metrics tracked:
    - Total deliberation participations per archon
    - Vote counts by outcome (ACKNOWLEDGE, REFER, ESCALATE, DEFER, NO_RESPONSE) per archon
    - Derived acknowledgment rate (ACKNOWLEDGE / total participations)
    """

    def record_participation(self, archon_id: UUID) -> None:
        """Record an archon's participation in a completed deliberation.

        Called once per archon when a deliberation session reaches consensus.
        Increments the total participation counter for the archon.

        Args:
            archon_id: UUID of the participating archon.
        """
        ...

    def record_vote(self, archon_id: UUID, outcome: str) -> None:
        """Record an archon's vote with its outcome.

        Called once per archon when consensus is reached, recording
        the specific vote cast (ACKNOWLEDGE, REFER, ESCALATE, DEFER, or NO_RESPONSE).

        Args:
            archon_id: UUID of the voting archon.
            outcome: Vote outcome - must be one of ACKNOWLEDGE, REFER, ESCALATE, DEFER, NO_RESPONSE.

        Raises:
            ValueError: If outcome is not a valid deliberation outcome.
        """
        ...

    def record_deliberation_completion(
        self,
        archon_votes: dict[UUID, str],
    ) -> None:
        """Record metrics for all archons in a completed deliberation.

        Convenience method that calls record_participation and record_vote
        for each archon in the deliberation. This is the primary integration
        point with the consensus resolver.

        Args:
            archon_votes: Map of archon_id to their vote outcome.
        """
        ...
