"""Legitimacy metrics computation service (Story 8.1, FR-8.1, FR-8.2).

This module implements the LegitimacyMetricsProtocol for computing
legitimacy decay metrics per governance cycle.

Constitutional Constraints:
- FR-8.1: System SHALL compute legitimacy decay metric per cycle
- FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA
- NFR-1.5: Metric computation completes within 60 seconds
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any

import structlog

from src.application.ports.legitimacy_metrics import LegitimacyMetricsProtocol
from src.domain.models.legitimacy_metrics import LegitimacyMetrics
from src.domain.models.petition_submission import TERMINAL_STATES

logger = structlog.get_logger(__name__)


class LegitimacyMetricsService(LegitimacyMetricsProtocol):
    """Service for computing legitimacy decay metrics (Story 8.1, FR-8.1, FR-8.2).

    Computes legitimacy metrics by:
    1. Querying all petitions received during cycle period
    2. Identifying petitions that reached terminal state within SLA
    3. Computing legitimacy score: fated_petitions / total_petitions
    4. Computing average/median time to fate
    5. Storing results to legitimacy_metrics table

    SLA Definition:
    - A petition is "fated" if it reaches terminal state (ACKNOWLEDGED, REFERRED,
      or ESCALATED) within the cycle period.
    """

    def __init__(self, db_connection: Any) -> None:
        """Initialize the legitimacy metrics service.

        Args:
            db_connection: Database connection for querying petition data.
        """
        self._db = db_connection
        self._log = logger.bind(component="legitimacy_metrics")

    def compute_metrics(
        self,
        cycle_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> LegitimacyMetrics:
        """Compute legitimacy metrics for a governance cycle (FR-8.1, FR-8.2).

        Args:
            cycle_id: Governance cycle identifier (e.g., "2026-W04")
            cycle_start: Start of the governance cycle (UTC)
            cycle_end: End of the governance cycle (UTC)

        Returns:
            LegitimacyMetrics with computed scores.

        Raises:
            ValueError: If cycle_end <= cycle_start
        """
        if cycle_end <= cycle_start:
            raise ValueError(
                f"cycle_end ({cycle_end}) must be after cycle_start ({cycle_start})"
            )

        self._log.info(
            "computing_legitimacy_metrics",
            cycle_id=cycle_id,
            cycle_start=cycle_start.isoformat(),
            cycle_end=cycle_end.isoformat(),
        )

        # Query petition data for the cycle
        petition_data = self._query_petition_data(cycle_start, cycle_end)

        total_petitions = len(petition_data)
        fated_petitions = sum(1 for p in petition_data if p["is_fated"])

        # Compute timing metrics
        fate_durations = [p["time_to_fate"] for p in petition_data if p["is_fated"]]

        if fate_durations:
            average_time_to_fate = sum(fate_durations) / len(fate_durations)
            median_time_to_fate = median(fate_durations)
        else:
            average_time_to_fate = None
            median_time_to_fate = None

        # Compute legitimacy metrics
        metrics = LegitimacyMetrics.compute(
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=total_petitions,
            fated_petitions=fated_petitions,
            average_time_to_fate=average_time_to_fate,
            median_time_to_fate=median_time_to_fate,
        )

        self._log.info(
            "computed_legitimacy_metrics",
            cycle_id=cycle_id,
            total_petitions=total_petitions,
            fated_petitions=fated_petitions,
            legitimacy_score=metrics.legitimacy_score,
            health_status=metrics.health_status(),
        )

        return metrics

    def store_metrics(self, metrics: LegitimacyMetrics) -> None:
        """Store computed legitimacy metrics to persistent storage.

        Args:
            metrics: Computed legitimacy metrics to store.

        Raises:
            ValueError: If metrics with same cycle_id already exist
        """
        self._log.info(
            "storing_legitimacy_metrics",
            cycle_id=metrics.cycle_id,
            metrics_id=str(metrics.metrics_id),
        )

        # Execute INSERT
        query = """
            INSERT INTO legitimacy_metrics (
                metrics_id,
                cycle_id,
                cycle_start,
                cycle_end,
                total_petitions,
                fated_petitions,
                legitimacy_score,
                average_time_to_fate,
                median_time_to_fate,
                computed_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        try:
            with self._db.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        str(metrics.metrics_id),
                        metrics.cycle_id,
                        metrics.cycle_start,
                        metrics.cycle_end,
                        metrics.total_petitions,
                        metrics.fated_petitions,
                        metrics.legitimacy_score,
                        metrics.average_time_to_fate,
                        metrics.median_time_to_fate,
                        metrics.computed_at,
                    ),
                )
                self._db.commit()

                self._log.info(
                    "stored_legitimacy_metrics",
                    cycle_id=metrics.cycle_id,
                    metrics_id=str(metrics.metrics_id),
                )

        except Exception as e:
            self._db.rollback()
            self._log.error(
                "failed_to_store_legitimacy_metrics",
                cycle_id=metrics.cycle_id,
                error=str(e),
            )
            raise

    def get_metrics(self, cycle_id: str) -> LegitimacyMetrics | None:
        """Retrieve legitimacy metrics for a specific cycle.

        Args:
            cycle_id: Governance cycle identifier (e.g., "2026-W04")

        Returns:
            LegitimacyMetrics if found, None otherwise.
        """
        query = """
            SELECT
                metrics_id,
                cycle_id,
                cycle_start,
                cycle_end,
                total_petitions,
                fated_petitions,
                legitimacy_score,
                average_time_to_fate,
                median_time_to_fate,
                computed_at
            FROM legitimacy_metrics
            WHERE cycle_id = %s
        """

        with self._db.cursor() as cursor:
            cursor.execute(query, (cycle_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_metrics(row)

    def get_recent_metrics(self, limit: int = 10) -> list[LegitimacyMetrics]:
        """Retrieve recent legitimacy metrics for trend analysis.

        Args:
            limit: Maximum number of recent cycles to retrieve (default: 10)

        Returns:
            List of LegitimacyMetrics ordered by cycle_start descending.
        """
        query = """
            SELECT
                metrics_id,
                cycle_id,
                cycle_start,
                cycle_end,
                total_petitions,
                fated_petitions,
                legitimacy_score,
                average_time_to_fate,
                median_time_to_fate,
                computed_at
            FROM legitimacy_metrics
            ORDER BY cycle_start DESC
            LIMIT %s
        """

        with self._db.cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

            return [self._row_to_metrics(row) for row in rows]

    def _query_petition_data(
        self, cycle_start: datetime, cycle_end: datetime
    ) -> list[dict[str, Any]]:
        """Query petition data for a governance cycle.

        Returns petition data including:
        - Whether petition reached terminal state within cycle
        - Time to fate (seconds from RECEIVED to terminal)

        Args:
            cycle_start: Start of the cycle (UTC)
            cycle_end: End of the cycle (UTC)

        Returns:
            List of petition data dictionaries with keys:
            - petition_id: UUID of the petition
            - is_fated: True if reached terminal state within cycle
            - time_to_fate: Seconds from RECEIVED to terminal (if fated)
        """
        # Query petitions received during cycle
        # For now, using petition_submissions table (new petition system)
        # TODO: May need to union with old cessation_petition table if migration incomplete

        query = """
            SELECT
                petition_id,
                state,
                created_at,
                updated_at,
                EXTRACT(EPOCH FROM (updated_at - created_at)) AS time_to_fate_seconds
            FROM petition_submissions
            WHERE created_at >= %s AND created_at < %s
        """

        with self._db.cursor() as cursor:
            cursor.execute(query, (cycle_start, cycle_end))
            rows = cursor.fetchall()

            petition_data = []
            for row in rows:
                petition_id, state, created_at, updated_at, time_to_fate = row

                # Check if petition reached terminal state within cycle
                is_terminal = state in [s.value for s in TERMINAL_STATES]
                is_fated = is_terminal and updated_at <= cycle_end

                petition_data.append(
                    {
                        "petition_id": petition_id,
                        "is_fated": is_fated,
                        "time_to_fate": time_to_fate if is_fated else None,
                    }
                )

            return petition_data

    def _row_to_metrics(self, row: tuple) -> LegitimacyMetrics:
        """Convert database row to LegitimacyMetrics.

        Args:
            row: Database row tuple

        Returns:
            LegitimacyMetrics instance
        """
        (
            metrics_id,
            cycle_id,
            cycle_start,
            cycle_end,
            total_petitions,
            fated_petitions,
            legitimacy_score,
            average_time_to_fate,
            median_time_to_fate,
            computed_at,
        ) = row

        return LegitimacyMetrics(
            metrics_id=metrics_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=total_petitions,
            fated_petitions=fated_petitions,
            legitimacy_score=float(legitimacy_score) if legitimacy_score else None,
            average_time_to_fate=(
                float(average_time_to_fate) if average_time_to_fate else None
            ),
            median_time_to_fate=(
                float(median_time_to_fate) if median_time_to_fate else None
            ),
            computed_at=computed_at,
        )
