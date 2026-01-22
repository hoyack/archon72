"""Legitimacy metrics port (Story 8.1, FR-8.1, FR-8.2).

This module defines the protocol for computing and storing legitimacy
decay metrics per governance cycle.

Constitutional Constraints:
- FR-8.1: System SHALL compute legitimacy decay metric per cycle
- FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA
- NFR-1.5: Metric computation completes within 60 seconds
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.domain.models.legitimacy_metrics import LegitimacyMetrics


class LegitimacyMetricsProtocol(Protocol):
    """Protocol for legitimacy metrics computation (Story 8.1, FR-8.1, FR-8.2).

    Implementations compute legitimacy decay metrics for governance cycles
    by analyzing petition lifecycle data and computing responsiveness scores.
    """

    def compute_metrics(
        self,
        cycle_id: str,
        cycle_start: datetime,
        cycle_end: datetime,
    ) -> LegitimacyMetrics:
        """Compute legitimacy metrics for a governance cycle (FR-8.1, FR-8.2).

        Analyzes all petitions received during the cycle period and computes:
        - Total petition count
        - Fated petition count (reached terminal state within SLA)
        - Legitimacy score (ratio of fated to total)
        - Average/median time to fate

        Args:
            cycle_id: Governance cycle identifier (e.g., "2026-W04")
            cycle_start: Start of the governance cycle (UTC)
            cycle_end: End of the governance cycle (UTC)

        Returns:
            LegitimacyMetrics with computed scores.

        Raises:
            ValueError: If cycle_end <= cycle_start
            TimeoutError: If computation exceeds 60 seconds (NFR-1.5)
        """
        ...

    def store_metrics(self, metrics: LegitimacyMetrics) -> None:
        """Store computed legitimacy metrics to persistent storage.

        Args:
            metrics: Computed legitimacy metrics to store.

        Raises:
            ValueError: If metrics with same cycle_id already exist
        """
        ...

    def get_metrics(self, cycle_id: str) -> LegitimacyMetrics | None:
        """Retrieve legitimacy metrics for a specific cycle.

        Args:
            cycle_id: Governance cycle identifier (e.g., "2026-W04")

        Returns:
            LegitimacyMetrics if found, None otherwise.
        """
        ...

    def get_recent_metrics(self, limit: int = 10) -> list[LegitimacyMetrics]:
        """Retrieve recent legitimacy metrics for trend analysis.

        Args:
            limit: Maximum number of recent cycles to retrieve (default: 10)

        Returns:
            List of LegitimacyMetrics ordered by cycle_start descending.
        """
        ...
