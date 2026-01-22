"""Legitimacy metrics domain model (Story 8.1, FR-8.1, FR-8.2).

This module defines the domain model for tracking petition system legitimacy
through decay metrics computed per governance cycle.

Constitutional Constraints:
- FR-8.1: System SHALL compute legitimacy decay metric per cycle
- FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA
- NFR-1.5: Metric computation completes within 60 seconds
- CT-12: Witnessing creates accountability -> Frozen dataclass
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class LegitimacyMetrics:
    """Legitimacy metrics for a governance cycle (Story 8.1, FR-8.1, FR-8.2).

    Tracks petition responsiveness and system health metrics for a given
    governance cycle. The legitimacy score is computed as the ratio of
    petitions that reached terminal state within SLA to total petitions.

    Constitutional Requirements:
    - FR-8.1: Computed per governance cycle
    - FR-8.2: Formula: fated_petitions / total_petitions within SLA
    - NFR-1.5: Computation completes within 60 seconds

    Attributes:
        metrics_id: Unique identifier for this metrics record
        cycle_id: Governance cycle identifier (format: YYYY-Wnn, e.g., "2026-W04")
        cycle_start: Start of the governance cycle (UTC)
        cycle_end: End of the governance cycle (UTC)
        total_petitions: Count of petitions received this cycle
        fated_petitions: Count of petitions that reached terminal state within SLA
        legitimacy_score: Ratio of fated to total (0.0 to 1.0), None if no petitions
        average_time_to_fate: Mean duration from RECEIVED to terminal (seconds)
        median_time_to_fate: Median duration from RECEIVED to terminal (seconds)
        computed_at: When these metrics were computed (UTC)
    """

    metrics_id: UUID
    cycle_id: str
    cycle_start: datetime
    cycle_end: datetime
    total_petitions: int
    fated_petitions: int
    legitimacy_score: float | None
    average_time_to_fate: float | None
    median_time_to_fate: float | None
    computed_at: datetime

    @classmethod
    def compute(
        cls,
        cycle_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
        total_petitions: int,
        fated_petitions: int,
        average_time_to_fate: float | None,
        median_time_to_fate: float | None,
    ) -> LegitimacyMetrics:
        """Compute legitimacy metrics for a cycle (FR-8.1, FR-8.2).

        Args:
            cycle_id: Governance cycle identifier (e.g., "2026-W04")
            cycle_start: Start of the governance cycle (UTC)
            cycle_end: End of the governance cycle (UTC)
            total_petitions: Count of petitions received this cycle
            fated_petitions: Count of petitions that reached terminal state
            average_time_to_fate: Mean duration to terminal state (seconds)
            median_time_to_fate: Median duration to terminal state (seconds)

        Returns:
            LegitimacyMetrics instance with computed score.
        """
        # Compute legitimacy score (FR-8.2)
        if total_petitions == 0:
            legitimacy_score = None  # No data
        else:
            legitimacy_score = fated_petitions / total_petitions

        return cls(
            metrics_id=uuid4(),
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=total_petitions,
            fated_petitions=fated_petitions,
            legitimacy_score=legitimacy_score,
            average_time_to_fate=average_time_to_fate,
            median_time_to_fate=median_time_to_fate,
            computed_at=datetime.now(timezone.utc),
        )

    def is_healthy(self, threshold: float = 0.85) -> bool:
        """Check if legitimacy score meets health threshold (FR-8.3).

        Args:
            threshold: Minimum acceptable legitimacy score (default: 0.85)

        Returns:
            True if score >= threshold, False otherwise.
            Returns False if no score (no petitions).
        """
        if self.legitimacy_score is None:
            return False
        return self.legitimacy_score >= threshold

    def health_status(self) -> str:
        """Get health status based on legitimacy score (FR-8.3).

        Returns:
            "HEALTHY" if >= 0.85
            "WARNING" if >= 0.70 and < 0.85
            "CRITICAL" if < 0.70
            "NO_DATA" if no petitions
        """
        if self.legitimacy_score is None:
            return "NO_DATA"
        elif self.legitimacy_score >= 0.85:
            return "HEALTHY"
        elif self.legitimacy_score >= 0.70:
            return "WARNING"
        else:
            return "CRITICAL"
