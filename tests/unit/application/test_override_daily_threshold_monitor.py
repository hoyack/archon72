"""Unit tests for OverrideDailyThresholdMonitor (Story 8.4, FR145).

Tests cover:
- check_daily_threshold() when threshold not exceeded
- check_daily_threshold() when threshold exceeded (>3)
- check_daily_threshold() with existing incident (no duplicate)
- check_daily_threshold() during halt (CT-11)
- run_monitoring_cycle() convenience method
- get_current_daily_count() read-only query
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.override_daily_threshold_monitor import (
    DailyOverrideCheckResult,
    OverrideDailyThresholdMonitor,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.incident_report import (
    DAILY_OVERRIDE_THRESHOLD,
    IncidentReport,
    IncidentStatus,
    IncidentType,
)
from src.infrastructure.stubs.incident_report_repository_stub import (
    IncidentReportRepositoryStub,
)


class TestOverrideDailyThresholdMonitor:
    """Tests for OverrideDailyThresholdMonitor."""

    @pytest.fixture
    def override_repo(self) -> AsyncMock:
        """Create a mock override trend repository."""
        repo = AsyncMock()
        repo.get_override_count_for_period = AsyncMock(return_value=0)
        return repo

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def incident_service(self) -> AsyncMock:
        """Create a mock incident reporting service."""
        service = AsyncMock()
        # Return a mock incident when creating threshold incident
        mock_incident = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.OVERRIDE_THRESHOLD,
            title="Override threshold exceeded",
            timeline=[],
            cause="Test cause",
            impact="Test impact",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.DRAFT,
        )
        service.create_override_threshold_incident = AsyncMock(return_value=mock_incident)
        return service

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def monitor(
        self,
        override_repo: AsyncMock,
        incident_repo: IncidentReportRepositoryStub,
        incident_service: AsyncMock,
        halt_checker: AsyncMock,
    ) -> OverrideDailyThresholdMonitor:
        """Create a threshold monitor with test dependencies."""
        return OverrideDailyThresholdMonitor(
            override_repository=override_repo,
            incident_repository=incident_repo,
            incident_service=incident_service,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_check_threshold_not_exceeded(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
    ) -> None:
        """Test when daily threshold is not exceeded."""
        # Set override count below threshold
        override_repo.get_override_count_for_period = AsyncMock(
            return_value=DAILY_OVERRIDE_THRESHOLD - 1
        )

        result = await monitor.check_daily_threshold()

        assert isinstance(result, DailyOverrideCheckResult)
        assert result.override_count == DAILY_OVERRIDE_THRESHOLD - 1
        assert result.threshold == DAILY_OVERRIDE_THRESHOLD
        assert result.threshold_exceeded is False
        assert result.incident_created is False

    @pytest.mark.asyncio
    async def test_check_threshold_at_exactly_threshold(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
    ) -> None:
        """Test when count equals threshold (not exceeded)."""
        # Set override count exactly at threshold
        override_repo.get_override_count_for_period = AsyncMock(
            return_value=DAILY_OVERRIDE_THRESHOLD
        )

        result = await monitor.check_daily_threshold()

        # At threshold is not exceeded (FR145: >3, not >=3)
        assert result.threshold_exceeded is False
        assert result.incident_created is False

    @pytest.mark.asyncio
    async def test_check_threshold_exceeded_creates_incident(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
        incident_service: AsyncMock,
    ) -> None:
        """Test when daily threshold is exceeded (FR145)."""
        # Set override count above threshold
        override_repo.get_override_count_for_period = AsyncMock(
            return_value=DAILY_OVERRIDE_THRESHOLD + 1
        )

        result = await monitor.check_daily_threshold()

        assert result.threshold_exceeded is True
        assert result.incident_created is True
        assert result.existing_incident_id is not None

        # Incident service should be called
        incident_service.create_override_threshold_incident.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_threshold_exceeded_no_duplicate(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
        incident_repo: IncidentReportRepositoryStub,
        incident_service: AsyncMock,
    ) -> None:
        """Test no duplicate incident when one already exists."""
        # Set override count above threshold
        override_repo.get_override_count_for_period = AsyncMock(
            return_value=DAILY_OVERRIDE_THRESHOLD + 1
        )

        # Create an existing incident for today
        existing_incident = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.OVERRIDE_THRESHOLD,
            title="Existing incident",
            timeline=[],
            cause="Test",
            impact="Test",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.DRAFT,
        )
        await incident_repo.save(existing_incident)

        result = await monitor.check_daily_threshold()

        assert result.threshold_exceeded is True
        assert result.incident_created is False
        assert result.existing_incident_id == "(existing)"

        # Incident service should NOT be called (duplicate prevention)
        incident_service.create_override_threshold_incident.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_threshold_during_halt(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
        halt_checker: AsyncMock,
    ) -> None:
        """Test check blocked during halt when incident creation needed (CT-11)."""
        # Set override count above threshold
        override_repo.get_override_count_for_period = AsyncMock(
            return_value=DAILY_OVERRIDE_THRESHOLD + 1
        )

        # Simulate system halt
        halt_checker.is_halted = AsyncMock(return_value=True)
        halt_checker.get_halt_reason = AsyncMock(return_value="System is halted")

        with pytest.raises(SystemHaltedError):
            await monitor.check_daily_threshold()

    @pytest.mark.asyncio
    async def test_check_threshold_with_specific_date(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
    ) -> None:
        """Test checking threshold for a specific date."""
        specific_date = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        override_repo.get_override_count_for_period = AsyncMock(return_value=2)

        result = await monitor.check_daily_threshold(date=specific_date)

        assert result.date == specific_date
        assert result.threshold_exceeded is False

        # Verify the date range used for query
        call_args = override_repo.get_override_count_for_period.call_args
        start_date = call_args.kwargs.get("start_date") or call_args[1].get("start_date")
        assert start_date.date() == specific_date.date()

    @pytest.mark.asyncio
    async def test_run_monitoring_cycle(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
    ) -> None:
        """Test the monitoring cycle convenience method."""
        override_repo.get_override_count_for_period = AsyncMock(return_value=1)

        result = await monitor.run_monitoring_cycle()

        assert isinstance(result, DailyOverrideCheckResult)
        assert result.override_count == 1

    @pytest.mark.asyncio
    async def test_get_current_daily_count(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
    ) -> None:
        """Test read-only daily count query."""
        override_repo.get_override_count_for_period = AsyncMock(return_value=5)

        count = await monitor.get_current_daily_count()

        assert count == 5

    @pytest.mark.asyncio
    async def test_get_current_daily_count_during_halt(
        self,
        monitor: OverrideDailyThresholdMonitor,
        override_repo: AsyncMock,
        halt_checker: AsyncMock,
    ) -> None:
        """Test read-only query works during halt (CT-13)."""
        override_repo.get_override_count_for_period = AsyncMock(return_value=3)

        # Simulate system halt
        halt_checker.is_halted = AsyncMock(return_value=True)

        # Read-only query should still work (CT-13)
        count = await monitor.get_current_daily_count()

        assert count == 3
