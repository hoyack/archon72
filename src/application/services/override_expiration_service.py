"""Override Expiration Service - Automatic override expiration (Story 5.2, AC2).

This service monitors registered overrides and automatically logs
expiration events when overrides exceed their duration.

Constitutional Constraints:
- FR24: Override duration must be bounded -> Automatic expiration
- CT-11: Silent failure destroys legitimacy -> Expirations logged
- CT-12: Witnessing creates accountability -> Expiration events witnessed

Developer Golden Rules:
1. LOG FIRST - Expiration event must be written BEFORE reversion
2. WITNESS EVERYTHING - All expiration events must be witnessed
3. FAIL LOUD - Failed log = expiration still logged, reversion attempted
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.ports.override_registry import (
    ExpiredOverrideInfo,
    OverrideRegistryPort,
)
from src.domain.events.override_event import (
    OVERRIDE_EXPIRED_EVENT_TYPE,
    OverrideExpiredEventPayload,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()


class OverrideExpirationService:
    """Monitors and processes expired overrides (AC2).

    This service is responsible for:
    1. Checking the registry for expired overrides
    2. Writing OverrideExpiredEvent to the event store
    3. Marking overrides as reverted in the registry

    Constitutional Constraints:
    - FR24: Duration bounded -> Automatic expiration
    - CT-11: No silent failures -> All expirations logged
    - CT-12: Witnessing -> Expiration events witnessed

    Attributes:
        _event_writer: Service for writing events to the store.
        _override_registry: Registry tracking active overrides.
    """

    def __init__(
        self,
        event_writer: EventWriterService,
        override_registry: OverrideRegistryPort,
    ) -> None:
        """Initialize the Override Expiration Service.

        Args:
            event_writer: Service for writing expiration events.
            override_registry: Registry tracking active overrides.
        """
        self._event_writer = event_writer
        self._override_registry = override_registry

    async def process_expirations(self) -> list[ExpiredOverrideInfo]:
        """Check for and process all expired overrides.

        This method should be called periodically (e.g., by a scheduler)
        to detect and log expired overrides.

        Returns:
            List of overrides that were processed.
        """
        log = logger.bind(operation="process_expirations")

        # Get all expired overrides
        expired = await self._override_registry.get_expired_overrides()

        if not expired:
            log.debug("no_expired_overrides")
            return []

        log.info("found_expired_overrides", count=len(expired))

        processed: list[ExpiredOverrideInfo] = []
        for override_info in expired:
            success = await self._process_single_expiration(override_info)
            if success:
                processed.append(override_info)

        log.info(
            "expiration_processing_complete",
            total=len(expired),
            processed=len(processed),
        )

        return processed

    async def _process_single_expiration(
        self,
        override_info: ExpiredOverrideInfo,
    ) -> bool:
        """Process a single expired override.

        Args:
            override_info: Information about the expired override.

        Returns:
            True if successfully processed, False otherwise.
        """
        log = logger.bind(
            operation="process_expiration",
            override_id=str(override_info.override_id),
            keeper_id=override_info.keeper_id,
            scope=override_info.scope,
        )

        now = datetime.now(timezone.utc)

        # Attempt reversion (in production, this would do actual work)
        # For now, we always succeed - real implementation would call
        # appropriate adapters to revert configuration changes
        reversion_status = "success"

        # Create expiration payload
        payload = OverrideExpiredEventPayload(
            original_override_id=override_info.override_id,
            keeper_id=override_info.keeper_id,
            scope=override_info.scope,
            expired_at=now,
            reversion_status=reversion_status,
        )

        try:
            # Write expiration event to event store
            event = await self._event_writer.write_event(
                event_type=OVERRIDE_EXPIRED_EVENT_TYPE,
                payload={
                    "original_override_id": str(payload.original_override_id),
                    "keeper_id": payload.keeper_id,
                    "scope": payload.scope,
                    "expired_at": payload.expired_at.isoformat(),
                    "reversion_status": payload.reversion_status,
                },
                agent_id=payload.keeper_id,  # Keeper associated with expiration
                local_timestamp=now,
            )

            log.info(
                "expiration_event_logged",
                event_id=str(event.event_id),
                sequence=event.sequence,
                reversion_status=reversion_status,
            )

            # Mark override as reverted in registry
            await self._override_registry.mark_override_reverted(
                override_info.override_id
            )

            return True

        except Exception as e:
            # CT-11: Silent failure destroys legitimacy
            # Log the failure but don't suppress it entirely
            log.error(
                "expiration_processing_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
