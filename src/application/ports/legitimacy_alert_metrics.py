"""Port for legitimacy alert metrics (Story 8.2, AC6)."""

from __future__ import annotations

from typing import Protocol


class LegitimacyAlertMetricsProtocol(Protocol):
    """Protocol for legitimacy alert metrics collection."""

    def record_alert_triggered(self, severity: str) -> None:
        """Record an alert trigger event."""
        ...

    def record_alert_recovered(self, severity: str, duration_seconds: int) -> None:
        """Record an alert recovery event."""
        ...

    def record_delivery_failure(self, channel: str) -> None:
        """Record a delivery failure event."""
        ...
