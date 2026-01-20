"""Knight concurrent referral limit service (Story 4.7, FR-4.7, NFR-7.3).

This module implements the KnightConcurrentLimitProtocol for enforcing
maximum concurrent referrals per Knight.

Constitutional Constraints:
- FR-4.7: System SHALL enforce max concurrent referrals per Knight
- NFR-7.3: Referral load balancing - max concurrent per Knight configurable
- CT-12: Every action that affects an Archon must be witnessed

Developer Golden Rules:
1. FAIR ASSIGNMENT - Distribute referrals across eligible Knights
2. RESPECT LIMITS - Never exceed realm knight_capacity
3. DEFER GRACEFULLY - When no Knights available, keep referral PENDING
4. WITNESS EVERYTHING - All assignments require attribution (CT-12)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.knight_concurrent_limit import (
    AssignmentResult,
    KnightEligibilityResult,
)
from src.domain.errors.knight_concurrent_limit import (
    KnightAtCapacityError,
    KnightNotFoundError,
    KnightNotInRealmError,
    NoEligibleKnightsError,
    ReferralAlreadyAssignedError,
)
from src.domain.events.referral import (
    REFERRAL_EVENT_SCHEMA_VERSION,
    ReferralAssignedEvent,
    ReferralDeferredEvent,
)
from src.domain.models.referral import ReferralStatus

if TYPE_CHECKING:
    from src.application.ports.content_hash_service import ContentHashServiceProtocol
    from src.application.ports.event_writer import EventWriterProtocol
    from src.application.ports.knight_concurrent_limit import KnightRegistryProtocol
    from src.application.ports.realm_registry import RealmRegistryProtocol
    from src.application.ports.referral_execution import ReferralRepositoryProtocol

logger = get_logger(__name__)


class KnightConcurrentLimitService:
    """Service for Knight concurrent referral limit enforcement (Story 4.7).

    Implements fair referral assignment by checking Knight workloads
    against realm capacity limits. When all Knights are at capacity,
    referrals are deferred (remain PENDING).

    The service ensures:
    1. Knights don't exceed realm knight_capacity (FR-4.7)
    2. Referrals go to least-loaded eligible Knights (NFR-7.3)
    3. All assignments/deferrals are witnessed (CT-12)
    4. Deferred referrals remain PENDING for retry

    Example:
        >>> service = KnightConcurrentLimitService(
        ...     referral_repo=referral_repo,
        ...     knight_registry=knight_registry,
        ...     realm_registry=realm_registry,
        ...     event_writer=event_writer,
        ...     hash_service=hash_service,
        ... )
        >>> result = await service.assign_to_eligible_knight(
        ...     referral_id=referral.referral_id,
        ...     realm_id=realm.id,
        ... )
    """

    def __init__(
        self,
        referral_repo: ReferralRepositoryProtocol,
        knight_registry: KnightRegistryProtocol,
        realm_registry: RealmRegistryProtocol,
        event_writer: EventWriterProtocol,
        hash_service: ContentHashServiceProtocol,
    ) -> None:
        """Initialize the Knight concurrent limit service.

        Args:
            referral_repo: Repository for referral persistence
            knight_registry: Registry for Knight lookups
            realm_registry: Registry for realm capacity lookups
            event_writer: Service for event emission and witnessing
            hash_service: Service for generating witness hashes
        """
        self._referral_repo = referral_repo
        self._knight_registry = knight_registry
        self._realm_registry = realm_registry
        self._event_writer = event_writer
        self._hash_service = hash_service

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
        log = logger.bind(knight_id=str(knight_id), realm_id=str(realm_id))
        log.debug("Checking Knight eligibility")

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

        log.info(
            "Knight eligibility checked",
            is_eligible=is_eligible,
            current_count=current_count,
            max_allowed=max_allowed,
        )

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
        log = logger.bind(realm_id=str(realm_id), limit=limit)
        log.debug("Finding eligible Knights")

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
        for knight_id in all_knights:
            count = await self._referral_repo.count_active_by_knight(knight_id)
            if count < max_allowed:
                knight_workloads.append((knight_id, count))

        # Sort by workload (ascending) for fair distribution
        knight_workloads.sort(key=lambda x: x[1])

        # Return limited list of Knight IDs
        eligible = [kid for kid, _ in knight_workloads[:limit]]

        log.info(
            "Found eligible Knights",
            total_knights=len(all_knights),
            eligible_count=len(eligible),
        )

        return eligible

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
        log = logger.bind(
            referral_id=str(referral_id),
            realm_id=str(realm_id),
            preferred_knight_id=str(preferred_knight_id) if preferred_knight_id else None,
        )
        log.info("Attempting referral assignment")

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
            log.warning(
                "Referral not in PENDING status",
                current_status=referral.status.value,
            )
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

        # Try preferred Knight first if provided
        selected_knight_id: UUID | None = None
        workload_before: int = 0

        if preferred_knight_id:
            try:
                eligibility = await self.check_knight_eligibility(
                    preferred_knight_id, realm_id
                )
                if eligibility.is_eligible:
                    selected_knight_id = preferred_knight_id
                    workload_before = eligibility.current_count
                    log.info("Using preferred Knight", knight_id=str(preferred_knight_id))
            except (KnightNotFoundError, KnightNotInRealmError) as e:
                log.warning("Preferred Knight not eligible", error=str(e))

        # Find least-loaded eligible Knight if no preferred
        if selected_knight_id is None:
            eligible_knights = await self.find_eligible_knights(realm_id, limit=1)
            if eligible_knights:
                selected_knight_id = eligible_knights[0]
                workload_before = await self._referral_repo.count_active_by_knight(
                    selected_knight_id
                )
                log.info("Selected least-loaded Knight", knight_id=str(selected_knight_id))

        # If no eligible Knights, defer
        if selected_knight_id is None:
            return await self._handle_deferral(
                referral=referral,
                realm_id=realm_id,
                max_allowed=max_allowed,
            )

        # Assign to selected Knight
        return await self._execute_assignment(
            referral=referral,
            knight_id=selected_knight_id,
            realm_id=realm_id,
            workload_before=workload_before,
            max_allowed=max_allowed,
        )

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
        return await self._referral_repo.count_active_by_knight(knight_id)

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

    async def _execute_assignment(
        self,
        referral: "Referral",
        knight_id: UUID,
        realm_id: UUID,
        workload_before: int,
        max_allowed: int,
    ) -> AssignmentResult:
        """Execute the referral assignment to a Knight.

        Updates the referral with assignment and emits witnessed event.

        Args:
            referral: The referral to assign.
            knight_id: The Knight to assign to.
            realm_id: The realm for the assignment.
            workload_before: Knight's workload before assignment.
            max_allowed: Realm's knight_capacity.

        Returns:
            Successful AssignmentResult.
        """
        from src.domain.models.referral import Referral

        log = logger.bind(
            referral_id=str(referral.referral_id),
            knight_id=str(knight_id),
        )

        # Update referral with assignment (transitions to ASSIGNED)
        updated_referral = referral.with_assignment(knight_id)
        await self._referral_repo.update(updated_referral)

        # Generate witness hash (CT-12)
        now = datetime.now(timezone.utc)
        witness_content = self._build_assignment_witness_content(
            referral_id=referral.referral_id,
            petition_id=referral.petition_id,
            knight_id=knight_id,
            realm_id=realm_id,
            assigned_at=now,
        )
        witness_hash_bytes = self._hash_service.hash_text(witness_content)
        witness_hash = f"blake3:{witness_hash_bytes.hex()}"

        # Emit assignment event
        event = ReferralAssignedEvent(
            event_id=uuid4(),
            referral_id=referral.referral_id,
            petition_id=referral.petition_id,
            knight_id=knight_id,
            realm_id=realm_id,
            knight_workload_before=workload_before,
            knight_workload_after=workload_before + 1,
            realm_capacity=max_allowed,
            witness_hash=witness_hash,
            emitted_at=now,
        )
        await self._event_writer.write(event.to_dict())

        log.info(
            "Referral assigned successfully",
            workload_before=workload_before,
            workload_after=workload_before + 1,
            witness_hash=witness_hash,
        )

        return AssignmentResult(
            success=True,
            assigned_knight_id=knight_id,
            referral=updated_referral,
        )

    async def _handle_deferral(
        self,
        referral: "Referral",
        realm_id: UUID,
        max_allowed: int,
    ) -> AssignmentResult:
        """Handle deferral when no Knights are eligible.

        Emits deferral event and returns deferred result.
        Referral remains in PENDING status.

        Args:
            referral: The referral to defer.
            realm_id: The realm with no eligible Knights.
            max_allowed: Realm's knight_capacity.

        Returns:
            Deferred AssignmentResult.
        """
        log = logger.bind(
            referral_id=str(referral.referral_id),
            realm_id=str(realm_id),
        )

        # Get Knight counts for event
        all_knights = await self._knight_registry.get_knights_in_realm(realm_id)
        total_knights = len(all_knights)
        knights_at_capacity = total_knights  # All are at capacity if we got here

        reason = f"All {total_knights} Knights in realm at capacity ({max_allowed} max)"

        # Generate witness hash (CT-12)
        now = datetime.now(timezone.utc)
        witness_content = self._build_deferral_witness_content(
            referral_id=referral.referral_id,
            petition_id=referral.petition_id,
            realm_id=realm_id,
            total_knights=total_knights,
            deferred_at=now,
        )
        witness_hash_bytes = self._hash_service.hash_text(witness_content)
        witness_hash = f"blake3:{witness_hash_bytes.hex()}"

        # Emit deferral event
        event = ReferralDeferredEvent(
            event_id=uuid4(),
            referral_id=referral.referral_id,
            petition_id=referral.petition_id,
            realm_id=realm_id,
            total_knights=total_knights,
            knights_at_capacity=knights_at_capacity,
            realm_capacity=max_allowed,
            reason=reason,
            witness_hash=witness_hash,
            emitted_at=now,
        )
        await self._event_writer.write(event.to_dict())

        log.info(
            "Referral assignment deferred",
            total_knights=total_knights,
            knights_at_capacity=knights_at_capacity,
            reason=reason,
            witness_hash=witness_hash,
        )

        return AssignmentResult(
            success=False,
            deferred_reason=reason,
            all_knights_at_capacity=True,
        )

    def _build_assignment_witness_content(
        self,
        referral_id: UUID,
        petition_id: UUID,
        knight_id: UUID,
        realm_id: UUID,
        assigned_at: datetime,
    ) -> str:
        """Build content string for assignment witness hash generation.

        Creates a deterministic string representation for hashing
        per CT-12 witnessing requirements.

        Args:
            referral_id: UUID for the referral
            petition_id: Petition being referred
            knight_id: Knight being assigned
            realm_id: Target realm
            assigned_at: Assignment timestamp

        Returns:
            Deterministic string for hashing
        """
        parts = [
            f"referral_id:{referral_id}",
            f"petition_id:{petition_id}",
            f"knight_id:{knight_id}",
            f"realm_id:{realm_id}",
            f"assigned_at:{assigned_at.isoformat()}",
            f"action:assignment",
            f"schema_version:{REFERRAL_EVENT_SCHEMA_VERSION}",
        ]
        return "|".join(parts)

    def _build_deferral_witness_content(
        self,
        referral_id: UUID,
        petition_id: UUID,
        realm_id: UUID,
        total_knights: int,
        deferred_at: datetime,
    ) -> str:
        """Build content string for deferral witness hash generation.

        Creates a deterministic string representation for hashing
        per CT-12 witnessing requirements.

        Args:
            referral_id: UUID for the referral
            petition_id: Petition being referred
            realm_id: Target realm
            total_knights: Number of Knights in realm
            deferred_at: Deferral timestamp

        Returns:
            Deterministic string for hashing
        """
        parts = [
            f"referral_id:{referral_id}",
            f"petition_id:{petition_id}",
            f"realm_id:{realm_id}",
            f"total_knights:{total_knights}",
            f"deferred_at:{deferred_at.isoformat()}",
            f"action:deferral",
            f"schema_version:{REFERRAL_EVENT_SCHEMA_VERSION}",
        ]
        return "|".join(parts)
