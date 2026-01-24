"""Adoption ratio repository port (Story 8.6, PREVENT-7).

This module defines the abstract interface for adoption ratio metrics and
alert storage operations.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
- CT-12: Witnessing creates accountability → All writes are witnessed
- CT-11: Silent failure destroys legitimacy → All operations must be logged

Developer Golden Rules:
1. HALT CHECK FIRST - Service layer checks halt, not repository
2. WITNESS EVERYTHING - Repository stores, service witnesses
3. FAIL LOUD - Repository raises on errors
4. READS DURING HALT - Repository reads work during halt (CT-13)
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.models.adoption_ratio import (
    AdoptionRatioAlert,
    AdoptionRatioMetrics,
)


class AdoptionRatioRepositoryProtocol(Protocol):
    """Protocol for adoption ratio metrics and alert storage (Story 8.6).

    Defines the contract for adoption ratio persistence. Implementations
    may use Supabase, in-memory storage, or other backends.

    Constitutional Constraints:
    - PREVENT-7: Support alert creation, resolution, and querying
    - ASM-7: Support metrics storage and retrieval for monitoring

    Methods:
        save_metrics: Store computed adoption ratio metrics
        get_metrics_by_realm_cycle: Get metrics for specific realm/cycle
        get_previous_cycle_metrics: Get metrics from previous cycle (trend)
        get_all_realms_current_cycle: Get all realm metrics for a cycle
        save_alert: Store or update an adoption ratio alert
        get_active_alert: Get active alert for a realm
        get_all_active_alerts: Get all active alerts
        resolve_alert: Mark an alert as resolved
    """

    async def save_metrics(self, metrics: AdoptionRatioMetrics) -> None:
        """Save adoption ratio metrics to storage.

        Args:
            metrics: The adoption ratio metrics to save.

        Raises:
            AdoptionRatioMetricsAlreadyExistsError: If metrics for this
                realm/cycle already exist (use upsert pattern).
        """
        ...

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
        ...

    async def get_previous_cycle_metrics(
        self,
        realm_id: str,
        current_cycle_id: str,
    ) -> AdoptionRatioMetrics | None:
        """Get metrics from the previous cycle for trend comparison.

        Args:
            realm_id: Realm identifier.
            current_cycle_id: Current cycle ID (will compute previous).

        Returns:
            The AdoptionRatioMetrics from the previous cycle, or None.
        """
        ...

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
        ...

    async def save_alert(self, alert: AdoptionRatioAlert) -> None:
        """Save or update an adoption ratio alert.

        For new alerts (no existing alert_id), creates a new record.
        For existing alerts, updates the record (e.g., resolution).

        Args:
            alert: The adoption ratio alert to save/update.

        Raises:
            AdoptionRatioAlertNotFoundError: If updating non-existent alert.
        """
        ...

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
        ...

    async def get_all_active_alerts(self) -> list[AdoptionRatioAlert]:
        """Get all currently active adoption ratio alerts.

        Returns:
            List of all active AdoptionRatioAlert instances.
        """
        ...

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
        ...

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
        ...
