"""Unit tests for LegitimacyAlertingService (Story 8.2, FR-8.3, NFR-7.2).

Tests cover:
- Alert triggering at WARNING and CRITICAL thresholds
- Hysteresis for recovery
- Flap detection via consecutive breaches
- Alert state management
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.domain.events.legitimacy_alert import AlertSeverity
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
def alerting_service(mock_petition_repo):
    """Create alerting service with default thresholds."""
    return LegitimacyAlertingService(
        petition_repo=mock_petition_repo,
        warning_threshold=0.85,
        critical_threshold=0.70,
        hysteresis_buffer=0.02,
        min_consecutive_breaches=1,
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


class TestAlertTriggering:
    """Tests for alert triggering logic."""

    @pytest.mark.asyncio
    async def test_no_alert_when_score_healthy(self, alerting_service):
        """Test no alert when score >= 0.85."""
        metrics = create_metrics(score=0.90)
        trigger, recovery = await alerting_service.check_and_alert(metrics, None)

        assert trigger is None
        assert recovery is None

    @pytest.mark.asyncio
    async def test_warning_alert_triggered_at_threshold(self, alerting_service):
        """Test WARNING alert triggered when score < 0.85."""
        metrics = create_metrics(score=0.84)
        trigger, recovery = await alerting_service.check_and_alert(metrics, None)

        assert trigger is not None
        assert trigger.severity == AlertSeverity.WARNING
        assert trigger.current_score == 0.84
        assert trigger.threshold == 0.85
        assert trigger.stuck_petition_count == 5
        assert recovery is None

    @pytest.mark.asyncio
    async def test_critical_alert_triggered_at_threshold(self, alerting_service):
        """Test CRITICAL alert triggered when score < 0.70."""
        metrics = create_metrics(score=0.69)
        trigger, recovery = await alerting_service.check_and_alert(metrics, None)

        assert trigger is not None
        assert trigger.severity == AlertSeverity.CRITICAL
        assert trigger.current_score == 0.69
        assert trigger.threshold == 0.70
        assert recovery is None

    @pytest.mark.asyncio
    async def test_exact_boundary_no_alert(self, alerting_service):
        """Test no alert at exact threshold boundaries."""
        # Test WARNING threshold exactly - should NOT trigger (boundary inclusive)
        metrics_warning = create_metrics(score=0.85)
        trigger, recovery = await alerting_service.check_and_alert(metrics_warning, None)
        assert trigger is None

        # Test CRITICAL threshold exactly - should trigger WARNING (0.70 < 0.85)
        # Note: 0.70 is NOT < 0.70 (no CRITICAL), but IS < 0.85 (YES WARNING)
        metrics_critical = create_metrics(score=0.70)
        trigger, recovery = await alerting_service.check_and_alert(metrics_critical, None)
        assert trigger is not None
        assert trigger.severity == AlertSeverity.WARNING
        assert trigger.threshold == 0.85


class TestHysteresisRecovery:
    """Tests for hysteresis and recovery logic."""

    @pytest.mark.asyncio
    async def test_recovery_requires_hysteresis_buffer(self, alerting_service):
        """Test recovery requires score >= threshold + buffer."""
        # Trigger alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)
        assert trigger is not None

        # Create active alert state
        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )

        # Score improves but not enough (0.85 < 0.87 required)
        metrics2 = create_metrics(score=0.85, cycle_id="2026-W05")
        trigger2, recovery = await alerting_service.check_and_alert(metrics2, state)
        assert trigger2 is None
        assert recovery is None  # No recovery yet

        # Score improves above hysteresis threshold (0.87)
        metrics3 = create_metrics(score=0.87, cycle_id="2026-W06")
        trigger3, recovery2 = await alerting_service.check_and_alert(metrics3, state)
        assert trigger3 is None
        assert recovery2 is not None
        assert recovery2.current_score == 0.87
        assert recovery2.previous_score == 0.84

    @pytest.mark.asyncio
    async def test_critical_recovery_threshold(self, alerting_service):
        """Test CRITICAL alert recovery requires 0.72 (0.70 + 0.02)."""
        # Trigger CRITICAL alert
        metrics1 = create_metrics(score=0.69, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)
        assert trigger.severity == AlertSeverity.CRITICAL

        # Create active CRITICAL alert state
        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.CRITICAL,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.69,
        )

        # Score improves to 0.71 (not enough)
        metrics2 = create_metrics(score=0.71, cycle_id="2026-W05")
        _, recovery = await alerting_service.check_and_alert(metrics2, state)
        assert recovery is None

        # Score improves to 0.72 (recovery threshold met)
        metrics3 = create_metrics(score=0.72, cycle_id="2026-W06")
        _, recovery2 = await alerting_service.check_and_alert(metrics3, state)
        assert recovery2 is not None


class TestFlapDetection:
    """Tests for flap detection via consecutive breaches."""

    @pytest.mark.asyncio
    async def test_single_breach_triggers_with_default_config(self, alerting_service):
        """Test single breach triggers alert with min_consecutive_breaches=1."""
        metrics = create_metrics(score=0.84)
        trigger, _ = await alerting_service.check_and_alert(metrics, None)
        assert trigger is not None

    @pytest.mark.asyncio
    async def test_requires_consecutive_breaches_when_configured(self, mock_petition_repo):
        """Test flap detection requires N consecutive breaches."""
        service = LegitimacyAlertingService(
            petition_repo=mock_petition_repo,
            min_consecutive_breaches=2,
        )

        # First breach - no alert yet
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger1, _ = await service.check_and_alert(metrics1, None)
        assert trigger1 is None

        # Create state with 1 consecutive breach
        state = LegitimacyAlertState.no_alert(last_updated=datetime.now(timezone.utc))
        state.consecutive_breaches = 1

        # Second consecutive breach - alert triggers
        metrics2 = create_metrics(score=0.83, cycle_id="2026-W05")
        trigger2, _ = await service.check_and_alert(metrics2, state)
        assert trigger2 is not None


class TestAlertStateManagement:
    """Tests for alert state management."""

    @pytest.mark.asyncio
    async def test_alert_updates_breach_count_on_continued_breach(self, alerting_service):
        """Test active alert updates consecutive breach count."""
        # Trigger alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)

        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
            consecutive_breaches=1,
        )

        # Next cycle still breaches
        metrics2 = create_metrics(score=0.83, cycle_id="2026-W05")
        await alerting_service.check_and_alert(metrics2, state)

        assert state.consecutive_breaches == 2

    @pytest.mark.asyncio
    async def test_alert_clears_on_recovery(self, alerting_service):
        """Test alert state clears on recovery."""
        # Trigger alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)

        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )

        # Recovery
        metrics2 = create_metrics(score=0.87, cycle_id="2026-W05")
        _, recovery = await alerting_service.check_and_alert(metrics2, state)

        assert recovery is not None
        assert state.is_active is False
        assert state.consecutive_breaches == 0


class TestServiceConfiguration:
    """Tests for service configuration validation."""

    def test_invalid_threshold_ordering_raises_error(self, mock_petition_repo):
        """Test error when CRITICAL >= WARNING threshold."""
        with pytest.raises(ValueError, match="CRITICAL threshold.*must be less than"):
            LegitimacyAlertingService(
                petition_repo=mock_petition_repo,
                warning_threshold=0.70,
                critical_threshold=0.85,
            )

    def test_invalid_hysteresis_buffer_raises_error(self, mock_petition_repo):
        """Test error when hysteresis buffer out of range."""
        with pytest.raises(ValueError, match="Hysteresis buffer"):
            LegitimacyAlertingService(
                petition_repo=mock_petition_repo,
                hysteresis_buffer=0.15,  # Too large
            )

    def test_invalid_min_consecutive_breaches_raises_error(self, mock_petition_repo):
        """Test error when min_consecutive_breaches < 1."""
        with pytest.raises(ValueError, match="min_consecutive_breaches"):
            LegitimacyAlertingService(
                petition_repo=mock_petition_repo,
                min_consecutive_breaches=0,
            )


class TestSeverityEscalation:
    """Tests for alert severity escalation and de-escalation."""

    @pytest.mark.asyncio
    async def test_severity_escalation_warning_to_critical(self, alerting_service):
        """Test severity escalates from WARNING to CRITICAL as score degrades."""
        # Trigger WARNING alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)
        assert trigger.severity == AlertSeverity.WARNING

        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )

        # Score degrades to CRITICAL (< 0.70)
        metrics2 = create_metrics(score=0.69, cycle_id="2026-W05")
        await alerting_service.check_and_alert(metrics2, state)

        # State severity should remain WARNING until recovery
        # (alert state tracks original severity until recovery)
        assert state.severity == AlertSeverity.WARNING
        assert state.consecutive_breaches == 2

    @pytest.mark.asyncio
    async def test_critical_alert_from_healthy_state(self, alerting_service):
        """Test direct CRITICAL alert from healthy state."""
        metrics = create_metrics(score=0.65)
        trigger, recovery = await alerting_service.check_and_alert(metrics, None)

        assert trigger is not None
        assert trigger.severity == AlertSeverity.CRITICAL
        assert trigger.threshold == 0.70
        assert recovery is None

    @pytest.mark.asyncio
    async def test_multiple_threshold_boundaries(self, alerting_service):
        """Test behavior at multiple threshold boundaries."""
        # Just above WARNING - no alert
        metrics1 = create_metrics(score=0.851)
        trigger1, _ = await alerting_service.check_and_alert(metrics1, None)
        assert trigger1 is None

        # Just below WARNING - WARNING alert
        metrics2 = create_metrics(score=0.849)
        trigger2, _ = await alerting_service.check_and_alert(metrics2, None)
        assert trigger2 is not None
        assert trigger2.severity == AlertSeverity.WARNING

        # Just above CRITICAL - WARNING alert
        metrics3 = create_metrics(score=0.701)
        trigger3, _ = await alerting_service.check_and_alert(metrics3, None)
        assert trigger3 is not None
        assert trigger3.severity == AlertSeverity.WARNING

        # Just below CRITICAL - CRITICAL alert
        metrics4 = create_metrics(score=0.699)
        trigger4, _ = await alerting_service.check_and_alert(metrics4, None)
        assert trigger4 is not None
        assert trigger4.severity == AlertSeverity.CRITICAL


class TestStuckPetitionCounting:
    """Tests for stuck petition counting."""

    @pytest.mark.asyncio
    async def test_stuck_petition_count_included_in_trigger(self, mock_petition_repo, alerting_service):
        """Test stuck petition count is included in trigger event."""
        mock_petition_repo.count_stuck_petitions.return_value = 12

        metrics = create_metrics(score=0.84)
        trigger, _ = await alerting_service.check_and_alert(metrics, None)

        assert trigger is not None
        assert trigger.stuck_petition_count == 12
        mock_petition_repo.count_stuck_petitions.assert_called_once()

    @pytest.mark.asyncio
    async def test_stuck_petition_count_zero(self, mock_petition_repo):
        """Test alert triggers even with zero stuck petitions."""
        mock_petition_repo.count_stuck_petitions.return_value = 0
        service = LegitimacyAlertingService(petition_repo=mock_petition_repo)

        metrics = create_metrics(score=0.84)
        trigger, _ = await service.check_and_alert(metrics, None)

        assert trigger is not None
        assert trigger.stuck_petition_count == 0


class TestEventStructure:
    """Tests for alert event structure and content."""

    @pytest.mark.asyncio
    async def test_triggered_event_contains_all_required_fields(self, alerting_service):
        """Test LegitimacyAlertTriggeredEvent contains all required fields."""
        metrics = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics, None)

        assert trigger is not None
        assert trigger.alert_id is not None
        assert trigger.cycle_id == "2026-W04"
        assert trigger.current_score == 0.84
        assert trigger.threshold == 0.85
        assert trigger.severity == AlertSeverity.WARNING
        assert trigger.stuck_petition_count == 5
        assert trigger.triggered_at is not None

    @pytest.mark.asyncio
    async def test_recovered_event_contains_all_required_fields(self, alerting_service):
        """Test LegitimacyAlertRecoveredEvent contains all required fields."""
        # Trigger alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)

        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )

        # Recovery
        metrics2 = create_metrics(score=0.87, cycle_id="2026-W05")
        _, recovery = await alerting_service.check_and_alert(metrics2, state)

        assert recovery is not None
        assert recovery.alert_id == trigger.alert_id
        assert recovery.cycle_id == "2026-W05"
        assert recovery.current_score == 0.87
        assert recovery.previous_score == 0.84
        assert recovery.alert_duration_seconds is not None
        assert recovery.recovered_at is not None

    @pytest.mark.asyncio
    async def test_event_has_signable_content(self, alerting_service):
        """Test alert events support witnessing (CT-12)."""
        metrics = create_metrics(score=0.84)
        trigger, _ = await alerting_service.check_and_alert(metrics, None)

        # Alert events should have signable_content() for witnessing
        assert hasattr(trigger, 'signable_content')
        signable = trigger.signable_content()
        assert isinstance(signable, bytes)
        assert len(signable) > 0


class TestMultiCycleScenarios:
    """Tests for multi-cycle alert scenarios."""

    @pytest.mark.asyncio
    async def test_prolonged_alert_across_multiple_cycles(self, alerting_service):
        """Test alert remains active across multiple cycles."""
        # Trigger alert in W04
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)

        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
            consecutive_breaches=1,
        )

        # W05 - still breaching
        metrics2 = create_metrics(score=0.83, cycle_id="2026-W05")
        trigger2, recovery2 = await alerting_service.check_and_alert(metrics2, state)
        assert trigger2 is None  # No new trigger
        assert recovery2 is None  # No recovery
        assert state.consecutive_breaches == 2

        # W06 - still breaching
        metrics3 = create_metrics(score=0.82, cycle_id="2026-W06")
        trigger3, recovery3 = await alerting_service.check_and_alert(metrics3, state)
        assert trigger3 is None
        assert recovery3 is None
        assert state.consecutive_breaches == 3

        # W07 - recovery
        metrics4 = create_metrics(score=0.87, cycle_id="2026-W07")
        trigger4, recovery4 = await alerting_service.check_and_alert(metrics4, state)
        assert trigger4 is None
        assert recovery4 is not None
        assert state.is_active is False

    @pytest.mark.asyncio
    async def test_flapping_score_with_hysteresis(self, alerting_service):
        """Test hysteresis prevents flapping from oscillating scores."""
        # Trigger alert
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)

        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=datetime.now(timezone.utc),
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )

        # Score oscillates around threshold: 0.849, 0.851, 0.848
        # Hysteresis requires 0.87 for recovery, so no recovery/retrigger

        # 0.849 - still below threshold, no recovery
        metrics2 = create_metrics(score=0.849, cycle_id="2026-W05")
        _, recovery2 = await alerting_service.check_and_alert(metrics2, state)
        assert recovery2 is None
        assert state.is_active is True

        # 0.851 - above threshold but below hysteresis, no recovery
        metrics3 = create_metrics(score=0.851, cycle_id="2026-W06")
        _, recovery3 = await alerting_service.check_and_alert(metrics3, state)
        assert recovery3 is None
        assert state.is_active is True

        # 0.848 - below threshold again, still active
        metrics4 = create_metrics(score=0.848, cycle_id="2026-W07")
        _, recovery4 = await alerting_service.check_and_alert(metrics4, state)
        assert recovery4 is None
        assert state.is_active is True


class TestAlertDuration:
    """Tests for alert duration calculation."""

    @pytest.mark.asyncio
    async def test_alert_duration_calculated_on_recovery(self, alerting_service):
        """Test alert duration is calculated correctly on recovery."""
        # Trigger alert
        triggered_time = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        metrics1 = create_metrics(score=0.84, cycle_id="2026-W04")
        trigger, _ = await alerting_service.check_and_alert(metrics1, None)

        state = LegitimacyAlertState.active_alert(
            alert_id=trigger.alert_id,
            severity=AlertSeverity.WARNING,
            triggered_at=triggered_time,
            triggered_cycle_id="2026-W04",
            triggered_score=0.84,
        )

        # Recovery after some time
        metrics2 = create_metrics(score=0.87, cycle_id="2026-W05")
        _, recovery = await alerting_service.check_and_alert(metrics2, state)

        assert recovery is not None
        assert recovery.alert_duration_seconds > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_none_legitimacy_score_no_alert(self, alerting_service):
        """Test no alert when legitimacy score is None."""
        metrics = LegitimacyMetrics.compute(
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, tzinfo=timezone.utc),
            total_petitions=0,  # No petitions -> None score
            fated_petitions=0,
            average_time_to_fate=None,
            median_time_to_fate=None,
        )

        trigger, recovery = await alerting_service.check_and_alert(metrics, None)
        assert trigger is None
        assert recovery is None

    @pytest.mark.asyncio
    async def test_perfect_score_no_alert(self, alerting_service):
        """Test no alert when legitimacy score is 1.0 (perfect)."""
        metrics = create_metrics(score=1.0)
        trigger, recovery = await alerting_service.check_and_alert(metrics, None)
        assert trigger is None
        assert recovery is None

    @pytest.mark.asyncio
    async def test_zero_score_critical_alert(self, alerting_service):
        """Test CRITICAL alert when legitimacy score is 0.0."""
        metrics = create_metrics(score=0.0)
        trigger, recovery = await alerting_service.check_and_alert(metrics, None)
        assert trigger is not None
        assert trigger.severity == AlertSeverity.CRITICAL
        assert trigger.current_score == 0.0
