"""Amendment repository stub implementation (Story 6.7, FR126-FR128).

This module provides an in-memory stub implementation of AmendmentRepositoryProtocol
for testing and development purposes.

Constitutional Constraints:
- FR126: Amendment proposals SHALL be publicly visible minimum 14 days before vote
- FR128: Amendment history cannot be made unreviewable
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.ports.amendment_repository import (
    AmendmentProposal,
    AmendmentRepositoryProtocol,
)
from src.domain.errors.amendment import AmendmentNotFoundError
from src.domain.events.amendment import AmendmentStatus


class AmendmentRepositoryStub(AmendmentRepositoryProtocol):
    """In-memory stub for amendment storage (testing only).

    This stub provides an in-memory implementation of AmendmentRepositoryProtocol
    suitable for unit and integration tests.

    The stub stores amendment proposals in a dictionary keyed by amendment_id.
    All query operations iterate over the stored amendments.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._amendments: dict[str, AmendmentProposal] = {}

    def clear(self) -> None:
        """Clear all stored amendments (for test cleanup)."""
        self._amendments.clear()

    async def save_amendment(self, amendment: AmendmentProposal) -> None:
        """Save an amendment proposal to storage.

        Args:
            amendment: The amendment proposal to save.
        """
        self._amendments[amendment.amendment_id] = amendment

    async def get_amendment(self, amendment_id: str) -> AmendmentProposal | None:
        """Retrieve a specific amendment by ID.

        Args:
            amendment_id: The unique identifier of the amendment.

        Returns:
            The amendment proposal if found, None otherwise.
        """
        return self._amendments.get(amendment_id)

    async def list_pending_amendments(self) -> list[AmendmentProposal]:
        """Retrieve all amendments awaiting vote (in visibility period).

        Returns:
            List of pending amendment proposals, ordered by proposed_at.
        """
        pending_statuses = {
            AmendmentStatus.PROPOSED,
            AmendmentStatus.VISIBILITY_PERIOD,
            AmendmentStatus.VOTABLE,
        }
        pending = [a for a in self._amendments.values() if a.status in pending_statuses]
        return sorted(pending, key=lambda a: a.proposed_at)

    async def list_votable_amendments(self) -> list[AmendmentProposal]:
        """Retrieve all amendments past 14-day visibility (FR126).

        Returns:
            List of votable amendment proposals, ordered by proposed_at.
        """
        now = datetime.now(timezone.utc)
        votable = [
            a
            for a in self._amendments.values()
            if now >= a.votable_from
            and a.status in {AmendmentStatus.VISIBILITY_PERIOD, AmendmentStatus.VOTABLE}
        ]
        return sorted(votable, key=lambda a: a.proposed_at)

    async def get_amendment_history(self) -> list[AmendmentProposal]:
        """Retrieve all historical amendments (FR128).

        Constitutional Constraint (FR128):
        Amendment history cannot be made unreviewable. This method provides
        full access to all amendments ever proposed.

        Returns:
            List of all amendment proposals ever stored, ordered by proposed_at.
        """
        amendments = list(self._amendments.values())
        return sorted(amendments, key=lambda a: a.proposed_at)

    async def is_amendment_votable(self, amendment_id: str) -> tuple[bool, int]:
        """Check if an amendment can proceed to vote (FR126).

        Args:
            amendment_id: The amendment to check.

        Returns:
            Tuple of (is_votable, days_remaining).

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
        """
        amendment = self._amendments.get(amendment_id)
        if amendment is None:
            raise AmendmentNotFoundError(amendment_id=amendment_id)

        now = datetime.now(timezone.utc)
        if now >= amendment.votable_from:
            return True, 0
        else:
            days_remaining = (amendment.votable_from - now).days + 1
            return False, days_remaining

    async def update_status(
        self, amendment_id: str, new_status: AmendmentStatus
    ) -> None:
        """Update the status of an amendment.

        Args:
            amendment_id: The amendment to update.
            new_status: The new status to set.

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
        """
        amendment = self._amendments.get(amendment_id)
        if amendment is None:
            raise AmendmentNotFoundError(amendment_id=amendment_id)

        # Create new proposal with updated status (dataclass is frozen)
        updated = AmendmentProposal(
            amendment_id=amendment.amendment_id,
            amendment_type=amendment.amendment_type,
            title=amendment.title,
            summary=amendment.summary,
            proposed_at=amendment.proposed_at,
            visible_from=amendment.visible_from,
            votable_from=amendment.votable_from,
            proposer_id=amendment.proposer_id,
            is_core_guarantee=amendment.is_core_guarantee,
            affected_guarantees=amendment.affected_guarantees,
            status=new_status,
            impact_analysis=amendment.impact_analysis,
        )
        self._amendments[amendment_id] = updated

    # Test helper methods (not part of protocol)

    def get_amendment_count(self) -> int:
        """Get total number of stored amendments."""
        return len(self._amendments)

    def get_amendments_by_status(
        self, status: AmendmentStatus
    ) -> list[AmendmentProposal]:
        """Get amendments with a specific status (for testing)."""
        return [a for a in self._amendments.values() if a.status == status]
