"""Integration tests for Override Trend Analysis (Story 5.5, FR27, RT-3).

These tests verify end-to-end behavior of the override trend analysis system
including event witnessing and cross-component interactions.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.override_trend_repository import OverrideTrendData
from src.application.services.override_trend_service import (
    OverrideTrendAnalysisService,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.anti_success_alert import (
    ANTI_SUCCESS_ALERT_EVENT_TYPE,
    AlertType,
)
from src.domain.events.governance_review_required import (
    GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.override_trend_repository_stub import (
    OverrideTrendRepositoryStub,
)


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a HaltCheckerStub for testing."""
    return HaltCheckerStub()


@pytest.fixture
def trend_repository() -> OverrideTrendRepositoryStub:
    """Create an OverrideTrendRepositoryStub."""
    return OverrideTrendRepositoryStub()


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock EventWriterService that tracks written events."""
    writer = AsyncMock()
    writer.written_events: list[tuple[str, dict, str, datetime]] = []

    async def capture_event(
        *,
        event_type: str,
        payload: dict,
        agent_id: str,
        local_timestamp: datetime,
    ) -> None:
        writer.written_events.append((event_type, payload, agent_id, local_timestamp))

    writer.write_event = AsyncMock(side_effect=capture_event)
    return writer


@pytest.fixture
def service(
    trend_repository: OverrideTrendRepositoryStub,
    mock_event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> OverrideTrendAnalysisService:
    """Create OverrideTrendAnalysisService with test dependencies."""
    return OverrideTrendAnalysisService(
        trend_repository=trend_repository,
        event_writer=mock_event_writer,
        halt_checker=halt_checker,
    )


class TestAC1_90DayTrendQuery:
    """Tests for AC1: 90-Day Rolling Trend Query."""

    @pytest.mark.asyncio
    async def test_90_day_trend_query_returns_correct_data(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
    ) -> None:
        """Test 90-day trend query returns count and rate (AC1).

        Given: Override history with various timestamps
        When: I query trends
        Then: I receive 90-day rolling count and rate
        """
        now = datetime.now(timezone.utc)

        # Set up override history spanning 90 days
        history = [
            now - timedelta(days=10),
            now - timedelta(days=25),
            now - timedelta(days=40),
            now - timedelta(days=60),
            now - timedelta(days=85),
        ]
        trend_repository.set_override_history(history)

        # Query trend
        trend = await service.get_90_day_trend()

        # Verify results
        assert isinstance(trend, OverrideTrendData)
        assert trend.total_count == 5
        assert trend.period_days == 90
        assert trend.daily_rate == pytest.approx(5 / 90, rel=0.01)
        assert trend.oldest_override is not None
        assert trend.newest_override is not None


class TestAC2_50PercentIncreaseAlert:
    """Tests for AC2: 50% Increase Anti-Success Alert."""

    @pytest.mark.asyncio
    async def test_50_percent_increase_triggers_anti_success_alert(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test >50% increase triggers alert (AC2).

        Given: Override count increases >50% over 30 days
        When: Threshold is crossed
        Then: AntiSuccessAlert event is created with before/after counts
        """
        now = datetime.now(timezone.utc)

        # Set up: Previous period had 3 overrides, current has 6 (100% increase)
        history = [
            # Current period (last 30 days): 6 overrides
            now - timedelta(days=5),
            now - timedelta(days=10),
            now - timedelta(days=15),
            now - timedelta(days=18),
            now - timedelta(days=22),
            now - timedelta(days=28),
            # Previous period (30-60 days ago): 3 overrides
            now - timedelta(days=35),
            now - timedelta(days=45),
            now - timedelta(days=55),
        ]
        trend_repository.set_override_history(history)

        # Analyze
        result = await service.analyze_50_percent_increase()

        # Verify alert triggered
        assert result.alert_triggered is True
        assert result.before_count == 3
        assert result.after_count == 6
        assert result.percentage_change == 100.0
        assert result.event_written is True

        # Verify event written with correct type and payload
        assert len(mock_event_writer.written_events) == 1
        event_type, payload, agent_id, local_timestamp = mock_event_writer.written_events[0]
        assert event_type == ANTI_SUCCESS_ALERT_EVENT_TYPE
        assert payload["alert_type"] == AlertType.PERCENTAGE_INCREASE.value
        assert payload["before_count"] == 3
        assert payload["after_count"] == 6
        assert agent_id == "system.trend_analysis"
        assert isinstance(local_timestamp, datetime)


class TestAC3_30DayThresholdAlert:
    """Tests for AC3: 30-Day Threshold Alert (>5 overrides)."""

    @pytest.mark.asyncio
    async def test_30_day_threshold_triggers_alert(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test >5 overrides in 30 days triggers alert (AC3).

        Given: >5 overrides in any 30-day period
        When: Threshold is crossed
        Then: Alert is triggered
        """
        now = datetime.now(timezone.utc)

        # Set up: 7 overrides in last 30 days
        history = [now - timedelta(days=i * 4) for i in range(7)]
        trend_repository.set_override_history(history)

        # Check threshold
        result = await service.check_30_day_threshold()

        # Verify alert triggered
        assert result.threshold_exceeded is True
        assert result.count == 7
        assert result.threshold == 5
        assert result.event_written is True

        # Verify event written
        assert len(mock_event_writer.written_events) == 1
        event_type, payload, agent_id, local_timestamp = mock_event_writer.written_events[0]
        assert event_type == ANTI_SUCCESS_ALERT_EVENT_TYPE
        assert payload["alert_type"] == AlertType.THRESHOLD_30_DAY.value


class TestAC4_365DayGovernanceReview:
    """Tests for AC4: 365-Day Governance Review Trigger (RT-3)."""

    @pytest.mark.asyncio
    async def test_365_day_governance_review_triggered(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test >20 overrides in 365 days triggers governance review (RT-3).

        Given: >20 overrides in any 365-day rolling window (RT-3)
        When: Threshold is crossed
        Then: Governance review is triggered
        And: GovernanceReviewRequiredEvent is created
        """
        now = datetime.now(timezone.utc)

        # Set up: 22 overrides in last 365 days
        history = [now - timedelta(days=i * 15) for i in range(22)]
        trend_repository.set_override_history(history)

        # Check governance trigger
        result = await service.check_365_day_governance_trigger()

        # Verify governance review triggered
        assert result.threshold_exceeded is True
        assert result.count == 22
        assert result.threshold == 20
        assert result.event_written is True

        # Verify governance review event written
        assert len(mock_event_writer.written_events) == 1
        event_type, payload, agent_id, local_timestamp = mock_event_writer.written_events[0]
        assert event_type == GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE
        assert payload["override_count"] == 22
        assert payload["threshold"] == 20
        assert payload["window_days"] == 365


class TestEventWitnessing:
    """Tests for event witnessing (CT-12).

    Note: Payload witnessing (signable_content) is tested in domain event unit tests.
    These integration tests verify the payload dict has all required fields for witnessing.
    The EventWriterService handles the actual witnessing workflow.
    """

    @pytest.mark.asyncio
    async def test_anti_success_alert_payload_has_witnessable_fields(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test AntiSuccessAlert payload has all fields needed for witnessing.

        Constitutional Constraint (CT-12): Witnessing creates accountability.
        The payload dict must contain all fields that would be in signable_content.
        """
        now = datetime.now(timezone.utc)

        # Trigger 30-day threshold
        history = [now - timedelta(days=i * 3) for i in range(8)]
        trend_repository.set_override_history(history)

        await service.check_30_day_threshold()

        # Verify payload has all required witnessing fields
        _, payload, agent_id, local_timestamp = mock_event_writer.written_events[0]
        assert "alert_type" in payload
        assert "before_count" in payload
        assert "after_count" in payload
        assert "percentage_change" in payload
        assert "window_days" in payload
        assert "detected_at" in payload
        # Agent ID required for attribution
        assert agent_id == "system.trend_analysis"

    @pytest.mark.asyncio
    async def test_governance_review_payload_has_witnessable_fields(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test GovernanceReviewRequired payload has all fields for witnessing.

        Constitutional Constraint (CT-12): Witnessing creates accountability.
        """
        now = datetime.now(timezone.utc)

        # Trigger governance review
        history = [now - timedelta(days=i * 15) for i in range(25)]
        trend_repository.set_override_history(history)

        await service.check_365_day_governance_trigger()

        # Verify payload has all required witnessing fields
        _, payload, agent_id, local_timestamp = mock_event_writer.written_events[0]
        assert "override_count" in payload
        assert "window_days" in payload
        assert "threshold" in payload
        assert "detected_at" in payload
        # Agent ID required for attribution
        assert agent_id == "system.trend_analysis"


class TestHaltStateHandling:
    """Tests for halt state handling (CT-11)."""

    @pytest.mark.asyncio
    async def test_full_analysis_during_halt_raises_error(
        self,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test full analysis blocked during halt state.

        Constitutional Constraint (CT-11): HALT CHECK FIRST.
        """
        halt_checker = HaltCheckerStub()
        halt_checker.set_halted(True, reason="Fork detected")

        service = OverrideTrendAnalysisService(
            trend_repository=trend_repository,
            event_writer=mock_event_writer,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.run_full_analysis()

        assert "CT-11" in str(exc_info.value)
        assert "halted" in str(exc_info.value).lower()


class TestMultipleThresholds:
    """Tests for multiple threshold scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_thresholds_crossed_creates_multiple_events(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test multiple thresholds can trigger multiple events."""
        now = datetime.now(timezone.utc)

        # Set up history that crosses multiple thresholds:
        # - >5 in last 30 days (AC3)
        # - >50% increase (AC2) if previous period was lower
        # This requires careful setup
        history = [
            # Current 30 days: 8 overrides
            now - timedelta(days=2),
            now - timedelta(days=5),
            now - timedelta(days=8),
            now - timedelta(days=12),
            now - timedelta(days=16),
            now - timedelta(days=20),
            now - timedelta(days=24),
            now - timedelta(days=28),
            # Previous 30 days: 2 overrides (300% increase)
            now - timedelta(days=35),
            now - timedelta(days=50),
        ]
        trend_repository.set_override_history(history)

        # Run both checks
        result_50 = await service.analyze_50_percent_increase()
        mock_event_writer.written_events.clear()  # Clear for next check
        result_30 = await service.check_30_day_threshold()

        # Both should trigger
        assert result_50.alert_triggered is True
        assert result_30.threshold_exceeded is True

    @pytest.mark.asyncio
    async def test_full_analysis_runs_all_checks(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test run_full_analysis executes all analysis methods."""
        now = datetime.now(timezone.utc)

        # Add minimal history
        history = [now - timedelta(days=10)]
        trend_repository.set_override_history(history)

        # Run full analysis
        report = await service.run_full_analysis()

        # Verify all components present
        assert report.trend_data is not None
        assert report.anti_success_50_percent is not None
        assert report.threshold_30_day is not None
        assert report.governance_365_day is not None
        assert report.analyzed_at is not None
