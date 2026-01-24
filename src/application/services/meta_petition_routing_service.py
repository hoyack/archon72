"""META petition routing service (Story 8.5, FR-10.4).

This service routes META petitions to the High Archon queue, bypassing
normal Three Fates deliberation.

Constitutional Constraints:
- FR-10.4: META petitions SHALL route to High Archon [P2]
- META-1: Prevents deadlock from system-about-system petitions
- CT-11: Silent failure destroys legitimacy -> All operations logged
- CT-12: Witnessing creates accountability -> All events witnessed
- CT-13: No writes during halt -> Check halt state first

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before any write operation
2. WITNESS EVERYTHING - Emit MetaPetitionReceived event on routing
3. FAIL LOUD - Never silently swallow errors
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.application.ports.meta_petition_event_emitter import (
    MetaPetitionEventEmitterProtocol,
)
from src.application.ports.meta_petition_queue_repository import (
    MetaPetitionQueueRepositoryProtocol,
)
from src.domain.events.meta_petition import (
    META_PETITION_RECEIVED_EVENT_TYPE,
    MetaPetitionReceivedEventPayload,
)
from src.domain.models.meta_petition import MetaPetitionQueueItem
from src.domain.models.petition_submission import PetitionSubmission, PetitionType

logger = structlog.get_logger(__name__)

# Maximum length for petition text preview in events
META_PETITION_TEXT_PREVIEW_LENGTH: int = 500


class MetaPetitionRoutingService:
    """Routes META petitions to High Archon queue (FR-10.4).

    This service:
    1. Detects META petition type
    2. Bypasses normal deliberation
    3. Enqueues to High Archon queue
    4. Emits MetaPetitionReceived event

    Constitutional Compliance:
    - FR-10.4: META petitions route directly to High Archon
    - META-1: Prevents deliberation deadlock on system-about-system petitions
    - CT-12: Events are witnessed for accountability

    Usage:
        service = MetaPetitionRoutingService(queue_repo, event_emitter)
        if service.should_route_to_high_archon(petition):
            event = await service.route_meta_petition(petition)
    """

    def __init__(
        self,
        queue_repository: MetaPetitionQueueRepositoryProtocol,
        event_emitter: MetaPetitionEventEmitterProtocol | None = None,
    ) -> None:
        """Initialize the routing service.

        Args:
            queue_repository: Repository for META petition queue operations.
            event_emitter: Optional event emitter for META petition events.
        """
        self._queue_repo = queue_repository
        self._event_emitter = event_emitter
        self._log = logger.bind(service="meta_petition_routing")

    def should_route_to_high_archon(self, petition: PetitionSubmission) -> bool:
        """Check if petition should bypass deliberation and route to High Archon.

        A petition routes to High Archon if and only if its type is META.
        No keyword detection or inference is performed - explicit type only.

        Args:
            petition: The petition to check.

        Returns:
            True if petition.type == PetitionType.META, False otherwise.
        """
        return petition.type == PetitionType.META

    async def route_meta_petition(
        self,
        petition: PetitionSubmission,
    ) -> MetaPetitionReceivedEventPayload:
        """Route META petition to High Archon queue.

        This method:
        1. Validates petition is META type
        2. Enqueues to High Archon queue
        3. Emits MetaPetitionReceived event (if emitter configured)
        4. Returns the event payload

        Constitutional Constraints:
        - FR-10.4: META petitions route to High Archon
        - CT-12: Event emission for witnessing
        - AC2: Deliberation bypassed for META type

        Args:
            petition: The META petition to route.

        Returns:
            MetaPetitionReceivedEventPayload for witnessing.

        Raises:
            ValueError: If petition is not META type.
            PetitionAlreadyInQueueError: If petition already in queue.
        """
        log = self._log.bind(
            petition_id=str(petition.id),
            petition_type=petition.type.value,
        )

        # Validate META type
        if not self.should_route_to_high_archon(petition):
            log.error(
                "meta_routing_rejected",
                reason="not_meta_type",
            )
            raise ValueError(
                f"Cannot route non-META petition to High Archon: {petition.type.value}"
            )

        log.info("meta_routing_started")

        # Enqueue to High Archon queue (AC2)
        queue_item = await self._queue_repo.enqueue(
            petition_id=petition.id,
            submitter_id=petition.submitter_id,
            petition_text=petition.text,
        )

        log.info(
            "meta_petition_enqueued",
            enqueued_at=queue_item.received_at.isoformat(),
        )

        # Create event payload (AC2, AC6)
        now = datetime.now(timezone.utc)
        event = MetaPetitionReceivedEventPayload(
            petition_id=petition.id,
            submitter_id=petition.submitter_id if petition.submitter_id else UUID(int=0),
            petition_text_preview=petition.text[:META_PETITION_TEXT_PREVIEW_LENGTH],
            received_at=now,
            routing_reason="EXPLICIT_META_TYPE",
        )

        # Emit event if emitter configured (CT-12)
        if self._event_emitter:
            await self._event_emitter.emit_meta_petition_received(event)
            log.info(
                "meta_petition_received_event_emitted",
                event_type=META_PETITION_RECEIVED_EVENT_TYPE,
            )

        log.info(
            "meta_routing_completed",
            routing_reason=event.routing_reason,
        )

        return event


