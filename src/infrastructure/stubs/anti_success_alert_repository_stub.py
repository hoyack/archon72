"""Anti-success alert repository stub implementation (Story 7.1, FR38).

This module provides an in-memory stub implementation of AntiSuccessAlertRepositoryProtocol
for testing and development purposes.

Constitutional Constraints:
- FR38: Anti-success alert sustained 90 days triggers cessation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.ports.anti_success_alert_repository import (
    AntiSuccessAlertRepositoryProtocol,
    SustainedAlertInfo,
)


@dataclass
class AlertRecord:
    """Internal record for tracking an alert."""

    alert_id: UUID
    alert_timestamp: datetime
    event_id: UUID


class AntiSuccessAlertRepositoryStub(AntiSuccessAlertRepositoryProtocol):
    """In-memory stub for anti-success alert storage (testing only).

    This stub provides an in-memory implementation of AntiSuccessAlertRepositoryProtocol
    suitable for unit and integration tests.

    The stub tracks alert records and the start of any sustained period.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._alerts: list[AlertRecord] = []
        self._sustained_start: datetime | None = None
        self._is_active: bool = False

    def clear(self) -> None:
        """Clear all stored alerts (for test cleanup)."""
        self._alerts.clear()
        self._sustained_start = None
        self._is_active = False

    async def record_alert(
        self,
        alert_id: UUID,
        alert_timestamp: datetime,
        event_id: UUID,
    ) -> None:
        """Record an anti-success alert.

        If no sustained period is active, this starts one.
        If a period is active, this extends it.

        Args:
            alert_id: Unique identifier for this alert.
            alert_timestamp: When the alert was triggered (UTC).
            event_id: Reference to the witnessed event.
        """
        record = AlertRecord(
            alert_id=alert_id,
            alert_timestamp=alert_timestamp,
            event_id=event_id,
        )
        self._alerts.append(record)

        # Start sustained period if not already active
        if not self._is_active:
            self._sustained_start = alert_timestamp
            self._is_active = True

    async def record_resolution(self, resolution_timestamp: datetime) -> None:
        """Record resolution of anti-success alerts.

        This ends the current sustained period if one is active.

        Args:
            resolution_timestamp: When the alerts were resolved (UTC).
        """
        self._is_active = False
        # Don't clear sustained_start - keep it for historical reference

    async def get_sustained_alert_duration(self) -> SustainedAlertInfo | None:
        """Get current sustained alert duration information (FR38).

        Returns information about the current sustained alert period,
        if one is active. Returns None if alerts are resolved.

        Returns:
            SustainedAlertInfo if active sustained period, None otherwise.
        """
        if not self._is_active or self._sustained_start is None:
            return None

        now = datetime.now(timezone.utc)
        sustained_days = (now - self._sustained_start).days

        # Get alert event IDs in the sustained period
        alert_event_ids = tuple(
            a.event_id
            for a in self._alerts
            if a.alert_timestamp >= self._sustained_start
        )

        return SustainedAlertInfo(
            first_alert_date=self._sustained_start,
            sustained_days=sustained_days,
            alert_event_ids=alert_event_ids,
            is_active=self._is_active,
        )

    async def get_alerts_in_window(self, window_days: int) -> list[UUID]:
        """Get all anti-success alert event IDs in a time window.

        Args:
            window_days: The rolling window in days.

        Returns:
            List of alert event IDs, ordered by timestamp.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        alerts = [a for a in self._alerts if a.alert_timestamp >= cutoff]
        alerts.sort(key=lambda a: a.alert_timestamp)
        return [a.event_id for a in alerts]

    async def is_threshold_reached(self, threshold_days: int = 90) -> bool:
        """Check if the sustained alert threshold is reached (FR38).

        Args:
            threshold_days: The threshold in days (default: 90 per FR38).

        Returns:
            True if sustained for >= threshold_days, False otherwise.
        """
        if not self._is_active or self._sustained_start is None:
            return False

        now = datetime.now(timezone.utc)
        sustained_days = (now - self._sustained_start).days
        return sustained_days >= threshold_days

    # Test helper methods (not part of protocol)

    def set_sustained_start(self, start_date: datetime) -> None:
        """Set the sustained period start date directly (for testing).

        Args:
            start_date: The date to set as the sustained period start.
        """
        self._sustained_start = start_date
        self._is_active = True

    def set_active(self, is_active: bool) -> None:
        """Set whether a sustained period is active (for testing).

        Args:
            is_active: Whether alerts are actively sustained.
        """
        self._is_active = is_active

    def get_alert_count(self) -> int:
        """Get total number of stored alerts."""
        return len(self._alerts)

    def is_period_active(self) -> bool:
        """Check if a sustained period is currently active."""
        return self._is_active
