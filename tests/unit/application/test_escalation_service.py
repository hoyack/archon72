"""Unit tests for EscalationService (Story 6.2, FR31).

Tests:
- check_and_escalate_breaches() finds breaches > 7 days old
- check_and_escalate_breaches() skips acknowledged breaches
- check_and_escalate_breaches() skips already escalated breaches
- acknowledge_breach() stops escalation timer
- acknowledge_breach() creates witnessed event (CT-12)
- acknowledge_breach() fails for nonexistent breach
- acknowledge_breach() fails for already acknowledged
- get_pending_escalations() returns sorted by urgency
- get_pending_escalations() calculates time remaining correctly
- HALT CHECK on all operations

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.escalation_service import EscalationService
from src.domain.errors.escalation import (
    BreachAlreadyAcknowledgedError,
    BreachAlreadyEscalatedError,
    BreachNotFoundError,
    InvalidAcknowledgmentError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)
from src.domain.events.escalation import ResponseChoice


def create_breach(
    breach_id: UUID | None = None,
    breach_type: BreachType = BreachType.THRESHOLD_VIOLATION,
    detection_timestamp: datetime | None = None,
) -> BreachEventPayload:
    """Helper to create a breach event payload."""
    return BreachEventPayload(
        breach_id=breach_id or uuid4(),
        breach_type=breach_type,
        violated_requirement="FR31",
        severity=BreachSeverity.HIGH,
        detection_timestamp=detection_timestamp or datetime.now(timezone.utc),
        details=MappingProxyType({}),
    )


@pytest.fixture
def mock_breach_repository() -> AsyncMock:
    """Create mock breach repository."""
    mock = AsyncMock()
    mock.list_all.return_value = []
    mock.get_by_id.return_value = None
    return mock


@pytest.fixture
def mock_escalation_repository() -> AsyncMock:
    """Create mock escalation repository."""
    mock = AsyncMock()
    mock.get_acknowledgment_for_breach.return_value = None
    mock.get_escalation_for_breach.return_value = None
    mock.save_escalation.return_value = None
    mock.save_acknowledgment.return_value = None
    return mock


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer."""
    mock = AsyncMock()
    mock.write_event.return_value = None
    return mock


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker."""
    mock = AsyncMock()
    mock.is_halted.return_value = False
    mock.get_halt_reason.return_value = None
    return mock


@pytest.fixture
def escalation_service(
    mock_breach_repository: AsyncMock,
    mock_escalation_repository: AsyncMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
) -> EscalationService:
    """Create escalation service with mocked dependencies."""
    return EscalationService(
        breach_repository=mock_breach_repository,
        escalation_repository=mock_escalation_repository,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
    )


class TestCheckAndEscalateBreaches:
    """Tests for check_and_escalate_breaches method."""

    @pytest.mark.asyncio
    async def test_escalates_breach_older_than_7_days(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that breaches > 7 days old are escalated (FR31)."""
        # Create breach 8 days old
        old_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=8)
        )
        mock_breach_repository.list_all.return_value = [old_breach]

        result = await escalation_service.check_and_escalate_breaches()

        assert len(result) == 1
        assert result[0].breach_id == old_breach.breach_id
        assert result[0].days_since_breach == 8
        mock_event_writer.write_event.assert_called_once()
        mock_escalation_repository.save_escalation.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_breach_younger_than_7_days(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that breaches < 7 days old are not escalated."""
        # Create breach 5 days old
        young_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        mock_breach_repository.list_all.return_value = [young_breach]

        result = await escalation_service.check_and_escalate_breaches()

        assert len(result) == 0
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_acknowledged_breach(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that acknowledged breaches are not escalated."""
        # Create breach 10 days old but acknowledged
        old_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=10)
        )
        mock_breach_repository.list_all.return_value = [old_breach]

        # Mark as acknowledged
        mock_ack = MagicMock()
        mock_escalation_repository.get_acknowledgment_for_breach.return_value = mock_ack

        result = await escalation_service.check_and_escalate_breaches()

        assert len(result) == 0
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_already_escalated_breach(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that already escalated breaches are not re-escalated."""
        # Create breach 10 days old but already escalated
        old_breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=10)
        )
        mock_breach_repository.list_all.return_value = [old_breach]

        # Mark as escalated
        mock_esc = MagicMock()
        mock_escalation_repository.get_escalation_for_breach.return_value = mock_esc

        result = await escalation_service.check_and_escalate_breaches()

        assert len(result) == 0
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        escalation_service: EscalationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK FIRST (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError) as exc_info:
            await escalation_service.check_and_escalate_breaches()

        assert "CT-11" in str(exc_info.value)
        assert "halted" in str(exc_info.value).lower()


class TestAcknowledgeBreach:
    """Tests for acknowledge_breach method."""

    @pytest.mark.asyncio
    async def test_acknowledge_breach_success(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test successful breach acknowledgment (FR31)."""
        breach = create_breach()
        mock_breach_repository.get_by_id.return_value = breach

        result = await escalation_service.acknowledge_breach(
            breach_id=breach.breach_id,
            acknowledged_by="keeper:alice@archon72.io",
            response_choice=ResponseChoice.CORRECTIVE,
        )

        assert result.breach_id == breach.breach_id
        assert result.acknowledged_by == "keeper:alice@archon72.io"
        assert result.response_choice == ResponseChoice.CORRECTIVE
        mock_event_writer.write_event.assert_called_once()
        mock_escalation_repository.save_acknowledgment.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_breach_stops_timer(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test acknowledgment stops escalation timer (FR31)."""
        # Create breach 5 days old (approaching deadline)
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        mock_breach_repository.get_by_id.return_value = breach

        await escalation_service.acknowledge_breach(
            breach_id=breach.breach_id,
            acknowledged_by="keeper:bob",
            response_choice=ResponseChoice.DISMISS,
        )

        # Acknowledgment was saved
        mock_escalation_repository.save_acknowledgment.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_breach_fails(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test acknowledgment fails for nonexistent breach."""
        mock_breach_repository.get_by_id.return_value = None

        with pytest.raises(BreachNotFoundError):
            await escalation_service.acknowledge_breach(
                breach_id=uuid4(),
                acknowledged_by="keeper:alice",
                response_choice=ResponseChoice.CORRECTIVE,
            )

    @pytest.mark.asyncio
    async def test_acknowledge_already_acknowledged_fails(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test acknowledgment fails for already acknowledged breach."""
        breach = create_breach()
        mock_breach_repository.get_by_id.return_value = breach

        # Mark as already acknowledged
        mock_ack = MagicMock()
        mock_escalation_repository.get_acknowledgment_for_breach.return_value = mock_ack

        with pytest.raises(BreachAlreadyAcknowledgedError):
            await escalation_service.acknowledge_breach(
                breach_id=breach.breach_id,
                acknowledged_by="keeper:alice",
                response_choice=ResponseChoice.DEFER,
            )

    @pytest.mark.asyncio
    async def test_acknowledge_empty_attribution_fails(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test acknowledgment fails for empty attribution."""
        breach = create_breach()
        mock_breach_repository.get_by_id.return_value = breach

        with pytest.raises(InvalidAcknowledgmentError):
            await escalation_service.acknowledge_breach(
                breach_id=breach.breach_id,
                acknowledged_by="",
                response_choice=ResponseChoice.ACCEPT,
            )

    @pytest.mark.asyncio
    async def test_acknowledge_whitespace_attribution_fails(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test acknowledgment fails for whitespace-only attribution."""
        breach = create_breach()
        mock_breach_repository.get_by_id.return_value = breach

        with pytest.raises(InvalidAcknowledgmentError):
            await escalation_service.acknowledge_breach(
                breach_id=breach.breach_id,
                acknowledged_by="   ",
                response_choice=ResponseChoice.ACCEPT,
            )

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        escalation_service: EscalationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK FIRST (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError) as exc_info:
            await escalation_service.acknowledge_breach(
                breach_id=uuid4(),
                acknowledged_by="keeper:alice",
                response_choice=ResponseChoice.CORRECTIVE,
            )

        assert "CT-11" in str(exc_info.value)


class TestGetPendingEscalations:
    """Tests for get_pending_escalations method."""

    @pytest.mark.asyncio
    async def test_returns_pending_breaches(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns breaches not yet acknowledged or escalated."""
        breach1 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=3)
        )
        breach2 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        mock_breach_repository.list_all.return_value = [breach1, breach2]

        result = await escalation_service.get_pending_escalations()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_sorted_by_urgency(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test results are sorted by urgency (least time remaining first)."""
        # breach1: 3 days old, 4 days remaining
        breach1 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=3)
        )
        # breach2: 6 days old, 1 day remaining (more urgent)
        breach2 = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=6)
        )
        mock_breach_repository.list_all.return_value = [breach1, breach2]

        result = await escalation_service.get_pending_escalations()

        # breach2 should be first (more urgent)
        assert len(result) == 2
        assert result[0].breach_id == breach2.breach_id
        assert result[1].breach_id == breach1.breach_id

    @pytest.mark.asyncio
    async def test_excludes_acknowledged_breaches(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test excludes acknowledged breaches from pending list."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        mock_breach_repository.list_all.return_value = [breach]

        # Mark as acknowledged
        mock_ack = MagicMock()
        mock_escalation_repository.get_acknowledgment_for_breach.return_value = mock_ack

        result = await escalation_service.get_pending_escalations()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_excludes_escalated_breaches(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test excludes already escalated breaches from pending list."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        mock_breach_repository.list_all.return_value = [breach]

        # Mark as escalated
        mock_esc = MagicMock()
        mock_escalation_repository.get_escalation_for_breach.return_value = mock_esc

        result = await escalation_service.get_pending_escalations()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_time_remaining_calculated(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test time remaining is calculated correctly."""
        # Create breach 5 days old (approximately 2 days remaining)
        # Note: Due to timing, days_remaining may be 1 or 2 depending on exact milliseconds
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5)
        )
        mock_breach_repository.list_all.return_value = [breach]

        result = await escalation_service.get_pending_escalations()

        assert len(result) == 1
        assert 1 <= result[0].days_remaining <= 2  # approximately 2 days
        assert 46 <= result[0].hours_remaining <= 49  # approximately 48 hours

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        escalation_service: EscalationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK FIRST (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError) as exc_info:
            await escalation_service.get_pending_escalations()

        assert "CT-11" in str(exc_info.value)


class TestIsBreachAcknowledged:
    """Tests for is_breach_acknowledged method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_acknowledged(
        self,
        escalation_service: EscalationService,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test returns True when breach is acknowledged."""
        mock_ack = MagicMock()
        mock_escalation_repository.get_acknowledgment_for_breach.return_value = mock_ack

        result = await escalation_service.is_breach_acknowledged(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_acknowledged(
        self,
        escalation_service: EscalationService,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test returns False when breach is not acknowledged."""
        mock_escalation_repository.get_acknowledgment_for_breach.return_value = None

        result = await escalation_service.is_breach_acknowledged(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        escalation_service: EscalationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK FIRST (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError):
            await escalation_service.is_breach_acknowledged(uuid4())


class TestIsBreachEscalated:
    """Tests for is_breach_escalated method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_escalated(
        self,
        escalation_service: EscalationService,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test returns True when breach is escalated."""
        mock_esc = MagicMock()
        mock_escalation_repository.get_escalation_for_breach.return_value = mock_esc

        result = await escalation_service.is_breach_escalated(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_escalated(
        self,
        escalation_service: EscalationService,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test returns False when breach is not escalated."""
        mock_escalation_repository.get_escalation_for_breach.return_value = None

        result = await escalation_service.is_breach_escalated(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        escalation_service: EscalationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK FIRST (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError):
            await escalation_service.is_breach_escalated(uuid4())


class TestGetBreachStatus:
    """Tests for get_breach_status method."""

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_breach(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns None when breach doesn't exist."""
        mock_breach_repository.get_by_id.return_value = None

        result = await escalation_service.get_breach_status(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_status_for_existing_breach(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test returns status dict for existing breach."""
        breach = create_breach()
        mock_breach_repository.get_by_id.return_value = breach

        result = await escalation_service.get_breach_status(breach.breach_id)

        assert result is not None
        assert "is_acknowledged" in result
        assert "is_escalated" in result
        assert "acknowledgment_details" in result
        assert "escalation_details" in result

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        escalation_service: EscalationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK FIRST (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError):
            await escalation_service.get_breach_status(uuid4())


class TestEscalateBreach:
    """Tests for manual escalate_breach method."""

    @pytest.mark.asyncio
    async def test_manual_escalation_success(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test successful manual escalation."""
        breach = create_breach(
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=3)
        )
        mock_breach_repository.get_by_id.return_value = breach

        result = await escalation_service.escalate_breach(breach.breach_id)

        assert result.breach_id == breach.breach_id
        mock_event_writer.write_event.assert_called_once()
        mock_escalation_repository.save_escalation.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_escalation_breach_not_found(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """Test manual escalation fails for nonexistent breach."""
        mock_breach_repository.get_by_id.return_value = None

        with pytest.raises(BreachNotFoundError):
            await escalation_service.escalate_breach(uuid4())

    @pytest.mark.asyncio
    async def test_manual_escalation_already_escalated(
        self,
        escalation_service: EscalationService,
        mock_breach_repository: AsyncMock,
        mock_escalation_repository: AsyncMock,
    ) -> None:
        """Test manual escalation fails for already escalated breach."""
        breach = create_breach()
        mock_breach_repository.get_by_id.return_value = breach

        # Mark as already escalated
        mock_esc = MagicMock()
        mock_escalation_repository.get_escalation_for_breach.return_value = mock_esc

        with pytest.raises(BreachAlreadyEscalatedError):
            await escalation_service.escalate_breach(breach.breach_id)

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        escalation_service: EscalationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test HALT CHECK FIRST (CT-11)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError):
            await escalation_service.escalate_breach(uuid4())
