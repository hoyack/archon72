"""Unit tests for DeliberationMetricsCollector (Story 3.6, FR-3.6)."""

from uuid import uuid4

import pytest
from prometheus_client import CollectorRegistry

from src.infrastructure.monitoring.deliberation_metrics import (
    DeliberationMetricsCollector,
    get_deliberation_metrics_collector,
    reset_deliberation_metrics_collector,
)


class TestDeliberationMetricsCollector:
    """Tests for DeliberationMetricsCollector Prometheus integration."""

    def test_record_participation_creates_counter(self) -> None:
        """Test record_participation creates and increments counter (AC-1)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        collector.record_participation(archon_id)

        sample = registry.get_sample_value(
            "deliberation_participations_total",
            labels={
                "archon_id": str(archon_id),
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 1.0

    def test_record_vote_acknowledge(self) -> None:
        """Test record_vote with ACKNOWLEDGE outcome (AC-2)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        collector.record_vote(archon_id, "ACKNOWLEDGE")

        sample = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_id),
                "outcome": "ACKNOWLEDGE",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 1.0

    def test_record_vote_refer(self) -> None:
        """Test record_vote with REFER outcome (AC-3)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        collector.record_vote(archon_id, "REFER")

        sample = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_id),
                "outcome": "REFER",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 1.0

    def test_record_vote_escalate(self) -> None:
        """Test record_vote with ESCALATE outcome (AC-3)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        collector.record_vote(archon_id, "ESCALATE")

        sample = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_id),
                "outcome": "ESCALATE",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 1.0

    def test_record_vote_invalid_outcome_raises(self) -> None:
        """Test record_vote raises ValueError for invalid outcome."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        with pytest.raises(ValueError, match="Invalid outcome"):
            collector.record_vote(archon_id, "INVALID")

    def test_record_deliberation_completion(self) -> None:
        """Test record_deliberation_completion records all archons (AC-5)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)

        archon_1 = uuid4()
        archon_2 = uuid4()
        archon_3 = uuid4()

        archon_votes = {
            archon_1: "ACKNOWLEDGE",
            archon_2: "ACKNOWLEDGE",
            archon_3: "ESCALATE",
        }

        collector.record_deliberation_completion(archon_votes)

        # Verify all archons have participation recorded
        for archon_id in [archon_1, archon_2, archon_3]:
            sample = registry.get_sample_value(
                "deliberation_participations_total",
                labels={
                    "archon_id": str(archon_id),
                    "service": "archon72-api",
                    "environment": "development",
                },
            )
            assert sample == 1.0

        # Verify votes by outcome
        assert (
            registry.get_sample_value(
                "deliberation_votes_total",
                labels={
                    "archon_id": str(archon_1),
                    "outcome": "ACKNOWLEDGE",
                    "service": "archon72-api",
                    "environment": "development",
                },
            )
            == 1.0
        )

        assert (
            registry.get_sample_value(
                "deliberation_votes_total",
                labels={
                    "archon_id": str(archon_3),
                    "outcome": "ESCALATE",
                    "service": "archon72-api",
                    "environment": "development",
                },
            )
            == 1.0
        )

    def test_counter_monotonically_increases(self) -> None:
        """Test counters only increase (Prometheus counter semantics)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        # Increment multiple times
        collector.record_participation(archon_id)
        collector.record_participation(archon_id)
        collector.record_participation(archon_id)

        sample = registry.get_sample_value(
            "deliberation_participations_total",
            labels={
                "archon_id": str(archon_id),
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 3.0

    def test_multiple_archons_isolated(self) -> None:
        """Test different archons have isolated counters."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)

        archon_1 = uuid4()
        archon_2 = uuid4()

        collector.record_participation(archon_1)
        collector.record_participation(archon_1)
        collector.record_participation(archon_2)

        sample_1 = registry.get_sample_value(
            "deliberation_participations_total",
            labels={
                "archon_id": str(archon_1),
                "service": "archon72-api",
                "environment": "development",
            },
        )
        sample_2 = registry.get_sample_value(
            "deliberation_participations_total",
            labels={
                "archon_id": str(archon_2),
                "service": "archon72-api",
                "environment": "development",
            },
        )

        assert sample_1 == 2.0
        assert sample_2 == 1.0

    def test_get_registry_returns_registry(self) -> None:
        """Test get_registry returns the collector registry."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)

        assert collector.get_registry() is registry


class TestDeliberationMetricsSingleton:
    """Tests for singleton pattern."""

    def test_get_singleton_returns_same_instance(self) -> None:
        """Test get_deliberation_metrics_collector returns singleton."""
        reset_deliberation_metrics_collector()

        collector1 = get_deliberation_metrics_collector()
        collector2 = get_deliberation_metrics_collector()

        assert collector1 is collector2

        # Cleanup
        reset_deliberation_metrics_collector()

    def test_reset_clears_singleton(self) -> None:
        """Test reset_deliberation_metrics_collector clears singleton."""
        collector1 = get_deliberation_metrics_collector()
        reset_deliberation_metrics_collector()
        collector2 = get_deliberation_metrics_collector()

        assert collector1 is not collector2

        # Cleanup
        reset_deliberation_metrics_collector()
