"""Unit tests for AcknowledgmentRateMetricsService (Story 3.6, FR-3.6)."""

from uuid import uuid4

import pytest
from prometheus_client import CollectorRegistry

from src.application.services.acknowledgment_rate_metrics_service import (
    AcknowledgmentRateMetricsService,
)
from src.infrastructure.monitoring.deliberation_metrics import (
    DeliberationMetricsCollector,
)


class TestAcknowledgmentRateMetricsService:
    """Tests for AcknowledgmentRateMetricsService."""

    def test_record_participation_increments_counter(self) -> None:
        """Test record_participation increments Prometheus counter (AC-1)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        archon_id = uuid4()

        service.record_participation(archon_id)

        # Verify counter was incremented
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
        """Test record_vote increments ACKNOWLEDGE vote counter (AC-2)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        archon_id = uuid4()

        service.record_vote(archon_id, "ACKNOWLEDGE")

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
        """Test record_vote increments REFER vote counter (AC-3)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        archon_id = uuid4()

        service.record_vote(archon_id, "REFER")

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
        """Test record_vote increments ESCALATE vote counter (AC-3)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        archon_id = uuid4()

        service.record_vote(archon_id, "ESCALATE")

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
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        archon_id = uuid4()

        with pytest.raises(ValueError, match="Invalid outcome"):
            service.record_vote(archon_id, "INVALID")

    def test_record_deliberation_completion(self) -> None:
        """Test record_deliberation_completion records all archons (AC-5)."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)

        archon_1 = uuid4()
        archon_2 = uuid4()
        archon_3 = uuid4()

        archon_votes = {
            archon_1: "ACKNOWLEDGE",
            archon_2: "ACKNOWLEDGE",
            archon_3: "REFER",
        }

        service.record_deliberation_completion(archon_votes)

        # Verify participations
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

        # Verify votes
        sample_ack_1 = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_1),
                "outcome": "ACKNOWLEDGE",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample_ack_1 == 1.0

        sample_refer = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_3),
                "outcome": "REFER",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample_refer == 1.0

    def test_multiple_participations_accumulate(self) -> None:
        """Test counters accumulate over multiple deliberations."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        archon_id = uuid4()

        # Record multiple participations
        service.record_participation(archon_id)
        service.record_participation(archon_id)
        service.record_participation(archon_id)

        sample = registry.get_sample_value(
            "deliberation_participations_total",
            labels={
                "archon_id": str(archon_id),
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 3.0

    def test_multiple_votes_same_outcome_accumulate(self) -> None:
        """Test vote counters accumulate for same outcome."""
        registry = CollectorRegistry()
        collector = DeliberationMetricsCollector(registry=registry)
        service = AcknowledgmentRateMetricsService(metrics_collector=collector)
        archon_id = uuid4()

        # Record multiple ACKNOWLEDGE votes
        service.record_vote(archon_id, "ACKNOWLEDGE")
        service.record_vote(archon_id, "ACKNOWLEDGE")

        sample = registry.get_sample_value(
            "deliberation_votes_total",
            labels={
                "archon_id": str(archon_id),
                "outcome": "ACKNOWLEDGE",
                "service": "archon72-api",
                "environment": "development",
            },
        )
        assert sample == 2.0
