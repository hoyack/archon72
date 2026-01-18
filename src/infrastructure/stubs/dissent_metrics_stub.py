"""Dissent metrics stub implementation (Story 2.4, FR12).

In-memory stub for DissentMetricsPort for development and testing.
Follows DEV_MODE_WATERMARK pattern per RT-1/ADR-4.

Constitutional Constraints:
- FR12: Dissent percentages visible in every vote tally
- NFR-023: Alerts fire if dissent drops below 10% over 30 days
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern for dev stubs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.ports.dissent_metrics import DissentRecord

# DEV_MODE_WATERMARK per RT-1/ADR-4
# This constant indicates this is a development stub, not production code
DEV_MODE_WATERMARK: str = "DEV_STUB:DissentMetricsStub:v1"


class DissentMetricsStub:
    """In-memory stub for DissentMetricsPort (FR12).

    Development and testing implementation that stores dissent records
    in memory. Follows DEV_MODE_WATERMARK pattern.

    WARNING: This is a development stub. Not for production use.
    Production implementations should use a persistent store.

    Attributes:
        _records: In-memory list of dissent records.

    Example:
        >>> stub = DissentMetricsStub()
        >>> await stub.record_vote_dissent(uuid4(), 15.5, datetime.now(timezone.utc))
        >>> avg = await stub.get_rolling_average(days=30)
    """

    def __init__(self) -> None:
        """Initialize empty dissent metrics store."""
        self._records: list[DissentRecord] = []

    async def record_vote_dissent(
        self,
        output_id: UUID,
        dissent_percentage: float,
        recorded_at: datetime,
    ) -> None:
        """Record dissent percentage for a collective output.

        Args:
            output_id: UUID of the collective output.
            dissent_percentage: Calculated dissent percentage (0.0-100.0).
            recorded_at: UTC timestamp of the vote.

        Raises:
            ValueError: If dissent_percentage is invalid.
        """
        record = DissentRecord(
            output_id=output_id,
            dissent_percentage=dissent_percentage,
            recorded_at=recorded_at,
        )
        self._records.append(record)

    async def get_rolling_average(self, days: int = 30) -> float:
        """Calculate rolling average dissent over specified period.

        Args:
            days: Number of days to include in average (default 30).

        Returns:
            Average dissent percentage over the period.
            Returns 0.0 if no records exist.
        """
        filtered = self._get_records_in_period(days)

        if not filtered:
            return 0.0

        total = sum(r.dissent_percentage for r in filtered)
        return total / len(filtered)

    async def get_dissent_history(self, days: int = 30) -> list[DissentRecord]:
        """Get dissent records for the specified period.

        Args:
            days: Number of days of history to retrieve (default 30).

        Returns:
            List of DissentRecord objects, ordered by recorded_at ascending.
        """
        filtered = self._get_records_in_period(days)
        return sorted(filtered, key=lambda r: r.recorded_at)

    async def is_below_threshold(
        self,
        threshold: float = 10.0,
        days: int = 30,
    ) -> bool:
        """Check if rolling average is below alert threshold.

        Per NFR-023, alerts should fire if dissent drops below 10%
        over 30 days.

        Args:
            threshold: Dissent percentage threshold (default 10.0).
            days: Number of days to consider (default 30).

        Returns:
            True if rolling average is below threshold, False otherwise.
        """
        average = await self.get_rolling_average(days)
        return average < threshold

    def _get_records_in_period(self, days: int) -> list[DissentRecord]:
        """Get records within the specified period.

        Args:
            days: Number of days to include.

        Returns:
            List of records within the period.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [r for r in self._records if r.recorded_at >= cutoff]
