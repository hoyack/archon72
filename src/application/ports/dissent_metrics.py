"""Dissent metrics port interface (Story 2.4, FR12).

Defines the DissentMetricsPort Protocol and DissentRecord dataclass
for tracking dissent percentages over time. FR12 requires monitoring
dissent trends to detect potential groupthink.

Constitutional Constraints:
- FR12: Dissent percentages visible in every vote tally
- NFR-023: Dissent health metrics (voting correlation)
- CT-11: Silent failure destroys legitimacy
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, eq=True)
class DissentRecord:
    """Record of dissent percentage for a single vote.

    Immutable record of dissent metric for time-series tracking.

    Attributes:
        output_id: UUID of the collective output this dissent relates to.
        dissent_percentage: Percentage of minority votes (0.0-100.0).
        recorded_at: UTC timestamp when the dissent was recorded.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> record = DissentRecord(
        ...     output_id=uuid4(),
        ...     dissent_percentage=15.5,
        ...     recorded_at=datetime.now(timezone.utc),
        ... )
    """

    output_id: UUID
    dissent_percentage: float
    recorded_at: datetime

    def __post_init__(self) -> None:
        """Validate dissent percentage is within valid range.

        Raises:
            ValueError: If dissent_percentage is outside 0.0-100.0 range.
        """
        if not (0.0 <= self.dissent_percentage <= 100.0):
            raise ValueError(
                f"dissent_percentage must be between 0.0 and 100.0, "
                f"got {self.dissent_percentage}"
            )

    def to_dict(self) -> dict[str, object]:
        """Convert record to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "output_id": str(self.output_id),
            "dissent_percentage": self.dissent_percentage,
            "recorded_at": self.recorded_at.isoformat(),
        }


class DissentMetricsPort(Protocol):
    """Port for dissent metrics tracking (FR12).

    Protocol defining the interface for recording and querying
    dissent percentages over time. Implementations track dissent
    trends to detect potential groupthink patterns.

    Methods:
        record_vote_dissent: Record dissent for a collective output.
        get_rolling_average: Calculate rolling average over period.
        get_dissent_history: Get dissent records for period.
        is_below_threshold: Check if dissent is below alert threshold.

    Constitutional Requirements:
        - FR12: Dissent percentages visible in every vote tally
        - NFR-023: Alerts fire if dissent drops below 10% over 30 days
    """

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
        ...

    async def get_rolling_average(self, days: int = 30) -> float:
        """Calculate rolling average dissent over specified period.

        Args:
            days: Number of days to include in average (default 30).

        Returns:
            Average dissent percentage over the period.
            Returns 0.0 if no records exist.
        """
        ...

    async def get_dissent_history(self, days: int = 30) -> list[DissentRecord]:
        """Get dissent records for the specified period.

        Args:
            days: Number of days of history to retrieve (default 30).

        Returns:
            List of DissentRecord objects, ordered by recorded_at ascending.
        """
        ...

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
        ...
