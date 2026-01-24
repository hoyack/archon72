"""META petition event emitter implementation (Story 8.5, CT-12).

Concrete implementation of MetaPetitionEventEmitterProtocol that:
1. Logs events with structured logging
2. Records Prometheus metrics
3. Optionally publishes to event store

Constitutional Constraints:
- CT-12: Witnessing creates accountability -> Events logged
- CT-11: Silent failure destroys legitimacy -> Log all operations
- AC6: Events emitted for received and resolved
"""

from __future__ import annotations

import structlog

from src.application.ports.meta_petition_event_emitter import (
    MetaPetitionEventEmitterProtocol,
)
from src.domain.events.meta_petition import (
    META_PETITION_RECEIVED_EVENT_TYPE,
    META_PETITION_RESOLVED_EVENT_TYPE,
    MetaPetitionReceivedEventPayload,
    MetaPetitionResolvedEventPayload,
)
from src.infrastructure.monitoring.metrics import get_metrics_collector

logger = structlog.get_logger(__name__)


class MetaPetitionEventEmitter(MetaPetitionEventEmitterProtocol):
    """Concrete event emitter for META petition events (CT-12).

    This implementation:
    1. Logs events with structured logging for witnessing
    2. Records Prometheus metrics for observability
    3. Can be extended to publish to event store

    Usage:
        emitter = MetaPetitionEventEmitter()
        routing_service = MetaPetitionRoutingService(queue_repo, emitter)
        resolution_service = MetaPetitionResolutionService(queue_repo, emitter)
    """

    def __init__(self) -> None:
        """Initialize the event emitter."""
        self._log = logger.bind(component="meta_petition_event_emitter")
        self._metrics = get_metrics_collector()

    async def emit_meta_petition_received(
        self,
        event: MetaPetitionReceivedEventPayload,
    ) -> None:
        """Emit MetaPetitionReceived event (AC6, CT-12).

        Logs the event for witnessing and records metrics.

        Args:
            event: The event payload to emit.
        """
        # Log for witnessing (CT-12)
        self._log.info(
            "meta_petition_received",
            event_type=META_PETITION_RECEIVED_EVENT_TYPE,
            petition_id=str(event.petition_id),
            submitter_id=str(event.submitter_id),
            routing_reason=event.routing_reason,
            received_at=event.received_at.isoformat(),
            content_hash=event.signable_content(),
        )

        # Record metrics (AC6)
        self._metrics.increment_meta_petitions_received()

    async def emit_meta_petition_resolved(
        self,
        event: MetaPetitionResolvedEventPayload,
    ) -> None:
        """Emit MetaPetitionResolved event (AC6, CT-12).

        Logs the event for witnessing and records metrics.

        Args:
            event: The event payload to emit.
        """
        # Log for witnessing (CT-12)
        log_context = {
            "event_type": META_PETITION_RESOLVED_EVENT_TYPE,
            "petition_id": str(event.petition_id),
            "disposition": event.disposition.value,
            "high_archon_id": str(event.high_archon_id),
            "resolved_at": event.resolved_at.isoformat(),
            "content_hash": event.signable_content(),
        }

        # Include forward_target if present
        if event.forward_target:
            log_context["forward_target"] = event.forward_target

        self._log.info("meta_petition_resolved", **log_context)

        # Record metrics (AC6)
        self._metrics.increment_meta_petitions_resolved(
            disposition=event.disposition.value
        )


# Factory function for dependency injection
def create_meta_petition_event_emitter() -> MetaPetitionEventEmitter:
    """Create a MetaPetitionEventEmitter instance.

    Returns:
        Configured MetaPetitionEventEmitter.
    """
    return MetaPetitionEventEmitter()
