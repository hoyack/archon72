"""Amendment repository port (Story 6.7, FR126-FR128).

This module defines the repository interface for storing and querying
constitutional amendment proposals.

Constitutional Constraints:
- FR126: Amendment proposals SHALL be publicly visible minimum 14 days before vote
- FR127: Core guarantee amendments require impact analysis
- FR128: Amendment history cannot be made unreviewable
- CT-11: Silent failure destroys legitimacy -> Query failures must not be silent
- CT-12: Witnessing creates accountability -> All stored amendments were witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.events.amendment import (
    AmendmentImpactAnalysis,
    AmendmentStatus,
    AmendmentType,
)


@dataclass(frozen=True, eq=True)
class AmendmentProposal:
    """A constitutional amendment proposal.

    Represents an amendment moving through the visibility and voting process.
    Per FR126, amendments must be publicly visible for 14 days before voting.

    Attributes:
        amendment_id: Unique identifier for this amendment.
        amendment_type: Constitutional tier (Tier 2 or Tier 3 per ADR-6).
        title: Brief description of the amendment.
        summary: Full amendment text/summary.
        proposed_at: When the amendment was submitted (UTC).
        visible_from: When visibility period started (same as proposed_at).
        votable_from: When vote can occur (14 days after visible_from).
        proposer_id: Who submitted the amendment (attribution).
        is_core_guarantee: True if this affects core constitutional guarantees.
        impact_analysis: Required if is_core_guarantee is True (FR127).
        affected_guarantees: Which constitutional guarantees are affected.
        status: Current status of the amendment.
    """

    amendment_id: str
    amendment_type: AmendmentType
    title: str
    summary: str
    proposed_at: datetime
    visible_from: datetime
    votable_from: datetime
    proposer_id: str
    is_core_guarantee: bool
    affected_guarantees: tuple[str, ...]
    status: AmendmentStatus
    impact_analysis: AmendmentImpactAnalysis | None = None


class AmendmentRepositoryProtocol(Protocol):
    """Protocol for amendment proposal storage and retrieval (FR126-FR128).

    This protocol defines the interface for storing amendment proposals
    and querying amendment history.

    All implementations must support:
    - Saving new amendments
    - Querying pending (awaiting vote) amendments
    - Querying votable (past 14-day visibility) amendments
    - Retrieving full amendment history for FR128 protection

    Constitutional Constraints:
    - FR126: Visibility period tracking
    - FR128: History must remain accessible (never deletable)
    """

    async def save_amendment(self, amendment: AmendmentProposal) -> None:
        """Save an amendment proposal to storage.

        Constitutional Constraint:
        The amendment event is assumed to have already been witnessed
        via the EventWriterService before being saved here.

        Args:
            amendment: The amendment proposal to save.

        Raises:
            AmendmentError: If save fails.
        """
        ...

    async def get_amendment(self, amendment_id: str) -> AmendmentProposal | None:
        """Retrieve a specific amendment by ID.

        Args:
            amendment_id: The unique identifier of the amendment.

        Returns:
            The amendment proposal if found, None otherwise.

        Raises:
            AmendmentError: If query fails.
        """
        ...

    async def list_pending_amendments(self) -> list[AmendmentProposal]:
        """Retrieve all amendments awaiting vote (in visibility period).

        This returns amendments that have been proposed but have not yet
        completed their 14-day visibility period or are still awaiting vote.

        Returns:
            List of pending amendment proposals, ordered by proposed_at.

        Raises:
            AmendmentError: If query fails.
        """
        ...

    async def list_votable_amendments(self) -> list[AmendmentProposal]:
        """Retrieve all amendments past 14-day visibility (FR126).

        This returns amendments that have completed their visibility period
        and are eligible for voting.

        Returns:
            List of votable amendment proposals, ordered by proposed_at.

        Raises:
            AmendmentError: If query fails.
        """
        ...

    async def get_amendment_history(self) -> list[AmendmentProposal]:
        """Retrieve all historical amendments (FR128).

        Constitutional Constraint (FR128):
        Amendment history cannot be made unreviewable. This method provides
        full access to all amendments ever proposed.

        Returns:
            List of all amendment proposals ever stored, ordered by proposed_at.

        Raises:
            AmendmentError: If query fails.
        """
        ...

    async def is_amendment_votable(self, amendment_id: str) -> tuple[bool, int]:
        """Check if an amendment can proceed to vote (FR126).

        Args:
            amendment_id: The amendment to check.

        Returns:
            Tuple of (is_votable, days_remaining).
            - is_votable: True if 14-day visibility period is complete.
            - days_remaining: Days until votable (0 if already votable).

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
            AmendmentError: If query fails.
        """
        ...

    async def update_status(
        self, amendment_id: str, new_status: AmendmentStatus
    ) -> None:
        """Update the status of an amendment.

        Used to transition amendments through the lifecycle:
        PROPOSED -> VISIBILITY_PERIOD -> VOTABLE -> VOTING -> APPROVED/REJECTED

        Args:
            amendment_id: The amendment to update.
            new_status: The new status to set.

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
            AmendmentError: If update fails.
        """
        ...
