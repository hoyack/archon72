"""Unit tests for constitutional health domain models (Story 8.10, ADR-10).

Tests the ConstitutionalHealthSnapshot domain model and related
threshold constants and status calculations.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- System health = worst component health (conservative)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.models.constitutional_health import (
    BREACH_CRITICAL_THRESHOLD,
    BREACH_WARNING_THRESHOLD,
    DISSENT_WARNING_THRESHOLD,
    OVERRIDE_INCIDENT_THRESHOLD,
    WITNESS_DEGRADED_THRESHOLD,
    ConstitutionalHealthMetric,
    ConstitutionalHealthSnapshot,
    ConstitutionalHealthStatus,
    MetricName,
)


class TestConstitutionalHealthStatus:
    """Tests for ConstitutionalHealthStatus enum."""

    def test_status_values_exist(self) -> None:
        """Verify all status values exist."""
        assert ConstitutionalHealthStatus.HEALTHY is not None
        assert ConstitutionalHealthStatus.WARNING is not None
        assert ConstitutionalHealthStatus.UNHEALTHY is not None

    def test_status_string_values(self) -> None:
        """Verify status string representations."""
        assert ConstitutionalHealthStatus.HEALTHY.value == "healthy"
        assert ConstitutionalHealthStatus.WARNING.value == "warning"
        assert ConstitutionalHealthStatus.UNHEALTHY.value == "unhealthy"


class TestThresholdConstants:
    """Tests for threshold constants."""

    def test_breach_thresholds(self) -> None:
        """Verify breach count thresholds match FR32."""
        assert BREACH_WARNING_THRESHOLD == 8
        assert BREACH_CRITICAL_THRESHOLD == 10

    def test_override_threshold(self) -> None:
        """Verify override threshold matches Story 8.4."""
        assert OVERRIDE_INCIDENT_THRESHOLD == 3

    def test_dissent_threshold(self) -> None:
        """Verify dissent threshold matches NFR-023."""
        assert DISSENT_WARNING_THRESHOLD == 10.0

    def test_witness_threshold(self) -> None:
        """Verify witness threshold matches FR117."""
        assert WITNESS_DEGRADED_THRESHOLD == 12


class TestMetricName:
    """Tests for MetricName enum."""

    def test_all_metric_names_exist(self) -> None:
        """Verify all required metric names exist."""
        assert MetricName.BREACH_COUNT is not None
        assert MetricName.OVERRIDE_RATE is not None
        assert MetricName.DISSENT_HEALTH is not None
        assert MetricName.WITNESS_COVERAGE is not None


class TestConstitutionalHealthMetric:
    """Tests for ConstitutionalHealthMetric dataclass."""

    def test_healthy_breach_count_metric(self) -> None:
        """Test metric with value below warning threshold."""
        metric = ConstitutionalHealthMetric(
            name=MetricName.BREACH_COUNT,
            value=5,
            warning_threshold=8,
            critical_threshold=10,
        )
        assert metric.status == ConstitutionalHealthStatus.HEALTHY
        assert metric.is_healthy is True
        assert metric.is_blocking is False

    def test_warning_breach_count_metric(self) -> None:
        """Test metric at warning threshold."""
        metric = ConstitutionalHealthMetric(
            name=MetricName.BREACH_COUNT,
            value=8,
            warning_threshold=8,
            critical_threshold=10,
        )
        assert metric.status == ConstitutionalHealthStatus.WARNING
        assert metric.is_healthy is False
        assert metric.is_blocking is False

    def test_critical_breach_count_metric(self) -> None:
        """Test metric above critical threshold."""
        metric = ConstitutionalHealthMetric(
            name=MetricName.BREACH_COUNT,
            value=11,
            warning_threshold=8,
            critical_threshold=10,
        )
        assert metric.status == ConstitutionalHealthStatus.UNHEALTHY
        assert metric.is_healthy is False
        assert metric.is_blocking is True

    def test_dissent_health_below_threshold_is_warning(self) -> None:
        """Test dissent health where low is bad (inverted)."""
        # For dissent, low values are concerning
        metric = ConstitutionalHealthMetric(
            name=MetricName.DISSENT_HEALTH,
            value=8.0,  # Below 10% threshold
            warning_threshold=10.0,
            critical_threshold=5.0,
            invert_comparison=True,  # Lower is worse
        )
        assert metric.status == ConstitutionalHealthStatus.WARNING

    def test_witness_coverage_degraded(self) -> None:
        """Test witness coverage below minimum."""
        metric = ConstitutionalHealthMetric(
            name=MetricName.WITNESS_COVERAGE,
            value=10,  # Below 12 threshold
            warning_threshold=12,
            critical_threshold=6,
            invert_comparison=True,  # Lower is worse
        )
        assert metric.status == ConstitutionalHealthStatus.WARNING

    def test_metric_to_dict(self) -> None:
        """Test serialization to dictionary."""
        metric = ConstitutionalHealthMetric(
            name=MetricName.BREACH_COUNT,
            value=5,
            warning_threshold=8,
            critical_threshold=10,
        )
        result = metric.to_dict()
        assert result["name"] == "breach_count"
        assert result["value"] == 5
        assert result["warning_threshold"] == 8
        assert result["critical_threshold"] == 10
        assert result["status"] == "healthy"


class TestConstitutionalHealthSnapshot:
    """Tests for ConstitutionalHealthSnapshot domain model."""

    def test_all_healthy_metrics(self) -> None:
        """Test snapshot when all metrics are healthy."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=5,
            override_rate_daily=1,
            dissent_health_percent=25.0,
            witness_coverage=20,
            calculated_at=datetime.now(timezone.utc),
        )
        assert snapshot.overall_status == ConstitutionalHealthStatus.HEALTHY
        assert snapshot.ceremonies_blocked is False
        assert len(snapshot.blocking_reasons) == 0

    def test_one_warning_metric(self) -> None:
        """Test snapshot with one metric at warning (AC2)."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=8,  # At warning threshold
            override_rate_daily=1,
            dissent_health_percent=25.0,
            witness_coverage=20,
            calculated_at=datetime.now(timezone.utc),
        )
        assert snapshot.overall_status == ConstitutionalHealthStatus.WARNING
        assert snapshot.ceremonies_blocked is False

    def test_one_critical_metric_blocks_ceremonies(self) -> None:
        """Test snapshot with critical metric blocks ceremonies (AC4)."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=11,  # Above critical threshold
            override_rate_daily=1,
            dissent_health_percent=25.0,
            witness_coverage=20,
            calculated_at=datetime.now(timezone.utc),
        )
        assert snapshot.overall_status == ConstitutionalHealthStatus.UNHEALTHY
        assert snapshot.ceremonies_blocked is True
        assert "breach_count" in snapshot.blocking_reasons[0].lower()

    def test_override_rate_high_triggers_warning(self) -> None:
        """Test override rate above threshold."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=0,
            override_rate_daily=4,  # Above 3/day threshold
            dissent_health_percent=25.0,
            witness_coverage=20,
            calculated_at=datetime.now(timezone.utc),
        )
        # Override rate > 3 triggers incident (warning level)
        assert snapshot.overall_status == ConstitutionalHealthStatus.WARNING

    def test_low_dissent_triggers_warning(self) -> None:
        """Test low dissent health triggers warning (NFR-023)."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=0,
            override_rate_daily=0,
            dissent_health_percent=8.0,  # Below 10% threshold
            witness_coverage=20,
            calculated_at=datetime.now(timezone.utc),
        )
        assert snapshot.overall_status == ConstitutionalHealthStatus.WARNING

    def test_degraded_witness_coverage(self) -> None:
        """Test degraded witness coverage (FR117)."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=0,
            override_rate_daily=0,
            dissent_health_percent=25.0,
            witness_coverage=10,  # Below 12 minimum
            calculated_at=datetime.now(timezone.utc),
        )
        assert snapshot.overall_status == ConstitutionalHealthStatus.WARNING

    def test_multiple_critical_metrics(self) -> None:
        """Test multiple critical metrics still results in UNHEALTHY."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=15,  # Critical
            override_rate_daily=10,  # High override
            dissent_health_percent=2.0,  # Critical low dissent
            witness_coverage=3,  # Critical low coverage
            calculated_at=datetime.now(timezone.utc),
        )
        assert snapshot.overall_status == ConstitutionalHealthStatus.UNHEALTHY
        assert snapshot.ceremonies_blocked is True
        # Should have multiple blocking reasons
        assert len(snapshot.blocking_reasons) >= 2

    def test_worst_component_health_rule(self) -> None:
        """Test ADR-10 resolution: System health = worst component health."""
        # All healthy except one critical
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=0,  # Healthy
            override_rate_daily=0,  # Healthy
            dissent_health_percent=50.0,  # Healthy
            witness_coverage=2,  # CRITICAL (< 6)
            calculated_at=datetime.now(timezone.utc),
        )
        # Overall should be UNHEALTHY (worst component)
        assert snapshot.overall_status == ConstitutionalHealthStatus.UNHEALTHY

    def test_get_all_metrics(self) -> None:
        """Test getting all metrics as list."""
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=5,
            override_rate_daily=1,
            dissent_health_percent=25.0,
            witness_coverage=20,
            calculated_at=datetime.now(timezone.utc),
        )
        metrics = snapshot.get_all_metrics()
        assert len(metrics) == 4
        metric_names = {m.name for m in metrics}
        assert MetricName.BREACH_COUNT in metric_names
        assert MetricName.OVERRIDE_RATE in metric_names
        assert MetricName.DISSENT_HEALTH in metric_names
        assert MetricName.WITNESS_COVERAGE in metric_names

    def test_to_dict_serialization(self) -> None:
        """Test full snapshot serialization."""
        now = datetime.now(timezone.utc)
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=5,
            override_rate_daily=1,
            dissent_health_percent=25.0,
            witness_coverage=20,
            calculated_at=now,
        )
        result = snapshot.to_dict()
        assert result["overall_status"] == "healthy"
        assert result["ceremonies_blocked"] is False
        assert result["blocking_reasons"] == []
        assert "metrics" in result
        assert len(result["metrics"]) == 4
        assert result["calculated_at"] == now.isoformat()


class TestConstitutionalHealthMetricValidation:
    """Tests for metric validation."""

    def test_negative_value_allowed(self) -> None:
        """Test that negative values are allowed (for edge cases)."""
        # Negative values might occur in delta calculations
        metric = ConstitutionalHealthMetric(
            name=MetricName.BREACH_COUNT,
            value=-1,
            warning_threshold=8,
            critical_threshold=10,
        )
        # Negative is below threshold, so healthy
        assert metric.status == ConstitutionalHealthStatus.HEALTHY

    def test_float_values_for_percentages(self) -> None:
        """Test float values work correctly for percentage metrics."""
        metric = ConstitutionalHealthMetric(
            name=MetricName.DISSENT_HEALTH,
            value=9.99,  # Just below 10%
            warning_threshold=10.0,
            critical_threshold=5.0,
            invert_comparison=True,
        )
        assert metric.status == ConstitutionalHealthStatus.WARNING
