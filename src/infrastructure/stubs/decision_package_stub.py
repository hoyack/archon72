"""In-memory stub implementation of DecisionPackageBuilderProtocol (Story 4.3).

This module provides an in-memory implementation for testing purposes.
Not intended for production use.

Constitutional Constraints:
- FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
- NFR-5.2: Authorization: Only assigned Knight can access package
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.domain.errors.decision_package import (
    DecisionPackageNotFoundError,
    ReferralNotAssignedError,
    UnauthorizedPackageAccessError,
)
from src.domain.models.decision_package import DecisionPackage
from src.domain.models.petition_submission import PetitionType
from src.domain.models.referral import ReferralStatus


class DecisionPackageBuilderStub:
    """In-memory stub implementation of DecisionPackageBuilderProtocol.

    Provides configurable behavior for testing decision package building.
    Can be configured to return specific packages or raise specific errors.

    Example:
        >>> stub = DecisionPackageBuilderStub()
        >>> stub.set_package(referral_id, knight_id, package)
        >>> result = await stub.build(referral_id, knight_id)
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        # Maps (referral_id, requester_id) -> DecisionPackage
        self._packages: dict[tuple[UUID, UUID], DecisionPackage] = {}
        # Maps referral_id -> assigned_knight_id (for auth testing)
        self._assignments: dict[UUID, UUID] = {}
        # Maps referral_id -> ReferralStatus (for state testing)
        self._statuses: dict[UUID, ReferralStatus] = {}
        # Set of referral_ids that exist (for not found testing)
        self._existing_referrals: set[UUID] = set()
        # Track build calls for verification
        self._build_calls: list[tuple[UUID, UUID]] = []

    def set_package(
        self,
        referral_id: UUID,
        knight_id: UUID,
        package: DecisionPackage,
    ) -> None:
        """Configure a package to be returned for a specific referral and knight.

        Args:
            referral_id: The referral UUID.
            knight_id: The assigned knight UUID.
            package: The package to return.
        """
        self._packages[(referral_id, knight_id)] = package
        self._assignments[referral_id] = knight_id
        self._statuses[referral_id] = package.status
        self._existing_referrals.add(referral_id)

    def set_assignment(
        self,
        referral_id: UUID,
        knight_id: UUID,
        status: ReferralStatus = ReferralStatus.ASSIGNED,
    ) -> None:
        """Configure a referral's assignment for authorization testing.

        Args:
            referral_id: The referral UUID.
            knight_id: The assigned knight UUID.
            status: The referral status.
        """
        self._assignments[referral_id] = knight_id
        self._statuses[referral_id] = status
        self._existing_referrals.add(referral_id)

    def set_referral_exists(self, referral_id: UUID, exists: bool = True) -> None:
        """Configure whether a referral exists.

        Args:
            referral_id: The referral UUID.
            exists: Whether the referral exists.
        """
        if exists:
            self._existing_referrals.add(referral_id)
        else:
            self._existing_referrals.discard(referral_id)

    def set_status(self, referral_id: UUID, status: ReferralStatus) -> None:
        """Configure a referral's status.

        Args:
            referral_id: The referral UUID.
            status: The referral status.
        """
        self._statuses[referral_id] = status
        self._existing_referrals.add(referral_id)

    async def build(
        self,
        referral_id: UUID,
        requester_id: UUID,
    ) -> DecisionPackage:
        """Build a decision package for a referral.

        Args:
            referral_id: The referral to build a package for.
            requester_id: The UUID of the requester (must be assigned Knight).

        Returns:
            The assembled DecisionPackage with all context.

        Raises:
            DecisionPackageNotFoundError: Referral doesn't exist.
            UnauthorizedPackageAccessError: Requester is not the assigned Knight.
            ReferralNotAssignedError: Referral is not in ASSIGNED or IN_REVIEW state.
        """
        self._build_calls.append((referral_id, requester_id))

        # Check if referral exists
        if referral_id not in self._existing_referrals:
            raise DecisionPackageNotFoundError(referral_id=referral_id)

        # Check referral status
        status = self._statuses.get(referral_id, ReferralStatus.PENDING)
        if status not in (ReferralStatus.ASSIGNED, ReferralStatus.IN_REVIEW):
            raise ReferralNotAssignedError(
                referral_id=referral_id,
                current_status=status.value,
            )

        # Check authorization
        assigned_knight = self._assignments.get(referral_id)
        if assigned_knight is None:
            raise UnauthorizedPackageAccessError(
                referral_id=referral_id,
                requester_id=requester_id,
                reason="Referral has no assigned Knight",
            )

        if requester_id != assigned_knight:
            raise UnauthorizedPackageAccessError(
                referral_id=referral_id,
                requester_id=requester_id,
                assigned_knight_id=assigned_knight,
            )

        # Return configured package or generate a default one
        key = (referral_id, requester_id)
        if key in self._packages:
            return self._packages[key]

        # Generate a default package
        now = datetime.now(timezone.utc)
        return DecisionPackage(
            referral_id=referral_id,
            petition_id=UUID("00000000-0000-0000-0000-000000000001"),
            realm_id=UUID("00000000-0000-0000-0000-000000000002"),
            assigned_knight_id=requester_id,
            deadline=now,
            status=status,
            extensions_granted=0,
            can_extend=True,
            petition_text="Default petition text for testing",
            petition_type=PetitionType.GENERAL,
            petition_created_at=now,
            submitter_id=None,
            co_signer_count=0,
            built_at=now,
        )

    def get_build_calls(self) -> list[tuple[UUID, UUID]]:
        """Return list of build calls made for verification."""
        return self._build_calls.copy()

    def clear(self) -> None:
        """Clear all stored data. For testing only."""
        self._packages.clear()
        self._assignments.clear()
        self._statuses.clear()
        self._existing_referrals.clear()
        self._build_calls.clear()
