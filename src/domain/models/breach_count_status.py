"""Breach count status model (Story 6.3, FR32).

This module provides the BreachCountStatus model for tracking
unacknowledged breach counts and trajectory.

Constitutional Constraints:
- FR32: >10 unacknowledged breaches in 90 days triggers cessation consideration
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.breach import BreachEventPayload

# Cessation threshold constants (FR32)
CESSATION_THRESHOLD: int = 10  # > 10 means 11+ triggers cessation
WARNING_THRESHOLD: int = 8  # Alert when reaching 8 unacknowledged breaches
CESSATION_WINDOW_DAYS: int = 90  # 90-day rolling window per FR32


class BreachTrajectory(str, Enum):
    """Trajectory of breach count over time.

    Used to indicate whether the breach count is trending up,
    stable, or declining over the analysis window.
    """

    INCREASING = "increasing"
    """More breaches in recent period than older period."""

    STABLE = "stable"
    """Similar count across recent and older periods."""

    DECREASING = "decreasing"
    """Fewer breaches in recent period than older period."""


@dataclass(frozen=True)
class BreachCountStatus:
    """Status of unacknowledged breach count in 90-day window (FR32).

    This model provides visibility into:
    - Current breach count vs thresholds
    - Trajectory over time
    - Alert/urgency levels

    Constitutional Constraints:
    - FR32: Cessation triggers at >10 unacknowledged breaches in 90 days
    """

    current_count: int
    """Number of unacknowledged breaches in the window."""

    window_days: int
    """Size of the rolling window in days (90)."""

    threshold: int
    """Threshold that must be exceeded for cessation (10)."""

    warning_threshold: int
    """Warning threshold for early alerting (8)."""

    breach_ids: tuple[UUID, ...]
    """IDs of the unacknowledged breaches in the window."""

    trajectory: BreachTrajectory
    """Trend direction of breach count."""

    calculated_at: datetime
    """When this status was calculated."""

    @property
    def is_above_threshold(self) -> bool:
        """True if count > threshold (triggers cessation per FR32).

        Note: FR32 specifies ">10 breaches" meaning 11+ triggers.
        """
        return self.current_count > self.threshold

    @property
    def is_at_warning(self) -> bool:
        """True if count >= warning_threshold (early alert)."""
        return self.current_count >= self.warning_threshold

    @property
    def urgency_level(self) -> str:
        """Get urgency level based on count.

        Returns:
            "CRITICAL" if above cessation threshold,
            "WARNING" if at warning threshold,
            "NORMAL" otherwise.
        """
        if self.is_above_threshold:
            return "CRITICAL"
        if self.is_at_warning:
            return "WARNING"
        return "NORMAL"

    @property
    def breaches_until_threshold(self) -> int:
        """Number of additional breaches until cessation threshold.

        Returns:
            Number of breaches needed to exceed threshold.
            Returns 0 if already above threshold.
        """
        remaining = self.threshold - self.current_count + 1
        return max(0, remaining)

    @classmethod
    def from_breaches(
        cls,
        breaches: Sequence[BreachEventPayload],
        window_days: int = CESSATION_WINDOW_DAYS,
        threshold: int = CESSATION_THRESHOLD,
        warning_threshold: int = WARNING_THRESHOLD,
        now: datetime | None = None,
    ) -> BreachCountStatus:
        """Create status from list of unacknowledged breaches.

        Calculates trajectory by comparing recent vs older breach counts
        within the window.

        Args:
            breaches: List of unacknowledged breaches in the window.
            window_days: Size of rolling window (default 90).
            threshold: Cessation threshold (default 10).
            warning_threshold: Warning threshold (default 8).
            now: Current time for trajectory calculation (defaults to UTC now).

        Returns:
            BreachCountStatus with all calculated metrics.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Calculate trajectory by comparing recent vs older breaches
        # Split window in half for comparison
        midpoint = now - timedelta(days=window_days // 2)

        recent_count = sum(1 for b in breaches if b.detection_timestamp > midpoint)
        older_count = len(breaches) - recent_count

        # Determine trajectory with a tolerance of 2 breaches
        # to avoid noise from minor fluctuations
        if recent_count > older_count + 2:
            trajectory = BreachTrajectory.INCREASING
        elif recent_count < older_count - 2:
            trajectory = BreachTrajectory.DECREASING
        else:
            trajectory = BreachTrajectory.STABLE

        return cls(
            current_count=len(breaches),
            window_days=window_days,
            threshold=threshold,
            warning_threshold=warning_threshold,
            breach_ids=tuple(b.breach_id for b in breaches),
            trajectory=trajectory,
            calculated_at=now,
        )
