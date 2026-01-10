"""Integration tests for Automatic Cessation Consideration (Story 6.3, FR32).

Tests:
- AC1: >10 unacknowledged breaches in 90 days triggers cessation consideration
- AC2: Dashboard query shows current breach count and trajectory
- AC3: Recording cessation decision (proceed/dismiss/defer)

Constitutional Constraints:
- FR32: >10 unacknowledged breaches in 90 days SHALL trigger cessation consideration
- CT-11: HALT CHECK FIRST - All operations must check halt status
- CT-12: Witnessing for accountability - All cessation events must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType
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
from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)
from src.domain.events.cessation import (
    CESSATION_CONSIDERATION_EVENT_TYPE,
    CESSATION_DECISION_EVENT_TYPE,
    CessationConsiderationEventPayload,
    CessationDecision,
)
from src.domain.models.breach_count_status import (
    CESSATION_THRESHOLD,
    CESSATION_WINDOW_DAYS,
    WARNING_THRESHOLD,
    BreachTrajectory,
)
from src.infrastructure.stubs import (
    BreachRepositoryStub,
    CessationRepositoryStub,
    HaltCheckerStub,
)


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a halt checker that returns not halted."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def halted_checker() -> HaltCheckerStub:
    """Create a halt checker that returns halted."""
    return HaltCheckerStub(force_halted=True, halt_reason="Fork detected")


@pytest.fixture
def breach_repository() -> BreachRepositoryStub:
    """Create a fresh breach repository stub."""
    return BreachRepositoryStub()


@pytest.fixture
def cessation_repository() -> CessationRepositoryStub:
    """Create a fresh cessation repository stub."""
    return CessationRepositoryStub()


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer that captures write calls."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def cessation_service(
    breach_repository: BreachRepositoryStub,
    cessation_repository: CessationRepositoryStub,
    mock_event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> CessationConsiderationService:
    """Create a cessation service with stub implementations."""
    return CessationConsiderationService(
        breach_repository=breach_repository,
        cessation_repository=cessation_repository,
        event_writer=mock_event_writer,
        halt_checker=halt_checker,
    )


@pytest.fixture
def halted_cessation_service(
    breach_repository: BreachRepositoryStub,
    cessation_repository: CessationRepositoryStub,
    mock_event_writer: AsyncMock,
    halted_checker: HaltCheckerStub,
) -> CessationConsiderationService:
    """Create a cessation service in halted state."""
    return CessationConsiderationService(
        breach_repository=breach_repository,
        cessation_repository=cessation_repository,
        event_writer=mock_event_writer,
        halt_checker=halted_checker,
    )


def create_breach(
    breach_id: uuid4 | None = None,
    breach_type: BreachType = BreachType.THRESHOLD_VIOLATION,
    detection_timestamp: datetime | None = None,
) -> BreachEventPayload:
    """Create a breach event payload for testing."""
    return BreachEventPayload(
        breach_id=breach_id or uuid4(),
        breach_type=breach_type,
        violated_requirement="FR32",
        severity=BreachSeverity.CRITICAL,
        detection_timestamp=detection_timestamp or datetime.now(timezone.utc),
        details=MappingProxyType({}),
    )


async def create_breaches_in_repo(
    breach_repository: BreachRepositoryStub,
    count: int,
    base_timestamp: datetime | None = None,
) -> list[BreachEventPayload]:
    """Helper to create multiple breaches in the repository."""
    if base_timestamp is None:
        base_timestamp = datetime.now(timezone.utc)

    breaches = []
    for i in range(count):
        breach = create_breach(
            detection_timestamp=base_timestamp - timedelta(days=i)
        )
        await breach_repository.save(breach)
        breaches.append(breach)
    return breaches


class TestFR32CessationTrigger:
    """AC1: >10 unacknowledged breaches in 90 days triggers cessation consideration."""

    @pytest.mark.asyncio
    async def test_fr32_cessation_triggers_at_11_breaches(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        cessation_repository: CessationRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """FR32: >10 unacknowledged breaches SHALL trigger cessation consideration."""
        # Create 11 unacknowledged breaches (within 90 days)
        breaches = await create_breaches_in_repo(breach_repository, 11)

        # Trigger cessation check
        result = await cessation_service.check_and_trigger_cessation()

        # Verify cessation was triggered
        assert result is not None
        assert result.breach_count == 11
        assert len(result.unacknowledged_breach_ids) == 11
        assert "FR32" in result.agenda_placement_reason

        # Verify event was written
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == CESSATION_CONSIDERATION_EVENT_TYPE
        assert call_kwargs["agent_id"] == CESSATION_SYSTEM_AGENT_ID

        # Verify consideration was persisted
        stored = await cessation_repository.get_active_consideration()
        assert stored is not None
        assert stored.consideration_id == result.consideration_id

    @pytest.mark.asyncio
    async def test_cessation_not_triggered_at_10_breaches(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        cessation_repository: CessationRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """FR32 boundary: Exactly 10 breaches does NOT trigger cessation."""
        # Create exactly 10 breaches
        await create_breaches_in_repo(breach_repository, 10)

        # Trigger cessation check
        result = await cessation_service.check_and_trigger_cessation()

        # Verify cessation was NOT triggered (>10, not >=10)
        assert result is None

        # Verify no event was written
        mock_event_writer.write_event.assert_not_called()

        # Verify no consideration was stored
        stored = await cessation_repository.get_active_consideration()
        assert stored is None

    @pytest.mark.asyncio
    async def test_cessation_event_is_witnessed(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """CT-12: Cessation consideration event must be witnessed."""
        # Create 11 breaches to trigger cessation
        await create_breaches_in_repo(breach_repository, 11)

        # Trigger cessation
        result = await cessation_service.check_and_trigger_cessation()

        # Verify event writer was called (witnessing handled by write_event)
        mock_event_writer.write_event.assert_called_once()

        # Verify payload has signable content for witnessing
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert hasattr(payload, "signable_content") or isinstance(payload, dict)

    @pytest.mark.asyncio
    async def test_cessation_event_includes_breach_references(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """AC1: Cessation event must reference all unacknowledged breaches."""
        # Create 12 breaches
        breaches = await create_breaches_in_repo(breach_repository, 12)

        # Trigger cessation
        result = await cessation_service.check_and_trigger_cessation()

        # Verify all breach IDs are referenced
        assert result is not None
        expected_ids = {b.breach_id for b in breaches}
        actual_ids = set(result.unacknowledged_breach_ids)
        assert expected_ids == actual_ids

    @pytest.mark.asyncio
    async def test_no_duplicate_consideration_while_active(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        cessation_repository: CessationRepositoryStub,
    ) -> None:
        """No duplicate cessation consideration while one is already active."""
        # Create 15 breaches
        await create_breaches_in_repo(breach_repository, 15)

        # First trigger should succeed
        first_result = await cessation_service.check_and_trigger_cessation()
        assert first_result is not None
        first_id = first_result.consideration_id

        # Second trigger should be skipped
        second_result = await cessation_service.check_and_trigger_cessation()
        assert second_result is None

        # Only one consideration should exist
        all_considerations = await cessation_repository.list_considerations()
        assert len(all_considerations) == 1
        assert all_considerations[0].consideration_id == first_id


class TestBreachCountStatus:
    """AC2: Dashboard query shows current breach count and trajectory."""

    @pytest.mark.asyncio
    async def test_breach_count_query_returns_status(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """AC2: Query returns current breach count status."""
        # Create 5 breaches
        await create_breaches_in_repo(breach_repository, 5)

        # Query status
        status = await cessation_service.get_breach_count_status()

        # Verify status fields
        assert status.current_count == 5
        assert status.threshold == CESSATION_THRESHOLD
        assert status.warning_threshold == WARNING_THRESHOLD
        assert status.window_days == CESSATION_WINDOW_DAYS
        assert len(status.breach_ids) == 5
        assert status.is_above_threshold is False
        assert status.is_at_warning is False
        assert status.urgency_level == "NORMAL"

    @pytest.mark.asyncio
    async def test_warning_alert_at_8_breaches(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """AC2: Warning alert fires at 8 breaches."""
        # Create 8 breaches
        await create_breaches_in_repo(breach_repository, 8)

        # Query alert status
        alert = await cessation_service.get_breach_alert_status()

        # Verify warning
        assert alert == "WARNING"

        # Also check status object
        status = await cessation_service.get_breach_count_status()
        assert status.is_at_warning is True
        assert status.urgency_level == "WARNING"

    @pytest.mark.asyncio
    async def test_critical_alert_at_11_breaches(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """AC2: Critical alert at >10 breaches."""
        # Create 11 breaches
        await create_breaches_in_repo(breach_repository, 11)

        # Query alert status
        alert = await cessation_service.get_breach_alert_status()

        # Verify critical
        assert alert == "CRITICAL"

        # Also check status object
        status = await cessation_service.get_breach_count_status()
        assert status.is_above_threshold is True
        assert status.urgency_level == "CRITICAL"

    @pytest.mark.asyncio
    async def test_trajectory_calculation(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """AC2: Trajectory calculation shows breach trend."""
        # Create recent breaches (more in recent period = increasing)
        now = datetime.now(timezone.utc)

        # Add 5 recent breaches (last 30 days)
        for i in range(5):
            breach = create_breach(detection_timestamp=now - timedelta(days=i * 5))
            await breach_repository.save(breach)

        # Add 1 old breach (60+ days ago)
        old_breach = create_breach(detection_timestamp=now - timedelta(days=70))
        await breach_repository.save(old_breach)

        # Query status - should show increasing trajectory
        status = await cessation_service.get_breach_count_status()

        # Verify trajectory is calculated
        assert status.trajectory is not None
        assert isinstance(status.trajectory, BreachTrajectory)


class TestCessationDecisionRecording:
    """AC3: Recording cessation decision (proceed/dismiss/defer)."""

    @pytest.mark.asyncio
    async def test_decision_recording_proceed(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        cessation_repository: CessationRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """AC3: Record decision to proceed to vote."""
        # Trigger cessation first
        await create_breaches_in_repo(breach_repository, 11)
        consideration = await cessation_service.check_and_trigger_cessation()
        assert consideration is not None
        mock_event_writer.reset_mock()

        # Record proceed decision
        decision = await cessation_service.record_cessation_decision(
            consideration_id=consideration.consideration_id,
            decision=CessationDecision.PROCEED_TO_VOTE,
            decided_by="Conclave Session 42",
            rationale="Persistent breach pattern warrants vote",
        )

        # Verify decision
        assert decision.decision == CessationDecision.PROCEED_TO_VOTE
        assert decision.decided_by == "Conclave Session 42"
        assert decision.consideration_id == consideration.consideration_id

        # Verify event was written
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == CESSATION_DECISION_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_decision_recording_dismiss(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        cessation_repository: CessationRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """AC3: Record decision to dismiss consideration."""
        # Trigger cessation first
        await create_breaches_in_repo(breach_repository, 11)
        consideration = await cessation_service.check_and_trigger_cessation()
        assert consideration is not None
        mock_event_writer.reset_mock()

        # Record dismiss decision
        decision = await cessation_service.record_cessation_decision(
            consideration_id=consideration.consideration_id,
            decision=CessationDecision.DISMISS_CONSIDERATION,
            decided_by="Conclave Session 43",
            rationale="Breaches were remediated",
        )

        # Verify decision
        assert decision.decision == CessationDecision.DISMISS_CONSIDERATION

        # Verify no longer active
        active = await cessation_service.is_cessation_consideration_active()
        assert active is False

    @pytest.mark.asyncio
    async def test_decision_recording_defer(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        cessation_repository: CessationRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """AC3: Record decision to defer review."""
        # Trigger cessation first
        await create_breaches_in_repo(breach_repository, 11)
        consideration = await cessation_service.check_and_trigger_cessation()
        assert consideration is not None
        mock_event_writer.reset_mock()

        # Record defer decision
        decision = await cessation_service.record_cessation_decision(
            consideration_id=consideration.consideration_id,
            decision=CessationDecision.DEFER_REVIEW,
            decided_by="Conclave Session 44",
            rationale="Pending additional evidence",
        )

        # Verify decision
        assert decision.decision == CessationDecision.DEFER_REVIEW

    @pytest.mark.asyncio
    async def test_decision_event_is_witnessed(
        self,
        cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """CT-12: Decision event must be witnessed."""
        # Trigger cessation first
        await create_breaches_in_repo(breach_repository, 11)
        consideration = await cessation_service.check_and_trigger_cessation()
        assert consideration is not None
        mock_event_writer.reset_mock()

        # Record decision
        await cessation_service.record_cessation_decision(
            consideration_id=consideration.consideration_id,
            decision=CessationDecision.PROCEED_TO_VOTE,
            decided_by="Conclave",
            rationale="Test",
        )

        # Verify event writer was called (witnessing handled by write_event)
        mock_event_writer.write_event.assert_called_once()


class TestHaltCheckPreventsOperations:
    """CT-11: HALT CHECK FIRST - All operations must check halt status."""

    @pytest.mark.asyncio
    async def test_halt_check_prevents_cessation_trigger_during_halt(
        self,
        halted_cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """CT-11: Halt prevents cessation trigger."""
        # Create breaches that would trigger cessation
        await create_breaches_in_repo(breach_repository, 15)

        # Attempt cessation check should fail
        with pytest.raises(SystemHaltedError) as exc_info:
            await halted_cessation_service.check_and_trigger_cessation()

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_check_prevents_decision_during_halt(
        self,
        cessation_service: CessationConsiderationService,
        halted_cessation_service: CessationConsiderationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """CT-11: Halt prevents decision recording."""
        # Create consideration using non-halted service
        await create_breaches_in_repo(breach_repository, 11)
        consideration = await cessation_service.check_and_trigger_cessation()
        assert consideration is not None

        # Attempt decision with halted service should fail
        with pytest.raises(SystemHaltedError) as exc_info:
            await halted_cessation_service.record_cessation_decision(
                consideration_id=consideration.consideration_id,
                decision=CessationDecision.DISMISS_CONSIDERATION,
                decided_by="Test",
                rationale="Test",
            )

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_check_prevents_status_query_during_halt(
        self,
        halted_cessation_service: CessationConsiderationService,
    ) -> None:
        """CT-11: Halt prevents breach status query."""
        with pytest.raises(SystemHaltedError):
            await halted_cessation_service.get_breach_count_status()

    @pytest.mark.asyncio
    async def test_halt_check_prevents_alert_query_during_halt(
        self,
        halted_cessation_service: CessationConsiderationService,
    ) -> None:
        """CT-11: Halt prevents alert status query."""
        with pytest.raises(SystemHaltedError):
            await halted_cessation_service.get_breach_alert_status()

    @pytest.mark.asyncio
    async def test_halt_check_prevents_active_check_during_halt(
        self,
        halted_cessation_service: CessationConsiderationService,
    ) -> None:
        """CT-11: Halt prevents active consideration check."""
        with pytest.raises(SystemHaltedError):
            await halted_cessation_service.is_cessation_consideration_active()
