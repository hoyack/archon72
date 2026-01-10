"""Anti-success alert repository port (Story 7.1, FR38).

This module defines the repository interface for tracking anti-success
alerts and their sustained duration for cessation agenda placement.

Constitutional Constraints:
- FR38: Anti-success alert sustained 90 days triggers cessation
- CT-11: Silent failure destroys legitimacy -> Query failures must not be silent
- CT-12: Witnessing creates accountability -> All stored alerts were witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID


@dataclass(frozen=True)
class SustainedAlertInfo:
    """Information about a sustained anti-success alert period.

    Represents a period where anti-success alerts were sustained
    without resolution.

    Attributes:
        first_alert_date: When the sustained period began.
        sustained_days: Number of days the alert has been sustained.
        alert_event_ids: References to alert events in the period.
        is_active: Whether the alert is still active/unresolved.
    """

    first_alert_date: datetime
    sustained_days: int
    alert_event_ids: tuple[UUID, ...]
    is_active: bool


class AntiSuccessAlertRepositoryProtocol(Protocol):
    """Protocol for anti-success alert tracking (FR38).

    This protocol defines the interface for tracking anti-success
    alerts and determining when the 90-day sustained threshold
    is reached for cessation agenda placement.

    Constitutional Constraint (CT-11):
    Query failures must not be silent - raise specific errors.

    Constitutional Constraint (CT-12):
    All stored alerts are assumed to have been witnessed
    before being recorded.
    """

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

        Raises:
            AntiSuccessAlertRepositoryError: If recording fails.
        """
        ...

    async def record_resolution(
        self,
        resolution_timestamp: datetime,
    ) -> None:
        """Record resolution of anti-success alerts.

        This ends the current sustained period if one is active.

        Args:
            resolution_timestamp: When the alerts were resolved (UTC).

        Raises:
            AntiSuccessAlertRepositoryError: If recording fails.
        """
        ...

    async def get_sustained_alert_duration(self) -> Optional[SustainedAlertInfo]:
        """Get current sustained alert duration information (FR38).

        Returns information about the current sustained alert period,
        if one is active. Returns None if alerts are resolved.

        Returns:
            SustainedAlertInfo if active sustained period, None otherwise.

        Raises:
            AntiSuccessAlertRepositoryError: If query fails.
        """
        ...

    async def get_alerts_in_window(
        self,
        window_days: int,
    ) -> list[UUID]:
        """Get all anti-success alert event IDs in a time window.

        Args:
            window_days: The rolling window in days.

        Returns:
            List of alert event IDs, ordered by timestamp.

        Raises:
            AntiSuccessAlertRepositoryError: If query fails.
        """
        ...

    async def is_threshold_reached(self, threshold_days: int = 90) -> bool:
        """Check if the sustained alert threshold is reached (FR38).

        Args:
            threshold_days: The threshold in days (default: 90 per FR38).

        Returns:
            True if sustained for >= threshold_days, False otherwise.

        Raises:
            AntiSuccessAlertRepositoryError: If query fails.
        """
        ...
