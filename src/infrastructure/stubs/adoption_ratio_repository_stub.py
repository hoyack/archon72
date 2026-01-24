"""Adoption ratio repository stub implementation (Story 8.6, PREVENT-7).

This module provides an in-memory stub implementation of AdoptionRatioRepositoryProtocol
for development and testing purposes.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
- CT-11: Silent failure destroys legitimacy → All operations logged
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.application.ports.adoption_ratio_repository import (
    AdoptionRatioRepositoryProtocol,
)
from src.domain.models.adoption_ratio import (
    AdoptionRatioAlert,
    AdoptionRatioMetrics,
)


class AdoptionRatioAlertNotFoundError(Exception):
    """Raised when an adoption ratio alert is not found."""

    def __init__(self, alert_id: str) -> None:
        self.alert_id = alert_id
        super().__init__(f"Adoption ratio alert not found: {alert_id}")


class AdoptionRatioAlertAlreadyResolvedError(Exception):
    """Raised when trying to resolve an already resolved alert."""

    def __init__(self, alert_id: str) -> None:
        self.alert_id = alert_id
        super().__init__(f"Adoption ratio alert already resolved: {alert_id}")


class AdoptionRatioRepositoryStub(AdoptionRatioRepositoryProtocol):
    """In-memory stub implementation of AdoptionRatioRepositoryProtocol.

    This stub stores adoption ratio metrics and alerts in memory for
    development and testing. It is NOT suitable for production use.

    Attributes:
        _metrics: Dictionary mapping (realm_id, cycle_id) to AdoptionRatioMetrics.
        _alerts: Dictionary mapping alert_id to AdoptionRatioAlert.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._metrics: dict[tuple[str, str], AdoptionRatioMetrics] = {}
        self._alerts: dict[UUID, AdoptionRatioAlert] = {}

    async def save_metrics(self, metrics: AdoptionRatioMetrics) -> None:
        """Save adoption ratio metrics to storage.

        Uses upsert semantics: overwrites existing metrics for same realm/cycle.

        Args:
            metrics: The adoption ratio metrics to save.
        """
        key = (metrics.realm_id, metrics.cycle_id)
        self._metrics[key] = metrics

    async def get_metrics_by_realm_cycle(
        self,
        realm_id: str,
        cycle_id: str,
    ) -> AdoptionRatioMetrics | None:
        """Get metrics for a specific realm and cycle.

        Args:
            realm_id: Realm identifier.
            cycle_id: Governance cycle identifier (e.g., "2026-W04").

        Returns:
            The AdoptionRatioMetrics if found, None otherwise.
        """
        key = (realm_id, cycle_id)
        return self._metrics.get(key)

    async def get_previous_cycle_metrics(
        self,
        realm_id: str,
        current_cycle_id: str,
    ) -> AdoptionRatioMetrics | None:
        """Get metrics from the previous cycle for trend comparison.

        Computes the previous cycle ID by parsing the current one.
        Format: YYYY-Wnn (ISO week number).

        Args:
            realm_id: Realm identifier.
            current_cycle_id: Current cycle ID (e.g., "2026-W04").

        Returns:
            The AdoptionRatioMetrics from the previous cycle, or None.
        """
        # Parse current cycle ID (format: YYYY-Wnn)
        try:
            year_str, week_str = current_cycle_id.split("-W")
            year = int(year_str)
            week = int(week_str)

            # Compute previous week
            if week == 1:
                # Previous year, week 52 or 53
                prev_year = year - 1
                # Simplified: assume 52 weeks
                prev_week = 52
            else:
                prev_year = year
                prev_week = week - 1

            prev_cycle_id = f"{prev_year}-W{prev_week:02d}"
            return await self.get_metrics_by_realm_cycle(realm_id, prev_cycle_id)
        except (ValueError, AttributeError):
            return None

    async def get_all_realms_current_cycle(
        self,
        cycle_id: str,
    ) -> list[AdoptionRatioMetrics]:
        """Get metrics for all realms in a specific cycle.

        Args:
            cycle_id: Governance cycle identifier.

        Returns:
            List of AdoptionRatioMetrics for all realms with data.
        """
        return [
            metrics
            for (_, c_id), metrics in self._metrics.items()
            if c_id == cycle_id
        ]

    async def save_alert(self, alert: AdoptionRatioAlert) -> None:
        """Save or update an adoption ratio alert.

        Args:
            alert: The adoption ratio alert to save/update.
        """
        self._alerts[alert.alert_id] = alert

    async def get_active_alert(
        self,
        realm_id: str,
    ) -> AdoptionRatioAlert | None:
        """Get the active alert for a realm (if any).

        A realm can only have one active alert at a time.

        Args:
            realm_id: Realm identifier.

        Returns:
            The active AdoptionRatioAlert if one exists, None otherwise.
        """
        for alert in self._alerts.values():
            if alert.realm_id == realm_id and alert.status == "ACTIVE":
                return alert
        return None

    async def get_all_active_alerts(self) -> list[AdoptionRatioAlert]:
        """Get all currently active adoption ratio alerts.

        Returns:
            List of all active AdoptionRatioAlert instances.
        """
        return [
            alert
            for alert in self._alerts.values()
            if alert.status == "ACTIVE"
        ]

    async def resolve_alert(
        self,
        alert_id: UUID,
        resolved_at: datetime,
    ) -> None:
        """Mark an alert as resolved.

        Args:
            alert_id: UUID of the alert to resolve.
            resolved_at: When the alert was resolved.

        Raises:
            AdoptionRatioAlertNotFoundError: If alert doesn't exist.
            AdoptionRatioAlertAlreadyResolvedError: If alert already resolved.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise AdoptionRatioAlertNotFoundError(str(alert_id))

        if alert.status == "RESOLVED":
            raise AdoptionRatioAlertAlreadyResolvedError(str(alert_id))

        # Create resolved copy and store it
        resolved_alert = alert.resolve(resolved_at)
        self._alerts[alert_id] = resolved_alert

    async def get_alert_by_id(
        self,
        alert_id: UUID,
    ) -> AdoptionRatioAlert | None:
        """Get an alert by its ID.

        Args:
            alert_id: UUID of the alert.

        Returns:
            The AdoptionRatioAlert if found, None otherwise.
        """
        return self._alerts.get(alert_id)

    def clear(self) -> None:
        """Clear all metrics and alerts (for testing)."""
        self._metrics.clear()
        self._alerts.clear()

    def add_metrics(self, metrics: AdoptionRatioMetrics) -> None:
        """Synchronous add for test setup.

        Args:
            metrics: The adoption ratio metrics to add.
        """
        key = (metrics.realm_id, metrics.cycle_id)
        self._metrics[key] = metrics
