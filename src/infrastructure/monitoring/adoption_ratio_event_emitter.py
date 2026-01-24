"""Adoption ratio event emitter (Story 8.6, PREVENT-7, CT-12).

Emits witnessed adoption ratio alert events and updates Prometheus metrics.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- CT-12: Witnessing creates accountability - events are witnessed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.application.services.adoption_ratio_alerting_service import (
    AdoptionRatioEventEmitterProtocol,
)
from src.domain.events.adoption_ratio import (
    ADOPTION_RATIO_EXCEEDED_EVENT_TYPE,
    ADOPTION_RATIO_NORMALIZED_EVENT_TYPE,
    AdoptionRatioExceededEventPayload,
    AdoptionRatioNormalizedEventPayload,
)
from src.infrastructure.monitoring.metrics import get_metrics_collector

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = structlog.get_logger(__name__)


class AdoptionRatioEventEmitter(AdoptionRatioEventEmitterProtocol):
    """Emits adoption ratio alert events (Story 8.6, CT-12).

    This emitter:
    1. Writes witnessed events via EventWriterService (CT-12)
    2. Updates Prometheus metrics for observability
    3. Logs events for operational visibility

    Usage:
        event_emitter = AdoptionRatioEventEmitter(event_writer=event_writer)

        await event_emitter.emit_exceeded(exceeded_payload)
        await event_emitter.emit_normalized(normalized_payload)
    """

    def __init__(self, event_writer: EventWriterService) -> None:
        """Initialize the event emitter.

        Args:
            event_writer: Service for writing witnessed events.
        """
        self._event_writer = event_writer
        self._metrics = get_metrics_collector()
        self._log = logger.bind(component="adoption_ratio_event_emitter")

    async def emit_exceeded(
        self,
        payload: AdoptionRatioExceededEventPayload,
    ) -> None:
        """Emit adoption ratio exceeded event (witnessed per CT-12).

        Writes the event to the append-only event log with witnessing,
        updates Prometheus metrics, and logs for visibility.

        Args:
            payload: Event payload to emit.
        """
        self._log.warning(
            "emitting_adoption_ratio_exceeded_event",
            event_id=str(payload.event_id),
            alert_id=str(payload.alert_id),
            realm_id=payload.realm_id,
            cycle_id=payload.cycle_id,
            adoption_ratio=payload.adoption_ratio,
            severity=payload.severity,
            threshold=payload.threshold,
        )

        # Write witnessed event (CT-12)
        await self._event_writer.write_event(
            event_type=ADOPTION_RATIO_EXCEEDED_EVENT_TYPE,
            payload=payload.to_dict(),
            signable_content=payload.signable_content(),
        )

        # Update Prometheus metrics
        self._metrics.increment_adoption_ratio_alerts(payload.severity)
        self._metrics.set_adoption_ratio(
            realm_id=payload.realm_id,
            cycle_id=payload.cycle_id,
            ratio=payload.adoption_ratio,
        )

        self._log.info(
            "adoption_ratio_exceeded_event_emitted",
            event_id=str(payload.event_id),
            alert_id=str(payload.alert_id),
        )

    async def emit_normalized(
        self,
        payload: AdoptionRatioNormalizedEventPayload,
    ) -> None:
        """Emit adoption ratio normalized event (witnessed per CT-12).

        Writes the event to the append-only event log with witnessing,
        updates Prometheus metrics, and logs for visibility.

        Args:
            payload: Event payload to emit.
        """
        self._log.info(
            "emitting_adoption_ratio_normalized_event",
            event_id=str(payload.event_id),
            alert_id=str(payload.alert_id),
            realm_id=payload.realm_id,
            cycle_id=payload.cycle_id,
            new_adoption_ratio=payload.new_adoption_ratio,
            previous_ratio=payload.previous_ratio,
            alert_duration_seconds=payload.alert_duration_seconds,
        )

        # Write witnessed event (CT-12)
        await self._event_writer.write_event(
            event_type=ADOPTION_RATIO_NORMALIZED_EVENT_TYPE,
            payload=payload.to_dict(),
            signable_content=payload.signable_content(),
        )

        # Update Prometheus metrics
        # Note: Use "WARN" as default severity since we don't track original severity
        # in the normalized payload. In production, would retrieve from alert history.
        self._metrics.increment_adoption_ratio_alerts_resolved("WARN")
        self._metrics.set_adoption_ratio(
            realm_id=payload.realm_id,
            cycle_id=payload.cycle_id,
            ratio=payload.new_adoption_ratio,
        )

        self._log.info(
            "adoption_ratio_normalized_event_emitted",
            event_id=str(payload.event_id),
            alert_id=str(payload.alert_id),
        )
