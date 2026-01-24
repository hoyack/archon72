"""Adoption ratio compute service (Story 8.6, PREVENT-7, ASM-7).

This module implements the service for computing adoption ratio metrics
per realm per governance cycle to detect excessive petition-to-Motion
conversion patterns.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio to detect budget contention
- CT-11: Silent failure destroys legitimacy -> Log all operations
- CT-12: Witnessing creates accountability -> Metrics are immutable

Developer Golden Rules:
1. HALT CHECK FIRST - This service does not modify state during halt
2. WITNESS EVERYTHING - Metrics stored are read-only
3. FAIL LOUD - Raise on errors, don't swallow
4. READS DURING HALT - Metrics computation is read-only (CT-13)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.application.ports.adoption_ratio_repository import (
    AdoptionRatioRepositoryProtocol,
)
from src.domain.models.adoption_ratio import AdoptionRatioMetrics

if TYPE_CHECKING:
    from typing import Any

logger = structlog.get_logger(__name__)


class AdoptionRatioComputeService:
    """Service for computing adoption ratio metrics (Story 8.6, PREVENT-7).

    Computes adoption ratio metrics by:
    1. Querying all petitions escalated to a realm during the cycle
    2. Identifying petitions adopted by the realm's King
    3. Computing adoption ratio: adopted_count / escalation_count
    4. Storing results via the repository

    Thresholds (PREVENT-7):
    - > 50%: WARN alert - potential rubber-stamping
    - > 70%: CRITICAL alert - severe rubber-stamping

    This service is read-heavy and can operate during system halt (CT-13).
    """

    def __init__(
        self,
        db_connection: Any,
        repository: AdoptionRatioRepositoryProtocol,
    ) -> None:
        """Initialize the adoption ratio compute service.

        Args:
            db_connection: Database connection for querying petition data.
            repository: Repository for storing/retrieving metrics.
        """
        self._db = db_connection
        self._repository = repository
        self._log = logger.bind(component="adoption_ratio_compute")

    async def compute_metrics_for_realm(
        self,
        realm_id: str,
        cycle_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> AdoptionRatioMetrics:
        """Compute adoption ratio metrics for a specific realm/cycle (PREVENT-7).

        Queries petition_submissions table to count:
        1. Petitions escalated to this realm's King during the cycle
        2. Petitions adopted by this realm's King during the cycle

        Args:
            realm_id: Realm identifier.
            cycle_id: Governance cycle identifier (e.g., "2026-W04").
            cycle_start: Start of the governance cycle (UTC).
            cycle_end: End of the governance cycle (UTC).

        Returns:
            AdoptionRatioMetrics with computed values.

        Raises:
            ValueError: If cycle_end <= cycle_start.
        """
        if cycle_end <= cycle_start:
            raise ValueError(
                f"cycle_end ({cycle_end}) must be after cycle_start ({cycle_start})"
            )

        self._log.info(
            "computing_adoption_ratio_metrics",
            realm_id=realm_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start.isoformat(),
            cycle_end=cycle_end.isoformat(),
        )

        # Query escalation and adoption data for the realm/cycle
        escalation_data = await self._query_escalation_data(
            realm_id=realm_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        escalation_count = escalation_data["escalation_count"]
        adoption_count = escalation_data["adoption_count"]
        adopting_kings = escalation_data["adopting_kings"]

        # Compute metrics
        metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=escalation_count,
            adoption_count=adoption_count,
            adopting_kings=adopting_kings,
        )

        self._log.info(
            "computed_adoption_ratio_metrics",
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=escalation_count,
            adoption_count=adoption_count,
            adoption_ratio=metrics.adoption_ratio,
            health_status=metrics.health_status(),
        )

        return metrics

    async def compute_and_store_metrics(
        self,
        realm_id: str,
        cycle_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> AdoptionRatioMetrics:
        """Compute and store adoption ratio metrics (PREVENT-7).

        Combines computation and storage in a single operation.

        Args:
            realm_id: Realm identifier.
            cycle_id: Governance cycle identifier.
            cycle_start: Start of the governance cycle (UTC).
            cycle_end: End of the governance cycle (UTC).

        Returns:
            Computed and stored AdoptionRatioMetrics.
        """
        metrics = await self.compute_metrics_for_realm(
            realm_id=realm_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        await self._repository.save_metrics(metrics)

        self._log.info(
            "stored_adoption_ratio_metrics",
            realm_id=realm_id,
            cycle_id=cycle_id,
            metrics_id=str(metrics.metrics_id),
        )

        return metrics

    async def compute_all_realms(
        self,
        cycle_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> list[AdoptionRatioMetrics]:
        """Compute adoption ratio metrics for all realms with escalations.

        Discovers all realms that received escalations during the cycle
        and computes metrics for each.

        Args:
            cycle_id: Governance cycle identifier.
            cycle_start: Start of the governance cycle (UTC).
            cycle_end: End of the governance cycle (UTC).

        Returns:
            List of AdoptionRatioMetrics for all realms with escalations.
        """
        self._log.info(
            "computing_all_realm_adoption_metrics",
            cycle_id=cycle_id,
            cycle_start=cycle_start.isoformat(),
            cycle_end=cycle_end.isoformat(),
        )

        # Query distinct realms with escalations during the cycle
        realms = await self._query_realms_with_escalations(cycle_start, cycle_end)

        metrics_list: list[AdoptionRatioMetrics] = []
        for realm_id in realms:
            metrics = await self.compute_and_store_metrics(
                realm_id=realm_id,
                cycle_id=cycle_id,
                cycle_start=cycle_start,
                cycle_end=cycle_end,
            )
            metrics_list.append(metrics)

        self._log.info(
            "computed_all_realm_adoption_metrics",
            cycle_id=cycle_id,
            realm_count=len(metrics_list),
        )

        return metrics_list

    async def get_previous_cycle_metrics(
        self,
        realm_id: str,
        current_cycle_id: str,
    ) -> AdoptionRatioMetrics | None:
        """Get metrics from previous cycle for trend comparison.

        Delegates to the repository to find previous cycle metrics.

        Args:
            realm_id: Realm identifier.
            current_cycle_id: Current cycle ID.

        Returns:
            Previous cycle metrics if found, None otherwise.
        """
        return await self._repository.get_previous_cycle_metrics(
            realm_id=realm_id,
            current_cycle_id=current_cycle_id,
        )

    async def compute_trend_delta(
        self,
        current_metrics: AdoptionRatioMetrics,
    ) -> float | None:
        """Compute trend delta from previous cycle (PREVENT-7).

        Calculates the change in adoption ratio from the previous cycle.
        Positive delta indicates increasing adoption (concerning).
        Negative delta indicates decreasing adoption (improving).

        Args:
            current_metrics: Current cycle metrics.

        Returns:
            Delta (current - previous) if previous exists, None otherwise.
        """
        if current_metrics.adoption_ratio is None:
            return None

        previous = await self.get_previous_cycle_metrics(
            realm_id=current_metrics.realm_id,
            current_cycle_id=current_metrics.cycle_id,
        )

        if previous is None or previous.adoption_ratio is None:
            return None

        return current_metrics.adoption_ratio - previous.adoption_ratio

    async def _query_escalation_data(
        self,
        realm_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> dict[str, Any]:
        """Query escalation and adoption data for a realm/cycle.

        Returns:
            Dict with keys:
            - escalation_count: Total petitions escalated to this realm
            - adoption_count: Petitions adopted by this realm's King
            - adopting_kings: List of King UUIDs who adopted petitions
        """
        # Query petitions escalated to this realm during the cycle
        # AND petitions adopted by this realm's King during the cycle
        query = """
            SELECT
                COUNT(*) FILTER (
                    WHERE escalated_to_realm = %s
                    AND escalated_at >= %s AND escalated_at < %s
                ) AS escalation_count,
                COUNT(*) FILTER (
                    WHERE escalated_to_realm = %s
                    AND adopted_at >= %s AND adopted_at < %s
                    AND adopted_by_king_id IS NOT NULL
                ) AS adoption_count,
                ARRAY_AGG(DISTINCT adopted_by_king_id) FILTER (
                    WHERE escalated_to_realm = %s
                    AND adopted_at >= %s AND adopted_at < %s
                    AND adopted_by_king_id IS NOT NULL
                ) AS adopting_kings
            FROM petition_submissions
            WHERE state = 'ESCALATED'
        """

        with self._db.cursor() as cursor:
            cursor.execute(
                query,
                (
                    realm_id,
                    cycle_start,
                    cycle_end,
                    realm_id,
                    cycle_start,
                    cycle_end,
                    realm_id,
                    cycle_start,
                    cycle_end,
                ),
            )
            row = cursor.fetchone()

            escalation_count = row[0] or 0
            adoption_count = row[1] or 0
            # ARRAY_AGG returns None if no matches, convert to empty list
            adopting_kings_raw = row[2] or []
            # Filter out None values and convert to UUIDs
            adopting_kings = [UUID(str(k)) for k in adopting_kings_raw if k is not None]

            return {
                "escalation_count": escalation_count,
                "adoption_count": adoption_count,
                "adopting_kings": adopting_kings,
            }

    async def _query_realms_with_escalations(
        self,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> list[str]:
        """Query distinct realms that received escalations during the cycle.

        Returns:
            List of realm IDs with at least one escalation.
        """
        query = """
            SELECT DISTINCT escalated_to_realm
            FROM petition_submissions
            WHERE state = 'ESCALATED'
            AND escalated_at >= %s AND escalated_at < %s
            AND escalated_to_realm IS NOT NULL
        """

        with self._db.cursor() as cursor:
            cursor.execute(query, (cycle_start, cycle_end))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
