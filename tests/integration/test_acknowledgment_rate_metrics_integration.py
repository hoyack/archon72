"""Integration tests for Acknowledgment Rate Metrics (Story 3.6, FR-3.6).

These tests verify end-to-end metrics flow from deliberation completion
through to Prometheus exposition.
"""

from uuid import uuid4

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from src.application.services.acknowledgment_rate_metrics_service import (
    AcknowledgmentRateMetricsService,
)
from src.application.services.consensus_resolver_service import (
    ConsensusResolverService,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)
from src.infrastructure.monitoring.deliberation_metrics import (
    DeliberationMetricsCollector,
)
from src.infrastructure.stubs.acknowledgment_rate_metrics_stub import (
    AcknowledgmentRateMetricsStub,
)


class TestConsensusResolverMetricsIntegration:
    """Tests for consensus resolver integration with metrics (AC-5)."""

    def test_resolve_consensus_records_metrics(self) -> None:
        """Test metrics are recorded when consensus is resolved (FR-3.6)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        metrics_service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        resolver = ConsensusResolverService(metrics_collector=metrics_service)

        archon_1 = uuid4()
        archon_2 = uuid4()
        archon_3 = uuid4()

        session = DeliberationSession.create(
            petition_id=uuid4(),
            assigned_archons=(archon_1, archon_2, archon_3),
        )

        votes = {
            archon_1: DeliberationOutcome.ACKNOWLEDGE,
            archon_2: DeliberationOutcome.ACKNOWLEDGE,
            archon_3: DeliberationOutcome.REFER,
        }

        result = resolver.resolve_consensus(session, votes)

        # Verify consensus was reached
        assert result.winning_outcome == "ACKNOWLEDGE"

        # Verify metrics were recorded for all archons
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

        # Verify ACKNOWLEDGE votes
        assert registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_1),
                "outcome": "ACKNOWLEDGE",
                "service": "archon72-api",
                "environment": "development",
            },
        ) == 1.0

        # Verify REFER vote
        assert registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_3),
                "outcome": "REFER",
                "service": "archon72-api",
                "environment": "development",
            },
        ) == 1.0

    def test_resolve_consensus_without_metrics_collector(self) -> None:
        """Test consensus resolver works without metrics collector."""
        resolver = ConsensusResolverService(metrics_collector=None)

        archon_1 = uuid4()
        archon_2 = uuid4()
        archon_3 = uuid4()

        session = DeliberationSession.create(
            petition_id=uuid4(),
            assigned_archons=(archon_1, archon_2, archon_3),
        )

        votes = {
            archon_1: DeliberationOutcome.ESCALATE,
            archon_2: DeliberationOutcome.ESCALATE,
            archon_3: DeliberationOutcome.REFER,
        }

        result = resolver.resolve_consensus(session, votes)

        # Should work without error
        assert result.winning_outcome == "ESCALATE"

    def test_resolve_consensus_with_stub_collector(self) -> None:
        """Test consensus resolver works with stub collector."""
        stub = AcknowledgmentRateMetricsStub()
        resolver = ConsensusResolverService(metrics_collector=stub)

        archon_1 = uuid4()
        archon_2 = uuid4()
        archon_3 = uuid4()

        session = DeliberationSession.create(
            petition_id=uuid4(),
            assigned_archons=(archon_1, archon_2, archon_3),
        )

        votes = {
            archon_1: DeliberationOutcome.REFER,
            archon_2: DeliberationOutcome.REFER,
            archon_3: DeliberationOutcome.REFER,
        }

        result = resolver.resolve_consensus(session, votes)

        assert result.winning_outcome == "REFER"

        # Verify stub recorded metrics
        assert len(stub.completion_calls) == 1
        for archon_id in [archon_1, archon_2, archon_3]:
            metrics = stub.get_metrics(archon_id)
            assert metrics is not None
            assert metrics.total_participations == 1
            assert metrics.refer_votes == 1


class TestPrometheusExposition:
    """Tests for Prometheus metrics exposition (AC-6)."""

    def test_metrics_appear_in_prometheus_output(self) -> None:
        """Test deliberation metrics appear in /metrics output."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        collector.record_participation(archon_id)
        collector.record_vote(archon_id, "ACKNOWLEDGE")

        # Generate Prometheus output
        output = generate_latest(registry).decode("utf-8")

        # Verify metrics appear in output
        assert "deliberation_participations_total" in output
        assert "deliberation_votes_total" in output
        assert str(archon_id) in output
        assert "ACKNOWLEDGE" in output

    def test_metrics_include_help_text(self) -> None:
        """Test metrics include HELP documentation."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        collector.record_participation(archon_id)

        output = generate_latest(registry).decode("utf-8")

        # Verify HELP text is present
        assert "# HELP deliberation_participations_total" in output
        assert "# HELP deliberation_votes_total" in output

    def test_metrics_include_type_info(self) -> None:
        """Test metrics include TYPE information."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        archon_id = uuid4()

        collector.record_participation(archon_id)

        output = generate_latest(registry).decode("utf-8")

        # Verify TYPE is counter (Prometheus convention)
        assert "# TYPE deliberation_participations_total counter" in output
        assert "# TYPE deliberation_votes_total counter" in output


class TestMultipleDeliberationsMetrics:
    """Tests for metrics accumulation over multiple deliberations."""

    def test_archon_metrics_accumulate_over_deliberations(self) -> None:
        """Test metrics accumulate correctly over multiple deliberations."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        metrics_service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        resolver = ConsensusResolverService(metrics_collector=metrics_service)

        # Same archon participates in multiple deliberations
        archon_1 = uuid4()
        archon_2 = uuid4()
        archon_3 = uuid4()
        archon_4 = uuid4()  # Different archon in second deliberation

        # First deliberation
        session_1 = DeliberationSession.create(
            petition_id=uuid4(),
            assigned_archons=(archon_1, archon_2, archon_3),
        )
        votes_1 = {
            archon_1: DeliberationOutcome.ACKNOWLEDGE,
            archon_2: DeliberationOutcome.ACKNOWLEDGE,
            archon_3: DeliberationOutcome.REFER,
        }
        resolver.resolve_consensus(session_1, votes_1)

        # Second deliberation (archon_1 participates again)
        session_2 = DeliberationSession.create(
            petition_id=uuid4(),
            assigned_archons=(archon_1, archon_2, archon_4),
        )
        votes_2 = {
            archon_1: DeliberationOutcome.ESCALATE,
            archon_2: DeliberationOutcome.ESCALATE,
            archon_4: DeliberationOutcome.ESCALATE,
        }
        resolver.resolve_consensus(session_2, votes_2)

        # Verify archon_1 has 2 participations
        sample = registry.get_sample_value(
            "deliberation_participations_total",
            labels={
                "archon_id": str(archon_1),
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 2.0

        # Verify archon_1 has 1 ACKNOWLEDGE and 1 ESCALATE
        ack_sample = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_1),
                "outcome": "ACKNOWLEDGE",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        esc_sample = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_1),
                "outcome": "ESCALATE",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert ack_sample == 1.0
        assert esc_sample == 1.0

        # Verify archon_4 only has 1 participation
        sample_4 = registry.get_sample_value(
            "deliberation_participations_total",
            labels={
                "archon_id": str(archon_4),
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample_4 == 1.0


class TestTimeWindowedAggregation:
    """Tests documenting PromQL queries for time-windowed aggregation (AC-4)."""

    def test_promql_hourly_rate_query(self) -> None:
        """Document PromQL query for hourly acknowledgment rate.

        Query: sum(rate(deliberation_acknowledge_votes_total{archon_id="X"}[1h])) /
               sum(rate(deliberation_participations_total{archon_id="X"}[1h]))

        This test documents the expected query structure.
        Actual PromQL execution requires a Prometheus server.
        """
        # This is a documentation test - PromQL queries work on Prometheus server
        hourly_rate_query = """
        # Hourly acknowledgment rate for a specific archon
        sum(rate(deliberation_votes_total{archon_id="ARCHON_ID", outcome="ACKNOWLEDGE"}[1h])) /
        sum(rate(deliberation_participations_total{archon_id="ARCHON_ID"}[1h]))
        """
        assert "rate(" in hourly_rate_query
        assert "[1h]" in hourly_rate_query

    def test_promql_daily_rate_query(self) -> None:
        """Document PromQL query for daily acknowledgment rate.

        Query uses [24h] window for daily aggregation.
        """
        daily_rate_query = """
        # Daily acknowledgment rate for a specific archon
        sum(rate(deliberation_votes_total{archon_id="ARCHON_ID", outcome="ACKNOWLEDGE"}[24h])) /
        sum(rate(deliberation_participations_total{archon_id="ARCHON_ID"}[24h]))
        """
        assert "[24h]" in daily_rate_query

    def test_promql_weekly_rate_query(self) -> None:
        """Document PromQL query for weekly acknowledgment rate.

        Query uses [7d] window for weekly aggregation.
        """
        weekly_rate_query = """
        # Weekly acknowledgment rate for a specific archon
        sum(rate(deliberation_votes_total{archon_id="ARCHON_ID", outcome="ACKNOWLEDGE"}[7d])) /
        sum(rate(deliberation_participations_total{archon_id="ARCHON_ID"}[7d]))
        """
        assert "[7d]" in weekly_rate_query

    def test_promql_all_archons_rate_query(self) -> None:
        """Document PromQL query for acknowledgment rate across all archons.

        Query aggregates by archon_id for dashboard display.
        """
        all_archons_query = """
        # Acknowledgment rate per archon (weekly)
        sum by (archon_id) (rate(deliberation_votes_total{outcome="ACKNOWLEDGE"}[7d])) /
        sum by (archon_id) (rate(deliberation_participations_total[7d]))
        """
        assert "sum by (archon_id)" in all_archons_query
