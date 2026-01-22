"""Legitimacy dashboard domain model (Story 8.4, FR-8.4).

This module defines the domain model for the High Archon legitimacy dashboard,
which aggregates petition system health metrics.

Constitutional Constraints:
- FR-8.4: High Archon SHALL have access to legitimacy dashboard
- NFR-5.6: Dashboard data refreshes every 5 minutes
- CT-12: Witnessing creates accountability -> Frozen dataclass
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PetitionStateCounts:
    """Petition counts by state (FR-8.4).

    Provides a snapshot of petitions in each state for monitoring
    system responsiveness.

    Attributes:
        received: Count of petitions in RECEIVED state
        deliberating: Count of petitions in DELIBERATING state
        acknowledged: Count of petitions in ACKNOWLEDGED state
        referred: Count of petitions in REFERRED state
        escalated: Count of petitions in ESCALATED state
    """

    received: int
    deliberating: int
    acknowledged: int
    referred: int
    escalated: int

    def total(self) -> int:
        """Return total petition count across all states."""
        return (
            self.received
            + self.deliberating
            + self.acknowledged
            + self.referred
            + self.escalated
        )


@dataclass(frozen=True)
class DeliberationMetrics:
    """Deliberation performance metrics (FR-8.4).

    Tracks Three Fates deliberation outcomes and performance.

    Attributes:
        total_deliberations: Total deliberations completed this cycle
        consensus_rate: Percentage of deliberations reaching consensus (0.0-1.0)
        timeout_rate: Percentage of deliberations timing out (0.0-1.0)
        deadlock_rate: Percentage of deliberations deadlocking (0.0-1.0)
    """

    total_deliberations: int
    consensus_rate: float
    timeout_rate: float
    deadlock_rate: float


@dataclass(frozen=True)
class ArchonAcknowledgmentRate:
    """Per-archon acknowledgment metrics (FR-8.4, FR-3.6).

    Tracks individual archon acknowledgment activity.

    Attributes:
        archon_id: Archon identifier
        archon_name: Archon display name
        acknowledgment_count: Number of petitions acknowledged this cycle
        rate: Acknowledgments per day (acknowledgment_count / cycle_duration_days)
    """

    archon_id: UUID
    archon_name: str
    acknowledgment_count: int
    rate: float


@dataclass(frozen=True)
class LegitimacyTrendPoint:
    """Historical legitimacy trend data point (FR-8.4).

    Represents legitimacy score for a single cycle.

    Attributes:
        cycle_id: Governance cycle identifier (e.g., "2026-W04")
        legitimacy_score: Legitimacy score for this cycle (0.0-1.0)
        computed_at: When this metric was computed
    """

    cycle_id: str
    legitimacy_score: float
    computed_at: datetime


@dataclass(frozen=True)
class LegitimacyDashboardData:
    """Complete legitimacy dashboard data (Story 8.4, FR-8.4).

    Aggregates all petition system health metrics for High Archon visibility.

    Constitutional Requirements:
    - FR-8.4: Dashboard accessible to High Archon only
    - NFR-5.6: Data refreshes every 5 minutes (caching)

    Attributes:
        current_cycle_score: Current cycle legitimacy score (0.0-1.0)
        current_cycle_id: Current governance cycle identifier
        health_status: Overall health (HEALTHY, WARNING, CRITICAL, NO_DATA)
        historical_trend: Last 10 cycles' legitimacy scores
        petitions_by_state: Count of petitions in each state
        orphan_petition_count: Count of orphan petitions (FR-8.5)
        average_time_to_fate: Mean seconds from RECEIVED to terminal state
        median_time_to_fate: Median seconds from RECEIVED to terminal state
        deliberation_metrics: Deliberation performance metrics
        archon_acknowledgment_rates: Per-archon acknowledgment rates
        data_refreshed_at: When this dashboard data was computed
    """

    current_cycle_score: float | None
    current_cycle_id: str
    health_status: str
    historical_trend: list[LegitimacyTrendPoint]
    petitions_by_state: PetitionStateCounts
    orphan_petition_count: int
    average_time_to_fate: float | None
    median_time_to_fate: float | None
    deliberation_metrics: DeliberationMetrics
    archon_acknowledgment_rates: list[ArchonAcknowledgmentRate]
    data_refreshed_at: datetime

    def is_healthy(self) -> bool:
        """Check if current legitimacy score is healthy (>= 0.85)."""
        if self.current_cycle_score is None:
            return False
        return self.current_cycle_score >= 0.85

    def requires_attention(self) -> bool:
        """Check if dashboard indicates issues requiring High Archon attention."""
        # Critical legitimacy score
        if self.current_cycle_score is not None and self.current_cycle_score < 0.70:
            return True

        # High orphan count (> 10% of total petitions)
        total_petitions = self.petitions_by_state.total()
        if total_petitions > 0:
            orphan_ratio = self.orphan_petition_count / total_petitions
            if orphan_ratio > 0.10:
                return True

        # High timeout or deadlock rate (> 20%)
        if (
            self.deliberation_metrics.timeout_rate > 0.20
            or self.deliberation_metrics.deadlock_rate > 0.20
        ):
            return True

        return False
