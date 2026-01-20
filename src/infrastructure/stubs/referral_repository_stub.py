"""In-memory stub implementation of ReferralRepositoryProtocol (Story 4.2).

This module provides an in-memory implementation for testing purposes.
Not intended for production use.

Constitutional Constraints:
- FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
- FR-4.2: System SHALL assign referral deadline (3 cycles default)
"""

from __future__ import annotations

from uuid import UUID

from src.domain.errors.referral import ReferralAlreadyExistsError, ReferralNotFoundError
from src.domain.models.referral import Referral, ReferralStatus


class ReferralRepositoryStub:
    """In-memory implementation of ReferralRepositoryProtocol.

    Stores referrals in memory for testing. Provides all repository
    operations needed by ReferralExecutionService.

    Example:
        >>> stub = ReferralRepositoryStub()
        >>> await stub.save(referral)
        >>> result = await stub.get_by_id(referral.referral_id)
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._referrals: dict[UUID, Referral] = {}
        self._by_petition: dict[UUID, UUID] = {}  # petition_id -> referral_id

    async def save(self, referral: Referral) -> None:
        """Persist a referral record.

        Args:
            referral: The referral to save

        Raises:
            ReferralAlreadyExistsError: Referral for petition exists
        """
        # Check for existing referral for this petition
        if referral.petition_id in self._by_petition:
            existing_id = self._by_petition[referral.petition_id]
            raise ReferralAlreadyExistsError(
                petition_id=referral.petition_id,
                existing_referral_id=existing_id,
            )

        self._referrals[referral.referral_id] = referral
        self._by_petition[referral.petition_id] = referral.referral_id

    async def update(self, referral: Referral) -> None:
        """Update an existing referral record.

        Args:
            referral: The referral to update

        Raises:
            ReferralNotFoundError: Referral doesn't exist
        """
        if referral.referral_id not in self._referrals:
            raise ReferralNotFoundError(referral_id=referral.referral_id)

        self._referrals[referral.referral_id] = referral

    async def get_by_id(self, referral_id: UUID) -> Referral | None:
        """Retrieve referral by ID.

        Args:
            referral_id: The referral UUID

        Returns:
            The Referral if found, None otherwise
        """
        return self._referrals.get(referral_id)

    async def get_by_petition_id(self, petition_id: UUID) -> Referral | None:
        """Retrieve referral by petition ID.

        Args:
            petition_id: The petition UUID

        Returns:
            The Referral if petition was referred, None otherwise
        """
        referral_id = self._by_petition.get(petition_id)
        if referral_id is None:
            return None
        return self._referrals.get(referral_id)

    async def exists_for_petition(self, petition_id: UUID) -> bool:
        """Check if referral exists for a petition.

        Args:
            petition_id: The petition UUID

        Returns:
            True if a referral exists, False otherwise
        """
        return petition_id in self._by_petition

    async def get_pending_by_realm(
        self,
        realm_id: UUID,
        limit: int = 10,
    ) -> list[Referral]:
        """Get pending referrals for a realm.

        Args:
            realm_id: The realm UUID
            limit: Maximum number of referrals to return

        Returns:
            List of pending referrals in the realm
        """
        pending = [
            r
            for r in self._referrals.values()
            if r.realm_id == realm_id and r.status == ReferralStatus.PENDING
        ]
        # Sort by created_at for deterministic ordering
        pending.sort(key=lambda r: r.created_at)
        return pending[:limit]

    async def get_active_by_knight(
        self,
        knight_id: UUID,
    ) -> list[Referral]:
        """Get active referrals assigned to a Knight.

        Args:
            knight_id: The Knight's archon UUID

        Returns:
            List of active referrals assigned to the Knight
        """
        active_statuses = {ReferralStatus.ASSIGNED, ReferralStatus.IN_REVIEW}
        return [
            r
            for r in self._referrals.values()
            if r.assigned_knight_id == knight_id and r.status in active_statuses
        ]

    async def count_active_by_knight(
        self,
        knight_id: UUID,
    ) -> int:
        """Count active referrals assigned to a Knight.

        Args:
            knight_id: The Knight's archon UUID

        Returns:
            Number of active referrals assigned to the Knight
        """
        active = await self.get_active_by_knight(knight_id)
        return len(active)

    def clear(self) -> None:
        """Clear all stored referrals. For testing only."""
        self._referrals.clear()
        self._by_petition.clear()

    def count(self) -> int:
        """Return number of stored referrals. For testing only."""
        return len(self._referrals)
