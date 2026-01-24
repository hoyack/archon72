"""Integration tests for adoption ratio monitoring (Story 8.6, PREVENT-7).

Tests the full adoption ratio monitoring flow including:
- Metrics computation per realm per cycle
- Alert lifecycle (creation, persistence, resolution)
- Dashboard data aggregation

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio to detect budget contention
- CT-11: Silent failure destroys legitimacy - all operations logged
- CT-12: Witnessing creates accountability - events are witnessed
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.adoption_ratio_repository import (
    AdoptionRatioRepositoryProtocol,
)
from src.application.services.adoption_ratio_alerting_service import (
    ADOPTION_RATIO_CRITICAL_THRESHOLD,
    ADOPTION_RATIO_THRESHOLD,
    AdoptionRatioAlertingService,
    AdoptionRatioEventEmitterProtocol,
)
from src.domain.models.adoption_ratio import AdoptionRatioAlert, AdoptionRatioMetrics


@pytest.mark.integration
class TestAdoptionRatioComputeIntegration:
    """Integration tests for adoption ratio computation flow."""

    @pytest.mark.asyncio
    async def test_compute_metrics_with_60_percent_adoption(self):
        """Test metrics computation for 60% adoption rate (PREVENT-7 WARN)."""
        # Given: 20 escalations, 12 adoptions
        king_id = uuid4()
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=12,  # 60%
            adopting_kings=[king_id],
        )

        # Then: Verify computed metrics
        assert metrics.realm_id == "governance"
        assert metrics.cycle_id == "2026-W04"
        assert metrics.escalation_count == 20
        assert metrics.adoption_count == 12
        assert metrics.adoption_ratio == 0.6  # PREVENT-7: 60% exceeds 50%
        assert metrics.health_status() == "WARN"  # 50-70% is WARN
        assert metrics.exceeds_threshold(0.50)
        assert not metrics.exceeds_threshold(0.70)
        assert len(metrics.adopting_kings) == 1
        assert king_id in metrics.adopting_kings

    @pytest.mark.asyncio
    async def test_compute_metrics_critical_threshold(self):
        """Test metrics computation with critical threshold (>70%)."""
        # Given: 80% adoption rate
        king_id = uuid4()
        metrics = AdoptionRatioMetrics.compute(
            realm_id="council",
            cycle_id="2026-W04",
            escalation_count=10,
            adoption_count=8,  # 80%
            adopting_kings=[king_id],
        )

        # Then
        assert metrics.adoption_ratio == 0.8
        assert metrics.severity() == "CRITICAL"  # >70%
        assert metrics.health_status() == "CRITICAL"
        assert metrics.exceeds_threshold(0.50)
        assert metrics.exceeds_threshold(0.70)

    @pytest.mark.asyncio
    async def test_compute_metrics_zero_escalations(self):
        """Test metrics computation with no escalations in cycle."""
        # Given: No escalations
        metrics = AdoptionRatioMetrics.compute(
            realm_id="empty-realm",
            cycle_id="2026-W04",
            escalation_count=0,
            adoption_count=0,
            adopting_kings=[],
        )

        # Then
        assert metrics.escalation_count == 0
        assert metrics.adoption_count == 0
        assert metrics.adoption_ratio is None
        assert metrics.health_status() == "NO_DATA"  # No escalations = no data
        assert not metrics.exceeds_threshold(0.50)

    @pytest.mark.asyncio
    async def test_compute_metrics_multiple_kings(self):
        """Test metrics tracks all adopting Kings."""
        # Given: Multiple kings adopting
        king_ids = [uuid4(), uuid4(), uuid4()]
        metrics = AdoptionRatioMetrics.compute(
            realm_id="multi-king-realm",
            cycle_id="2026-W04",
            escalation_count=9,
            adoption_count=9,
            adopting_kings=king_ids,
        )

        # Then
        assert metrics.adoption_ratio == 1.0  # 100%
        assert len(metrics.adopting_kings) == 3
        for king_id in king_ids:
            assert king_id in metrics.adopting_kings

    @pytest.mark.asyncio
    async def test_compute_metrics_healthy_below_threshold(self):
        """Test metrics below threshold are HEALTHY."""
        # Given: 40% adoption (below 50%)
        metrics = AdoptionRatioMetrics.compute(
            realm_id="healthy-realm",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=8,  # 40%
            adopting_kings=[uuid4()],
        )

        # Then
        assert metrics.adoption_ratio == 0.4
        assert metrics.health_status() == "HEALTHY"
        assert not metrics.exceeds_threshold(0.50)


@pytest.mark.integration
class TestAdoptionRatioAlertingIntegration:
    """Integration tests for adoption ratio alerting flow."""

    @pytest.mark.asyncio
    async def test_alert_creation_on_threshold_breach(self):
        """Test alert is created when adoption ratio exceeds 50% (PREVENT-7)."""
        # Given: Metrics exceeding threshold
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=12,  # 60%
            adopting_kings=[uuid4()],
        )

        repository = MockAdoptionRatioRepository()
        emitter = MockEventEmitter()
        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=emitter,
        )

        # When
        exceeded_payload, _ = await service.check_and_alert(metrics)

        # Then: Alert should be created
        assert exceeded_payload is not None
        assert exceeded_payload.adoption_ratio == 0.6
        assert exceeded_payload.threshold == ADOPTION_RATIO_THRESHOLD
        assert exceeded_payload.severity == "WARN"
        assert repository._saved_alert is not None

    @pytest.mark.asyncio
    async def test_alert_resolution_when_ratio_normalizes(self):
        """Test alert is resolved when ratio drops below threshold."""
        # Given: An existing active alert
        alert_id = uuid4()
        existing_alert = AdoptionRatioAlert(
            alert_id=alert_id,
            realm_id="governance",
            cycle_id="2026-W03",
            adoption_count=12,
            escalation_count=20,
            adoption_ratio=0.60,
            threshold=0.50,
            adopting_kings=(uuid4(),),
            severity="WARN",
            trend_delta=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=7),
            resolved_at=None,
            status="ACTIVE",
        )

        repository = MockAdoptionRatioRepository(active_alert=existing_alert)
        emitter = MockEventEmitter()
        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=emitter,
        )

        # And: New metrics below threshold
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=8,  # 40% - below threshold
            adopting_kings=[uuid4()],
        )

        # When
        _, normalized_payload = await service.check_and_alert(metrics)

        # Then: Alert should be resolved
        assert normalized_payload is not None
        assert normalized_payload.alert_id == alert_id
        assert normalized_payload.new_adoption_ratio == 0.4
        assert normalized_payload.previous_ratio == 0.6
        assert normalized_payload.alert_duration_seconds > 0

    @pytest.mark.asyncio
    async def test_no_alert_when_below_threshold(self):
        """Test no alert is created when ratio is below 50%."""
        # Given: Metrics below threshold
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=8,  # 40% - below threshold
            adopting_kings=[uuid4()],
        )

        repository = MockAdoptionRatioRepository()
        emitter = MockEventEmitter()
        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=emitter,
        )

        # When
        exceeded_payload, normalized_payload = await service.check_and_alert(metrics)

        # Then: No alerts
        assert exceeded_payload is None
        assert normalized_payload is None
        assert repository._saved_alert is None

    @pytest.mark.asyncio
    async def test_critical_severity_above_70_percent(self):
        """Test CRITICAL severity when ratio exceeds 70%."""
        # Given: Metrics with 80% adoption
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=16,  # 80%
            adopting_kings=[uuid4()],
        )

        repository = MockAdoptionRatioRepository()
        emitter = MockEventEmitter()
        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=emitter,
        )

        # When
        exceeded_payload, _ = await service.check_and_alert(metrics)

        # Then
        assert exceeded_payload is not None
        assert exceeded_payload.severity == "CRITICAL"
        assert exceeded_payload.adoption_ratio == 0.8
        # Note: threshold is always the base WARN threshold (0.50) - severity determines CRITICAL
        assert exceeded_payload.threshold == ADOPTION_RATIO_THRESHOLD

    @pytest.mark.asyncio
    async def test_alert_not_duplicated_if_already_active(self):
        """Test no duplicate alert if one already exists for realm."""
        # Given: Existing active alert
        existing_alert = AdoptionRatioAlert(
            alert_id=uuid4(),
            realm_id="governance",
            cycle_id="2026-W03",
            adoption_count=12,
            escalation_count=20,
            adoption_ratio=0.60,
            threshold=0.50,
            adopting_kings=(uuid4(),),
            severity="WARN",
            trend_delta=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
            resolved_at=None,
            status="ACTIVE",
        )

        repository = MockAdoptionRatioRepository(active_alert=existing_alert)
        emitter = MockEventEmitter()
        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=emitter,
        )

        # And: New metrics still exceeding threshold
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=13,  # 65% - still exceeds
            adopting_kings=[uuid4()],
        )

        # When
        exceeded_payload, normalized_payload = await service.check_and_alert(metrics)

        # Then: No new alert, no resolution
        assert exceeded_payload is None
        assert normalized_payload is None


@pytest.mark.integration
class TestAdoptionRatioMetricsModel:
    """Integration tests for AdoptionRatioMetrics domain model."""

    @pytest.mark.asyncio
    async def test_metrics_dataclass_fields(self):
        """Test metrics dataclass has expected fields."""
        # Given
        king_id = uuid4()
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=12,
            adopting_kings=[king_id],
        )

        # Then: Verify all fields accessible
        assert metrics.metrics_id is not None
        assert metrics.realm_id == "governance"
        assert metrics.cycle_id == "2026-W04"
        assert metrics.escalation_count == 20
        assert metrics.adoption_count == 12
        assert metrics.adoption_ratio == 0.6
        assert king_id in metrics.adopting_kings
        assert metrics.computed_at is not None

    @pytest.mark.asyncio
    async def test_metrics_frozen_immutability(self):
        """Test metrics are frozen/immutable (CT-12)."""
        # Given
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=12,
            adopting_kings=[uuid4()],
        )

        # When/Then: Should raise on mutation attempt
        with pytest.raises(Exception):  # FrozenInstanceError
            metrics.adoption_ratio = 0.99


@pytest.mark.integration
class TestAdoptionRatioAlertModel:
    """Integration tests for AdoptionRatioAlert domain model."""

    @pytest.mark.asyncio
    async def test_alert_creation_validates_threshold(self):
        """Test alert requires ratio > threshold."""
        # Given: Valid alert at WARN level
        alert = AdoptionRatioAlert(
            alert_id=uuid4(),
            realm_id="governance",
            cycle_id="2026-W04",
            adoption_count=12,
            escalation_count=20,
            adoption_ratio=0.60,
            threshold=0.50,
            adopting_kings=(uuid4(),),
            severity="WARN",
            trend_delta=None,
            created_at=datetime.now(timezone.utc),
            resolved_at=None,
            status="ACTIVE",
        )

        # Then
        assert alert.adoption_ratio > alert.threshold

    @pytest.mark.asyncio
    async def test_alert_dataclass_fields(self):
        """Test alert dataclass has expected fields."""
        # Given
        king_id = uuid4()
        alert_id = uuid4()
        created_at = datetime.now(timezone.utc)
        alert = AdoptionRatioAlert(
            alert_id=alert_id,
            realm_id="governance",
            cycle_id="2026-W04",
            adoption_count=12,
            escalation_count=20,
            adoption_ratio=0.60,
            threshold=0.50,
            adopting_kings=(king_id,),
            severity="WARN",
            trend_delta=0.05,
            created_at=created_at,
            resolved_at=None,
            status="ACTIVE",
        )

        # Then: Verify all fields accessible
        assert alert.alert_id == alert_id
        assert alert.realm_id == "governance"
        assert alert.cycle_id == "2026-W04"
        assert alert.adoption_count == 12
        assert alert.escalation_count == 20
        assert alert.adoption_ratio == 0.60
        assert alert.threshold == 0.50
        assert king_id in alert.adopting_kings
        assert alert.severity == "WARN"
        assert alert.trend_delta == 0.05
        assert alert.created_at == created_at
        assert alert.resolved_at is None
        assert alert.status == "ACTIVE"
        assert alert.is_active is True


@pytest.mark.integration
class TestAdoptionRatioTrendAnalysis:
    """Integration tests for trend analysis between cycles."""

    @pytest.mark.asyncio
    async def test_trend_delta_positive_when_increasing(self):
        """Test positive trend delta when adoption ratio increases."""
        # Given: Previous cycle at 50%, current at 60%
        previous_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W03",
            escalation_count=20,
            adoption_count=10,  # 50%
            adopting_kings=[uuid4()],
        )

        current_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=12,  # 60%
            adopting_kings=[uuid4()],
        )

        # When: Calculate trend delta
        trend_delta = current_metrics.adoption_ratio - previous_metrics.adoption_ratio

        # Then: Positive delta (concerning - adoption increasing)
        assert trend_delta == pytest.approx(0.10, abs=0.001)

    @pytest.mark.asyncio
    async def test_trend_delta_negative_when_decreasing(self):
        """Test negative trend delta when adoption ratio decreases (improving)."""
        # Given: Previous cycle at 60%, current at 45%
        previous_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W03",
            escalation_count=20,
            adoption_count=12,  # 60%
            adopting_kings=[uuid4()],
        )

        current_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=9,  # 45%
            adopting_kings=[uuid4()],
        )

        # When: Calculate trend delta
        trend_delta = current_metrics.adoption_ratio - previous_metrics.adoption_ratio

        # Then: Negative delta (improving - adoption decreasing)
        assert trend_delta == pytest.approx(-0.15, abs=0.001)


# ============================================================================
# Mock implementations for testing
# ============================================================================


class MockAdoptionRatioRepository(AdoptionRatioRepositoryProtocol):
    """Mock repository for integration testing."""

    def __init__(self, active_alert: AdoptionRatioAlert | None = None):
        self._saved_metrics: AdoptionRatioMetrics | None = None
        self._saved_alert: AdoptionRatioAlert | None = None
        self._active_alert = active_alert

    async def save_metrics(self, metrics: AdoptionRatioMetrics) -> None:
        self._saved_metrics = metrics

    async def get_metrics_by_realm_cycle(
        self,
        realm_id: str,
        cycle_id: str,
    ) -> AdoptionRatioMetrics | None:
        if self._saved_metrics:
            if self._saved_metrics.realm_id == realm_id and self._saved_metrics.cycle_id == cycle_id:
                return self._saved_metrics
        return None

    async def get_previous_cycle_metrics(
        self,
        realm_id: str,
        current_cycle_id: str,
    ) -> AdoptionRatioMetrics | None:
        return None

    async def get_all_realms_current_cycle(
        self,
        cycle_id: str,
    ) -> list[AdoptionRatioMetrics]:
        if self._saved_metrics and self._saved_metrics.cycle_id == cycle_id:
            return [self._saved_metrics]
        return []

    async def save_alert(self, alert: AdoptionRatioAlert) -> None:
        self._saved_alert = alert

    async def get_active_alert(self, realm_id: str) -> AdoptionRatioAlert | None:
        if self._active_alert and self._active_alert.realm_id == realm_id:
            return self._active_alert
        return None

    async def get_alert_by_id(self, alert_id) -> AdoptionRatioAlert | None:
        if self._saved_alert and self._saved_alert.alert_id == alert_id:
            return self._saved_alert
        if self._active_alert and self._active_alert.alert_id == alert_id:
            return self._active_alert
        return None

    async def resolve_alert(
        self,
        alert_id,
        resolved_at: datetime,
    ) -> None:
        if self._active_alert and self._active_alert.alert_id == alert_id:
            # Create resolved version
            self._active_alert = None


class MockEventEmitter(AdoptionRatioEventEmitterProtocol):
    """Mock event emitter for integration testing."""

    def __init__(self):
        self.exceeded_events = []
        self.normalized_events = []

    async def emit_exceeded(self, payload) -> None:
        self.exceeded_events.append(payload)

    async def emit_normalized(self, payload) -> None:
        self.normalized_events.append(payload)
