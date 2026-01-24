"""Unit tests for legitimacy metrics domain model (Story 8.1, FR-8.1, FR-8.2).

Tests legitimacy metrics computation, health checks, and health status determination.

Constitutional Constraints:
- FR-8.1: System SHALL compute legitimacy decay metric per cycle
- FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA
- FR-8.3: System SHALL alert on decay below 0.85 threshold
"""

from datetime import datetime, timezone
from uuid import uuid4

from src.domain.models.legitimacy_metrics import LegitimacyMetrics


class TestLegitimacyMetricsCompute:
    """Test legitimacy metrics computation (FR-8.1, FR-8.2)."""

    def test_compute_with_petitions_calculates_score(self):
        """Given petitions received, compute legitimacy score."""
        # Given
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)
        total_petitions = 100
        fated_petitions = 90

        # When
        metrics = LegitimacyMetrics.compute(
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=total_petitions,
            fated_petitions=fated_petitions,
            average_time_to_fate=3600.0,  # 1 hour
            median_time_to_fate=3000.0,
        )

        # Then
        assert metrics.cycle_id == cycle_id
        assert metrics.cycle_start == cycle_start
        assert metrics.cycle_end == cycle_end
        assert metrics.total_petitions == 100
        assert metrics.fated_petitions == 90
        assert metrics.legitimacy_score == 0.9  # FR-8.2: 90/100
        assert metrics.average_time_to_fate == 3600.0
        assert metrics.median_time_to_fate == 3000.0
        assert metrics.computed_at is not None
        assert metrics.metrics_id is not None

    def test_compute_with_zero_petitions_sets_score_none(self):
        """Given zero petitions, legitimacy score is None."""
        # Given
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = LegitimacyMetrics.compute(
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=0,
            fated_petitions=0,
            average_time_to_fate=None,
            median_time_to_fate=None,
        )

        # Then
        assert metrics.legitimacy_score is None  # No data
        assert metrics.average_time_to_fate is None
        assert metrics.median_time_to_fate is None

    def test_compute_with_all_fated_achieves_perfect_score(self):
        """Given all petitions fated, legitimacy score is 1.0."""
        # Given
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = LegitimacyMetrics.compute(
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=50,
            fated_petitions=50,
            average_time_to_fate=1800.0,
            median_time_to_fate=1500.0,
        )

        # Then
        assert metrics.legitimacy_score == 1.0  # Perfect responsiveness

    def test_compute_with_zero_fated_achieves_zero_score(self):
        """Given zero fated petitions, legitimacy score is 0.0."""
        # Given
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = LegitimacyMetrics.compute(
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=100,
            fated_petitions=0,
            average_time_to_fate=None,
            median_time_to_fate=None,
        )

        # Then
        assert metrics.legitimacy_score == 0.0  # No responsiveness

    def test_compute_preserves_cycle_boundaries(self):
        """Computed metrics preserve cycle start/end boundaries."""
        # Given
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = LegitimacyMetrics.compute(
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            total_petitions=50,
            fated_petitions=40,
            average_time_to_fate=2400.0,
            median_time_to_fate=2200.0,
        )

        # Then
        assert metrics.cycle_start == cycle_start
        assert metrics.cycle_end == cycle_end


class TestLegitimacyMetricsHealthCheck:
    """Test legitimacy metrics health check (FR-8.3)."""

    def test_is_healthy_returns_true_above_threshold(self):
        """Given score >= 0.85, health check passes."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=90,
            legitimacy_score=0.9,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.is_healthy(threshold=0.85) is True

    def test_is_healthy_returns_true_at_threshold(self):
        """Given score == 0.85, health check passes."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=85,
            legitimacy_score=0.85,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.is_healthy(threshold=0.85) is True

    def test_is_healthy_returns_false_below_threshold(self):
        """Given score < 0.85, health check fails."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=80,
            legitimacy_score=0.8,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.is_healthy(threshold=0.85) is False

    def test_is_healthy_returns_false_with_no_score(self):
        """Given no score (None), health check fails."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=0,
            fated_petitions=0,
            legitimacy_score=None,
            average_time_to_fate=None,
            median_time_to_fate=None,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.is_healthy(threshold=0.85) is False

    def test_is_healthy_supports_custom_threshold(self):
        """Health check supports custom threshold values."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=75,
            legitimacy_score=0.75,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.is_healthy(threshold=0.70) is True
        assert metrics.is_healthy(threshold=0.75) is True
        assert metrics.is_healthy(threshold=0.80) is False


class TestLegitimacyMetricsHealthStatus:
    """Test legitimacy metrics health status (FR-8.3)."""

    def test_health_status_healthy_above_085(self):
        """Given score >= 0.85, health status is HEALTHY."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=90,
            legitimacy_score=0.9,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "HEALTHY"

    def test_health_status_warning_between_070_and_085(self):
        """Given 0.70 <= score < 0.85, health status is WARNING."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=80,
            legitimacy_score=0.8,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "WARNING"

    def test_health_status_critical_below_070(self):
        """Given score < 0.70, health status is CRITICAL."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=60,
            legitimacy_score=0.6,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "CRITICAL"

    def test_health_status_no_data_with_no_score(self):
        """Given no score (None), health status is NO_DATA."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=0,
            fated_petitions=0,
            legitimacy_score=None,
            average_time_to_fate=None,
            median_time_to_fate=None,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "NO_DATA"

    def test_health_status_boundary_at_085(self):
        """Given score == 0.85, health status is HEALTHY (boundary)."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=85,
            legitimacy_score=0.85,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "HEALTHY"

    def test_health_status_boundary_at_070(self):
        """Given score == 0.70, health status is WARNING (boundary)."""
        # Given
        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=70,
            legitimacy_score=0.70,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "WARNING"
