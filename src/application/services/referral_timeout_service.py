"""Referral timeout service implementation (Story 4.6, FR-4.5).

This module implements the ReferralTimeoutProtocol for processing
referral timeout jobs when Knights fail to submit recommendations.

Constitutional Constraints:
- FR-4.5: System SHALL auto-ACKNOWLEDGE on referral timeout (reason: EXPIRED)
- NFR-3.4: Referral timeout reliability: 100% timeouts fire
- NFR-4.4: Referral deadline persistence: Survives scheduler restart
- CT-12: Every action that affects an Archon must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before modifying referrals (writes)
2. WITNESS EVERYTHING - All timeout events require attribution
3. FAIL LOUD - Never silently swallow timeout errors
4. READS DURING HALT - Referral queries work during halt (CT-13)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.referral_timeout import (
    ReferralTimeoutAction,
    ReferralTimeoutAcknowledgeError,
    ReferralTimeoutResult,
    ReferralTimeoutWitnessError,
)
from src.domain.events.referral import (
    REFERRAL_EVENT_SCHEMA_VERSION,
    ReferralExpiredEvent,
)
from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode
from src.domain.models.referral import ReferralStatus

if TYPE_CHECKING:
    from src.application.ports.acknowledgment_execution import (
        AcknowledgmentExecutionProtocol,
    )
    from src.application.ports.content_hash import ContentHashProtocol
    from src.application.ports.event_writer import EventWriterProtocol
    from src.application.ports.realm_registry import RealmRegistryProtocol
    from src.application.ports.referral_execution import ReferralRepositoryProtocol

logger = get_logger(__name__)

# System archon IDs used for auto-acknowledge (FR-4.5 exemption)
# EXPIRED acknowledgments don't have deliberating archons - they're system-generated
SYSTEM_ARCHON_IDS: tuple[int, ...] = ()


class ReferralTimeoutService:
    """Service for processing referral timeouts (Story 4.6, FR-4.5).

    Handles referral timeout jobs fired by the job scheduler when a Knight
    fails to submit a recommendation before the deadline. Coordinates:
    1. Referral expiration (status -> EXPIRED)
    2. Auto-acknowledge with EXPIRED reason code
    3. Event emission with witness hashes

    The service ensures idempotency - multiple calls for the same referral
    will result in no-op responses after the first successful processing.

    Example:
        >>> service = ReferralTimeoutService(
        ...     referral_repo=referral_repo,
        ...     acknowledgment_service=ack_service,
        ...     event_writer=event_writer,
        ...     hash_service=hash_service,
        ...     realm_registry=realm_registry,
        ... )
        >>> result = await service.process_timeout(
        ...     referral_id=referral.referral_id,
        ...     petition_id=referral.petition_id,
        ...     realm_id=referral.realm_id,
        ... )
        >>> if result.was_processed:
        ...     print(f"Auto-acknowledged petition {result.petition_id}")
    """

    def __init__(
        self,
        referral_repo: ReferralRepositoryProtocol,
        acknowledgment_service: AcknowledgmentExecutionProtocol,
        event_writer: EventWriterProtocol,
        hash_service: ContentHashProtocol,
        realm_registry: RealmRegistryProtocol,
    ) -> None:
        """Initialize the referral timeout service.

        Args:
            referral_repo: Repository for referral persistence.
            acknowledgment_service: Service for executing auto-acknowledge.
            event_writer: Service for event emission and witnessing.
            hash_service: Service for generating witness hashes.
            realm_registry: Service for looking up realm names.
        """
        self._referral_repo = referral_repo
        self._acknowledgment_service = acknowledgment_service
        self._event_writer = event_writer
        self._hash_service = hash_service
        self._realm_registry = realm_registry

    async def process_timeout(
        self,
        referral_id: UUID,
        petition_id: UUID,
        realm_id: UUID,
    ) -> ReferralTimeoutResult:
        """Process a referral timeout.

        Called when a referral deadline job fires. Handles the full
        timeout flow including expiration, auto-acknowledge, and events.

        Idempotency: Safe to call multiple times. Returns no-op result
        if referral is already in terminal state.

        Args:
            referral_id: UUID of the referral to timeout.
            petition_id: UUID of the associated petition.
            realm_id: UUID of the realm for rationale generation.

        Returns:
            ReferralTimeoutResult describing the outcome.

        Raises:
            ReferralTimeoutWitnessError: If witness hash generation fails.
            ReferralTimeoutAcknowledgeError: If auto-acknowledge fails.
        """
        log = logger.bind(
            referral_id=str(referral_id),
            petition_id=str(petition_id),
            realm_id=str(realm_id),
        )
        log.info("Processing referral timeout")

        # Step 1: Retrieve referral and check current state
        referral = await self._referral_repo.get_by_id(referral_id)

        if referral is None:
            log.warning("Referral not found for timeout processing")
            return ReferralTimeoutResult(
                referral_id=referral_id,
                petition_id=petition_id,
                action=ReferralTimeoutAction.NOT_FOUND,
                message=f"Referral {referral_id} not found",
            )

        # Step 2: Check if already in terminal state (idempotency)
        if referral.status == ReferralStatus.COMPLETED:
            log.info(
                "Referral already completed, skipping timeout",
                recommendation=referral.recommendation.value if referral.recommendation else None,
            )
            return ReferralTimeoutResult(
                referral_id=referral_id,
                petition_id=petition_id,
                action=ReferralTimeoutAction.ALREADY_COMPLETED,
                message="Referral was completed before timeout",
            )

        if referral.status == ReferralStatus.EXPIRED:
            log.info("Referral already expired, skipping duplicate timeout")
            return ReferralTimeoutResult(
                referral_id=referral_id,
                petition_id=petition_id,
                action=ReferralTimeoutAction.ALREADY_EXPIRED,
                message="Referral was already expired",
            )

        # Step 3: Get realm name for rationale
        realm = self._realm_registry.get_realm_by_id(realm_id)
        realm_name = realm.name if realm else str(realm_id)

        # Step 4: Generate rationale for auto-acknowledge
        rationale = self._build_expired_rationale(realm_name)

        # Step 5: Process timestamp
        expired_at = datetime.now(timezone.utc)

        # Step 6: Generate witness hash for expiration (CT-12)
        try:
            witness_content = self._build_witness_content(
                referral_id=referral_id,
                petition_id=petition_id,
                realm_id=realm_id,
                expired_at=expired_at,
            )
            witness_hash = await self._hash_service.compute_hash(witness_content)
        except Exception as e:
            raise ReferralTimeoutWitnessError(
                referral_id=referral_id,
                petition_id=petition_id,
                reason=str(e),
            ) from e

        # Step 7: Expire the referral
        expired_referral = referral.with_expired()
        await self._referral_repo.save(expired_referral)

        log.info(
            "Referral expired",
            previous_status=referral.status.value,
        )

        # Step 8: Emit ReferralExpiredEvent (CT-12)
        expired_event = ReferralExpiredEvent(
            event_id=uuid4(),
            referral_id=referral_id,
            petition_id=petition_id,
            realm_id=realm_id,
            deadline=referral.deadline,
            expired_at=expired_at,
            witness_hash=witness_hash,
        )
        await self._event_writer.write(expired_event.to_dict())

        # Step 9: Auto-acknowledge petition with EXPIRED reason
        try:
            acknowledgment = await self._acknowledgment_service.execute_system_acknowledge(
                petition_id=petition_id,
                reason_code=AcknowledgmentReasonCode.EXPIRED,
                rationale=rationale,
            )
            acknowledgment_id = acknowledgment.id
            log.info(
                "Auto-acknowledge completed",
                acknowledgment_id=str(acknowledgment_id),
            )
        except Exception as e:
            # Log but don't fail - referral is already expired
            # The acknowledgment can be retried or handled separately
            log.error(
                "Auto-acknowledge failed",
                error=str(e),
            )
            raise ReferralTimeoutAcknowledgeError(
                referral_id=referral_id,
                petition_id=petition_id,
                reason=str(e),
            ) from e

        log.info(
            "Referral timeout processing completed",
            witness_hash=witness_hash,
        )

        return ReferralTimeoutResult(
            referral_id=referral_id,
            petition_id=petition_id,
            action=ReferralTimeoutAction.EXPIRED,
            acknowledgment_id=acknowledgment_id,
            expired_at=expired_at,
            witness_hash=witness_hash,
            rationale=rationale,
            message=f"Referral expired and petition auto-acknowledged with reason EXPIRED",
        )

    async def handle_expired_referral(
        self,
        referral_id: UUID,
    ) -> bool:
        """Check if a referral has been handled for timeout.

        Args:
            referral_id: UUID of the referral to check.

        Returns:
            True if referral is in terminal state (COMPLETED or EXPIRED).
            False if referral still needs timeout processing.
        """
        referral = await self._referral_repo.get_by_id(referral_id)
        if referral is None:
            return True  # Not found, treat as handled

        return referral.status.is_terminal()

    def _build_expired_rationale(self, realm_name: str) -> str:
        """Build the auto-acknowledge rationale for expired referrals.

        Args:
            realm_name: Name of the realm the petition was referred to.

        Returns:
            Rationale string for the EXPIRED acknowledgment.
        """
        return f"Referral to {realm_name} expired without Knight response"

    def _build_witness_content(
        self,
        referral_id: UUID,
        petition_id: UUID,
        realm_id: UUID,
        expired_at: datetime,
    ) -> str:
        """Build content string for witness hash generation.

        Creates a deterministic string representation of the expiration
        for hashing per CT-12 witnessing requirements.

        Args:
            referral_id: UUID for the referral.
            petition_id: Petition being expired.
            realm_id: Target realm.
            expired_at: Expiration timestamp.

        Returns:
            Deterministic string for hashing.
        """
        parts = [
            f"referral_id:{referral_id}",
            f"petition_id:{petition_id}",
            f"realm_id:{realm_id}",
            f"expired_at:{expired_at.isoformat()}",
            f"schema_version:{REFERRAL_EVENT_SCHEMA_VERSION}",
        ]
        return "|".join(parts)
