"""Legitimacy dashboard query service (Story 8.4, FR-8.4).

This module implements the service for querying and aggregating petition
system health metrics for the High Archon legitimacy dashboard.

Constitutional Constraints:
- FR-8.4: High Archon SHALL have access to legitimacy dashboard
- NFR-5.6: Dashboard data refreshes every 5 minutes
- NFR-1.2: Dashboard query responds within 500ms
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from src.domain.models.legitimacy_dashboard import (
    ArchonAcknowledgmentRate,
    DeliberationMetrics,
    LegitimacyDashboardData,
    LegitimacyTrendPoint,
    PetitionStateCounts,
)
from src.infrastructure.cache.dashboard_cache import DashboardCache

logger = structlog.get_logger(__name__)


class LegitimacyDashboardService:
    """Service for querying legitimacy dashboard data (Story 8.4, FR-8.4).

    Aggregates petition system health metrics including:
    - Current cycle legitimacy score
    - Historical trend (last 10 cycles)
    - Petitions by state
    - Orphan petition count
    - Time-to-fate metrics
    - Deliberation performance metrics
    - Per-archon acknowledgment rates

    Constitutional Requirements:
    - FR-8.4: Dashboard data aggregation
    - NFR-5.6: 5-minute cache TTL
    - NFR-1.2: <500ms response time
    """

    def __init__(
        self, db_connection: Any, cache: DashboardCache | None = None
    ) -> None:
        """Initialize the legitimacy dashboard service.

        Args:
            db_connection: Database connection for querying metrics.
            cache: Optional dashboard cache (NFR-5.6). If None, caching is disabled.
        """
        self._db = db_connection
        self._cache = cache or DashboardCache()
        self._log = logger.bind(component="legitimacy_dashboard")

    def get_dashboard_data(self, current_cycle_id: str) -> LegitimacyDashboardData:
        """Get complete legitimacy dashboard data (FR-8.4).

        Queries and aggregates all dashboard metrics for High Archon visibility.
        Uses 5-minute cache per NFR-5.6.

        Args:
            current_cycle_id: Current governance cycle identifier (e.g., "2026-W04")

        Returns:
            LegitimacyDashboardData with complete dashboard metrics.

        Raises:
            ValueError: If current_cycle_id is invalid or not found.
        """
        self._log.info("querying_dashboard_data", cycle_id=current_cycle_id)

        # Check cache first (NFR-5.6: 5-minute TTL)
        cached_data = self._cache.get(current_cycle_id)
        if cached_data is not None:
            self._log.info(
                "dashboard_data_from_cache",
                cycle_id=current_cycle_id,
            )
            return cached_data

        # Query current cycle metrics
        current_metrics = self._query_current_cycle_metrics(current_cycle_id)

        # Query historical trend (last 10 cycles)
        historical_trend = self._query_historical_trend(limit=10)

        # Query petition state counts
        petition_counts = self._query_petition_state_counts()

        # Query orphan petition count
        orphan_count = self._query_orphan_petition_count()

        # Query deliberation metrics
        deliberation_metrics = self._query_deliberation_metrics(current_cycle_id)

        # Query per-archon acknowledgment rates
        archon_rates = self._query_archon_acknowledgment_rates(current_cycle_id)

        dashboard_data = LegitimacyDashboardData(
            current_cycle_score=current_metrics["legitimacy_score"],
            current_cycle_id=current_cycle_id,
            health_status=current_metrics["health_status"],
            historical_trend=historical_trend,
            petitions_by_state=petition_counts,
            orphan_petition_count=orphan_count,
            average_time_to_fate=current_metrics["average_time_to_fate"],
            median_time_to_fate=current_metrics["median_time_to_fate"],
            deliberation_metrics=deliberation_metrics,
            archon_acknowledgment_rates=archon_rates,
            data_refreshed_at=datetime.now(timezone.utc),
        )

        self._log.info(
            "dashboard_data_retrieved",
            cycle_id=current_cycle_id,
            health_status=dashboard_data.health_status,
            orphan_count=orphan_count,
            requires_attention=dashboard_data.requires_attention(),
        )

        # Cache the result (NFR-5.6: 5-minute TTL)
        self._cache.set(current_cycle_id, dashboard_data)

        return dashboard_data

    def _query_current_cycle_metrics(self, cycle_id: str) -> dict[str, Any]:
        """Query current cycle legitimacy metrics.

        Args:
            cycle_id: Current governance cycle identifier.

        Returns:
            Dict containing legitimacy_score, health_status, average/median time to fate.
        """
        cursor = self._db.cursor()

        # Query legitimacy_metrics table for current cycle
        cursor.execute(
            """
            SELECT
                legitimacy_score,
                average_time_to_fate,
                median_time_to_fate
            FROM legitimacy_metrics
            WHERE cycle_id = %s
            ORDER BY computed_at DESC
            LIMIT 1
            """,
            (cycle_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row is None:
            # No metrics computed yet for this cycle
            return {
                "legitimacy_score": None,
                "health_status": "NO_DATA",
                "average_time_to_fate": None,
                "median_time_to_fate": None,
            }

        legitimacy_score = row[0]
        average_time_to_fate = row[1]
        median_time_to_fate = row[2]

        # Determine health status
        if legitimacy_score is None:
            health_status = "NO_DATA"
        elif legitimacy_score >= 0.85:
            health_status = "HEALTHY"
        elif legitimacy_score >= 0.70:
            health_status = "WARNING"
        else:
            health_status = "CRITICAL"

        return {
            "legitimacy_score": legitimacy_score,
            "health_status": health_status,
            "average_time_to_fate": average_time_to_fate,
            "median_time_to_fate": median_time_to_fate,
        }

    def _query_historical_trend(self, limit: int = 10) -> list[LegitimacyTrendPoint]:
        """Query historical legitimacy trend (last N cycles).

        Args:
            limit: Number of historical cycles to retrieve (default: 10).

        Returns:
            List of LegitimacyTrendPoint ordered by cycle (most recent first).
        """
        cursor = self._db.cursor()

        cursor.execute(
            """
            SELECT
                cycle_id,
                legitimacy_score,
                computed_at
            FROM legitimacy_metrics
            WHERE legitimacy_score IS NOT NULL
            ORDER BY cycle_start DESC
            LIMIT %s
            """,
            (limit,),
        )

        rows = cursor.fetchall()
        cursor.close()

        trend_points = [
            LegitimacyTrendPoint(
                cycle_id=row[0],
                legitimacy_score=row[1],
                computed_at=row[2],
            )
            for row in rows
        ]

        return trend_points

    def _query_petition_state_counts(self) -> PetitionStateCounts:
        """Query count of petitions in each state.

        Returns:
            PetitionStateCounts with current state distribution.
        """
        cursor = self._db.cursor()

        cursor.execute(
            """
            SELECT
                state,
                COUNT(*) as count
            FROM petition_submissions
            GROUP BY state
            """
        )

        rows = cursor.fetchall()
        cursor.close()

        # Initialize counts
        counts = {
            "RECEIVED": 0,
            "DELIBERATING": 0,
            "ACKNOWLEDGED": 0,
            "REFERRED": 0,
            "ESCALATED": 0,
        }

        # Populate from query results
        for row in rows:
            state = row[0]
            count = row[1]
            if state in counts:
                counts[state] = count

        return PetitionStateCounts(
            received=counts["RECEIVED"],
            deliberating=counts["DELIBERATING"],
            acknowledged=counts["ACKNOWLEDGED"],
            referred=counts["REFERRED"],
            escalated=counts["ESCALATED"],
        )

    def _query_orphan_petition_count(self) -> int:
        """Query count of orphan petitions (FR-8.5).

        Returns:
            Count of petitions in orphan_petitions table.
        """
        cursor = self._db.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM orphan_petitions
            WHERE resolved_at IS NULL
            """
        )

        row = cursor.fetchone()
        cursor.close()

        return row[0] if row else 0

    def _query_deliberation_metrics(self, cycle_id: str) -> DeliberationMetrics:
        """Query deliberation performance metrics for current cycle.

        Args:
            cycle_id: Current governance cycle identifier.

        Returns:
            DeliberationMetrics with consensus/timeout/deadlock rates.
        """
        cursor = self._db.cursor()

        # Query deliberation outcomes for current cycle
        # This assumes deliberation_sessions table tracks outcomes
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_deliberations,
                SUM(CASE WHEN outcome = 'CONSENSUS' THEN 1 ELSE 0 END) as consensus_count,
                SUM(CASE WHEN outcome = 'TIMEOUT' THEN 1 ELSE 0 END) as timeout_count,
                SUM(CASE WHEN outcome = 'DEADLOCK' THEN 1 ELSE 0 END) as deadlock_count
            FROM deliberation_sessions
            WHERE created_at >= (
                SELECT cycle_start FROM legitimacy_metrics WHERE cycle_id = %s LIMIT 1
            )
            AND created_at < (
                SELECT cycle_end FROM legitimacy_metrics WHERE cycle_id = %s LIMIT 1
            )
            """,
            (cycle_id, cycle_id),
        )

        row = cursor.fetchone()
        cursor.close()

        if row is None or row[0] == 0:
            # No deliberations in this cycle
            return DeliberationMetrics(
                total_deliberations=0,
                consensus_rate=0.0,
                timeout_rate=0.0,
                deadlock_rate=0.0,
            )

        total = row[0]
        consensus_count = row[1] or 0
        timeout_count = row[2] or 0
        deadlock_count = row[3] or 0

        return DeliberationMetrics(
            total_deliberations=total,
            consensus_rate=consensus_count / total if total > 0 else 0.0,
            timeout_rate=timeout_count / total if total > 0 else 0.0,
            deadlock_rate=deadlock_count / total if total > 0 else 0.0,
        )

    def _query_archon_acknowledgment_rates(
        self, cycle_id: str
    ) -> list[ArchonAcknowledgmentRate]:
        """Query per-archon acknowledgment rates for current cycle.

        Args:
            cycle_id: Current governance cycle identifier.

        Returns:
            List of ArchonAcknowledgmentRate ordered by acknowledgment count (desc).
        """
        cursor = self._db.cursor()

        # Query acknowledgment counts per archon for current cycle
        # This assumes acknowledgments table tracks acknowledging archon IDs
        cursor.execute(
            """
            SELECT
                a.archon_id,
                a.archon_name,
                COUNT(ack.acknowledgment_id) as acknowledgment_count,
                EXTRACT(EPOCH FROM (
                    SELECT cycle_end - cycle_start
                    FROM legitimacy_metrics
                    WHERE cycle_id = %s
                    LIMIT 1
                )) / 86400 as cycle_duration_days
            FROM archons a
            LEFT JOIN acknowledgments ack
                ON a.archon_id = ANY(ack.acknowledging_archon_ids)
                AND ack.acknowledged_at >= (
                    SELECT cycle_start FROM legitimacy_metrics WHERE cycle_id = %s LIMIT 1
                )
                AND ack.acknowledged_at < (
                    SELECT cycle_end FROM legitimacy_metrics WHERE cycle_id = %s LIMIT 1
                )
            GROUP BY a.archon_id, a.archon_name
            ORDER BY acknowledgment_count DESC
            """,
            (cycle_id, cycle_id, cycle_id),
        )

        rows = cursor.fetchall()
        cursor.close()

        rates = []
        for row in rows:
            archon_id = row[0]
            archon_name = row[1]
            acknowledgment_count = row[2]
            cycle_duration_days = row[3] or 7.0  # Default to 7 days if null

            rate = (
                acknowledgment_count / cycle_duration_days
                if cycle_duration_days > 0
                else 0.0
            )

            rates.append(
                ArchonAcknowledgmentRate(
                    archon_id=archon_id,
                    archon_name=archon_name,
                    acknowledgment_count=acknowledgment_count,
                    rate=rate,
                )
            )

        return rates
