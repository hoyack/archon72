"""Adoption ratio alerting service (Story 8.6, PREVENT-7).

This module implements the alerting service for adoption ratio monitoring.
It detects when realms exceed the 50% adoption threshold and manages
alert lifecycle including creation and auto-resolution.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
- CT-11: Silent failure destroys legitimacy -> Log all operations
- CT-12: Witnessing creates accountability -> Events are witnessed

Developer Golden Rules:
1. WITNESS EVERYTHING - Alert events must be witnessed (CT-12)
2. FAIL LOUD - Raise on errors, don't swallow
3. AUTO-RESOLVE - Alerts resolve when ratio normalizes
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

import structlog

from src.application.ports.adoption_ratio_repository import (
    AdoptionRatioRepositoryProtocol,
)
from src.domain.events.adoption_ratio import (
    AdoptionRatioExceededEventPayload,
    AdoptionRatioNormalizedEventPayload,
)
from src.domain.models.adoption_ratio import (
    AdoptionRatioAlert,
    AdoptionRatioMetrics,
)

if TYPE_CHECKING:
    from typing import Any

logger = structlog.get_logger(__name__)


# Alert threshold constants (PREVENT-7)
ADOPTION_RATIO_THRESHOLD: float = 0.50
ADOPTION_RATIO_CRITICAL_THRESHOLD: float = 0.70


class AdoptionRatioEventEmitterProtocol(Protocol):
    """Protocol for emitting adoption ratio alert events."""

    async def emit_exceeded(
        self,
        payload: AdoptionRatioExceededEventPayload,
    ) -> None:
        """Emit adoption ratio exceeded event (witnessed).

        Args:
            payload: Event payload to emit.
        """
        ...

    async def emit_normalized(
        self,
        payload: AdoptionRatioNormalizedEventPayload,
    ) -> None:
        """Emit adoption ratio normalized event (witnessed).

        Args:
            payload: Event payload to emit.
        """
        ...


class AdoptionRatioAlertingService:
    """Service for adoption ratio alerting (Story 8.6, PREVENT-7).

    Monitors adoption ratio metrics and manages alert lifecycle:
    1. Creates alerts when ratio exceeds 50% threshold
    2. Escalates severity at 70% threshold (CRITICAL)
    3. Auto-resolves alerts when ratio normalizes

    Alert Severity Levels (PREVENT-7):
    - WARN: 50% < ratio <= 70% (potential rubber-stamping)
    - CRITICAL: ratio > 70% (severe rubber-stamping)

    Usage:
        alerting_service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # Check metrics and manage alerts
        alert_event, resolution_event = await alerting_service.check_and_alert(
            metrics=computed_metrics,
        )
    """

    def __init__(
        self,
        repository: AdoptionRatioRepositoryProtocol,
        event_emitter: AdoptionRatioEventEmitterProtocol,
        threshold: float = ADOPTION_RATIO_THRESHOLD,
    ) -> None:
        """Initialize the alerting service.

        Args:
            repository: Repository for alert persistence.
            event_emitter: Service for emitting witnessed events.
            threshold: Alert threshold (default: 0.50 per PREVENT-7).
        """
        self._repository = repository
        self._event_emitter = event_emitter
        self._threshold = threshold
        self._log = logger.bind(component="adoption_ratio_alerting")

    async def check_and_alert(
        self,
        metrics: AdoptionRatioMetrics,
        trend_delta: float | None = None,
    ) -> tuple[
        AdoptionRatioExceededEventPayload | None,
        AdoptionRatioNormalizedEventPayload | None,
    ]:
        """Check metrics and manage alert lifecycle (PREVENT-7).

        This is the main alerting method that:
        1. Checks if metrics exceed threshold
        2. Creates new alert if threshold exceeded and no active alert
        3. Auto-resolves active alert if ratio normalizes

        Args:
            metrics: Computed adoption ratio metrics.
            trend_delta: Optional change from previous cycle.

        Returns:
            Tuple of (exceeded_event, normalized_event).
            - exceeded_event: Set if alert was triggered
            - normalized_event: Set if alert was resolved
        """
        realm_id = metrics.realm_id
        cycle_id = metrics.cycle_id

        self._log.info(
            "checking_adoption_ratio_alert",
            realm_id=realm_id,
            cycle_id=cycle_id,
            adoption_ratio=metrics.adoption_ratio,
            threshold=self._threshold,
        )

        # Check for active alert in this realm
        active_alert = await self._repository.get_active_alert(realm_id)

        # Case 1: Ratio exceeds threshold
        if metrics.exceeds_threshold(self._threshold):
            if active_alert is None:
                # Trigger new alert
                return await self._trigger_alert(metrics, trend_delta), None
            else:
                # Alert already active - log continuation
                self._log.info(
                    "adoption_ratio_alert_continues",
                    realm_id=realm_id,
                    alert_id=str(active_alert.alert_id),
                    current_ratio=metrics.adoption_ratio,
                )
                return None, None

        # Case 2: Ratio is normal (below threshold)
        if active_alert is not None:
            # Resolve active alert
            return None, await self._resolve_alert(
                alert=active_alert,
                current_metrics=metrics,
            )

        # Case 3: No alert and ratio is normal
        self._log.debug(
            "adoption_ratio_healthy",
            realm_id=realm_id,
            cycle_id=cycle_id,
            adoption_ratio=metrics.adoption_ratio,
        )
        return None, None

    async def _trigger_alert(
        self,
        metrics: AdoptionRatioMetrics,
        trend_delta: float | None,
    ) -> AdoptionRatioExceededEventPayload:
        """Trigger a new adoption ratio alert (PREVENT-7).

        Creates alert, persists it, and emits witnessed event.

        Args:
            metrics: Metrics that exceeded threshold.
            trend_delta: Optional change from previous cycle.

        Returns:
            Event payload for the triggered alert.
        """
        # Create alert domain object
        alert = AdoptionRatioAlert.create(
            realm_id=metrics.realm_id,
            cycle_id=metrics.cycle_id,
            metrics=metrics,
            trend_delta=trend_delta,
            threshold=self._threshold,
        )

        # Persist alert
        await self._repository.save_alert(alert)

        self._log.warning(
            "adoption_ratio_alert_triggered",
            realm_id=metrics.realm_id,
            cycle_id=metrics.cycle_id,
            alert_id=str(alert.alert_id),
            adoption_ratio=metrics.adoption_ratio,
            severity=alert.severity,
            threshold=self._threshold,
            trend_delta=trend_delta,
        )

        # Create event payload
        event_payload = AdoptionRatioExceededEventPayload(
            event_id=uuid4(),
            alert_id=alert.alert_id,
            realm_id=alert.realm_id,
            cycle_id=alert.cycle_id,
            adoption_ratio=alert.adoption_ratio,
            threshold=alert.threshold,
            severity=alert.severity,
            adopting_kings=tuple(str(k) for k in alert.adopting_kings),
            adoption_count=alert.adoption_count,
            escalation_count=alert.escalation_count,
            trend_delta=alert.trend_delta,
            occurred_at=alert.created_at,
        )

        # Emit witnessed event (CT-12)
        await self._event_emitter.emit_exceeded(event_payload)

        return event_payload

    async def _resolve_alert(
        self,
        alert: AdoptionRatioAlert,
        current_metrics: AdoptionRatioMetrics,
    ) -> AdoptionRatioNormalizedEventPayload:
        """Resolve an active alert when ratio normalizes (PREVENT-7).

        Updates alert status, persists it, and emits witnessed event.

        Args:
            alert: Active alert to resolve.
            current_metrics: Current metrics (normalized).

        Returns:
            Event payload for the resolved alert.
        """
        resolved_at = datetime.now(timezone.utc)

        # Resolve alert in repository
        await self._repository.resolve_alert(
            alert_id=alert.alert_id,
            resolved_at=resolved_at,
        )

        # Calculate alert duration
        duration_seconds = alert.alert_duration_seconds(resolved_at)

        self._log.info(
            "adoption_ratio_alert_resolved",
            realm_id=alert.realm_id,
            cycle_id=current_metrics.cycle_id,
            alert_id=str(alert.alert_id),
            new_adoption_ratio=current_metrics.adoption_ratio,
            previous_ratio=alert.adoption_ratio,
            alert_duration_seconds=duration_seconds,
        )

        # Create event payload
        event_payload = AdoptionRatioNormalizedEventPayload(
            event_id=uuid4(),
            alert_id=alert.alert_id,
            realm_id=alert.realm_id,
            cycle_id=current_metrics.cycle_id,
            new_adoption_ratio=current_metrics.adoption_ratio or 0.0,
            previous_ratio=alert.adoption_ratio,
            alert_duration_seconds=duration_seconds,
            normalized_at=resolved_at,
        )

        # Emit witnessed event (CT-12)
        await self._event_emitter.emit_normalized(event_payload)

        return event_payload

    async def get_active_alerts(self) -> list[AdoptionRatioAlert]:
        """Get all active adoption ratio alerts.

        Returns:
            List of all currently active alerts.
        """
        return await self._repository.get_all_active_alerts()

    async def get_realm_alert_status(
        self,
        realm_id: str,
    ) -> dict[str, Any]:
        """Get alert status for a specific realm.

        Args:
            realm_id: Realm identifier.

        Returns:
            Dict with alert status information:
            - has_active_alert: bool
            - alert: AdoptionRatioAlert | None
        """
        alert = await self._repository.get_active_alert(realm_id)
        return {
            "has_active_alert": alert is not None,
            "alert": alert,
        }
