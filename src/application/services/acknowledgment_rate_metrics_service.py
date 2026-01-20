"""Acknowledgment rate metrics service (Story 3.6, FR-3.6).

This module implements the AcknowledgmentRateMetricsProtocol for tracking
archon deliberation metrics and exposing them via Prometheus.

Constitutional Constraints:
- FR-3.6: System SHALL track acknowledgment rate metrics per Marquis
- FM-3.2: Source for acknowledgment rate metrics requirement
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from uuid import UUID

import structlog

from src.application.ports.acknowledgment_rate_metrics import (
    AcknowledgmentRateMetricsProtocol,
)

logger = structlog.get_logger(__name__)


class AcknowledgmentRateMetricsService(AcknowledgmentRateMetricsProtocol):
    """Service for tracking acknowledgment rate metrics per archon (FR-3.6).

    This service wraps the DeliberationMetricsCollector to provide the
    protocol interface expected by the consensus resolver and deliberation
    orchestrator.

    Metrics are exposed via Prometheus counters that enable time-windowed
    aggregation using rate() and increase() functions.
    """

    def __init__(
        self,
        metrics_collector: AcknowledgmentRateMetricsProtocol | None = None,
    ) -> None:
        """Initialize the acknowledgment rate metrics service.

        Args:
            metrics_collector: Optional metrics collector. If not provided,
                uses the singleton instance.
        """
        if metrics_collector is None:
            raise ValueError("metrics_collector is required")
        self._metrics = metrics_collector
        self._log = logger.bind(component="acknowledgment_rate_metrics")

    def record_participation(self, archon_id: UUID) -> None:
        """Record an archon's participation in a completed deliberation.

        Called once per archon when a deliberation session reaches consensus.
        Increments the total participation counter for the archon.

        Args:
            archon_id: UUID of the participating archon.
        """
        self._log.debug(
            "recording_participation",
            archon_id=str(archon_id),
        )
        self._metrics.record_participation(archon_id)

    def record_vote(self, archon_id: UUID, outcome: str) -> None:
        """Record an archon's vote with its outcome.

        Called once per archon when consensus is reached, recording
        the specific vote cast (ACKNOWLEDGE, REFER, or ESCALATE).

        Args:
            archon_id: UUID of the voting archon.
            outcome: Vote outcome - must be one of ACKNOWLEDGE, REFER, ESCALATE.

        Raises:
            ValueError: If outcome is not a valid deliberation outcome.
        """
        valid_outcomes = ("ACKNOWLEDGE", "REFER", "ESCALATE")
        if outcome not in valid_outcomes:
            raise ValueError(
                f"Invalid outcome '{outcome}'. Must be one of {valid_outcomes}."
            )

        self._log.debug(
            "recording_vote",
            archon_id=str(archon_id),
            outcome=outcome,
        )
        self._metrics.record_vote(archon_id, outcome)

    def record_deliberation_completion(
        self,
        archon_votes: dict[UUID, str],
    ) -> None:
        """Record metrics for all archons in a completed deliberation.

        Convenience method that calls record_participation and record_vote
        for each archon in the deliberation. This is the primary integration
        point with the consensus resolver.

        Args:
            archon_votes: Map of archon_id to their vote outcome.
        """
        self._log.info(
            "recording_deliberation_completion",
            archon_count=len(archon_votes),
            outcomes=[v for v in archon_votes.values()],
        )

        for archon_id, outcome in archon_votes.items():
            self.record_participation(archon_id)
            self.record_vote(archon_id, outcome)
