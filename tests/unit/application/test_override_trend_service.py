"""Unit tests for OverrideTrendAnalysisService (Story 5.5, FR27, RT-3)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.override_trend_repository import OverrideTrendData
from src.application.services.override_trend_service import (
    AntiSuccessAnalysisResult,
    OverrideTrendAnalysisService,
    ThresholdCheckResult,
    TrendAnalysisReport,
)
from src.domain.errors.trend import InsufficientDataError
from src.domain.errors.writer import SystemHaltedError
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.override_trend_repository_stub import (
    OverrideTrendRepositoryStub,
)


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a HaltCheckerStub."""
    return HaltCheckerStub()


@pytest.fixture
def trend_repository() -> OverrideTrendRepositoryStub:
    """Create an OverrideTrendRepositoryStub."""
    return OverrideTrendRepositoryStub()


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock EventWriterService."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def service(
    trend_repository: OverrideTrendRepositoryStub,
    mock_event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> OverrideTrendAnalysisService:
    """Create an OverrideTrendAnalysisService."""
    return OverrideTrendAnalysisService(
        trend_repository=trend_repository,
        event_writer=mock_event_writer,
        halt_checker=halt_checker,
    )


class TestGet90DayTrend:
    """Tests for get_90_day_trend() method (AC1)."""

    @pytest.mark.asyncio
    async def test_returns_correct_trend_data(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
    ) -> None:
        """Test get_90_day_trend returns correct data (AC1)."""
        now = datetime.now(timezone.utc)
        history = [now - timedelta(days=i * 10) for i in range(5)]
        trend_repository.set_override_history(history)

        result = await service.get_90_day_trend()

        assert isinstance(result, OverrideTrendData)
        assert result.total_count == 5
        assert result.period_days == 90

    @pytest.mark.asyncio
    async def test_returns_empty_trend_with_no_data(
        self,
        service: OverrideTrendAnalysisService,
    ) -> None:
        """Test get_90_day_trend with no override history."""
        result = await service.get_90_day_trend()

        assert result.total_count == 0
        assert result.daily_rate == 0.0


class TestAnalyze50PercentIncrease:
    """Tests for analyze_50_percent_increase() method (AC2)."""

    @pytest.mark.asyncio
    async def test_triggers_alert_when_threshold_crossed(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test alert triggered when >50% increase (AC2)."""
        now = datetime.now(timezone.utc)
        # Previous 30 days: 2 overrides
        # Current 30 days: 5 overrides (150% increase)
        history = [
            now - timedelta(days=5),
            now - timedelta(days=10),
            now - timedelta(days=15),
            now - timedelta(days=20),
            now - timedelta(days=25),
            now - timedelta(days=40),  # Previous period
            now - timedelta(days=50),  # Previous period
        ]
        trend_repository.set_override_history(history)

        result = await service.analyze_50_percent_increase()

        assert result.alert_triggered is True
        assert result.after_count == 5
        assert result.before_count == 2
        assert result.percentage_change == 150.0
        assert result.event_written is True
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_alert_when_below_threshold(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test no alert when increase <=50%."""
        now = datetime.now(timezone.utc)
        # Previous 30 days: 4 overrides
        # Current 30 days: 5 overrides (25% increase)
        history = [
            now - timedelta(days=5),
            now - timedelta(days=10),
            now - timedelta(days=15),
            now - timedelta(days=20),
            now - timedelta(days=25),
            now - timedelta(days=35),  # Previous period
            now - timedelta(days=40),  # Previous period
            now - timedelta(days=45),  # Previous period
            now - timedelta(days=50),  # Previous period
        ]
        trend_repository.set_override_history(history)

        result = await service.analyze_50_percent_increase()

        assert result.alert_triggered is False
        assert result.event_written is False
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_zero_previous_count(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
    ) -> None:
        """Test handles zero overrides in previous period."""
        now = datetime.now(timezone.utc)
        # Only current period overrides
        history = [now - timedelta(days=5), now - timedelta(days=10)]
        trend_repository.set_override_history(history)

        result = await service.analyze_50_percent_increase()

        # Any overrides when previous was 0 = 100% increase
        assert result.alert_triggered is True
        assert result.percentage_change == 100.0


class TestCheck30DayThreshold:
    """Tests for check_30_day_threshold() method (AC3)."""

    @pytest.mark.asyncio
    async def test_triggers_alert_at_more_than_5_overrides(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test alert triggered when >5 overrides in 30 days (AC3)."""
        now = datetime.now(timezone.utc)
        # 6 overrides in 30 days
        history = [now - timedelta(days=i * 4) for i in range(6)]
        trend_repository.set_override_history(history)

        result = await service.check_30_day_threshold()

        assert result.threshold_exceeded is True
        assert result.count == 6
        assert result.threshold == 5
        assert result.event_written is True
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_alert_at_5_or_fewer_overrides(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test no alert when <=5 overrides in 30 days."""
        now = datetime.now(timezone.utc)
        # Exactly 5 overrides
        history = [now - timedelta(days=i * 5) for i in range(5)]
        trend_repository.set_override_history(history)

        result = await service.check_30_day_threshold()

        assert result.threshold_exceeded is False
        assert result.count == 5
        assert result.event_written is False
        mock_event_writer.write_event.assert_not_called()


class TestCheck365DayGovernanceTrigger:
    """Tests for check_365_day_governance_trigger() method (AC4, RT-3)."""

    @pytest.mark.asyncio
    async def test_triggers_governance_review_at_more_than_20_overrides(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test governance review triggered when >20 overrides (RT-3)."""
        now = datetime.now(timezone.utc)
        # 21 overrides in 365 days
        history = [now - timedelta(days=i * 15) for i in range(21)]
        trend_repository.set_override_history(history)

        result = await service.check_365_day_governance_trigger()

        assert result.threshold_exceeded is True
        assert result.count == 21
        assert result.threshold == 20
        assert result.event_written is True
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_trigger_at_20_or_fewer_overrides(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test no governance review when <=20 overrides."""
        now = datetime.now(timezone.utc)
        # Exactly 20 overrides
        history = [now - timedelta(days=i * 15) for i in range(20)]
        trend_repository.set_override_history(history)

        result = await service.check_365_day_governance_trigger()

        assert result.threshold_exceeded is False
        assert result.count == 20
        assert result.event_written is False
        mock_event_writer.write_event.assert_not_called()


class TestRunFullAnalysis:
    """Tests for run_full_analysis() method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test run_full_analysis checks halt first (CT-11 pattern)."""
        halt_checker = HaltCheckerStub()
        halt_checker.set_halted(True, reason="Test halt")

        service = OverrideTrendAnalysisService(
            trend_repository=trend_repository,
            event_writer=mock_event_writer,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.run_full_analysis()

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_aggregates_all_analyses(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
    ) -> None:
        """Test run_full_analysis aggregates all analysis results."""
        now = datetime.now(timezone.utc)
        # Add some history
        history = [now - timedelta(days=i * 10) for i in range(5)]
        trend_repository.set_override_history(history)

        result = await service.run_full_analysis()

        assert isinstance(result, TrendAnalysisReport)
        assert isinstance(result.trend_data, OverrideTrendData)
        assert isinstance(result.anti_success_50_percent, AntiSuccessAnalysisResult)
        assert isinstance(result.threshold_30_day, ThresholdCheckResult)
        assert isinstance(result.governance_365_day, ThresholdCheckResult)
        assert result.analyzed_at is not None

    @pytest.mark.asyncio
    async def test_full_analysis_without_event_writer(
        self,
        trend_repository: OverrideTrendRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test run_full_analysis works without event writer (query-only mode)."""
        service = OverrideTrendAnalysisService(
            trend_repository=trend_repository,
            event_writer=None,
            halt_checker=halt_checker,
        )

        result = await service.run_full_analysis()

        assert isinstance(result, TrendAnalysisReport)
        # No events written since no event_writer
        assert result.anti_success_50_percent.event_written is False
        assert result.threshold_30_day.event_written is False
        assert result.governance_365_day.event_written is False


class TestServiceConstants:
    """Tests for service constants."""

    def test_percentage_threshold(self) -> None:
        """Test PERCENTAGE_THRESHOLD is 50%."""
        assert OverrideTrendAnalysisService.PERCENTAGE_THRESHOLD == 50.0

    def test_threshold_30_day(self) -> None:
        """Test THRESHOLD_30_DAY is 5."""
        assert OverrideTrendAnalysisService.THRESHOLD_30_DAY == 5

    def test_threshold_365_day(self) -> None:
        """Test THRESHOLD_365_DAY matches RT-3 (20)."""
        assert OverrideTrendAnalysisService.THRESHOLD_365_DAY == 20


class TestEventWriterInterfaceCompliance:
    """Tests to verify correct EventWriterService interface usage."""

    @pytest.mark.asyncio
    async def test_anti_success_alert_passes_correct_interface_params(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test write_event is called with all required parameters."""
        from src.application.services.override_trend_service import (
            TREND_ANALYSIS_SYSTEM_AGENT_ID,
        )
        from src.domain.events.anti_success_alert import ANTI_SUCCESS_ALERT_EVENT_TYPE

        now = datetime.now(timezone.utc)
        # Trigger alert: >50% increase
        history = [
            now - timedelta(days=5),
            now - timedelta(days=10),
            now - timedelta(days=15),
            now - timedelta(days=40),  # Previous period: 1
        ]
        trend_repository.set_override_history(history)

        await service.analyze_50_percent_increase()

        # Verify write_event was called with correct kwargs
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert "event_type" in call_kwargs
        assert call_kwargs["event_type"] == ANTI_SUCCESS_ALERT_EVENT_TYPE

        assert "payload" in call_kwargs
        assert isinstance(call_kwargs["payload"], dict)

        assert "agent_id" in call_kwargs
        assert call_kwargs["agent_id"] == TREND_ANALYSIS_SYSTEM_AGENT_ID

        assert "local_timestamp" in call_kwargs
        assert isinstance(call_kwargs["local_timestamp"], datetime)

    @pytest.mark.asyncio
    async def test_governance_review_passes_correct_interface_params(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test governance review write_event has all required parameters."""
        from src.application.services.override_trend_service import (
            TREND_ANALYSIS_SYSTEM_AGENT_ID,
        )
        from src.domain.events.governance_review_required import (
            GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE,
        )

        now = datetime.now(timezone.utc)
        # 21 overrides in 365 days triggers governance review
        history = [now - timedelta(days=i * 15) for i in range(21)]
        trend_repository.set_override_history(history)

        await service.check_365_day_governance_trigger()

        # Verify write_event was called with correct kwargs
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert call_kwargs["event_type"] == GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE
        assert isinstance(call_kwargs["payload"], dict)
        assert call_kwargs["agent_id"] == TREND_ANALYSIS_SYSTEM_AGENT_ID
        assert isinstance(call_kwargs["local_timestamp"], datetime)

    @pytest.mark.asyncio
    async def test_payload_is_dict_not_dataclass(
        self,
        service: OverrideTrendAnalysisService,
        trend_repository: OverrideTrendRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test payload is converted to dict, not passed as dataclass."""
        now = datetime.now(timezone.utc)
        # Trigger 30-day threshold alert
        history = [now - timedelta(days=i * 4) for i in range(7)]
        trend_repository.set_override_history(history)

        await service.check_30_day_threshold()

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify it's a dict with expected keys
        assert isinstance(payload, dict)
        assert "alert_type" in payload
        assert "before_count" in payload
        assert "after_count" in payload
        assert "detected_at" in payload
        # alert_type should be string value, not enum
        assert isinstance(payload["alert_type"], str)
