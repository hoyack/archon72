"""Override trend repository stub (Story 5.5, FR27, RT-3).

This module provides a stub implementation of the OverrideTrendRepositoryProtocol
for use in development and testing environments.

WARNING: This stub is NOT for production use.
Production implementations should query actual event store data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.application.ports.override_trend_repository import (
    OverrideTrendData,
    OverrideTrendRepositoryProtocol,
)


class OverrideTrendRepositoryStub(OverrideTrendRepositoryProtocol):
    """Stub implementation of OverrideTrendRepositoryProtocol.

    This stub provides configurable override history for testing.
    Use set_override_history() to inject test data.

    WARNING: This is for testing only, not production use.

    Example usage:
        stub = OverrideTrendRepositoryStub()
        # Add 10 overrides in the last 30 days
        now = datetime.now(timezone.utc)
        history = [now - timedelta(days=i*3) for i in range(10)]
        stub.set_override_history(history)
    """

    def __init__(self) -> None:
        """Initialize with empty override history."""
        self._override_history: list[datetime] = []

    def set_override_history(self, history: list[datetime]) -> None:
        """Set the override history for testing.

        Args:
            history: List of datetime objects representing override timestamps.
                     Each datetime should be UTC.
        """
        self._override_history = sorted(history, reverse=True)  # newest first

    def add_override(self, timestamp: datetime | None = None) -> None:
        """Add a single override to the history.

        Args:
            timestamp: When the override occurred (defaults to now).
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        self._override_history.append(timestamp)
        self._override_history.sort(reverse=True)  # Keep sorted newest first

    def clear_history(self) -> None:
        """Clear all override history."""
        self._override_history = []

    async def get_override_count(self, days: int) -> int:
        """Get total override count for the last N days.

        Args:
            days: Number of days to look back from now.

        Returns:
            Total override count in the specified window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return sum(1 for ts in self._override_history if ts >= cutoff)

    async def get_override_count_for_period(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """Get override count for a specific date range.

        Args:
            start_date: Start of the period (inclusive, UTC).
            end_date: End of the period (inclusive, UTC).

        Returns:
            Total override count in the specified period.
        """
        return sum(1 for ts in self._override_history if start_date <= ts <= end_date)

    async def get_rolling_trend(self, days: int) -> OverrideTrendData:
        """Get rolling trend data for the last N days.

        Args:
            days: Number of days to analyze.

        Returns:
            OverrideTrendData with count, rate, and time boundaries.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        overrides_in_window = [ts for ts in self._override_history if ts >= cutoff]

        total_count = len(overrides_in_window)
        daily_rate = total_count / days if days > 0 else 0.0

        oldest: datetime | None = None
        newest: datetime | None = None

        if overrides_in_window:
            oldest = min(overrides_in_window)
            newest = max(overrides_in_window)

        return OverrideTrendData(
            total_count=total_count,
            daily_rate=daily_rate,
            period_days=days,
            oldest_override=oldest,
            newest_override=newest,
        )
