"""Knight concurrent referral limit protocol (Story 4.7, FR-4.7, NFR-7.3).

This module defines the protocol for enforcing maximum concurrent referrals
per Knight to prevent workload overload.

Constitutional Constraints:
- FR-4.7: System SHALL enforce max concurrent referrals per Knight
- NFR-7.3: Referral load balancing - max concurrent per Knight configurable

Developer Golden Rules:
1. FAIR ASSIGNMENT - Distribute referrals across eligible Knights
2. RESPECT LIMITS - Never exceed realm knight_capacity
3. DEFER GRACEFULLY - When no Knights available, keep referral PENDING
4. READS DURING HALT - Eligibility queries work during halt (CT-13)
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.domain.models.referral import Referral


@dataclass(frozen=True)
class KnightEligibilityResult:
    """Result of Knight eligibility check for referral assignment.

    Attributes:
        knight_id: The Knight's archon UUID.
        is_eligible: Whether Knight can accept new referrals.
        current_count: Current number of active referrals.
        max_allowed: Maximum allowed concurrent referrals (from realm).
        reason: Explanation if not eligible.
    """

    knight_id: UUID
    is_eligible: bool
    current_count: int
    max_allowed: int
    reason: str | None = None


@dataclass(frozen=True)
class AssignmentResult:
    """Result of attempting to assign a referral to a Knight.

    Attributes:
        success: Whether assignment was successful.
        assigned_knight_id: Knight who was assigned (if successful).
        referral: The updated referral (if successful).
        deferred_reason: Why assignment was deferred (if unsuccessful).
        all_knights_at_capacity: True if all Knights in realm are at capacity.
    """

    success: bool
    assigned_knight_id: UUID | None = None
    referral: Referral | None = None
    deferred_reason: str | None = None
    all_knights_at_capacity: bool = False


class KnightConcurrentLimitProtocol(Protocol):
    """Protocol for Knight concurrent referral limit enforcement (FR-4.7).

    This protocol defines the contract for checking and enforcing
    concurrent referral limits per Knight. The limit is configurable
    per realm via RealmRegistry.knight_capacity.

    The service handles:
    1. Checking if a Knight is eligible for new referrals
    2. Finding eligible Knights in a realm
    3. Assigning referrals to eligible Knights
    4. Tracking concurrent referral counts

    Constitutional Constraints:
    - FR-4.7: System SHALL enforce max concurrent referrals per Knight
    - NFR-7.3: Max concurrent per Knight configurable via RealmRegistry
    """

    @abstractmethod
    async def check_knight_eligibility(
        self,
        knight_id: UUID,
        realm_id: UUID,
    ) -> KnightEligibilityResult:
        """Check if a Knight is eligible for new referral assignment.

        A Knight is eligible if their current active referral count
        is below the realm's knight_capacity limit.

        Args:
            knight_id: The Knight's archon UUID.
            realm_id: The realm for capacity lookup.

        Returns:
            KnightEligibilityResult with eligibility status and details.

        Raises:
            RealmNotFoundError: If realm_id is invalid.
            KnightNotFoundError: If knight_id is not a valid Knight.
        """
        ...

    @abstractmethod
    async def find_eligible_knights(
        self,
        realm_id: UUID,
        limit: int = 10,
    ) -> list[UUID]:
        """Find Knights eligible for new referral assignment in a realm.

        Returns Knights sorted by current workload (ascending) to
        distribute referrals fairly.

        Args:
            realm_id: The realm to search for Knights.
            limit: Maximum number of Knights to return.

        Returns:
            List of Knight UUIDs who can accept new referrals,
            sorted by lowest current workload first.

        Raises:
            RealmNotFoundError: If realm_id is invalid.
        """
        ...

    @abstractmethod
    async def assign_to_eligible_knight(
        self,
        referral_id: UUID,
        realm_id: UUID,
        preferred_knight_id: UUID | None = None,
    ) -> AssignmentResult:
        """Attempt to assign a referral to an eligible Knight.

        If preferred_knight_id is provided and eligible, assigns to them.
        Otherwise finds the Knight with lowest current workload.
        If no Knights are eligible, returns deferred result.

        Args:
            referral_id: The referral to assign.
            realm_id: The realm for Knight selection.
            preferred_knight_id: Optional preferred Knight (if eligible).

        Returns:
            AssignmentResult indicating success or deferral.

        Raises:
            ReferralNotFoundError: If referral_id is invalid.
            ReferralAlreadyAssignedError: If referral is already assigned.
            RealmNotFoundError: If realm_id is invalid.
        """
        ...

    @abstractmethod
    async def get_knight_workload(
        self,
        knight_id: UUID,
    ) -> int:
        """Get current active referral count for a Knight.

        Active referrals include ASSIGNED and IN_REVIEW statuses.

        Args:
            knight_id: The Knight's archon UUID.

        Returns:
            Number of active referrals assigned to the Knight.
        """
        ...

    @abstractmethod
    async def get_realm_workload_summary(
        self,
        realm_id: UUID,
    ) -> dict[UUID, int]:
        """Get workload summary for all Knights in a realm.

        Useful for monitoring and load balancing decisions.

        Args:
            realm_id: The realm UUID.

        Returns:
            Dict mapping Knight UUID to active referral count.

        Raises:
            RealmNotFoundError: If realm_id is invalid.
        """
        ...


class KnightRegistryProtocol(Protocol):
    """Protocol for Knight registry operations.

    Provides access to Knight information for referral assignment.
    """

    @abstractmethod
    async def get_knights_in_realm(
        self,
        realm_id: UUID,
    ) -> list[UUID]:
        """Get all Knights assigned to a realm.

        Args:
            realm_id: The realm UUID.

        Returns:
            List of Knight archon UUIDs in the realm.
        """
        ...

    @abstractmethod
    async def is_knight(
        self,
        archon_id: UUID,
    ) -> bool:
        """Check if an archon is a Knight.

        Args:
            archon_id: The archon UUID.

        Returns:
            True if archon has Knight role, False otherwise.
        """
        ...

    @abstractmethod
    async def get_knight_realm(
        self,
        knight_id: UUID,
    ) -> UUID | None:
        """Get the realm a Knight is assigned to.

        Args:
            knight_id: The Knight's archon UUID.

        Returns:
            Realm UUID if Knight is assigned, None otherwise.
        """
        ...
