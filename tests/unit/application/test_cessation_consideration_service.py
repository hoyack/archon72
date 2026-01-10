"""Unit tests for CessationConsiderationService (Story 6.3, FR32).

Tests cover:
- check_and_trigger_cessation() behavior at various breach counts
- record_cessation_decision() validation and event creation
- get_breach_count_status() trajectory calculation
- get_breach_alert_status() alert levels
- HALT CHECK on all operations
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.cessation_consideration_service import (
    CESSATION_SYSTEM_AGENT_ID,
    CessationConsiderationService,
)
from src.domain.errors.cessation import (
    CessationConsiderationNotFoundError,
    InvalidCessationDecisionError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import BreachEventPayload, BreachSeverity, BreachType
from src.domain.events.cessation import (
    CESSATION_CONSIDERATION_EVENT_TYPE,
    CESSATION_DECISION_EVENT_TYPE,
    CessationConsiderationEventPayload,
    CessationDecision,
    CessationDecisionEventPayload,
)
from src.domain.models.breach_count_status import BreachTrajectory


@pytest.fixture
def mock_breach_repository() -> AsyncMock:
    """Create a mock breach repository."""
    mock = AsyncMock()
    mock.count_unacknowledged_in_window = AsyncMock(return_value=0)
    mock.get_unacknowledged_in_window = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_cessation_repository() -> AsyncMock:
    """Create a mock cessation repository."""
    mock = AsyncMock()
    mock.get_active_consideration = AsyncMock(return_value=None)
    mock.get_consideration_by_id = AsyncMock(return_value=None)
    mock.get_decision_for_consideration = AsyncMock(return_value=None)
    mock.save_consideration = AsyncMock()
    mock.save_decision = AsyncMock()
    return mock


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer."""
    mock = AsyncMock()
    mock.write_event = AsyncMock()
    return mock


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create a mock halt checker (not halted by default)."""
    mock = AsyncMock()
    mock.is_halted = AsyncMock(return_value=False)
    mock.get_halt_reason = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def service(
    mock_breach_repository: AsyncMock,
    mock_cessation_repository: AsyncMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
) -> CessationConsiderationService:
    """Create service with mocked dependencies."""
    return CessationConsiderationService(
        breach_repository=mock_breach_repository,
        cessation_repository=mock_cessation_repository,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
    )


def _create_breach(
    detection_time: datetime | None = None,
) -> BreachEventPayload:
    """Helper to create a breach payload."""
    from types import MappingProxyType

    if detection_time is None:
        detection_time = datetime.now(timezone.utc)
    return BreachEventPayload(
        breach_id=uuid4(),
        breach_type=BreachType.THRESHOLD_VIOLATION,
        violated_requirement="FR32",
        severity=BreachSeverity.MEDIUM,
        detection_timestamp=detection_time,
        details=MappingProxyType({"description": "Test breach"}),
    )


class TestCheckAndTriggerCessation:
    """Tests for check_and_trigger_cessation method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        service: CessationConsiderationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK is performed first (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_and_trigger_cessation()

        assert "CT-11" in str(exc_info.value)
        mock_halt_checker.is_halted.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_trigger_at_10_breaches(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test cessation is NOT triggered at exactly 10 breaches (FR32: >10)."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 10

        result = await service.check_and_trigger_cessation()

        assert result is None

    @pytest.mark.asyncio
    async def test_triggers_at_11_breaches(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
        mock_cessation_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test cessation IS triggered at 11 breaches (FR32: >10)."""
        breaches = [_create_breach() for _ in range(11)]
        mock_breach_repository.count_unacknowledged_in_window.return_value = 11
        mock_breach_repository.get_unacknowledged_in_window.return_value = breaches

        result = await service.check_and_trigger_cessation()

        assert result is not None
        assert result.breach_count == 11
        assert len(result.unacknowledged_breach_ids) == 11
        mock_event_writer.write_event.assert_called_once()
        mock_cessation_repository.save_consideration.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_if_active_consideration_exists(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test cessation is skipped if active consideration already exists."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 15
        existing = CessationConsiderationEventPayload(
            consideration_id=uuid4(),
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Test",
        )
        mock_cessation_repository.get_active_consideration.return_value = existing

        result = await service.check_and_trigger_cessation()

        assert result is None

    @pytest.mark.asyncio
    async def test_event_type_is_correct(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test correct event type is used for consideration event."""
        breaches = [_create_breach() for _ in range(11)]
        mock_breach_repository.count_unacknowledged_in_window.return_value = 11
        mock_breach_repository.get_unacknowledged_in_window.return_value = breaches

        await service.check_and_trigger_cessation()

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == CESSATION_CONSIDERATION_EVENT_TYPE
        assert call_kwargs["agent_id"] == CESSATION_SYSTEM_AGENT_ID


class TestRecordCessationDecision:
    """Tests for record_cessation_decision method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        service: CessationConsiderationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK is performed first (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.record_cessation_decision(
                consideration_id=uuid4(),
                decision=CessationDecision.DISMISS_CONSIDERATION,
                decided_by="Test",
                rationale="Test rationale",
            )

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fails_for_nonexistent_consideration(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test decision fails if consideration doesn't exist."""
        mock_cessation_repository.get_consideration_by_id.return_value = None

        with pytest.raises(CessationConsiderationNotFoundError):
            await service.record_cessation_decision(
                consideration_id=uuid4(),
                decision=CessationDecision.DISMISS_CONSIDERATION,
                decided_by="Test",
                rationale="Test rationale",
            )

    @pytest.mark.asyncio
    async def test_fails_if_decision_already_recorded(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test decision fails if decision already exists."""
        consideration_id = uuid4()
        existing_consideration = CessationConsiderationEventPayload(
            consideration_id=consideration_id,
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Test",
        )
        existing_decision = CessationDecisionEventPayload(
            decision_id=uuid4(),
            consideration_id=consideration_id,
            decision=CessationDecision.DISMISS_CONSIDERATION,
            decision_timestamp=datetime.now(timezone.utc),
            decided_by="Previous",
            rationale="Previous decision",
        )
        mock_cessation_repository.get_consideration_by_id.return_value = (
            existing_consideration
        )
        mock_cessation_repository.get_decision_for_consideration.return_value = (
            existing_decision
        )

        with pytest.raises(InvalidCessationDecisionError) as exc_info:
            await service.record_cessation_decision(
                consideration_id=consideration_id,
                decision=CessationDecision.PROCEED_TO_VOTE,
                decided_by="Test",
                rationale="Test rationale",
            )

        assert "already recorded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_creates_witnessed_event(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test decision creates witnessed event (CT-12)."""
        consideration_id = uuid4()
        existing = CessationConsiderationEventPayload(
            consideration_id=consideration_id,
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Test",
        )
        mock_cessation_repository.get_consideration_by_id.return_value = existing
        mock_cessation_repository.get_decision_for_consideration.return_value = None

        result = await service.record_cessation_decision(
            consideration_id=consideration_id,
            decision=CessationDecision.DISMISS_CONSIDERATION,
            decided_by="Conclave Session 42",
            rationale="Breaches addressed",
        )

        assert result.decision == CessationDecision.DISMISS_CONSIDERATION
        assert result.decided_by == "Conclave Session 42"
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == CESSATION_DECISION_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_rejects_empty_decided_by(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test decision rejects empty decided_by."""
        consideration_id = uuid4()
        existing = CessationConsiderationEventPayload(
            consideration_id=consideration_id,
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Test",
        )
        mock_cessation_repository.get_consideration_by_id.return_value = existing

        with pytest.raises(InvalidCessationDecisionError) as exc_info:
            await service.record_cessation_decision(
                consideration_id=consideration_id,
                decision=CessationDecision.DISMISS_CONSIDERATION,
                decided_by="",
                rationale="Test rationale",
            )

        assert "cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rejects_whitespace_decided_by(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test decision rejects whitespace-only decided_by."""
        consideration_id = uuid4()
        existing = CessationConsiderationEventPayload(
            consideration_id=consideration_id,
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Test",
        )
        mock_cessation_repository.get_consideration_by_id.return_value = existing

        with pytest.raises(InvalidCessationDecisionError) as exc_info:
            await service.record_cessation_decision(
                consideration_id=consideration_id,
                decision=CessationDecision.DISMISS_CONSIDERATION,
                decided_by="   ",  # whitespace only
                rationale="Test rationale",
            )

        assert "cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rejects_empty_rationale(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test decision rejects empty rationale."""
        consideration_id = uuid4()
        existing = CessationConsiderationEventPayload(
            consideration_id=consideration_id,
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Test",
        )
        mock_cessation_repository.get_consideration_by_id.return_value = existing

        with pytest.raises(InvalidCessationDecisionError) as exc_info:
            await service.record_cessation_decision(
                consideration_id=consideration_id,
                decision=CessationDecision.DISMISS_CONSIDERATION,
                decided_by="Test",
                rationale="   ",  # whitespace only
            )

        assert "cannot be empty" in str(exc_info.value)


class TestGetBreachCountStatus:
    """Tests for get_breach_count_status method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        service: CessationConsiderationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK is performed first (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError):
            await service.get_breach_count_status()

    @pytest.mark.asyncio
    async def test_returns_correct_count(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns correct breach count."""
        breaches = [_create_breach() for _ in range(5)]
        mock_breach_repository.get_unacknowledged_in_window.return_value = breaches

        status = await service.get_breach_count_status()

        assert status.current_count == 5

    @pytest.mark.asyncio
    async def test_trajectory_calculation(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test trajectory is calculated."""
        breaches = [_create_breach() for _ in range(3)]
        mock_breach_repository.get_unacknowledged_in_window.return_value = breaches

        status = await service.get_breach_count_status()

        # Should have a trajectory value
        assert status.trajectory is not None

    @pytest.mark.asyncio
    async def test_trajectory_increasing_when_recent_breaches_dominate(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test trajectory is INCREASING when recent breaches exceed older by >2."""
        now = datetime.now(timezone.utc)
        # Create 5 recent breaches (within last 45 days)
        recent_breaches = [
            _create_breach(detection_time=now - timedelta(days=i * 5))
            for i in range(5)
        ]
        # Create 1 older breach (>45 days ago)
        older_breaches = [
            _create_breach(detection_time=now - timedelta(days=60)),
        ]
        all_breaches = recent_breaches + older_breaches
        mock_breach_repository.get_unacknowledged_in_window.return_value = all_breaches

        status = await service.get_breach_count_status()

        # 5 recent vs 1 older = INCREASING (5 > 1 + 2)
        assert status.trajectory == BreachTrajectory.INCREASING

    @pytest.mark.asyncio
    async def test_trajectory_decreasing_when_older_breaches_dominate(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test trajectory is DECREASING when older breaches exceed recent by >2."""
        now = datetime.now(timezone.utc)
        # Create 1 recent breach (within last 45 days)
        recent_breaches = [
            _create_breach(detection_time=now - timedelta(days=10)),
        ]
        # Create 5 older breaches (>45 days ago)
        older_breaches = [
            _create_breach(detection_time=now - timedelta(days=50 + i * 5))
            for i in range(5)
        ]
        all_breaches = recent_breaches + older_breaches
        mock_breach_repository.get_unacknowledged_in_window.return_value = all_breaches

        status = await service.get_breach_count_status()

        # 1 recent vs 5 older = DECREASING (1 < 5 - 2)
        assert status.trajectory == BreachTrajectory.DECREASING

    @pytest.mark.asyncio
    async def test_trajectory_stable_when_counts_similar(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test trajectory is STABLE when recent and older breach counts are similar."""
        now = datetime.now(timezone.utc)
        # Create 3 recent breaches (within last 45 days)
        recent_breaches = [
            _create_breach(detection_time=now - timedelta(days=i * 10))
            for i in range(3)
        ]
        # Create 3 older breaches (>45 days ago)
        older_breaches = [
            _create_breach(detection_time=now - timedelta(days=50 + i * 10))
            for i in range(3)
        ]
        all_breaches = recent_breaches + older_breaches
        mock_breach_repository.get_unacknowledged_in_window.return_value = all_breaches

        status = await service.get_breach_count_status()

        # 3 recent vs 3 older = STABLE (difference <= 2)
        assert status.trajectory == BreachTrajectory.STABLE


class TestGetBreachAlertStatus:
    """Tests for get_breach_alert_status method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        service: CessationConsiderationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK is performed first (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError):
            await service.get_breach_alert_status()

    @pytest.mark.asyncio
    async def test_returns_none_below_warning(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns None when below warning threshold."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 5

        result = await service.get_breach_alert_status()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_warning_at_8(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns WARNING at 8 breaches."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 8

        result = await service.get_breach_alert_status()

        assert result == "WARNING"

    @pytest.mark.asyncio
    async def test_returns_warning_at_10(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns WARNING at 10 breaches (not yet critical)."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 10

        result = await service.get_breach_alert_status()

        assert result == "WARNING"

    @pytest.mark.asyncio
    async def test_returns_critical_at_11(
        self,
        service: CessationConsiderationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns CRITICAL at 11 breaches (>10)."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 11

        result = await service.get_breach_alert_status()

        assert result == "CRITICAL"


class TestIsCessationConsiderationActive:
    """Tests for is_cessation_consideration_active method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        service: CessationConsiderationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK is performed first (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError):
            await service.is_cessation_consideration_active()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_consideration(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test returns False when no active consideration."""
        mock_cessation_repository.get_active_consideration.return_value = None

        result = await service.is_cessation_consideration_active()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_active_consideration_exists(
        self,
        service: CessationConsiderationService,
        mock_cessation_repository: AsyncMock,
    ) -> None:
        """Test returns True when active consideration exists."""
        existing = CessationConsiderationEventPayload(
            consideration_id=uuid4(),
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Test",
        )
        mock_cessation_repository.get_active_consideration.return_value = existing

        result = await service.is_cessation_consideration_active()

        assert result is True
