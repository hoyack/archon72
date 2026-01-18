"""Unit tests for AutomaticAgendaPlacementService (Story 7.1, FR37-FR38, RT-4).

This module tests the automatic agenda placement service including:
- FR37: 3 consecutive failures in 30 days trigger
- RT-4: 5 failures in 90-day rolling window trigger
- FR38: Anti-success alert sustained 90 days trigger
- AC4: Idempotent triggers
- AC5: Event witnessing (CT-12)
- AC6: Halt state check (CT-11)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.automatic_agenda_placement_service import (
    AGENDA_PLACEMENT_SYSTEM_AGENT_ID,
    ANTI_SUCCESS_SUSTAINED_THRESHOLD_DAYS,
    CONSECUTIVE_FAILURE_THRESHOLD,
    CONSECUTIVE_FAILURE_WINDOW_DAYS,
    ROLLING_WINDOW_DAYS,
    ROLLING_WINDOW_THRESHOLD,
    AutomaticAgendaPlacementService,
)
from src.domain.errors import SystemHaltedError
from src.domain.events.cessation_agenda import AgendaTriggerType
from src.infrastructure.stubs.anti_success_alert_repository_stub import (
    AntiSuccessAlertRepositoryStub,
)
from src.infrastructure.stubs.cessation_agenda_repository_stub import (
    CessationAgendaRepositoryStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.integrity_failure_repository_stub import (
    IntegrityFailureRepositoryStub,
)


@pytest.fixture
def integrity_failure_repo() -> IntegrityFailureRepositoryStub:
    """Create an integrity failure repository stub."""
    return IntegrityFailureRepositoryStub()


@pytest.fixture
def anti_success_repo() -> AntiSuccessAlertRepositoryStub:
    """Create an anti-success alert repository stub."""
    return AntiSuccessAlertRepositoryStub()


@pytest.fixture
def cessation_agenda_repo() -> CessationAgendaRepositoryStub:
    """Create a cessation agenda repository stub."""
    return CessationAgendaRepositoryStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def event_writer() -> AsyncMock:
    """Create a mock event writer."""
    writer = AsyncMock()
    writer.write_event = AsyncMock(return_value=None)
    return writer


@pytest.fixture
def service(
    integrity_failure_repo: IntegrityFailureRepositoryStub,
    anti_success_repo: AntiSuccessAlertRepositoryStub,
    cessation_agenda_repo: CessationAgendaRepositoryStub,
    event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> AutomaticAgendaPlacementService:
    """Create the service with all dependencies."""
    return AutomaticAgendaPlacementService(
        integrity_failure_repo=integrity_failure_repo,
        anti_success_repo=anti_success_repo,
        cessation_agenda_repo=cessation_agenda_repo,
        event_writer=event_writer,
        halt_checker=halt_checker,
    )


class TestHaltStateCheck:
    """Tests for CT-11 halt state compliance (AC6)."""

    @pytest.mark.asyncio
    async def test_check_consecutive_failures_raises_when_halted(
        self,
        service: AutomaticAgendaPlacementService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """check_consecutive_failures raises SystemHaltedError when halted."""
        halt_checker.set_halted(True, "test halt reason")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_consecutive_failures()

        assert "CT-11" in str(exc_info.value)
        assert "halted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_rolling_window_failures_raises_when_halted(
        self,
        service: AutomaticAgendaPlacementService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """check_rolling_window_failures raises SystemHaltedError when halted."""
        halt_checker.set_halted(True, "test halt reason")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_rolling_window_failures()

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_anti_success_sustained_raises_when_halted(
        self,
        service: AutomaticAgendaPlacementService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """check_anti_success_sustained raises SystemHaltedError when halted."""
        halt_checker.set_halted(True, "test halt reason")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_anti_success_sustained()

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_evaluate_all_triggers_raises_when_halted(
        self,
        service: AutomaticAgendaPlacementService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """evaluate_all_triggers raises SystemHaltedError when halted."""
        halt_checker.set_halted(True, "test halt reason")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.evaluate_all_triggers()

        assert "CT-11" in str(exc_info.value)


class TestConsecutiveFailures:
    """Tests for FR37: 3 consecutive failures in 30 days."""

    @pytest.mark.asyncio
    async def test_no_trigger_with_zero_failures(
        self,
        service: AutomaticAgendaPlacementService,
    ) -> None:
        """No trigger when there are no failures."""
        result = await service.check_consecutive_failures()

        assert result.triggered is False
        assert result.trigger_type is None
        assert result.placement_id is None
        assert result.was_idempotent is False

    @pytest.mark.asyncio
    async def test_no_trigger_with_two_failures(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
    ) -> None:
        """No trigger when there are only 2 failures (boundary test)."""
        now = datetime.now(timezone.utc)
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=5))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=2))

        result = await service.check_consecutive_failures()

        assert result.triggered is False
        assert result.trigger_type is None

    @pytest.mark.asyncio
    async def test_trigger_with_exactly_three_failures(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Trigger when exactly 3 consecutive failures occur (boundary test)."""
        now = datetime.now(timezone.utc)
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=10))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=5))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=2))

        result = await service.check_consecutive_failures()

        assert result.triggered is True
        assert result.trigger_type == AgendaTriggerType.CONSECUTIVE_FAILURES
        assert result.placement_id is not None
        assert result.was_idempotent is False

        # Verify event was written (CT-12)
        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["agent_id"] == AGENDA_PLACEMENT_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_no_trigger_when_failures_outside_window(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
    ) -> None:
        """No trigger when failures are outside the 30-day window."""
        now = datetime.now(timezone.utc)
        # All failures > 30 days ago
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=35))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=40))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=45))

        result = await service.check_consecutive_failures()

        assert result.triggered is False

    @pytest.mark.asyncio
    async def test_successful_check_breaks_consecutive_sequence(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
    ) -> None:
        """A successful check resets consecutive failure count."""
        now = datetime.now(timezone.utc)

        # 2 failures, then successful check, then 2 more failures
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=15))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=12))
        await integrity_failure_repo.record_successful_check(now - timedelta(days=10))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=5))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=2))

        result = await service.check_consecutive_failures()

        # Only 2 consecutive failures after the successful check
        assert result.triggered is False


class TestRollingWindowFailures:
    """Tests for RT-4: 5 failures in 90-day rolling window."""

    @pytest.mark.asyncio
    async def test_no_trigger_with_four_failures(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
    ) -> None:
        """No trigger when there are only 4 failures (boundary test)."""
        now = datetime.now(timezone.utc)
        for i in range(4):
            integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=i * 15))

        result = await service.check_rolling_window_failures()

        assert result.triggered is False
        assert result.trigger_type is None

    @pytest.mark.asyncio
    async def test_trigger_with_exactly_five_failures(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Trigger when exactly 5 failures occur (boundary test)."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=i * 15))

        result = await service.check_rolling_window_failures()

        assert result.triggered is True
        assert result.trigger_type == AgendaTriggerType.ROLLING_WINDOW
        assert result.placement_id is not None
        assert result.was_idempotent is False

        # Verify event was written (CT-12)
        event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_trigger_when_failures_outside_90_day_window(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
    ) -> None:
        """No trigger when failures are outside the 90-day window."""
        now = datetime.now(timezone.utc)
        # All failures > 90 days ago
        for i in range(10):
            integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=100 + i))

        result = await service.check_rolling_window_failures()

        assert result.triggered is False

    @pytest.mark.asyncio
    async def test_non_consecutive_failures_count_for_rolling_window(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
    ) -> None:
        """Non-consecutive failures still count toward RT-4 threshold."""
        now = datetime.now(timezone.utc)

        # 5 failures with successful checks between them
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=80))
        await integrity_failure_repo.record_successful_check(now - timedelta(days=75))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=60))
        await integrity_failure_repo.record_successful_check(now - timedelta(days=55))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=40))
        await integrity_failure_repo.record_successful_check(now - timedelta(days=35))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=20))
        await integrity_failure_repo.record_successful_check(now - timedelta(days=15))
        integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=5))

        result = await service.check_rolling_window_failures()

        # RT-4 counts all failures regardless of consecutive status
        assert result.triggered is True
        assert result.trigger_type == AgendaTriggerType.ROLLING_WINDOW


class TestAntiSuccessSustained:
    """Tests for FR38: Anti-success alert sustained 90 days."""

    @pytest.mark.asyncio
    async def test_no_trigger_when_no_alerts(
        self,
        service: AutomaticAgendaPlacementService,
    ) -> None:
        """No trigger when there are no anti-success alerts."""
        result = await service.check_anti_success_sustained()

        assert result.triggered is False
        assert result.trigger_type is None

    @pytest.mark.asyncio
    async def test_no_trigger_at_89_days(
        self,
        service: AutomaticAgendaPlacementService,
        anti_success_repo: AntiSuccessAlertRepositoryStub,
    ) -> None:
        """No trigger when sustained for only 89 days (boundary test)."""
        now = datetime.now(timezone.utc)
        anti_success_repo.set_sustained_start(now - timedelta(days=89))

        result = await service.check_anti_success_sustained()

        assert result.triggered is False

    @pytest.mark.asyncio
    async def test_trigger_at_90_days(
        self,
        service: AutomaticAgendaPlacementService,
        anti_success_repo: AntiSuccessAlertRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Trigger when sustained for exactly 90 days (boundary test)."""
        now = datetime.now(timezone.utc)
        anti_success_repo.set_sustained_start(now - timedelta(days=90))

        result = await service.check_anti_success_sustained()

        assert result.triggered is True
        assert result.trigger_type == AgendaTriggerType.ANTI_SUCCESS_SUSTAINED
        assert result.placement_id is not None
        assert result.was_idempotent is False

        # Verify event was written (CT-12)
        event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_trigger_when_alerts_resolved(
        self,
        service: AutomaticAgendaPlacementService,
        anti_success_repo: AntiSuccessAlertRepositoryStub,
    ) -> None:
        """No trigger when alerts have been resolved."""
        now = datetime.now(timezone.utc)
        anti_success_repo.set_sustained_start(now - timedelta(days=100))
        await anti_success_repo.record_resolution(now)

        result = await service.check_anti_success_sustained()

        assert result.triggered is False


class TestIdempotency:
    """Tests for AC4: Idempotent triggers."""

    @pytest.mark.asyncio
    async def test_consecutive_failure_idempotent(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Consecutive failure trigger is idempotent."""
        now = datetime.now(timezone.utc)
        for i in range(3):
            integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=i * 5))

        # First call creates the placement
        result1 = await service.check_consecutive_failures()
        assert result1.triggered is True
        assert result1.was_idempotent is False
        assert event_writer.write_event.call_count == 1

        # Second call returns existing placement
        result2 = await service.check_consecutive_failures()
        assert result2.triggered is True
        assert result2.was_idempotent is True
        assert result2.placement_id == result1.placement_id
        # No new event written
        assert event_writer.write_event.call_count == 1

    @pytest.mark.asyncio
    async def test_rolling_window_idempotent(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Rolling window trigger is idempotent."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=i * 10))

        result1 = await service.check_rolling_window_failures()
        assert result1.triggered is True
        assert result1.was_idempotent is False

        result2 = await service.check_rolling_window_failures()
        assert result2.triggered is True
        assert result2.was_idempotent is True
        assert result2.placement_id == result1.placement_id

    @pytest.mark.asyncio
    async def test_anti_success_idempotent(
        self,
        service: AutomaticAgendaPlacementService,
        anti_success_repo: AntiSuccessAlertRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Anti-success sustained trigger is idempotent."""
        now = datetime.now(timezone.utc)
        anti_success_repo.set_sustained_start(now - timedelta(days=90))

        result1 = await service.check_anti_success_sustained()
        assert result1.triggered is True
        assert result1.was_idempotent is False

        result2 = await service.check_anti_success_sustained()
        assert result2.triggered is True
        assert result2.was_idempotent is True


class TestEvaluateAllTriggers:
    """Tests for evaluate_all_triggers method."""

    @pytest.mark.asyncio
    async def test_evaluates_all_three_triggers(
        self,
        service: AutomaticAgendaPlacementService,
    ) -> None:
        """evaluate_all_triggers checks all three trigger types."""
        results = await service.evaluate_all_triggers()

        assert len(results) == 3
        # All should not trigger with empty repos
        assert all(r.triggered is False for r in results)

    @pytest.mark.asyncio
    async def test_multiple_triggers_can_fire(
        self,
        service: AutomaticAgendaPlacementService,
        integrity_failure_repo: IntegrityFailureRepositoryStub,
        anti_success_repo: AntiSuccessAlertRepositoryStub,
    ) -> None:
        """Multiple triggers can fire in a single evaluation."""
        now = datetime.now(timezone.utc)

        # Set up conditions for all three triggers
        # 5 failures (triggers both consecutive and rolling window)
        for i in range(5):
            integrity_failure_repo.add_failure(uuid4(), now - timedelta(days=i * 5))

        # Anti-success sustained
        anti_success_repo.set_sustained_start(now - timedelta(days=100))

        results = await service.evaluate_all_triggers()

        # All three should trigger
        triggered_types = [r.trigger_type for r in results if r.triggered]
        assert AgendaTriggerType.CONSECUTIVE_FAILURES in triggered_types
        assert AgendaTriggerType.ROLLING_WINDOW in triggered_types
        assert AgendaTriggerType.ANTI_SUCCESS_SUSTAINED in triggered_types


class TestConstants:
    """Tests for threshold constants."""

    def test_consecutive_failure_threshold(self) -> None:
        """Consecutive failure threshold is 3 per FR37."""
        assert CONSECUTIVE_FAILURE_THRESHOLD == 3

    def test_consecutive_failure_window(self) -> None:
        """Consecutive failure window is 30 days per FR37."""
        assert CONSECUTIVE_FAILURE_WINDOW_DAYS == 30

    def test_rolling_window_threshold(self) -> None:
        """Rolling window threshold is 5 per RT-4."""
        assert ROLLING_WINDOW_THRESHOLD == 5

    def test_rolling_window_days(self) -> None:
        """Rolling window is 90 days per RT-4."""
        assert ROLLING_WINDOW_DAYS == 90

    def test_anti_success_threshold_days(self) -> None:
        """Anti-success threshold is 90 days per FR38."""
        assert ANTI_SUCCESS_SUSTAINED_THRESHOLD_DAYS == 90
