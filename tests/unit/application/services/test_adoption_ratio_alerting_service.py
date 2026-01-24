"""Unit tests for adoption ratio alerting service (Story 8.6, PREVENT-7).

Tests adoption ratio alerting including alert creation, resolution,
and event emission.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.adoption_ratio_alerting_service import (
    ADOPTION_RATIO_CRITICAL_THRESHOLD,
    ADOPTION_RATIO_THRESHOLD,
    AdoptionRatioAlertingService,
)
from src.domain.models.adoption_ratio import (
    AdoptionRatioAlert,
    AdoptionRatioMetrics,
)


class TestAdoptionRatioAlertingServiceThresholds:
    """Test alert threshold constants (PREVENT-7)."""

    def test_threshold_is_fifty_percent(self):
        """Alert threshold is 50% per PREVENT-7."""
        assert ADOPTION_RATIO_THRESHOLD == 0.50

    def test_critical_threshold_is_seventy_percent(self):
        """Critical threshold is 70%."""
        assert ADOPTION_RATIO_CRITICAL_THRESHOLD == 0.70


class TestAdoptionRatioAlertingServiceTrigger:
    """Test alert triggering (PREVENT-7)."""

    @pytest.mark.asyncio
    async def test_trigger_alert_when_threshold_exceeded(self):
        """Given metrics exceeding threshold, trigger alert."""
        # Given
        repository = AsyncMock()
        repository.get_active_alert.return_value = None  # No active alert

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # 55% adoption ratio - exceeds 50% threshold
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=11,  # 55%
            adopting_kings=[uuid4()],
        )

        # When
        exceeded_event, normalized_event = await service.check_and_alert(
            metrics=metrics,
            trend_delta=0.10,
        )

        # Then
        assert exceeded_event is not None
        assert normalized_event is None
        assert exceeded_event.adoption_ratio == 0.55
        assert exceeded_event.threshold == 0.50
        assert exceeded_event.severity == "WARN"
        assert exceeded_event.trend_delta == 0.10

        # Alert was saved
        repository.save_alert.assert_called_once()

        # Event was emitted (CT-12)
        event_emitter.emit_exceeded.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_critical_alert_above_seventy_percent(self):
        """Given metrics > 70%, trigger CRITICAL alert."""
        # Given
        repository = AsyncMock()
        repository.get_active_alert.return_value = None

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # 75% adoption ratio - critical level
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=15,  # 75%
            adopting_kings=[uuid4()],
        )

        # When
        exceeded_event, _ = await service.check_and_alert(metrics=metrics)

        # Then
        assert exceeded_event is not None
        assert exceeded_event.severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_no_duplicate_alert_when_already_active(self):
        """Given active alert exists, do not create duplicate."""
        # Given
        repository = AsyncMock()

        # Simulate active alert
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
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            resolved_at=None,
            status="ACTIVE",
        )
        repository.get_active_alert.return_value = existing_alert

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # Still exceeding threshold
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=13,  # 65%
            adopting_kings=[uuid4()],
        )

        # When
        exceeded_event, normalized_event = await service.check_and_alert(metrics=metrics)

        # Then
        assert exceeded_event is None  # No new alert
        assert normalized_event is None
        repository.save_alert.assert_not_called()
        event_emitter.emit_exceeded.assert_not_called()


class TestAdoptionRatioAlertingServiceResolution:
    """Test alert auto-resolution (PREVENT-7)."""

    @pytest.mark.asyncio
    async def test_resolve_alert_when_ratio_normalizes(self):
        """Given ratio below threshold, resolve active alert."""
        # Given
        repository = AsyncMock()

        # Simulate active alert
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
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            resolved_at=None,
            status="ACTIVE",
        )
        repository.get_active_alert.return_value = existing_alert

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # Ratio normalized to 40%
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=8,  # 40% - below threshold
            adopting_kings=[uuid4()],
        )

        # When
        exceeded_event, normalized_event = await service.check_and_alert(metrics=metrics)

        # Then
        assert exceeded_event is None
        assert normalized_event is not None
        assert normalized_event.new_adoption_ratio == 0.40
        assert normalized_event.previous_ratio == 0.60
        assert normalized_event.alert_duration_seconds > 0

        # Alert was resolved in repository
        repository.resolve_alert.assert_called_once()

        # Event was emitted (CT-12)
        event_emitter.emit_normalized.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_action_when_healthy_and_no_alert(self):
        """Given healthy ratio and no active alert, do nothing."""
        # Given
        repository = AsyncMock()
        repository.get_active_alert.return_value = None  # No active alert

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # Healthy ratio
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=8,  # 40%
            adopting_kings=[uuid4()],
        )

        # When
        exceeded_event, normalized_event = await service.check_and_alert(metrics=metrics)

        # Then
        assert exceeded_event is None
        assert normalized_event is None
        repository.save_alert.assert_not_called()
        repository.resolve_alert.assert_not_called()
        event_emitter.emit_exceeded.assert_not_called()
        event_emitter.emit_normalized.assert_not_called()


class TestAdoptionRatioAlertingServiceEventPayloads:
    """Test event payload structure (CT-12)."""

    @pytest.mark.asyncio
    async def test_exceeded_event_contains_required_fields(self):
        """Exceeded event payload contains all required fields."""
        # Given
        repository = AsyncMock()
        repository.get_active_alert.return_value = None

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        king_id = uuid4()
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=12,  # 60%
            adopting_kings=[king_id],
        )

        # When
        exceeded_event, _ = await service.check_and_alert(
            metrics=metrics,
            trend_delta=0.05,
        )

        # Then
        assert exceeded_event is not None
        assert exceeded_event.event_id is not None
        assert exceeded_event.alert_id is not None
        assert exceeded_event.realm_id == "governance"
        assert exceeded_event.cycle_id == "2026-W04"
        assert exceeded_event.adoption_ratio == 0.60
        assert exceeded_event.threshold == 0.50
        assert exceeded_event.severity == "WARN"
        assert str(king_id) in exceeded_event.adopting_kings
        assert exceeded_event.adoption_count == 12
        assert exceeded_event.escalation_count == 20
        assert exceeded_event.trend_delta == 0.05
        assert exceeded_event.occurred_at is not None
        assert exceeded_event.schema_version == 1

    @pytest.mark.asyncio
    async def test_normalized_event_contains_required_fields(self):
        """Normalized event payload contains all required fields."""
        # Given
        repository = AsyncMock()

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
            created_at=datetime.now(timezone.utc) - timedelta(hours=6),
            resolved_at=None,
            status="ACTIVE",
        )
        repository.get_active_alert.return_value = existing_alert

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # Normalized ratio
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=8,  # 40%
            adopting_kings=[uuid4()],
        )

        # When
        _, normalized_event = await service.check_and_alert(metrics=metrics)

        # Then
        assert normalized_event is not None
        assert normalized_event.event_id is not None
        assert normalized_event.alert_id == existing_alert.alert_id
        assert normalized_event.realm_id == "governance"
        assert normalized_event.cycle_id == "2026-W04"
        assert normalized_event.new_adoption_ratio == 0.40
        assert normalized_event.previous_ratio == 0.60
        assert normalized_event.alert_duration_seconds > 0
        assert normalized_event.normalized_at is not None
        assert normalized_event.schema_version == 1


class TestAdoptionRatioAlertingServiceQueries:
    """Test query methods."""

    @pytest.mark.asyncio
    async def test_get_active_alerts_returns_all_active(self):
        """Get all active alerts from repository."""
        # Given
        repository = AsyncMock()
        alert1 = AdoptionRatioAlert(
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
        alert2 = AdoptionRatioAlert(
            alert_id=uuid4(),
            realm_id="council",
            cycle_id="2026-W04",
            adoption_count=16,
            escalation_count=20,
            adoption_ratio=0.80,
            threshold=0.50,
            adopting_kings=(uuid4(),),
            severity="CRITICAL",
            trend_delta=None,
            created_at=datetime.now(timezone.utc),
            resolved_at=None,
            status="ACTIVE",
        )
        repository.get_all_active_alerts.return_value = [alert1, alert2]

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # When
        alerts = await service.get_active_alerts()

        # Then
        assert len(alerts) == 2
        assert alerts[0].realm_id == "governance"
        assert alerts[1].realm_id == "council"

    @pytest.mark.asyncio
    async def test_get_realm_alert_status(self):
        """Get alert status for a specific realm."""
        # Given
        repository = AsyncMock()
        existing_alert = AdoptionRatioAlert(
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
        repository.get_active_alert.return_value = existing_alert

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # When
        status = await service.get_realm_alert_status("governance")

        # Then
        assert status["has_active_alert"] is True
        assert status["alert"] == existing_alert


class TestAdoptionRatioAlertingServiceNoData:
    """Test behavior with no data."""

    @pytest.mark.asyncio
    async def test_no_alert_when_no_escalations(self):
        """Given no escalations (ratio is None), do not alert."""
        # Given
        repository = AsyncMock()
        repository.get_active_alert.return_value = None

        event_emitter = AsyncMock()

        service = AdoptionRatioAlertingService(
            repository=repository,
            event_emitter=event_emitter,
        )

        # No escalations
        metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=0,
            adoption_count=0,
            adopting_kings=[],
        )

        # When
        exceeded_event, normalized_event = await service.check_and_alert(metrics=metrics)

        # Then
        assert exceeded_event is None
        assert normalized_event is None
        # ratio is None, exceeds_threshold returns False
        assert metrics.adoption_ratio is None
        assert metrics.exceeds_threshold(0.50) is False
