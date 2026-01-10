"""Unit tests for ComplexityBudgetEscalationService (Story 8.6, RT-6, AC4).

Tests for automatic escalation of unresolved complexity budget breaches.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.complexity_budget_escalation_service import (
    COMPLEXITY_ESCALATION_SYSTEM_AGENT_ID,
    ESCALATION_PERIOD_DAYS,
    SECOND_ESCALATION_PERIOD_DAYS,
    ComplexityBudgetEscalationService,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.complexity_budget import (
    COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE,
    ComplexityBudgetBreachedPayload,
)
from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    ComplexityDimension,
)
from src.infrastructure.stubs.complexity_budget_repository_stub import (
    ComplexityBudgetRepositoryStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def repository() -> ComplexityBudgetRepositoryStub:
    """Create a complexity budget repository stub."""
    return ComplexityBudgetRepositoryStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a halt checker stub that is not halted."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def event_writer() -> AsyncMock:
    """Create a mock event writer."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def service(
    repository: ComplexityBudgetRepositoryStub,
    event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> ComplexityBudgetEscalationService:
    """Create a ComplexityBudgetEscalationService with all dependencies."""
    return ComplexityBudgetEscalationService(
        repository=repository,
        event_writer=event_writer,
        halt_checker=halt_checker,
    )


def create_breach(
    days_ago: int = 0,
    dimension: ComplexityDimension = ComplexityDimension.ADR_COUNT,
) -> ComplexityBudgetBreachedPayload:
    """Create a breach payload for testing."""
    return ComplexityBudgetBreachedPayload(
        breach_id=uuid4(),
        dimension=dimension,
        limit=ADR_LIMIT,
        actual_value=18,
        breached_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        requires_governance_ceremony=True,
    )


class TestCheckPendingBreaches:
    """Tests for check_pending_breaches method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_breaches(
        self, service: ComplexityBudgetEscalationService
    ) -> None:
        """Test that empty list is returned when no breaches."""
        result = await service.check_pending_breaches()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_breaches_are_recent(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that recent breaches are not pending escalation."""
        # Add a recent breach (1 day old)
        breach = create_breach(days_ago=1)
        repository.add_breach(breach)

        result = await service.check_pending_breaches()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_old_breaches(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that old breaches are returned as pending."""
        # Add an old breach (10 days old)
        breach = create_breach(days_ago=10)
        repository.add_breach(breach)

        result = await service.check_pending_breaches()

        assert len(result) == 1
        assert result[0].breach_id == breach.breach_id

    @pytest.mark.asyncio
    async def test_filters_out_resolved_breaches(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that resolved breaches are not pending."""
        # Add an old breach and resolve it
        breach = create_breach(days_ago=10)
        repository.add_breach(breach)
        await repository.mark_breach_resolved(breach.breach_id)

        result = await service.check_pending_breaches()

        assert result == []


class TestEscalateBreach:
    """Tests for escalate_breach method."""

    @pytest.mark.asyncio
    async def test_creates_escalation_payload(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that escalation payload is created correctly."""
        breach = create_breach(days_ago=10)
        repository.add_breach(breach)

        result = await service.escalate_breach(breach.breach_id)

        assert result.breach_id == breach.breach_id
        assert result.dimension == breach.dimension
        assert result.escalation_level == 1
        assert result.days_without_resolution >= 10

    @pytest.mark.asyncio
    async def test_writes_witnessed_event(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test that escalation event is witnessed (CT-12)."""
        breach = create_breach(days_ago=10)
        repository.add_breach(breach)

        await service.escalate_breach(breach.breach_id)

        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE
        assert call_kwargs["agent_id"] == COMPLEXITY_ESCALATION_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_saves_escalation_to_repository(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that escalation is saved to repository."""
        breach = create_breach(days_ago=10)
        repository.add_breach(breach)

        await service.escalate_breach(breach.breach_id)

        assert repository.get_escalation_count() == 1

    @pytest.mark.asyncio
    async def test_second_level_escalation(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that breaches over 14 days get level 2 escalation."""
        breach = create_breach(days_ago=15)
        repository.add_breach(breach)

        result = await service.escalate_breach(breach.breach_id)

        assert result.escalation_level == 2

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_breach(
        self, service: ComplexityBudgetEscalationService
    ) -> None:
        """Test that error is raised for nonexistent breach."""
        with pytest.raises(ValueError, match="Breach not found"):
            await service.escalate_breach(uuid4())

    @pytest.mark.asyncio
    async def test_halted_system_raises_error(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that escalation fails when halted (CT-11)."""
        halt_checker.set_halted(True, "Test halt")
        breach = create_breach(days_ago=10)
        repository.add_breach(breach)

        with pytest.raises(SystemHaltedError):
            await service.escalate_breach(breach.breach_id)


class TestEscalateAllPending:
    """Tests for escalate_all_pending method."""

    @pytest.mark.asyncio
    async def test_escalates_all_pending_breaches(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that all pending breaches are escalated."""
        # Add multiple old breaches
        breach1 = create_breach(days_ago=10)
        breach2 = create_breach(days_ago=12)
        repository.add_breach(breach1)
        repository.add_breach(breach2)

        result = await service.escalate_all_pending()

        assert len(result) == 2
        assert repository.get_escalation_count() == 2

    @pytest.mark.asyncio
    async def test_returns_empty_when_none_pending(
        self, service: ComplexityBudgetEscalationService
    ) -> None:
        """Test that empty list is returned when none pending."""
        result = await service.escalate_all_pending()

        assert result == []

    @pytest.mark.asyncio
    async def test_halted_system_raises_error(
        self,
        service: ComplexityBudgetEscalationService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that escalation fails when halted (CT-11)."""
        halt_checker.set_halted(True, "Test halt")

        with pytest.raises(SystemHaltedError):
            await service.escalate_all_pending()


class TestIsBreachResolved:
    """Tests for is_breach_resolved method."""

    @pytest.mark.asyncio
    async def test_returns_false_for_unresolved(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that False is returned for unresolved breach."""
        breach = create_breach(days_ago=5)
        repository.add_breach(breach)

        result = await service.is_breach_resolved(breach.breach_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_resolved(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that True is returned for resolved breach."""
        breach = create_breach(days_ago=5)
        repository.add_breach(breach)
        await repository.mark_breach_resolved(breach.breach_id)

        result = await service.is_breach_resolved(breach.breach_id)

        assert result is True


class TestResolveBreach:
    """Tests for resolve_breach method."""

    @pytest.mark.asyncio
    async def test_marks_breach_as_resolved(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that breach is marked as resolved."""
        breach = create_breach(days_ago=5)
        repository.add_breach(breach)

        result = await service.resolve_breach(breach.breach_id)

        assert result is True
        assert repository.get_resolved_count() == 1

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent(
        self, service: ComplexityBudgetEscalationService
    ) -> None:
        """Test that False is returned for nonexistent breach."""
        result = await service.resolve_breach(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_halted_system_raises_error(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that resolution fails when halted (CT-11)."""
        halt_checker.set_halted(True, "Test halt")
        breach = create_breach(days_ago=5)
        repository.add_breach(breach)

        with pytest.raises(SystemHaltedError):
            await service.resolve_breach(breach.breach_id)


class TestGetEscalations:
    """Tests for escalation retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_escalations_for_breach(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that escalations for a breach are retrieved."""
        breach = create_breach(days_ago=10)
        repository.add_breach(breach)
        await service.escalate_breach(breach.breach_id)

        result = await service.get_escalations_for_breach(breach.breach_id)

        assert len(result) == 1
        assert result[0].breach_id == breach.breach_id

    @pytest.mark.asyncio
    async def test_get_all_escalations(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that all escalations are retrieved."""
        breach1 = create_breach(days_ago=10)
        breach2 = create_breach(days_ago=12)
        repository.add_breach(breach1)
        repository.add_breach(breach2)
        await service.escalate_breach(breach1.breach_id)
        await service.escalate_breach(breach2.breach_id)

        result = await service.get_all_escalations()

        assert len(result) == 2


class TestGetPendingEscalationsCount:
    """Tests for get_pending_escalations_count method."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_none_pending(
        self, service: ComplexityBudgetEscalationService
    ) -> None:
        """Test that zero is returned when none pending."""
        result = await service.get_pending_escalations_count()

        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_correct_count(
        self,
        service: ComplexityBudgetEscalationService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that correct count is returned."""
        breach1 = create_breach(days_ago=10)
        breach2 = create_breach(days_ago=12)
        breach3 = create_breach(days_ago=3)  # Recent, not pending
        repository.add_breach(breach1)
        repository.add_breach(breach2)
        repository.add_breach(breach3)

        result = await service.get_pending_escalations_count()

        assert result == 2


class TestEscalationPeriodConfiguration:
    """Tests for configurable escalation period."""

    @pytest.mark.asyncio
    async def test_custom_escalation_period(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that custom escalation period is respected."""
        service = ComplexityBudgetEscalationService(
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
            escalation_period_days=3,  # Custom 3-day period
        )

        # Add a 4-day-old breach
        breach = create_breach(days_ago=4)
        repository.add_breach(breach)

        result = await service.check_pending_breaches()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_default_escalation_period(self) -> None:
        """Test that default escalation period is 7 days."""
        assert ESCALATION_PERIOD_DAYS == 7

    @pytest.mark.asyncio
    async def test_second_escalation_period(self) -> None:
        """Test that second escalation period is 14 days."""
        assert SECOND_ESCALATION_PERIOD_DAYS == 14
