"""Unit tests for adoption ratio domain model (Story 8.6, PREVENT-7).

Tests adoption ratio metrics computation, threshold checking, severity determination,
alert creation, and resolution.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
- CT-11: Adoption is a scarce resource
- CT-12: Events witnessed and immutable
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.adoption_ratio import (
    AdoptionRatioAlert,
    AdoptionRatioMetrics,
)


class TestAdoptionRatioMetricsCompute:
    """Test adoption ratio metrics computation (PREVENT-7)."""

    def test_compute_with_escalations_calculates_ratio(self):
        """Given escalations and adoptions, compute adoption ratio."""
        # Given
        realm_id = "technology"
        cycle_id = "2026-W04"
        escalation_count = 100
        adoption_count = 40
        king_id = uuid4()

        # When
        metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=escalation_count,
            adoption_count=adoption_count,
            adopting_kings=[king_id],
        )

        # Then
        assert metrics.realm_id == realm_id
        assert metrics.cycle_id == cycle_id
        assert metrics.escalation_count == 100
        assert metrics.adoption_count == 40
        assert metrics.adoption_ratio == 0.4  # 40/100
        assert len(metrics.adopting_kings) == 1
        assert metrics.adopting_kings[0] == king_id
        assert metrics.computed_at is not None
        assert metrics.metrics_id is not None

    def test_compute_with_zero_escalations_sets_ratio_none(self):
        """Given zero escalations, adoption ratio is None (PREVENT-7)."""
        # Given
        realm_id = "technology"
        cycle_id = "2026-W04"

        # When
        metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=0,
            adoption_count=0,
            adopting_kings=[],
        )

        # Then
        assert metrics.adoption_ratio is None  # No data, not 0

    def test_compute_with_all_adopted_achieves_100_percent(self):
        """Given all escalations adopted, ratio is 1.0."""
        # Given
        realm_id = "technology"
        cycle_id = "2026-W04"
        king_id = uuid4()

        # When
        metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=50,
            adoption_count=50,
            adopting_kings=[king_id],
        )

        # Then
        assert metrics.adoption_ratio == 1.0

    def test_compute_with_zero_adopted_achieves_zero_ratio(self):
        """Given zero adoptions, ratio is 0.0."""
        # Given
        realm_id = "technology"
        cycle_id = "2026-W04"

        # When
        metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=100,
            adoption_count=0,
            adopting_kings=[],
        )

        # Then
        assert metrics.adoption_ratio == 0.0

    def test_compute_with_multiple_adopting_kings(self):
        """Metrics track multiple adopting Kings."""
        # Given
        realm_id = "technology"
        cycle_id = "2026-W04"
        king_ids = [uuid4(), uuid4(), uuid4()]

        # When
        metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=100,
            adoption_count=30,
            adopting_kings=king_ids,
        )

        # Then
        assert len(metrics.adopting_kings) == 3
        assert set(metrics.adopting_kings) == set(king_ids)

    def test_compute_accepts_tuple_for_adopting_kings(self):
        """Compute accepts tuple for adopting kings (immutable input)."""
        # Given
        king_id = uuid4()

        # When
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=30,
            adopting_kings=(king_id,),
        )

        # Then
        assert metrics.adopting_kings[0] == king_id


class TestAdoptionRatioMetricsThreshold:
    """Test adoption ratio threshold checking (PREVENT-7)."""

    def test_exceeds_threshold_returns_true_above_50_percent(self):
        """Given ratio > 0.50, exceeds_threshold returns True."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=55,
            adoption_ratio=0.55,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.exceeds_threshold() is True
        assert metrics.exceeds_threshold(threshold=0.50) is True

    def test_exceeds_threshold_returns_false_at_50_percent(self):
        """Given ratio == 0.50, exceeds_threshold returns False (boundary)."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=50,
            adoption_ratio=0.50,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.exceeds_threshold(threshold=0.50) is False

    def test_exceeds_threshold_returns_false_below_50_percent(self):
        """Given ratio < 0.50, exceeds_threshold returns False."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=40,
            adoption_ratio=0.40,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.exceeds_threshold(threshold=0.50) is False

    def test_exceeds_threshold_returns_false_with_no_ratio(self):
        """Given no ratio (None), exceeds_threshold returns False."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=0,
            adoption_count=0,
            adoption_ratio=None,
            adopting_kings=(),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.exceeds_threshold(threshold=0.50) is False

    def test_exceeds_threshold_supports_custom_threshold(self):
        """Threshold checking supports custom threshold values."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=65,
            adoption_ratio=0.65,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.exceeds_threshold(threshold=0.60) is True
        assert metrics.exceeds_threshold(threshold=0.65) is False
        assert metrics.exceeds_threshold(threshold=0.70) is False


class TestAdoptionRatioMetricsSeverity:
    """Test adoption ratio severity determination (PREVENT-7)."""

    def test_severity_returns_none_at_or_below_50_percent(self):
        """Given ratio <= 0.50, severity is None."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=50,
            adoption_ratio=0.50,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.severity() is None

    def test_severity_returns_warn_between_50_and_70_percent(self):
        """Given 0.50 < ratio <= 0.70, severity is WARN."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=60,
            adoption_ratio=0.60,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.severity() == "WARN"

    def test_severity_returns_warn_at_70_percent_boundary(self):
        """Given ratio == 0.70, severity is WARN (boundary)."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=70,
            adoption_ratio=0.70,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.severity() == "WARN"

    def test_severity_returns_critical_above_70_percent(self):
        """Given ratio > 0.70, severity is CRITICAL."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=80,
            adoption_ratio=0.80,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.severity() == "CRITICAL"

    def test_severity_returns_none_with_no_ratio(self):
        """Given no ratio (None), severity is None."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=0,
            adoption_count=0,
            adoption_ratio=None,
            adopting_kings=(),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.severity() is None


class TestAdoptionRatioMetricsHealthStatus:
    """Test adoption ratio health status for dashboard."""

    def test_health_status_healthy_at_or_below_50_percent(self):
        """Given ratio <= 0.50, health status is HEALTHY."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=40,
            adoption_ratio=0.40,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "HEALTHY"

    def test_health_status_warn_between_50_and_70_percent(self):
        """Given 0.50 < ratio <= 0.70, health status is WARN."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=60,
            adoption_ratio=0.60,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "WARN"

    def test_health_status_critical_above_70_percent(self):
        """Given ratio > 0.70, health status is CRITICAL."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=80,
            adoption_ratio=0.80,
            adopting_kings=(uuid4(),),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "CRITICAL"

    def test_health_status_no_data_with_no_ratio(self):
        """Given no ratio (None), health status is NO_DATA."""
        # Given
        metrics = AdoptionRatioMetrics(
            metrics_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=0,
            adoption_count=0,
            adoption_ratio=None,
            adopting_kings=(),
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        assert metrics.health_status() == "NO_DATA"


class TestAdoptionRatioAlertCreate:
    """Test adoption ratio alert creation (PREVENT-7)."""

    def test_create_alert_from_exceeding_metrics(self):
        """Given metrics exceeding threshold, create alert."""
        # Given
        king_id = uuid4()
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=60,
            adopting_kings=[king_id],
        )

        # When
        alert = AdoptionRatioAlert.create(
            realm_id="technology",
            cycle_id="2026-W04",
            metrics=metrics,
            trend_delta=0.05,
        )

        # Then
        assert alert.realm_id == "technology"
        assert alert.cycle_id == "2026-W04"
        assert alert.adoption_count == 60
        assert alert.escalation_count == 100
        assert alert.adoption_ratio == 0.6
        assert alert.threshold == 0.50
        assert alert.severity == "WARN"
        assert alert.trend_delta == 0.05
        assert alert.status == "ACTIVE"
        assert alert.resolved_at is None
        assert king_id in alert.adopting_kings

    def test_create_alert_critical_severity_above_70_percent(self):
        """Given ratio > 0.70, alert has CRITICAL severity."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=80,
            adopting_kings=[uuid4()],
        )

        # When
        alert = AdoptionRatioAlert.create(
            realm_id="technology",
            cycle_id="2026-W04",
            metrics=metrics,
        )

        # Then
        assert alert.severity == "CRITICAL"

    def test_create_alert_raises_error_below_threshold(self):
        """Given metrics below threshold, raise ValueError."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=40,
            adopting_kings=[uuid4()],
        )

        # When/Then
        with pytest.raises(ValueError, match="does not exceed threshold"):
            AdoptionRatioAlert.create(
                realm_id="technology",
                cycle_id="2026-W04",
                metrics=metrics,
            )

    def test_create_alert_raises_error_with_no_ratio(self):
        """Given no ratio data, raise ValueError."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=0,
            adoption_count=0,
            adopting_kings=[],
        )

        # When/Then
        with pytest.raises(ValueError, match="no adoption ratio data"):
            AdoptionRatioAlert.create(
                realm_id="technology",
                cycle_id="2026-W04",
                metrics=metrics,
            )

    def test_create_alert_supports_custom_threshold(self):
        """Alert creation supports custom threshold values."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=45,
            adopting_kings=[uuid4()],
        )

        # When
        alert = AdoptionRatioAlert.create(
            realm_id="technology",
            cycle_id="2026-W04",
            metrics=metrics,
            threshold=0.40,  # Lower threshold
        )

        # Then
        assert alert.threshold == 0.40
        assert alert.adoption_ratio == 0.45


class TestAdoptionRatioAlertResolve:
    """Test adoption ratio alert resolution."""

    def test_resolve_creates_resolved_alert(self):
        """Resolving alert creates new alert with RESOLVED status."""
        # Given
        king_id = uuid4()
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=60,
            adopting_kings=[king_id],
        )
        alert = AdoptionRatioAlert.create(
            realm_id="technology",
            cycle_id="2026-W04",
            metrics=metrics,
        )
        resolved_at = datetime(2026, 1, 28, 12, 0, 0, tzinfo=timezone.utc)

        # When
        resolved_alert = alert.resolve(resolved_at=resolved_at)

        # Then
        assert resolved_alert.status == "RESOLVED"
        assert resolved_alert.resolved_at == resolved_at
        assert resolved_alert.alert_id == alert.alert_id
        assert resolved_alert.realm_id == alert.realm_id
        # Original alert unchanged (frozen dataclass)
        assert alert.status == "ACTIVE"
        assert alert.resolved_at is None

    def test_resolve_defaults_to_now(self):
        """Resolving alert without timestamp defaults to now."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=60,
            adopting_kings=[uuid4()],
        )
        alert = AdoptionRatioAlert.create(
            realm_id="technology",
            cycle_id="2026-W04",
            metrics=metrics,
        )

        # When
        resolved_alert = alert.resolve()

        # Then
        assert resolved_alert.status == "RESOLVED"
        assert resolved_alert.resolved_at is not None


class TestAdoptionRatioAlertDuration:
    """Test adoption ratio alert duration calculation."""

    def test_alert_duration_seconds(self):
        """Calculate alert duration in seconds."""
        # Given
        created_at = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        resolved_at = datetime(2026, 1, 20, 11, 30, 0, tzinfo=timezone.utc)

        alert = AdoptionRatioAlert(
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_count=60,
            escalation_count=100,
            adoption_ratio=0.60,
            threshold=0.50,
            adopting_kings=(uuid4(),),
            severity="WARN",
            trend_delta=None,
            created_at=created_at,
            resolved_at=None,
            status="ACTIVE",
        )

        # When
        duration = alert.alert_duration_seconds(resolved_at)

        # Then
        assert duration == 5400  # 1.5 hours in seconds

    def test_is_active_property(self):
        """Check is_active property."""
        # Given
        active_alert = AdoptionRatioAlert(
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_count=60,
            escalation_count=100,
            adoption_ratio=0.60,
            threshold=0.50,
            adopting_kings=(uuid4(),),
            severity="WARN",
            trend_delta=None,
            created_at=datetime.now(timezone.utc),
            resolved_at=None,
            status="ACTIVE",
        )

        resolved_alert = AdoptionRatioAlert(
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_count=60,
            escalation_count=100,
            adoption_ratio=0.60,
            threshold=0.50,
            adopting_kings=(uuid4(),),
            severity="WARN",
            trend_delta=None,
            created_at=datetime.now(timezone.utc),
            resolved_at=datetime.now(timezone.utc),
            status="RESOLVED",
        )

        # When/Then
        assert active_alert.is_active is True
        assert resolved_alert.is_active is False


class TestAdoptionRatioMetricsImmutability:
    """Test domain model immutability (CT-12)."""

    def test_metrics_is_frozen_dataclass(self):
        """AdoptionRatioMetrics is immutable (CT-12)."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=60,
            adopting_kings=[uuid4()],
        )

        # When/Then
        with pytest.raises(Exception):  # FrozenInstanceError
            metrics.adoption_ratio = 0.99  # type: ignore

    def test_alert_is_frozen_dataclass(self):
        """AdoptionRatioAlert is immutable (CT-12)."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="technology",
            cycle_id="2026-W04",
            escalation_count=100,
            adoption_count=60,
            adopting_kings=[uuid4()],
        )
        alert = AdoptionRatioAlert.create(
            realm_id="technology",
            cycle_id="2026-W04",
            metrics=metrics,
        )

        # When/Then
        with pytest.raises(Exception):  # FrozenInstanceError
            alert.status = "RESOLVED"  # type: ignore
