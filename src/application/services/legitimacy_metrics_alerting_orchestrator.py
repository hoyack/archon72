"""Legitimacy Metrics & Alerting Orchestrator (Story 8.2 Integration).

This orchestrator integrates Story 8.1 (Legitimacy Metrics Computation) with
Story 8.2 (Legitimacy Decay Alerting) to provide a unified metrics + alerting pipeline.

Constitutional Constraints:
- FR-8.1: System SHALL compute legitimacy decay metric per cycle
- FR-8.3: System SHALL alert on decay below 0.85 threshold
- NFR-7.2: Alert delivery within 1 minute of trigger
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import structlog

from src.application.ports.legitimacy_metrics import LegitimacyMetricsProtocol
from src.application.services.event_writer_service import EventWriterService
from src.domain.events.legitimacy_alert import (
    LegitimacyAlertRecoveredEvent,
    LegitimacyAlertTriggeredEvent,
)
from src.domain.models.legitimacy_alert_state import LegitimacyAlertState
from src.domain.models.legitimacy_metrics import LegitimacyMetrics
from src.infrastructure.monitoring.legitimacy_alert_metrics import (
    LegitimacyAlertMetrics,
    get_legitimacy_alert_metrics,
)
from src.services.legitimacy_alerting_service import LegitimacyAlertingService

logger = structlog.get_logger(__name__)


class AlertStateRepositoryProtocol(Protocol):
    """Protocol for alert state persistence."""

    async def get_current_state(self) -> LegitimacyAlertState | None:
        """Retrieve current alert state.

        Returns:
            Current alert state if exists, None if no alert.
        """
        ...

    async def upsert_state(self, state: LegitimacyAlertState) -> None:
        """Persist or update alert state.

        Args:
            state: Alert state to persist.
        """
        ...


class AlertHistoryRepositoryProtocol(Protocol):
    """Protocol for alert history persistence."""

    async def record_triggered(self, event: LegitimacyAlertTriggeredEvent) -> None:
        """Record alert trigger in history.

        Args:
            event: Alert triggered event to record.
        """
        ...

    async def record_recovered(self, event: LegitimacyAlertRecoveredEvent) -> None:
        """Record alert recovery in history.

        Args:
            event: Alert recovered event to record.
        """
        ...


class AlertDeliveryServiceProtocol(Protocol):
    """Protocol for multi-channel alert delivery."""

    async def deliver_alert(self, event: LegitimacyAlertTriggeredEvent) -> dict[str, bool]:
        """Deliver alert to configured channels.

        Args:
            event: Alert triggered event to deliver.

        Returns:
            Dictionary of channel name -> delivery success status.
        """
        ...

    async def deliver_recovery(self, event: LegitimacyAlertRecoveredEvent) -> dict[str, bool]:
        """Deliver recovery notification to configured channels.

        Args:
            event: Alert recovered event to deliver.

        Returns:
            Dictionary of channel name -> delivery success status.
        """
        ...


class LegitimacyMetricsAlertingOrchestrator:
    """Orchestrator for combined metrics computation and alerting (Story 8.1 + 8.2).

    This service coordinates:
    1. Legitimacy metrics computation (Story 8.1)
    2. Alert condition checking (Story 8.2)
    3. Event emission (CT-12 compliance)
    4. Alert delivery (multi-channel)
    5. Alert state management

    Usage:
        orchestrator = LegitimacyMetricsAlertingOrchestrator(
            metrics_service=metrics_service,
            alerting_service=alerting_service,
            alert_state_repo=state_repo,
            alert_history_repo=history_repo,
            alert_delivery=delivery_service,
            event_writer=event_writer,
        )

        # Compute metrics and check for alerts
        metrics = await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(...),
            cycle_end=datetime(...),
        )
    """

    def __init__(
        self,
        metrics_service: LegitimacyMetricsProtocol,
        alerting_service: LegitimacyAlertingService,
        alert_state_repo: AlertStateRepositoryProtocol,
        alert_history_repo: AlertHistoryRepositoryProtocol,
        alert_delivery: AlertDeliveryServiceProtocol,
        event_writer: EventWriterService,
    ):
        """Initialize the orchestrator with all required dependencies.

        Args:
            metrics_service: Service for computing legitimacy metrics (Story 8.1)
            alerting_service: Service for alert logic (Story 8.2)
            alert_state_repo: Repository for alert state persistence
            alert_history_repo: Repository for alert history persistence
            alert_delivery: Service for multi-channel alert delivery
            event_writer: Service for event emission (CT-12 witnessing)
        """
        self._metrics_service = metrics_service
        self._alerting_service = alerting_service
        self._alert_state_repo = alert_state_repo
        self._alert_history_repo = alert_history_repo
        self._alert_delivery = alert_delivery
        self._event_writer = event_writer
        self._prom_metrics = get_legitimacy_alert_metrics()
        self._log = logger.bind(component="legitimacy_metrics_alerting_orchestrator")

    async def compute_and_alert(
        self,
        cycle_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> LegitimacyMetrics:
        """Compute legitimacy metrics and check for alert conditions.

        This is the main orchestration method that:
        1. Computes legitimacy metrics for the cycle
        2. Retrieves previous alert state
        3. Checks if alert should be triggered or recovered
        4. Emits alert events (witnessed per CT-12)
        5. Delivers alerts to configured channels
        6. Persists alert state and history

        Args:
            cycle_id: Governance cycle identifier (e.g., "2026-W04")
            cycle_start: Start of the governance cycle (UTC)
            cycle_end: End of the governance cycle (UTC)

        Returns:
            Computed LegitimacyMetrics for the cycle.

        Raises:
            ValueError: If cycle parameters are invalid
            Exception: If critical failure occurs in metrics or alerting

        Constitutional Requirements:
        - FR-8.1: Compute legitimacy decay metric per cycle
        - FR-8.3: Alert on decay below 0.85 threshold
        - NFR-7.2: Alert delivery within 1 minute
        - CT-12: Alert events are witnessed
        """
        self._log.info(
            "compute_and_alert_start",
            cycle_id=cycle_id,
            cycle_start=cycle_start.isoformat(),
            cycle_end=cycle_end.isoformat(),
        )

        try:
            # Step 1: Compute metrics (Story 8.1)
            metrics = self._metrics_service.compute_metrics(cycle_id, cycle_start, cycle_end)
            self._metrics_service.store_metrics(metrics)

            self._log.info(
                "metrics_computed",
                cycle_id=cycle_id,
                legitimacy_score=metrics.legitimacy_score,
                health_status=metrics.health_status(),
            )

            # Step 2: Check alert conditions (Story 8.2)
            previous_state = await self._alert_state_repo.get_current_state()
            trigger_event, recovery_event = await self._alerting_service.check_and_alert(
                metrics, previous_state
            )

            # Step 3: Process alert trigger if any
            if trigger_event:
                await self._process_alert_trigger(trigger_event, previous_state)
                # Persist updated alert state after trigger
                if previous_state:
                    await self._alert_state_repo.upsert_state(previous_state)

            # Step 4: Process alert recovery if any
            if recovery_event:
                await self._process_alert_recovery(recovery_event, previous_state)
                # Persist cleared alert state after recovery
                if previous_state:
                    await self._alert_state_repo.upsert_state(previous_state)

            self._log.info(
                "compute_and_alert_complete",
                cycle_id=cycle_id,
                alert_triggered=trigger_event is not None,
                alert_recovered=recovery_event is not None,
            )

            return metrics

        except Exception as e:
            self._log.error(
                "compute_and_alert_failed",
                cycle_id=cycle_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def _process_alert_trigger(
        self,
        event: LegitimacyAlertTriggeredEvent,
        state: LegitimacyAlertState | None,
    ) -> None:
        """Process alert trigger: emit event, record history, deliver notification.

        Args:
            event: Alert triggered event
            state: Current alert state (modified by alerting service)
        """
        self._log.warning(
            "legitimacy_alert_triggered",
            alert_id=str(event.alert_id),
            cycle_id=event.cycle_id,
            severity=event.severity.value,
            current_score=event.current_score,
            threshold=event.threshold,
            stuck_petition_count=event.stuck_petition_count,
        )

        # Record Prometheus metrics (AC6)
        self._prom_metrics.record_alert_triggered(event.severity.value)

        # Emit witnessed event (CT-12)
        await self._event_writer.write_event(event)

        # Record in history
        await self._alert_history_repo.record_triggered(event)

        # Deliver to configured channels (async, non-blocking)
        try:
            delivery_status = await self._alert_delivery.deliver_alert(event)
            self._log.info(
                "alert_delivered",
                alert_id=str(event.alert_id),
                delivery_status=delivery_status,
            )

            # Record delivery failures
            for channel, success in delivery_status.items():
                if not success:
                    self._prom_metrics.record_delivery_failure(channel)
        except Exception as e:
            # Don't fail the entire pipeline on delivery failure
            self._log.error(
                "alert_delivery_failed",
                alert_id=str(event.alert_id),
                error=str(e),
            )

    async def _process_alert_recovery(
        self,
        event: LegitimacyAlertRecoveredEvent,
        state: LegitimacyAlertState | None,
    ) -> None:
        """Process alert recovery: emit event, record history, deliver notification.

        Args:
            event: Alert recovered event
            state: Current alert state (modified by alerting service)
        """
        self._log.info(
            "legitimacy_alert_recovered",
            alert_id=str(event.alert_id),
            cycle_id=event.cycle_id,
            current_score=event.current_score,
            previous_score=event.previous_score,
            alert_duration_seconds=event.alert_duration_seconds,
        )

        # Record Prometheus metrics (AC6)
        # Note: severity is not stored in recovery event, use WARNING as default
        # In production, would need to retrieve severity from alert state or history
        self._prom_metrics.record_alert_recovered("WARNING", event.alert_duration_seconds)

        # Emit witnessed event (CT-12)
        await self._event_writer.write_event(event)

        # Record in history
        await self._alert_history_repo.record_recovered(event)

        # Deliver recovery notification to configured channels
        try:
            delivery_status = await self._alert_delivery.deliver_recovery(event)
            self._log.info(
                "recovery_delivered",
                alert_id=str(event.alert_id),
                delivery_status=delivery_status,
            )

            # Record delivery failures
            for channel, success in delivery_status.items():
                if not success:
                    self._prom_metrics.record_delivery_failure(channel)
        except Exception as e:
            # Don't fail the entire pipeline on delivery failure
            self._log.error(
                "recovery_delivery_failed",
                alert_id=str(event.alert_id),
                error=str(e),
            )
