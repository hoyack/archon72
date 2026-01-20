"""Stub implementation of AcknowledgmentRateMetricsProtocol (Story 3.6, FR-3.6).

This module provides a test stub for tracking acknowledgment rate metrics
without Prometheus dependencies.

Constitutional Constraints:
- FR-3.6: System SHALL track acknowledgment rate metrics per Marquis
"""

from __future__ import annotations

from uuid import UUID

from src.application.ports.acknowledgment_rate_metrics import (
    AcknowledgmentRateMetricsProtocol,
)
from src.domain.models.archon_metrics import ArchonDeliberationMetrics


class AcknowledgmentRateMetricsStub(AcknowledgmentRateMetricsProtocol):
    """Test stub for acknowledgment rate metrics (FR-3.6).

    Stores metrics in-memory for test assertions without requiring
    Prometheus infrastructure.

    Attributes:
        metrics: Dict mapping archon_id to their metrics.
        participation_calls: List of all record_participation calls.
        vote_calls: List of all record_vote calls.
        completion_calls: List of all record_deliberation_completion calls.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty metrics storage."""
        self._metrics: dict[UUID, ArchonDeliberationMetrics] = {}
        self.participation_calls: list[UUID] = []
        self.vote_calls: list[tuple[UUID, str]] = []
        self.completion_calls: list[dict[UUID, str]] = []

    def record_participation(self, archon_id: UUID) -> None:
        """Record an archon's participation in a completed deliberation.

        Args:
            archon_id: UUID of the participating archon.
        """
        self.participation_calls.append(archon_id)

        if archon_id not in self._metrics:
            self._metrics[archon_id] = ArchonDeliberationMetrics.create(archon_id)

        self._metrics[archon_id] = self._metrics[archon_id].with_participation()

    def record_vote(self, archon_id: UUID, outcome: str) -> None:
        """Record an archon's vote with its outcome.

        Args:
            archon_id: UUID of the voting archon.
            outcome: Vote outcome - ACKNOWLEDGE, REFER, or ESCALATE.

        Raises:
            ValueError: If outcome is not a valid deliberation outcome.
        """
        valid_outcomes = ("ACKNOWLEDGE", "REFER", "ESCALATE")
        if outcome not in valid_outcomes:
            raise ValueError(
                f"Invalid outcome '{outcome}'. Must be one of {valid_outcomes}."
            )

        self.vote_calls.append((archon_id, outcome))

        if archon_id not in self._metrics:
            self._metrics[archon_id] = ArchonDeliberationMetrics.create(archon_id)

        self._metrics[archon_id] = self._metrics[archon_id].with_vote(outcome)

    def record_deliberation_completion(
        self,
        archon_votes: dict[UUID, str],
    ) -> None:
        """Record metrics for all archons in a completed deliberation.

        Args:
            archon_votes: Map of archon_id to their vote outcome.
        """
        self.completion_calls.append(dict(archon_votes))

        for archon_id, outcome in archon_votes.items():
            self.record_participation(archon_id)
            self.record_vote(archon_id, outcome)

    def get_metrics(self, archon_id: UUID) -> ArchonDeliberationMetrics | None:
        """Get metrics for a specific archon (test helper).

        Args:
            archon_id: UUID of the archon.

        Returns:
            ArchonDeliberationMetrics for the archon, or None if not found.
        """
        return self._metrics.get(archon_id)

    def get_all_metrics(self) -> dict[UUID, ArchonDeliberationMetrics]:
        """Get all recorded metrics (test helper).

        Returns:
            Dict mapping archon_id to their metrics.
        """
        return dict(self._metrics)

    def clear(self) -> None:
        """Clear all recorded metrics and calls (test helper)."""
        self._metrics.clear()
        self.participation_calls.clear()
        self.vote_calls.clear()
        self.completion_calls.clear()
