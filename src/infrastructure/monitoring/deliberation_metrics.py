"""Deliberation metrics for Prometheus exposition (Story 3.6, FR-3.6).

This module provides Prometheus counters for tracking archon deliberation
participation and voting patterns.

Constitutional Constraints:
- FR-3.6: System SHALL track acknowledgment rate metrics per Marquis
- FM-3.2: Source for acknowledgment rate metrics requirement
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

import os
import threading
from uuid import UUID

from prometheus_client import CollectorRegistry, Counter

# Thread lock for singleton initialization
_metrics_lock = threading.Lock()


class DeliberationMetricsCollector:
    """Collects deliberation metrics per archon for Prometheus (FR-3.6).

    This collector tracks:
    - Total deliberation participations per archon
    - Votes cast by outcome (ACKNOWLEDGE, REFER, ESCALATE) per archon

    These counters enable calculation of acknowledgment rates via Prometheus
    queries using rate() and increase() functions over time windows.

    Attributes:
        deliberation_participations_total: Counter for participations.
        deliberation_votes_total: Counter for votes with outcome label.
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        """Initialize deliberation metrics collector.

        Args:
            registry: Optional custom registry for testing isolation.
        """
        self._registry = registry or CollectorRegistry()
        self._environment = os.environ.get("ENVIRONMENT", "development")
        self._service_name = os.environ.get("SERVICE_NAME", "archon72-api")

        # Counter for deliberation participations (AC-1)
        # Each time an archon participates in a completed deliberation, increment
        self.deliberation_participations_total = Counter(
            name="deliberation_participations_total",
            documentation="Total deliberation participations per archon (FR-3.6)",
            labelnames=["archon_id", "service", "environment"],
            registry=self._registry,
        )

        # Counter for votes by outcome (AC-2, AC-3)
        # Labels include outcome for breakdown by ACKNOWLEDGE/REFER/ESCALATE
        self.deliberation_votes_total = Counter(
            name="deliberation_votes_total",
            documentation="Total votes cast per archon by outcome (FR-3.6)",
            labelnames=["archon_id", "outcome", "service", "environment"],
            registry=self._registry,
        )

    def record_participation(self, archon_id: UUID) -> None:
        """Record an archon's participation in a completed deliberation (AC-1).

        Called once per archon when a deliberation session reaches consensus.

        Args:
            archon_id: UUID of the participating archon.
        """
        self.deliberation_participations_total.labels(
            archon_id=str(archon_id),
            service=self._service_name,
            environment=self._environment,
        ).inc()

    def record_vote(self, archon_id: UUID, outcome: str) -> None:
        """Record an archon's vote with its outcome (AC-2, AC-3).

        Called once per archon when consensus is reached.

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

        self.deliberation_votes_total.labels(
            archon_id=str(archon_id),
            outcome=outcome,
            service=self._service_name,
            environment=self._environment,
        ).inc()

    def record_deliberation_completion(
        self,
        archon_votes: dict[UUID, str],
    ) -> None:
        """Record metrics for all archons in a completed deliberation (AC-5).

        Convenience method that records both participation and votes for
        all archons in a single deliberation.

        Args:
            archon_votes: Map of archon_id to their vote outcome.
        """
        for archon_id, outcome in archon_votes.items():
            self.record_participation(archon_id)
            self.record_vote(archon_id, outcome)

    def get_registry(self) -> CollectorRegistry:
        """Get the collector registry.

        Returns:
            The Prometheus collector registry.
        """
        return self._registry


# Singleton instance
_deliberation_metrics_collector: DeliberationMetricsCollector | None = None


def get_deliberation_metrics_collector() -> DeliberationMetricsCollector:
    """Get the singleton DeliberationMetricsCollector instance (thread-safe).

    Uses double-checked locking pattern for thread-safe lazy initialization.

    Returns:
        The global DeliberationMetricsCollector instance.
    """
    global _deliberation_metrics_collector
    if _deliberation_metrics_collector is None:
        with _metrics_lock:
            # Double-check inside lock
            if _deliberation_metrics_collector is None:
                _deliberation_metrics_collector = DeliberationMetricsCollector()
    return _deliberation_metrics_collector


def reset_deliberation_metrics_collector() -> None:
    """Reset the singleton collector (for testing only).

    Thread-safe reset using the metrics lock.
    """
    global _deliberation_metrics_collector
    with _metrics_lock:
        _deliberation_metrics_collector = None
