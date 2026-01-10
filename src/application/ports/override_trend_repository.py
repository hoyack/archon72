"""Override trend repository port (Story 5.5, FR27, RT-3).

This module defines the protocol for querying override history for trend analysis.
The repository provides data for detecting override abuse patterns.

Constitutional Constraints:
- FR27: Override trend analysis with anti-success alerts
- RT-3: >20 overrides in 365-day window triggers governance review
- CT-11: Silent failure destroys legitimacy -> Query errors must be surfaced

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before queries
2. No data modification - This is a read-only port
3. Time-based queries must use UTC
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


@dataclass(frozen=True)
class OverrideTrendData:
    """Data structure for override trend analysis results.

    Attributes:
        total_count: Total number of overrides in the window.
        daily_rate: Average overrides per day.
        period_days: The analysis window in days.
        oldest_override: Timestamp of the oldest override in window (if any).
        newest_override: Timestamp of the newest override in window (if any).
    """

    total_count: int
    daily_rate: float
    period_days: int
    oldest_override: Optional[datetime]
    newest_override: Optional[datetime]


class OverrideTrendRepositoryProtocol(Protocol):
    """Port for querying override history for trend analysis (FR27, RT-3).

    This protocol defines the interface for retrieving override statistics
    used to detect abuse patterns. Implementations must provide time-based
    query capabilities for rolling trend analysis.

    Constitutional Constraints:
    - FR27: Override trend analysis with anti-success alerts
    - RT-3: >20 overrides in 365-day window triggers governance review
    """

    async def get_override_count(self, days: int) -> int:
        """Get total override count for the last N days.

        Args:
            days: Number of days to look back from now.

        Returns:
            Total override count in the specified window.
        """
        ...

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
        ...

    async def get_rolling_trend(self, days: int) -> OverrideTrendData:
        """Get rolling trend data for the last N days.

        Args:
            days: Number of days to analyze.

        Returns:
            OverrideTrendData with count, rate, and time boundaries.
        """
        ...
