"""In-memory stub implementation of KnightConcurrentLimitProtocol (Story 4.7).

This module provides an in-memory implementation for testing purposes.
Not intended for production use.

Constitutional Constraints:
- FR-4.7: System SHALL enforce max concurrent referrals per Knight
- NFR-7.3: Referral load balancing - max concurrent per Knight configurable
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.application.ports.knight_concurrent_limit import (
    AssignmentResult,
    KnightEligibilityResult,
)
from src.domain.errors.knight_concurrent_limit import (
    KnightNotFoundError,
    KnightNotInRealmError,
    ReferralAlreadyAssignedError,
)
from src.domain.models.referral import ReferralStatus

if TYPE_CHECKING:
    from src.infrastructure.stubs.knight_registry_stub import KnightRegistryStub
    from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub
    from src.infrastructure.stubs.referral_repository_stub import ReferralRepositoryStub


class KnightConcurrentLimitStub:
    """In-memory implementation of KnightConcurrentLimitProtocol.

    Provides concurrent limit enforcement using in-memory stubs.
    Useful for testing without full service infrastructure.

    Example:
        >>> stub = KnightConcurrentLimitStub(
        ...     referral_repo=referral_stub,
        ...     knight_registry=knight_stub,
        ...     realm_registry=realm_stub,
        ... )
        >>> result = await stub.assign_to_eligible_knight(
        ...     referral_id=referral_id,
        ...     realm_id=realm_id,
        ... )
    """

    def __init__(
        self,
        referral_repo: ReferralRepositoryStub,
        knight_registry: KnightRegistryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Initialize the stub.

        Args:
            referral_repo: Stub for referral persistence.
            knight_registry: Stub for Knight lookups.
            realm_registry: Stub for realm capacity lookups.
        """
        self._referral_repo = referral_repo
        self._knight_registry = knight_registry
        self._realm_registry = realm_registry

    async def check_knight_eligibility(
        self,
        knight_id: UUID,
        realm_id: UUID,
    ) -> KnightEligibilityResult:
        """Check if a Knight is eligible for new referral assignment."""
        # Validate Knight exists
        is_knight = await self._knight_registry.is_knight(knight_id)
        if not is_knight:
            raise KnightNotFoundError(knight_id=knight_id)

        # Validate Knight is in the realm
        knight_realm = await self._knight_registry.get_knight_realm(knight_id)
        if knight_realm != realm_id:
            raise KnightNotInRealmError(
                knight_id=knight_id,
                realm_id=realm_id,
                actual_realm_id=knight_realm,
            )

        # Get realm capacity
        realm = self._realm_registry.get_realm_by_id(realm_id)
        if realm is None:
            from src.domain.errors.referral import InvalidRealmError

            raise InvalidRealmError(realm_id=realm_id)

        max_allowed = realm.knight_capacity

        # Get current workload
        current_count = await self._referral_repo.count_active_by_knight(knight_id)

        # Check eligibility
        is_eligible = current_count < max_allowed
        reason = None if is_eligible else f"At capacity ({current_count}/{max_allowed})"

        return KnightEligibilityResult(
            knight_id=knight_id,
            is_eligible=is_eligible,
            current_count=current_count,
            max_allowed=max_allowed,
            reason=reason,
        )

    async def find_eligible_knights(
        self,
        realm_id: UUID,
        limit: int = 10,
    ) -> list[UUID]:
        """Find Knights eligible for new referral assignment in a realm."""
        # Get realm capacity
        realm = self._realm_registry.get_realm_by_id(realm_id)
        if realm is None:
            from src.domain.errors.referral import InvalidRealmError

            raise InvalidRealmError(realm_id=realm_id)

        max_allowed = realm.knight_capacity

        # Get all Knights in realm
        all_knights = await self._knight_registry.get_knights_in_realm(realm_id)

        # Get workloads and filter eligible
        knight_workloads: list[tuple[UUID, int]] = []
        for kid in all_knights:
            count = await self._referral_repo.count_active_by_knight(kid)
            if count < max_allowed:
                knight_workloads.append((kid, count))

        # Sort by workload (ascending)
        knight_workloads.sort(key=lambda x: x[1])

        return [kid for kid, _ in knight_workloads[:limit]]

    async def assign_to_eligible_knight(
        self,
        referral_id: UUID,
        realm_id: UUID,
        preferred_knight_id: UUID | None = None,
    ) -> AssignmentResult:
        """Attempt to assign a referral to an eligible Knight."""
        # Get referral
        referral = await self._referral_repo.get_by_id(referral_id)
        if referral is None:
            from src.domain.errors.referral import ReferralNotFoundError

            raise ReferralNotFoundError(referral_id=referral_id)

        # Check if already assigned
        if referral.assigned_knight_id is not None:
            raise ReferralAlreadyAssignedError(
                referral_id=referral_id,
                assigned_knight_id=referral.assigned_knight_id,
            )

        # Validate referral is in PENDING status
        if referral.status != ReferralStatus.PENDING:
            return AssignmentResult(
                success=False,
                deferred_reason=f"Referral status is {referral.status.value}, expected PENDING",
            )

        # Get realm capacity
        realm = self._realm_registry.get_realm_by_id(realm_id)
        if realm is None:
            from src.domain.errors.referral import InvalidRealmError

            raise InvalidRealmError(realm_id=realm_id)

        max_allowed = realm.knight_capacity

        # Try preferred Knight first
        selected_knight_id: UUID | None = None

        if preferred_knight_id:
            try:
                eligibility = await self.check_knight_eligibility(
                    preferred_knight_id, realm_id
                )
                if eligibility.is_eligible:
                    selected_knight_id = preferred_knight_id
            except (KnightNotFoundError, KnightNotInRealmError):
                pass

        # Find least-loaded eligible Knight
        if selected_knight_id is None:
            eligible = await self.find_eligible_knights(realm_id, limit=1)
            if eligible:
                selected_knight_id = eligible[0]

        # Defer if no eligible Knights
        if selected_knight_id is None:
            all_knights = await self._knight_registry.get_knights_in_realm(realm_id)
            total_knights = len(all_knights)
            reason = (
                f"All {total_knights} Knights in realm at capacity ({max_allowed} max)"
            )
            return AssignmentResult(
                success=False,
                deferred_reason=reason,
                all_knights_at_capacity=True,
            )

        # Assign to selected Knight
        updated_referral = referral.with_assignment(selected_knight_id)
        await self._referral_repo.update(updated_referral)

        return AssignmentResult(
            success=True,
            assigned_knight_id=selected_knight_id,
            referral=updated_referral,
        )

    async def get_knight_workload(
        self,
        knight_id: UUID,
    ) -> int:
        """Get current active referral count for a Knight."""
        return await self._referral_repo.count_active_by_knight(knight_id)

    async def get_realm_workload_summary(
        self,
        realm_id: UUID,
    ) -> dict[UUID, int]:
        """Get workload summary for all Knights in a realm."""
        # Validate realm exists
        realm = self._realm_registry.get_realm_by_id(realm_id)
        if realm is None:
            from src.domain.errors.referral import InvalidRealmError

            raise InvalidRealmError(realm_id=realm_id)

        # Get all Knights in realm
        knights = await self._knight_registry.get_knights_in_realm(realm_id)

        # Get workloads
        summary: dict[UUID, int] = {}
        for knight_id in knights:
            count = await self._referral_repo.count_active_by_knight(knight_id)
            summary[knight_id] = count

        return summary
