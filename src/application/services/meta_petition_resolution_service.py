"""META petition resolution service (Story 8.5, AC4).

This service handles High Archon resolution of META petitions with
one of three dispositions: ACKNOWLEDGE, CREATE_ACTION, or FORWARD.

Constitutional Constraints:
- FR-10.4: META petitions SHALL route to High Archon [P2]
- CT-12: Witnessing creates accountability -> All events witnessed
- CT-13: Explicit consent -> High Archon disposition is explicit action

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before any write operation
2. WITNESS EVERYTHING - Emit MetaPetitionResolved event on resolution
3. FAIL LOUD - Never silently swallow errors
4. VALIDATE EARLY - Check rationale and forward_target requirements
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.application.ports.meta_petition_event_emitter import (
    MetaPetitionEventEmitterProtocol,
)
from src.application.ports.meta_petition_queue_repository import (
    MetaPetitionAlreadyResolvedError,
    MetaPetitionNotFoundError,
    MetaPetitionQueueRepositoryProtocol,
)
from src.domain.events.meta_petition import (
    META_PETITION_RESOLVED_EVENT_TYPE,
    MetaPetitionResolvedEventPayload,
)
from src.domain.models.meta_petition import (
    MetaDisposition,
    MetaPetitionQueueItem,
)

logger = structlog.get_logger(__name__)

# Minimum rationale length required (AC4)
MIN_RATIONALE_LENGTH: int = 10


class MetaPetitionResolutionService:
    """High Archon resolution of META petitions (AC4).

    This service:
    1. Validates disposition and rationale
    2. Marks petition as resolved in queue
    3. Emits MetaPetitionResolved event

    Constitutional Compliance:
    - CT-13: Explicit consent through disposition selection
    - CT-12: Events witnessed for accountability

    Usage:
        service = MetaPetitionResolutionService(queue_repo, event_emitter)
        event = await service.resolve_meta_petition(
            petition_id=petition_id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Acknowledged the system feedback",
            high_archon_id=archon_id,
        )
    """

    def __init__(
        self,
        queue_repository: MetaPetitionQueueRepositoryProtocol,
        event_emitter: MetaPetitionEventEmitterProtocol | None = None,
    ) -> None:
        """Initialize the resolution service.

        Args:
            queue_repository: Repository for META petition queue operations.
            event_emitter: Optional event emitter for META petition events.
        """
        self._queue_repo = queue_repository
        self._event_emitter = event_emitter
        self._log = logger.bind(service="meta_petition_resolution")

    async def resolve_meta_petition(
        self,
        petition_id: UUID,
        disposition: MetaDisposition,
        rationale: str,
        high_archon_id: UUID,
        forward_target: str | None = None,
    ) -> MetaPetitionResolvedEventPayload:
        """Resolve META petition with disposition.

        This method:
        1. Validates rationale length (AC4)
        2. Validates forward_target if disposition is FORWARD
        3. Marks petition resolved in queue
        4. Emits MetaPetitionResolved event

        Constitutional Constraints:
        - CT-13: Explicit consent through disposition (AC4)
        - CT-12: Event emission for witnessing (AC6)

        Args:
            petition_id: UUID of the META petition to resolve.
            disposition: ACKNOWLEDGE, CREATE_ACTION, or FORWARD.
            rationale: High Archon's rationale (min 10 chars).
            high_archon_id: UUID of the resolving High Archon.
            forward_target: Target governance body if disposition=FORWARD.

        Returns:
            MetaPetitionResolvedEventPayload for witnessing.

        Raises:
            ValueError: If rationale is too short.
            ValueError: If FORWARD without forward_target.
            MetaPetitionNotFoundError: If petition not in queue.
            MetaPetitionAlreadyResolvedError: If already resolved.
        """
        log = self._log.bind(
            petition_id=str(petition_id),
            high_archon_id=str(high_archon_id),
            disposition=disposition.value,
        )

        # Validate rationale (AC4)
        if not rationale or len(rationale.strip()) < MIN_RATIONALE_LENGTH:
            log.warning(
                "resolution_validation_failed",
                reason="rationale_too_short",
                min_length=MIN_RATIONALE_LENGTH,
                actual_length=len(rationale.strip()) if rationale else 0,
            )
            raise ValueError(
                f"Rationale must be at least {MIN_RATIONALE_LENGTH} characters"
            )

        # Validate forward_target for FORWARD disposition (AC4)
        if disposition == MetaDisposition.FORWARD and not forward_target:
            log.warning(
                "resolution_validation_failed",
                reason="forward_target_required",
            )
            raise ValueError("forward_target required for FORWARD disposition")

        log.info("meta_resolution_started")

        # Mark resolved in queue
        try:
            queue_item = await self._queue_repo.mark_resolved(
                petition_id=petition_id,
                high_archon_id=high_archon_id,
                disposition=disposition,
                rationale=rationale,
                forward_target=forward_target,
            )
        except MetaPetitionNotFoundError:
            log.error("meta_petition_not_found")
            raise
        except MetaPetitionAlreadyResolvedError:
            log.warning("meta_petition_already_resolved")
            raise

        log.info(
            "meta_petition_marked_resolved",
            status=queue_item.status.value,
        )

        # Create event payload (AC4, AC6)
        now = datetime.now(timezone.utc)
        event = MetaPetitionResolvedEventPayload(
            petition_id=petition_id,
            disposition=disposition,
            rationale=rationale,
            high_archon_id=high_archon_id,
            resolved_at=now,
            forward_target=forward_target,
        )

        # Emit event if emitter configured (CT-12)
        if self._event_emitter:
            await self._event_emitter.emit_meta_petition_resolved(event)
            log.info(
                "meta_petition_resolved_event_emitted",
                event_type=META_PETITION_RESOLVED_EVENT_TYPE,
            )

        log.info(
            "meta_resolution_completed",
            disposition=disposition.value,
            has_forward_target=forward_target is not None,
        )

        return event

    async def get_pending_queue(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MetaPetitionQueueItem], int]:
        """Get pending META petitions for High Archon review (AC3).

        Returns petitions sorted by received_at (oldest first, FIFO).

        Args:
            limit: Maximum items to return (default 50, max 100).
            offset: Pagination offset.

        Returns:
            Tuple of (list of pending items, total count).
        """
        # Clamp limit to max 100
        effective_limit = min(limit, 100)

        items, total = await self._queue_repo.get_pending(
            limit=effective_limit,
            offset=offset,
        )

        self._log.info(
            "pending_queue_retrieved",
            count=len(items),
            total=total,
            limit=effective_limit,
            offset=offset,
        )

        return items, total

    async def get_queue_item(
        self,
        petition_id: UUID,
    ) -> MetaPetitionQueueItem | None:
        """Get specific queue item by petition ID.

        Args:
            petition_id: UUID of the META petition.

        Returns:
            MetaPetitionQueueItem if found, None otherwise.
        """
        return await self._queue_repo.get_by_petition_id(petition_id)
