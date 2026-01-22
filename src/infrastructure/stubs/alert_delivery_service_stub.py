"""Alert delivery service stub (Story 8.2, FR-8.3, NFR-7.2).

This module provides a stub implementation of alert delivery for testing
and development. Real implementations would integrate with PagerDuty, Slack,
and email services.

Constitutional Constraints:
- FR-8.3: System SHALL alert on decay below 0.85 threshold
- NFR-7.2: Alert delivery within 1 minute of trigger
- CT-11: Silent failure destroys legitimacy → All operations logged
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.domain._compat import StrEnum
from typing import Protocol

from structlog import get_logger

from src.domain.events.legitimacy_alert import (
    LegitimacyAlertRecoveredEvent,
    LegitimacyAlertTriggeredEvent,
)

logger = get_logger()


class AlertChannel(StrEnum):
    """Alert delivery channels (Story 8.2, FR-8.3)."""

    PAGERDUTY = "pagerduty"
    SLACK = "slack"
    EMAIL = "email"


class DeliveryStatus(StrEnum):
    """Delivery status for alert channels."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class AlertDeliveryProtocol(Protocol):
    """Protocol for alert delivery services (Story 8.2, FR-8.3).

    Implementations deliver alerts to external channels (PagerDuty, Slack, email).
    """

    async def deliver_alert(
        self,
        alert: LegitimacyAlertTriggeredEvent,
        channels: list[AlertChannel],
    ) -> dict[AlertChannel, DeliveryStatus]:
        """Deliver alert to configured channels.

        Args:
            alert: Alert trigger event to deliver
            channels: List of channels to deliver to

        Returns:
            Dict mapping channel to delivery status
        """
        ...

    async def deliver_recovery(
        self,
        recovery: LegitimacyAlertRecoveredEvent,
        channels: list[AlertChannel],
    ) -> dict[AlertChannel, DeliveryStatus]:
        """Deliver recovery notification to configured channels.

        Args:
            recovery: Alert recovery event to deliver
            channels: List of channels to deliver to

        Returns:
            Dict mapping channel to delivery status
        """
        ...


@dataclass
class DeliveredAlert:
    """Record of a delivered alert (for stub tracking)."""

    alert_id: str
    event_type: str  # "TRIGGERED" or "RECOVERED"
    channels: list[AlertChannel]
    results: dict[AlertChannel, DeliveryStatus]


@dataclass
class AlertDeliveryServiceStub:
    """Stub implementation of alert delivery service (Story 8.2, FR-8.3).

    This stub tracks delivered alerts in memory for testing purposes.
    Real implementations would integrate with external services.

    Constitutional Compliance:
    - FR-8.3: Alert delivery tracked
    - NFR-7.2: Simulates fast delivery (<1min)
    - CT-11: All delivery attempts logged

    Attributes:
        enabled_channels: List of enabled delivery channels
        deliveries: In-memory record of all deliveries
        fail_channels: Channels to simulate failures for (testing)
    """

    enabled_channels: list[AlertChannel] = field(
        default_factory=lambda: [AlertChannel.SLACK, AlertChannel.EMAIL]
    )
    deliveries: list[DeliveredAlert] = field(default_factory=list)
    fail_channels: list[AlertChannel] = field(default_factory=list)

    async def deliver_alert(
        self,
        alert: LegitimacyAlertTriggeredEvent,
        channels: list[AlertChannel],
    ) -> dict[AlertChannel, DeliveryStatus]:
        """Deliver alert to configured channels (stub).

        Args:
            alert: Alert trigger event to deliver
            channels: List of channels to deliver to

        Returns:
            Dict mapping channel to delivery status
        """
        results: dict[AlertChannel, DeliveryStatus] = {}

        for channel in channels:
            if channel not in self.enabled_channels:
                results[channel] = DeliveryStatus.SKIPPED
                logger.info(
                    "alert_delivery.deliver_alert.skipped",
                    channel=channel.value,
                    reason="channel_disabled",
                )
                continue

            if channel in self.fail_channels:
                results[channel] = DeliveryStatus.FAILED
                logger.warning(
                    "alert_delivery.deliver_alert.failed",
                    channel=channel.value,
                    alert_id=str(alert.alert_id),
                    severity=alert.severity.value,
                )
                continue

            # Simulate successful delivery
            results[channel] = DeliveryStatus.SUCCESS
            logger.info(
                "alert_delivery.deliver_alert.success",
                channel=channel.value,
                alert_id=str(alert.alert_id),
                severity=alert.severity.value,
                cycle_id=alert.cycle_id,
                score=alert.current_score,
            )

        # Record delivery
        self.deliveries.append(
            DeliveredAlert(
                alert_id=str(alert.alert_id),
                event_type="TRIGGERED",
                channels=channels,
                results=results,
            )
        )

        return results

    async def deliver_recovery(
        self,
        recovery: LegitimacyAlertRecoveredEvent,
        channels: list[AlertChannel],
    ) -> dict[AlertChannel, DeliveryStatus]:
        """Deliver recovery notification to configured channels (stub).

        Args:
            recovery: Alert recovery event to deliver
            channels: List of channels to deliver to

        Returns:
            Dict mapping channel to delivery status
        """
        results: dict[AlertChannel, DeliveryStatus] = {}

        for channel in channels:
            if channel not in self.enabled_channels:
                results[channel] = DeliveryStatus.SKIPPED
                logger.info(
                    "alert_delivery.deliver_recovery.skipped",
                    channel=channel.value,
                    reason="channel_disabled",
                )
                continue

            if channel in self.fail_channels:
                results[channel] = DeliveryStatus.FAILED
                logger.warning(
                    "alert_delivery.deliver_recovery.failed",
                    channel=channel.value,
                    alert_id=str(recovery.alert_id),
                )
                continue

            # Simulate successful delivery
            results[channel] = DeliveryStatus.SUCCESS
            logger.info(
                "alert_delivery.deliver_recovery.success",
                channel=channel.value,
                alert_id=str(recovery.alert_id),
                cycle_id=recovery.cycle_id,
                score=recovery.current_score,
                alert_duration=recovery.alert_duration_seconds,
            )

        # Record delivery
        self.deliveries.append(
            DeliveredAlert(
                alert_id=str(recovery.alert_id),
                event_type="RECOVERED",
                channels=channels,
                results=results,
            )
        )

        return results

    def get_delivered_alerts(self) -> list[DeliveredAlert]:
        """Get all delivered alerts (for testing).

        Returns:
            List of all delivered alerts.
        """
        return self.deliveries

    def clear_deliveries(self) -> None:
        """Clear all delivery records (for testing)."""
        self.deliveries.clear()

    def set_fail_channel(self, channel: AlertChannel, should_fail: bool = True) -> None:
        """Set a channel to fail delivery (for testing).

        Args:
            channel: Channel to configure
            should_fail: Whether to simulate failure
        """
        if should_fail and channel not in self.fail_channels:
            self.fail_channels.append(channel)
        elif not should_fail and channel in self.fail_channels:
            self.fail_channels.remove(channel)
