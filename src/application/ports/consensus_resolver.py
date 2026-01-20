"""Consensus resolver protocol (Story 2A.6, FR-11.5, FR-11.6).

This module defines the abstract interface for supermajority consensus
resolution. The protocol enables dependency inversion and testability
for the consensus resolution logic.

Constitutional Constraints:
- AT-6: Deliberation is collective judgment, not unilateral decision
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.models.consensus_result import (
    ConsensusResult,
    VoteValidationResult,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)


class ConsensusResolverProtocol(Protocol):
    """Protocol for 2-of-3 supermajority consensus resolution (FR-11.5, FR-11.6).

    This protocol defines the interface for resolving consensus from
    archon votes. Implementations must ensure deterministic, reproducible
    results (NFR-10.3).

    Constitutional Constraints:
    - AT-6: Requires 2-of-3 agreement for any outcome
    - NFR-10.3: Same inputs must produce identical outputs
    """

    def validate_votes(
        self,
        session: DeliberationSession,
        votes: dict[UUID, DeliberationOutcome],
    ) -> VoteValidationResult:
        """Validate votes before consensus resolution (FR-11.5).

        Validates that:
        - All 3 assigned archons have voted
        - All voters are assigned to the session
        - All votes reference valid outcomes

        Args:
            session: The deliberation session with assigned archons.
            votes: Map of archon_id to their vote.

        Returns:
            VoteValidationResult indicating whether votes are valid.
        """
        ...

    def resolve_consensus(
        self,
        session: DeliberationSession,
        votes: dict[UUID, DeliberationOutcome],
    ) -> ConsensusResult:
        """Resolve 2-of-3 supermajority consensus from votes (FR-11.5, FR-11.6).

        Applies the supermajority algorithm to determine if consensus is
        reached. The algorithm is deterministic: given the same session
        and votes, it always produces the same result (NFR-10.3).

        Algorithm:
        1. Validate votes (must pass validation first)
        2. Count votes per outcome
        3. Check if any outcome has >= 2 votes
        4. Identify majority archons and any dissenter

        Args:
            session: The deliberation session with assigned archons.
            votes: Map of archon_id to their vote (must have exactly 3 votes).

        Returns:
            ConsensusResult with outcome, vote distribution, and attribution.

        Raises:
            ValueError: If votes are invalid (call validate_votes first).
            ConsensusNotReachedError: If no outcome achieves 2-of-3 majority.
        """
        ...

    def can_reach_consensus(
        self,
        votes: dict[UUID, DeliberationOutcome],
    ) -> bool:
        """Check if votes can mathematically reach consensus (helper method).

        With 3 archons and 3 possible outcomes, consensus is always
        reachable unless:
        - All 3 archons vote for different outcomes (edge case)

        Args:
            votes: Map of archon_id to their vote.

        Returns:
            True if votes can achieve 2-of-3 majority, False otherwise.
        """
        ...
