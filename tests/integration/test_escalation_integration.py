"""Integration tests for 7-Day Escalation to Agenda (Story 6.2, FR31).

Tests:
- AC1: Automatic escalation after 7 days
- AC2: Acknowledgment stops escalation timer
- AC3: Pending escalation query with time remaining

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: HALT CHECK FIRST - All operations must check halt status
- CT-12: Witnessing for accountability - All escalation events must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.escalation_service import (
    ESCALATION_SYSTEM_AGENT_ID,
    EscalationService,
)
from src.domain.errors.escalation import (
    BreachAlreadyAcknowledgedError,
    BreachNotFoundError,
)
from src.domain.events.breach import (
    BreachEventPayload,
    BreachType,
)
from src.domain.events.escalation import (
    BREACH_ACKNOWLEDGED_EVENT_TYPE,
    ESCALATION_EVENT_TYPE,
    ResponseChoice,
)
from src.domain.models.pending_escalation import ESCALATION_THRESHOLD_DAYS
from src.infrastructure.stubs import (
    BreachRepositoryStub,
    EscalationRepositoryStub,
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
def escalation_repository() -> EscalationRepositoryStub:
    """Create a fresh escalation repository stub."""
    return EscalationRepositoryStub()


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer that captures write calls."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def escalation_service(
    breach_repository: BreachRepositoryStub,
    escalation_repository: EscalationRepositoryStub,
    mock_event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> EscalationService:
    """Create an escalation service with stub implementations."""
    return EscalationService(
        breach_repository=breach_repository,
        escalation_repository=escalation_repository,
        event_writer=mock_event_writer,
        halt_checker=halt_checker,
    )


@pytest.fixture
def halted_escalation_service(
    breach_repository: BreachRepositoryStub,
    escalation_repository: EscalationRepositoryStub,
    mock_event_writer: AsyncMock,
    halted_checker: HaltCheckerStub,
) -> EscalationService:
    """Create an escalation service in halted state."""
    return EscalationService(
        breach_repository=breach_repository,
        escalation_repository=escalation_repository,
        event_writer=mock_event_writer,
        halt_checker=halted_checker,
    )


def create_breach(
    breach_id: None | uuid4 = None,
    breach_type: BreachType = BreachType.THRESHOLD_VIOLATION,
    detection_timestamp: datetime | None = None,
) -> BreachEventPayload:
    """Create a breach event payload for testing."""
    from types import MappingProxyType
    from src.domain.events.breach import BreachSeverity

    return BreachEventPayload(
        breach_id=breach_id or uuid4(),
        breach_type=breach_type,
        violated_requirement="FR31",
        severity=BreachSeverity.CRITICAL,
        detection_timestamp=detection_timestamp or datetime.now(timezone.utc),
        details=MappingProxyType({}),
    )


class TestAutomaticEscalationAfter7Days:
    """AC1: When a breach has been unacknowledged for 7+ days,
    THEN the system SHALL automatically add it to Conclave agenda.
    """

    @pytest.mark.asyncio
    async def test_breach_older_than_7_days_is_escalated(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        escalation_repository: EscalationRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that breaches older than 7 days are automatically escalated."""
        # Create breach 8 days old
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        await breach_repository.save(breach)

        # Run automatic escalation check
        escalated = await escalation_service.check_and_escalate_breaches()

        # Verify escalation occurred
        assert len(escalated) == 1
        assert escalated[0].breach_id == breach.breach_id
        assert escalated[0].days_since_breach >= 8

        # Verify escalation was persisted
        stored = await escalation_repository.get_escalation_for_breach(breach.breach_id)
        assert stored is not None
        assert stored.breach_id == breach.breach_id

        # Verify escalation event was written
        mock_event_writer.write_event.assert_called()

    @pytest.mark.asyncio
    async def test_breach_younger_than_7_days_not_escalated(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        escalation_repository: EscalationRepositoryStub,
    ) -> None:
        """Test that breaches younger than 7 days are not escalated."""
        # Create breach 5 days old
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        await breach_repository.save(breach)

        # Run automatic escalation check
        escalated = await escalation_service.check_and_escalate_breaches()

        # Verify no escalation
        assert len(escalated) == 0

        # Verify no escalation stored
        stored = await escalation_repository.get_escalation_for_breach(breach.breach_id)
        assert stored is None

    @pytest.mark.asyncio
    async def test_exactly_7_day_old_breach_is_escalated(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        escalation_repository: EscalationRepositoryStub,
    ) -> None:
        """Test that breaches exactly 7 days old are escalated."""
        # Create breach exactly 7 days old
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=7)
        )
        await breach_repository.save(breach)

        # Run automatic escalation check
        escalated = await escalation_service.check_and_escalate_breaches()

        # Verify escalation occurred
        assert len(escalated) == 1
        assert escalated[0].days_since_breach == 7

    @pytest.mark.asyncio
    async def test_multiple_breaches_escalated_correctly(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that multiple breaches are handled correctly."""
        # Create breaches with varying ages
        old_breach1 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=10)
        )
        old_breach2 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        recent_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=3)
        )

        await breach_repository.save(old_breach1)
        await breach_repository.save(old_breach2)
        await breach_repository.save(recent_breach)

        # Run automatic escalation check
        escalated = await escalation_service.check_and_escalate_breaches()

        # Verify only old breaches were escalated
        assert len(escalated) == 2
        escalated_ids = {e.breach_id for e in escalated}
        assert old_breach1.breach_id in escalated_ids
        assert old_breach2.breach_id in escalated_ids
        assert recent_breach.breach_id not in escalated_ids

    @pytest.mark.asyncio
    async def test_escalation_includes_fr31_reason(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that escalation includes FR31 constitutional reference."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        await breach_repository.save(breach)

        escalated = await escalation_service.check_and_escalate_breaches()

        assert len(escalated) == 1
        assert "FR31" in escalated[0].agenda_placement_reason


class TestAcknowledgmentStopsTimer:
    """AC2: When a Keeper acknowledges a breach with a response choice,
    THEN the escalation timer stops and the response is recorded.
    """

    @pytest.mark.asyncio
    async def test_acknowledgment_prevents_escalation(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        escalation_repository: EscalationRepositoryStub,
    ) -> None:
        """Test that acknowledged breaches are not escalated."""
        # Create old breach and acknowledge it
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=10)
        )
        await breach_repository.save(breach)

        # Acknowledge the breach
        await escalation_service.acknowledge_breach(
            breach_id=breach.breach_id,
            acknowledged_by="keeper_001",
            response_choice=ResponseChoice.CORRECTIVE,
        )

        # Run automatic escalation check
        escalated = await escalation_service.check_and_escalate_breaches()

        # Verify no escalation
        assert len(escalated) == 0

    @pytest.mark.asyncio
    async def test_acknowledgment_records_response_choice(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        escalation_repository: EscalationRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that acknowledgment records the response choice."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=3)
        )
        await breach_repository.save(breach)

        # Acknowledge with specific response
        ack = await escalation_service.acknowledge_breach(
            breach_id=breach.breach_id,
            acknowledged_by="keeper_001",
            response_choice=ResponseChoice.CORRECTIVE,
        )

        # Verify acknowledgment details
        assert ack.breach_id == breach.breach_id
        assert ack.acknowledged_by == "keeper_001"
        assert ack.response_choice == ResponseChoice.CORRECTIVE

        # Verify stored in repository
        stored = await escalation_repository.get_acknowledgment_for_breach(
            breach.breach_id
        )
        assert stored is not None
        assert stored.response_choice == ResponseChoice.CORRECTIVE

        # Verify event written
        mock_event_writer.write_event.assert_called()

    @pytest.mark.asyncio
    async def test_all_response_choices_valid(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that all ResponseChoice values are valid."""
        for choice in ResponseChoice:
            breach = create_breach()
            await breach_repository.save(breach)

            ack = await escalation_service.acknowledge_breach(
                breach_id=breach.breach_id,
                acknowledged_by=f"keeper_{choice.value}",
                response_choice=choice,
            )

            assert ack.response_choice == choice

    @pytest.mark.asyncio
    async def test_cannot_acknowledge_nonexistent_breach(
        self,
        escalation_service: EscalationService,
    ) -> None:
        """Test that acknowledging nonexistent breach raises error."""
        with pytest.raises(BreachNotFoundError):
            await escalation_service.acknowledge_breach(
                breach_id=uuid4(),
                acknowledged_by="keeper_001",
                response_choice=ResponseChoice.CORRECTIVE,
            )

    @pytest.mark.asyncio
    async def test_cannot_acknowledge_twice(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that breach cannot be acknowledged twice."""
        breach = create_breach()
        await breach_repository.save(breach)

        # First acknowledgment succeeds
        await escalation_service.acknowledge_breach(
            breach_id=breach.breach_id,
            acknowledged_by="keeper_001",
            response_choice=ResponseChoice.CORRECTIVE,
        )

        # Second acknowledgment fails
        with pytest.raises(BreachAlreadyAcknowledgedError):
            await escalation_service.acknowledge_breach(
                breach_id=breach.breach_id,
                acknowledged_by="keeper_002",
                response_choice=ResponseChoice.DISMISS,
            )


class TestPendingEscalationQuery:
    """AC3: When querying pending escalations,
    THEN the system returns breaches sorted by urgency with time remaining.
    """

    @pytest.mark.asyncio
    async def test_pending_escalations_sorted_by_urgency(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that pending escalations are sorted by urgency (oldest first)."""
        # Create breaches with varying ages
        newest = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=1)
        )
        middle = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=4)
        )
        oldest = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=6)
        )

        await breach_repository.save(newest)
        await breach_repository.save(middle)
        await breach_repository.save(oldest)

        # Get pending escalations
        pending = await escalation_service.get_pending_escalations()

        # Verify sorted by urgency (oldest first, least time remaining)
        assert len(pending) == 3
        assert pending[0].breach_id == oldest.breach_id
        assert pending[1].breach_id == middle.breach_id
        assert pending[2].breach_id == newest.breach_id

    @pytest.mark.asyncio
    async def test_pending_escalations_show_time_remaining(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that pending escalations show time remaining."""
        # Create breach 5 days old (2 days remaining)
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        await breach_repository.save(breach)

        pending = await escalation_service.get_pending_escalations()

        assert len(pending) == 1
        # Approximately 2 days remaining (7 - 5 = 2)
        assert 1 <= pending[0].days_remaining <= 2
        assert 46 <= pending[0].hours_remaining <= 49

    @pytest.mark.asyncio
    async def test_pending_excludes_acknowledged_breaches(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that acknowledged breaches are excluded from pending."""
        breach1 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        breach2 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=4)
        )
        await breach_repository.save(breach1)
        await breach_repository.save(breach2)

        # Acknowledge one breach
        await escalation_service.acknowledge_breach(
            breach_id=breach1.breach_id,
            acknowledged_by="keeper_001",
            response_choice=ResponseChoice.CORRECTIVE,
        )

        pending = await escalation_service.get_pending_escalations()

        assert len(pending) == 1
        assert pending[0].breach_id == breach2.breach_id

    @pytest.mark.asyncio
    async def test_pending_excludes_escalated_breaches(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that already escalated breaches are excluded from pending."""
        breach1 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        breach2 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        await breach_repository.save(breach1)
        await breach_repository.save(breach2)

        # Escalate the old breach
        await escalation_service.check_and_escalate_breaches()

        pending = await escalation_service.get_pending_escalations()

        # Only the non-escalated breach should be pending
        assert len(pending) == 1
        assert pending[0].breach_id == breach2.breach_id

    @pytest.mark.asyncio
    async def test_urgency_levels_correct(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test that urgency levels are correctly assigned."""
        # PENDING: > 72 hours remaining (6+ days to go, so 1 day old)
        pending_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=1)
        )
        # WARNING: 24-72 hours remaining (5-6 days old)
        warning_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        # URGENT: < 24 hours remaining (6.5+ days old)
        urgent_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=6, hours=12)
        )

        await breach_repository.save(pending_breach)
        await breach_repository.save(warning_breach)
        await breach_repository.save(urgent_breach)

        pending = await escalation_service.get_pending_escalations()

        # Find each breach's status
        pending_status = {p.breach_id: p for p in pending}

        assert pending_status[pending_breach.breach_id].urgency_level == "PENDING"
        assert pending_status[warning_breach.breach_id].urgency_level == "WARNING"
        assert pending_status[urgent_breach.breach_id].urgency_level == "URGENT"


class TestHaltCheckFirst:
    """CT-11: All operations must check halt status first."""

    @pytest.mark.asyncio
    async def test_escalation_respects_halt(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that automatic escalation fails when system is halted."""
        from src.domain.errors.writer import SystemHaltedError

        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        await breach_repository.save(breach)

        # Halt the system
        halt_checker.set_halted(True, reason="Test halt")

        with pytest.raises(SystemHaltedError) as exc_info:
            await escalation_service.check_and_escalate_breaches()

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_acknowledgment_respects_halt(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that acknowledgment fails when system is halted."""
        from src.domain.errors.writer import SystemHaltedError

        breach = create_breach()
        await breach_repository.save(breach)

        # Halt the system
        halt_checker.set_halted(True, reason="Test halt")

        with pytest.raises(SystemHaltedError) as exc_info:
            await escalation_service.acknowledge_breach(
                breach_id=breach.breach_id,
                acknowledged_by="keeper_001",
                response_choice=ResponseChoice.CORRECTIVE,
            )

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pending_query_respects_halt(
        self,
        escalation_service: EscalationService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that pending query fails when system is halted."""
        from src.domain.errors.writer import SystemHaltedError

        # Halt the system
        halt_checker.set_halted(True, reason="Test halt")

        with pytest.raises(SystemHaltedError) as exc_info:
            await escalation_service.get_pending_escalations()

        assert "CT-11" in str(exc_info.value)


class TestWitnessingForAccountability:
    """CT-12: All escalation events must be witnessed."""

    @pytest.mark.asyncio
    async def test_escalation_event_is_witnessed(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that escalation events are written to event store."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        await breach_repository.save(breach)

        await escalation_service.check_and_escalate_breaches()

        # Verify event was written via mock
        mock_event_writer.write_event.assert_called()
        # Verify correct event type and agent_id were passed
        call_args = mock_event_writer.write_event.call_args
        assert call_args is not None
        assert call_args.kwargs.get("event_type") == ESCALATION_EVENT_TYPE
        assert call_args.kwargs.get("agent_id") == ESCALATION_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_acknowledgment_event_is_witnessed(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that acknowledgment events are written to event store."""
        breach = create_breach()
        await breach_repository.save(breach)

        await escalation_service.acknowledge_breach(
            breach_id=breach.breach_id,
            acknowledged_by="keeper_001",
            response_choice=ResponseChoice.CORRECTIVE,
        )

        # Verify event was written via mock
        mock_event_writer.write_event.assert_called()
        # Verify correct event type was passed
        # Note: The service uses ESCALATION_SYSTEM_AGENT_ID for attribution
        call_args = mock_event_writer.write_event.call_args
        assert call_args is not None
        assert call_args.kwargs.get("event_type") == BREACH_ACKNOWLEDGED_EVENT_TYPE
        assert call_args.kwargs.get("agent_id") == ESCALATION_SYSTEM_AGENT_ID


class TestBreachStatusQueries:
    """Tests for breach status query methods."""

    @pytest.mark.asyncio
    async def test_is_breach_acknowledged(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test is_breach_acknowledged method."""
        breach = create_breach()
        await breach_repository.save(breach)

        # Not acknowledged initially
        assert not await escalation_service.is_breach_acknowledged(breach.breach_id)

        # Acknowledge it
        await escalation_service.acknowledge_breach(
            breach_id=breach.breach_id,
            acknowledged_by="keeper_001",
            response_choice=ResponseChoice.CORRECTIVE,
        )

        # Now acknowledged
        assert await escalation_service.is_breach_acknowledged(breach.breach_id)

    @pytest.mark.asyncio
    async def test_is_breach_escalated(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test is_breach_escalated method."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        await breach_repository.save(breach)

        # Not escalated initially
        assert not await escalation_service.is_breach_escalated(breach.breach_id)

        # Escalate it
        await escalation_service.check_and_escalate_breaches()

        # Now escalated
        assert await escalation_service.is_breach_escalated(breach.breach_id)

    @pytest.mark.asyncio
    async def test_get_breach_status(
        self,
        escalation_service: EscalationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Test get_breach_status method."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        await breach_repository.save(breach)

        # Check initial status
        status = await escalation_service.get_breach_status(breach.breach_id)
        assert status is not None
        assert status["is_acknowledged"] is False
        assert status["is_escalated"] is False

        # Escalate
        await escalation_service.check_and_escalate_breaches()

        # Check updated status
        status = await escalation_service.get_breach_status(breach.breach_id)
        assert status["is_escalated"] is True
        assert status["escalation_details"] is not None


class TestEscalationThresholdConstant:
    """Tests for the 7-day escalation threshold constant."""

    def test_threshold_is_7_days(self) -> None:
        """Test that escalation threshold is exactly 7 days per FR31."""
        assert ESCALATION_THRESHOLD_DAYS == 7
