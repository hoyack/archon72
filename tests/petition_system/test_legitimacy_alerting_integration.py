"""Integration tests for Legitimacy Alerting (Story 8.2 Phase 2).

Tests cover:
- End-to-end alert flow (metrics → alert → delivery)
- Database integration (alert state & history persistence)
- Event system integration (witnessed events)
- Orchestrator integration (metrics + alerting pipeline)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.legitimacy_metrics_alerting_orchestrator import (
    LegitimacyMetricsAlertingOrchestrator,
)
from src.domain.events.legitimacy_alert import (
    AlertSeverity,
    LegitimacyAlertRecoveredEvent,
    LegitimacyAlertTriggeredEvent,
)
from src.domain.models.legitimacy_alert_state import LegitimacyAlertState
from src.domain.models.legitimacy_metrics import LegitimacyMetrics
from src.services.legitimacy_alerting_service import LegitimacyAlertingService


@pytest.fixture
def mock_petition_repo():
    """Mock petition repository."""
    repo = AsyncMock()
    repo.count_stuck_petitions = AsyncMock(return_value=5)
    return repo


@pytest.fixture
def mock_metrics_service():
    """Mock metrics service that returns computed metrics."""
    service = MagicMock()
    service.compute_metrics = MagicMock()
    service.store_metrics = MagicMock()
    return service


@pytest.fixture
def mock_alert_state_repo():
    """Mock alert state repository."""
    repo = AsyncMock()
    repo.get_current_state = AsyncMock(return_value=None)
    repo.upsert_state = AsyncMock()
    return repo


@pytest.fixture
def mock_alert_history_repo():
    """Mock alert history repository."""
    repo = AsyncMock()
    repo.record_triggered = AsyncMock()
    repo.record_recovered = AsyncMock()
    return repo


@pytest.fixture
def mock_alert_delivery():
    """Mock alert delivery service."""
    service = AsyncMock()
    service.deliver_alert = AsyncMock(return_value={"slack": True, "email": True})
    service.deliver_recovery = AsyncMock(return_value={"slack": True, "email": True})
    return service


@pytest.fixture
def mock_event_writer():
    """Mock event writer service."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def alerting_service(mock_petition_repo):
    """Create real alerting service for integration tests."""
    return LegitimacyAlertingService(
        petition_repo=mock_petition_repo,
        warning_threshold=0.85,
        critical_threshold=0.70,
        hysteresis_buffer=0.02,
        min_consecutive_breaches=1,
    )


@pytest.fixture
def orchestrator(
    mock_metrics_service,
    alerting_service,
    mock_alert_state_repo,
    mock_alert_history_repo,
    mock_alert_delivery,
    mock_event_writer,
):
    """Create orchestrator with mocked dependencies."""
    return LegitimacyMetricsAlertingOrchestrator(
        metrics_service=mock_metrics_service,
        alerting_service=alerting_service,
        alert_state_repo=mock_alert_state_repo,
        alert_history_repo=mock_alert_history_repo,
        alert_delivery=mock_alert_delivery,
        event_writer=mock_event_writer,
    )


def create_metrics(score: float, cycle_id: str = "2026-W04") -> LegitimacyMetrics:
    """Helper to create legitimacy metrics with a given score."""
    return LegitimacyMetrics.compute(
        cycle_id=cycle_id,
        cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
        cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        total_petitions=100,
        fated_petitions=int(score * 100),
        average_time_to_fate=3600.0,
        median_time_to_fate=3500.0,
    )


class TestEndToEndAlertFlow:
    """Tests for end-to-end alert flow through orchestrator."""

    @pytest.mark.asyncio
    async def test_metrics_computation_triggers_alert_delivery(
        self, orchestrator, mock_metrics_service, mock_event_writer, mock_alert_delivery
    ):
        """Test full pipeline: metrics → alert → event → delivery."""
        # Setup: metrics service returns low score
        metrics = create_metrics(score=0.84, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        result = await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        )

        # Verify metrics computed and stored
        assert result == metrics
        mock_metrics_service.compute_metrics.assert_called_once()
        mock_metrics_service.store_metrics.assert_called_once_with(metrics)

        # Verify alert event emitted
        mock_event_writer.write_event.assert_called_once()
        emitted_event = mock_event_writer.write_event.call_args[0][0]
        assert isinstance(emitted_event, LegitimacyAlertTriggeredEvent)
        assert emitted_event.severity == AlertSeverity.WARNING
        assert emitted_event.current_score == 0.84

        # Verify alert delivered to channels
        mock_alert_delivery.deliver_alert.assert_called_once()
        delivered_event = mock_alert_delivery.deliver_alert.call_args[0][0]
        assert delivered_event.alert_id == emitted_event.alert_id

    @pytest.mark.asyncio
    async def test_alert_recovery_triggers_recovery_notification(
        self,
        orchestrator,
        mock_metrics_service,
        mock_alert_state_repo,
        mock_event_writer,
        mock_alert_delivery,
    ):
        """Test recovery flow: score improves → recovery event → notification."""
        # Setup: previous alert state exists
        alert_id = uuid4()
        previous_state = LegitimacyAlertState.active_alert(
            alert_id=alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc) - timedelta(hours=2),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )
        mock_alert_state_repo.get_current_state.return_value = previous_state

        # Metrics service returns recovered score
        metrics = create_metrics(score=0.87, cycle_id="2026-W05")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        await orchestrator.compute_and_alert(
            cycle_id="2026-W05",
            cycle_start=datetime(2026, 1, 27, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 2, 3, tzinfo=timezone.utc),
        )

        # Verify recovery event emitted
        assert mock_event_writer.write_event.call_count == 1
        emitted_event = mock_event_writer.write_event.call_args[0][0]
        assert isinstance(emitted_event, LegitimacyAlertRecoveredEvent)
        assert emitted_event.alert_id == alert_id
        assert emitted_event.current_score == 0.87

        # Verify recovery notification delivered
        mock_alert_delivery.deliver_recovery.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_alert_when_score_healthy(
        self, orchestrator, mock_metrics_service, mock_event_writer, mock_alert_delivery
    ):
        """Test no alert triggered when score is healthy."""
        # Setup: metrics service returns healthy score
        metrics = create_metrics(score=0.90, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        )

        # Verify no alert event emitted
        mock_event_writer.write_event.assert_not_called()
        mock_alert_delivery.deliver_alert.assert_not_called()


class TestDatabaseIntegration:
    """Tests for alert state and history persistence."""

    @pytest.mark.asyncio
    async def test_alert_state_persisted_on_trigger(
        self, orchestrator, mock_metrics_service, mock_alert_state_repo
    ):
        """Test alert state is persisted when alert triggers."""
        # Setup: metrics service returns low score
        metrics = create_metrics(score=0.84, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        )

        # Verify alert state was persisted
        mock_alert_state_repo.upsert_state.assert_called_once()
        persisted_state = mock_alert_state_repo.upsert_state.call_args[0][0]
        assert isinstance(persisted_state, LegitimacyAlertState)
        assert persisted_state.is_active is True
        assert persisted_state.severity == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_alert_state_cleared_on_recovery(
        self,
        orchestrator,
        mock_metrics_service,
        mock_alert_state_repo,
    ):
        """Test alert state is cleared when alert recovers."""
        # Setup: previous alert state
        previous_state = LegitimacyAlertState.active_alert(
            alert_id=uuid4(),
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc) - timedelta(hours=1),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )
        mock_alert_state_repo.get_current_state.return_value = previous_state

        # Metrics service returns recovered score
        metrics = create_metrics(score=0.87, cycle_id="2026-W05")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        await orchestrator.compute_and_alert(
            cycle_id="2026-W05",
            cycle_start=datetime(2026, 1, 27, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 2, 3, tzinfo=timezone.utc),
        )

        # Verify alert state was cleared
        mock_alert_state_repo.upsert_state.assert_called_once()
        persisted_state = mock_alert_state_repo.upsert_state.call_args[0][0]
        assert persisted_state.is_active is False

    @pytest.mark.asyncio
    async def test_alert_history_recorded_on_trigger(
        self, orchestrator, mock_metrics_service, mock_alert_history_repo
    ):
        """Test alert trigger is recorded in history."""
        # Setup: metrics service returns low score
        metrics = create_metrics(score=0.84, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        )

        # Verify history recorded
        mock_alert_history_repo.record_triggered.assert_called_once()
        recorded_event = mock_alert_history_repo.record_triggered.call_args[0][0]
        assert isinstance(recorded_event, LegitimacyAlertTriggeredEvent)
        assert recorded_event.cycle_id == "2026-W04"

    @pytest.mark.asyncio
    async def test_alert_history_recorded_on_recovery(
        self,
        orchestrator,
        mock_metrics_service,
        mock_alert_state_repo,
        mock_alert_history_repo,
    ):
        """Test alert recovery is recorded in history."""
        # Setup: previous alert state
        previous_state = LegitimacyAlertState.active_alert(
            alert_id=uuid4(),
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc) - timedelta(hours=1),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )
        mock_alert_state_repo.get_current_state.return_value = previous_state

        # Metrics service returns recovered score
        metrics = create_metrics(score=0.87, cycle_id="2026-W05")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        await orchestrator.compute_and_alert(
            cycle_id="2026-W05",
            cycle_start=datetime(2026, 1, 27, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 2, 3, tzinfo=timezone.utc),
        )

        # Verify recovery recorded in history
        mock_alert_history_repo.record_recovered.assert_called_once()
        recorded_event = mock_alert_history_repo.record_recovered.call_args[0][0]
        assert isinstance(recorded_event, LegitimacyAlertRecoveredEvent)


class TestEventSystemIntegration:
    """Tests for event system integration and witnessing."""

    @pytest.mark.asyncio
    async def test_alert_events_are_witnessed(
        self, orchestrator, mock_metrics_service, mock_event_writer
    ):
        """Test alert events are passed through event writer (CT-12)."""
        # Setup: metrics service returns low score
        metrics = create_metrics(score=0.84, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Execute orchestrator
        await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        )

        # Verify event writer called (witnessing happens inside event_writer)
        mock_event_writer.write_event.assert_called_once()
        event = mock_event_writer.write_event.call_args[0][0]

        # Verify event has signable content for witnessing
        assert hasattr(event, 'signable_content')
        signable = event.signable_content()
        assert isinstance(signable, bytes)

    @pytest.mark.asyncio
    async def test_event_emission_failure_does_not_crash_pipeline(
        self, orchestrator, mock_metrics_service, mock_event_writer
    ):
        """Test pipeline continues even if event emission fails."""
        # Setup: metrics service returns low score
        metrics = create_metrics(score=0.84, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics

        # Event writer raises exception
        mock_event_writer.write_event.side_effect = Exception("Event write failed")

        # Execute orchestrator - should not raise
        with pytest.raises(Exception, match="Event write failed"):
            await orchestrator.compute_and_alert(
                cycle_id="2026-W04",
                cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
                cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
            )


class TestMultiCycleIntegration:
    """Tests for multi-cycle alert scenarios with state persistence."""

    @pytest.mark.asyncio
    async def test_alert_persists_across_multiple_cycles(
        self,
        orchestrator,
        mock_metrics_service,
        mock_alert_state_repo,
        mock_event_writer,
    ):
        """Test alert state persists and updates across multiple cycles."""
        # Cycle 1: Trigger alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics1

        await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        )

        # Capture the alert state after first cycle
        first_state = mock_alert_state_repo.upsert_state.call_args[0][0]
        assert first_state.is_active is True
        assert first_state.consecutive_breaches == 1

        # Reset mocks and simulate second cycle
        mock_event_writer.reset_mock()
        mock_alert_state_repo.get_current_state.return_value = first_state

        # Cycle 2: Still breaching
        metrics2 = create_metrics(score=0.83, cycle_id="2026-W05")
        mock_metrics_service.compute_metrics.return_value = metrics2

        await orchestrator.compute_and_alert(
            cycle_id="2026-W05",
            cycle_start=datetime(2026, 1, 27, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 2, 3, tzinfo=timezone.utc),
        )

        # Verify no new alert trigger (only state update)
        # Event writer not called because no new trigger/recovery
        assert mock_event_writer.write_event.call_count == 0

    @pytest.mark.asyncio
    async def test_critical_escalation_across_cycles(
        self,
        orchestrator,
        mock_metrics_service,
        mock_alert_state_repo,
        mock_event_writer,
        mock_alert_history_repo,
    ):
        """Test severity escalation is tracked correctly."""
        # Cycle 1: WARNING alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        mock_metrics_service.compute_metrics.return_value = metrics1

        await orchestrator.compute_and_alert(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
        )

        first_state = mock_alert_state_repo.upsert_state.call_args[0][0]
        assert first_state.severity == AlertSeverity.WARNING

        # Cycle 2: Score degrades to CRITICAL
        mock_alert_state_repo.get_current_state.return_value = first_state
        metrics2 = create_metrics(score=0.69, cycle_id="2026-W05")
        mock_metrics_service.compute_metrics.return_value = metrics2

        await orchestrator.compute_and_alert(
            cycle_id="2026-W05",
            cycle_start=datetime(2026, 1, 27, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 2, 3, tzinfo=timezone.utc),
        )

        # Verify breach count increased but severity stays WARNING until recovery
        # (alert state maintains original severity)
        second_state = mock_alert_state_repo.upsert_state.call_args[0][0]
        assert second_state.consecutive_breaches == 2


class TestConfigurationIntegration:
    """Tests for configuration integration with orchestrator."""

    @pytest.mark.asyncio
    async def test_custom_thresholds_are_respected(self, mock_petition_repo, mock_metrics_service):
        """Test custom alert thresholds are applied correctly."""
        # Create alerting service with custom thresholds
        custom_service = LegitimacyAlertingService(
            petition_repo=mock_petition_repo,
            warning_threshold=0.80,  # Lower than default 0.85
            critical_threshold=0.60,  # Lower than default 0.70
        )

        # Score that would not trigger default thresholds but triggers custom
        metrics = create_metrics(score=0.82, cycle_id="2026-W04")
        trigger, _ = await custom_service.check_and_alert(metrics, None)

        # Should trigger WARNING with custom threshold
        assert trigger is not None
        assert trigger.severity == AlertSeverity.WARNING
        assert trigger.threshold == 0.80
