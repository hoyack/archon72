"""Unit tests for ComplexityBudgetService (Story 8.6, CT-14, RT-6).

Tests for complexity budget checking, breach detection, and governance
ceremony requirements.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.complexity_budget_service import (
    COMPLEXITY_BUDGET_SYSTEM_AGENT_ID,
    ComplexityBudgetService,
)
from src.domain.errors.complexity_budget import ComplexityBudgetApprovalRequiredError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.complexity_budget import (
    COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE,
    ComplexityBudgetBreachedPayload,
)
from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
    ComplexityBudgetStatus,
    ComplexityDimension,
    ComplexitySnapshot,
)
from src.infrastructure.stubs.complexity_budget_repository_stub import (
    ComplexityBudgetRepositoryStub,
)
from src.infrastructure.stubs.complexity_calculator_stub import (
    ComplexityCalculatorStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def calculator() -> ComplexityCalculatorStub:
    """Create a default complexity calculator stub."""
    return ComplexityCalculatorStub.with_default_values()


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
    calculator: ComplexityCalculatorStub,
    repository: ComplexityBudgetRepositoryStub,
    event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> ComplexityBudgetService:
    """Create a ComplexityBudgetService with all dependencies."""
    return ComplexityBudgetService(
        calculator=calculator,
        repository=repository,
        event_writer=event_writer,
        halt_checker=halt_checker,
    )


class TestCheckAllBudgets:
    """Tests for check_all_budgets method."""

    @pytest.mark.asyncio
    async def test_returns_snapshot_with_all_dimensions(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that snapshot contains all complexity dimensions."""
        snapshot = await service.check_all_budgets()

        assert snapshot is not None
        assert snapshot.adr_count >= 0
        assert snapshot.ceremony_types >= 0
        assert snapshot.cross_component_deps >= 0

    @pytest.mark.asyncio
    async def test_accepts_triggered_by_parameter(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that triggered_by is passed to calculator."""
        snapshot = await service.check_all_budgets(triggered_by="test_trigger")

        assert snapshot.triggered_by == "test_trigger"


class TestRecordSnapshot:
    """Tests for record_snapshot method."""

    @pytest.mark.asyncio
    async def test_saves_snapshot_to_repository(
        self,
        service: ComplexityBudgetService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that snapshot is saved to repository."""
        snapshot = ComplexitySnapshot.create(
            adr_count=5,
            ceremony_types=3,
            cross_component_deps=10,
        )

        await service.record_snapshot(snapshot)

        assert repository.get_snapshot_count() == 1
        saved = await repository.get_latest_snapshot()
        assert saved.adr_count == 5

    @pytest.mark.asyncio
    async def test_halted_system_raises_error(
        self,
        service: ComplexityBudgetService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that recording fails when system is halted (CT-11)."""
        halt_checker.set_halted(True, "Test halt")
        snapshot = ComplexitySnapshot.create(
            adr_count=5,
            ceremony_types=3,
            cross_component_deps=10,
        )

        with pytest.raises(SystemHaltedError):
            await service.record_snapshot(snapshot)


class TestGetBudgetStatus:
    """Tests for get_budget_status method."""

    @pytest.mark.asyncio
    async def test_returns_status_for_all_dimensions(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that status is returned for all dimensions."""
        status = await service.get_budget_status()

        assert ComplexityDimension.ADR_COUNT in status
        assert ComplexityDimension.CEREMONY_TYPES in status
        assert ComplexityDimension.CROSS_COMPONENT_DEPS in status

    @pytest.mark.asyncio
    async def test_within_budget_status(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that default values show within_budget status."""
        status = await service.get_budget_status()

        for dimension_status in status.values():
            assert dimension_status == ComplexityBudgetStatus.WITHIN_BUDGET

    @pytest.mark.asyncio
    async def test_breached_status_shown(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that breached dimension shows breached status."""
        calculator = ComplexityCalculatorStub.with_breached_adr_count()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        status = await service.get_budget_status()

        assert status[ComplexityDimension.ADR_COUNT] == ComplexityBudgetStatus.BREACHED


class TestIsBudgetBreached:
    """Tests for is_budget_breached method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_within_budget(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that False is returned when within budget."""
        result = await service.is_budget_breached(ComplexityDimension.ADR_COUNT)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_breached(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that True is returned when breached."""
        calculator = ComplexityCalculatorStub.with_breached_adr_count()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        result = await service.is_budget_breached(ComplexityDimension.ADR_COUNT)

        assert result is True


class TestIsAnyBudgetBreached:
    """Tests for is_any_budget_breached method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_all_within_budget(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that False is returned when all within budget."""
        result = await service.is_any_budget_breached()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_any_breached(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that True is returned when any dimension breached."""
        calculator = ComplexityCalculatorStub.with_breached_ceremony_types()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        result = await service.is_any_budget_breached()

        assert result is True


class TestGetBreachedDimensions:
    """Tests for get_breached_dimensions method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none_breached(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that empty list is returned when no breaches."""
        result = await service.get_breached_dimensions()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_breached_dimensions(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that breached dimensions are returned."""
        calculator = ComplexityCalculatorStub.with_all_breached()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        result = await service.get_breached_dimensions()

        assert ComplexityDimension.ADR_COUNT in result
        assert ComplexityDimension.CEREMONY_TYPES in result
        assert ComplexityDimension.CROSS_COMPONENT_DEPS in result


class TestRecordBreach:
    """Tests for record_breach method."""

    @pytest.mark.asyncio
    async def test_creates_breach_payload(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that breach payload is created with correct data."""
        result = await service.record_breach(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
        )

        assert result.dimension == ComplexityDimension.ADR_COUNT
        assert result.limit == ADR_LIMIT
        assert result.actual_value == 18
        assert result.requires_governance_ceremony is True

    @pytest.mark.asyncio
    async def test_writes_witnessed_event(
        self,
        service: ComplexityBudgetService,
        event_writer: AsyncMock,
    ) -> None:
        """Test that breach event is witnessed (CT-12)."""
        await service.record_breach(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
        )

        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE
        assert call_kwargs["agent_id"] == COMPLEXITY_BUDGET_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_saves_breach_to_repository(
        self,
        service: ComplexityBudgetService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that breach is saved to repository."""
        await service.record_breach(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
        )

        assert repository.get_breach_count() == 1

    @pytest.mark.asyncio
    async def test_halted_system_raises_error(
        self,
        service: ComplexityBudgetService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that breach recording fails when halted (CT-11)."""
        halt_checker.set_halted(True, "Test halt")

        with pytest.raises(SystemHaltedError):
            await service.record_breach(
                dimension=ComplexityDimension.ADR_COUNT,
                limit=ADR_LIMIT,
                actual_value=18,
            )


class TestDetectAndRecordBreaches:
    """Tests for detect_and_record_breaches method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_breaches(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that empty list is returned when no breaches."""
        result = await service.detect_and_record_breaches()

        assert result == []

    @pytest.mark.asyncio
    async def test_detects_and_records_breaches(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that all breaches are detected and recorded."""
        calculator = ComplexityCalculatorStub.with_all_breached()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        result = await service.detect_and_record_breaches()

        assert len(result) == 3
        assert repository.get_breach_count() == 3
        assert event_writer.write_event.call_count == 3

    @pytest.mark.asyncio
    async def test_halted_system_raises_error(
        self,
        service: ComplexityBudgetService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that detection fails when halted (CT-11)."""
        halt_checker.set_halted(True, "Test halt")

        with pytest.raises(SystemHaltedError):
            await service.detect_and_record_breaches()


class TestRequireGovernanceApproval:
    """Tests for require_governance_approval method (RT-6)."""

    @pytest.mark.asyncio
    async def test_raises_when_unresolved_breach_exists(
        self,
        service: ComplexityBudgetService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that error is raised when unresolved breach exists (RT-6)."""
        # Create an unresolved breach
        breach = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
            breached_at=datetime.now(timezone.utc),
            requires_governance_ceremony=True,
        )
        repository.add_breach(breach)

        with pytest.raises(ComplexityBudgetApprovalRequiredError) as exc_info:
            await service.require_governance_approval(ComplexityDimension.ADR_COUNT)

        assert exc_info.value.dimension == ComplexityDimension.ADR_COUNT
        assert exc_info.value.breach_id == breach.breach_id

    @pytest.mark.asyncio
    async def test_does_not_raise_when_no_unresolved_breaches(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that no error is raised when no unresolved breaches."""
        # Should not raise
        await service.require_governance_approval(ComplexityDimension.ADR_COUNT)


class TestGetDashboardData:
    """Tests for get_dashboard_data method."""

    @pytest.mark.asyncio
    async def test_returns_all_dashboard_fields(
        self, service: ComplexityBudgetService
    ) -> None:
        """Test that all dashboard fields are returned."""
        data = await service.get_dashboard_data()

        assert "adr_count" in data
        assert "adr_limit" in data
        assert "adr_utilization" in data
        assert "adr_status" in data
        assert "ceremony_types" in data
        assert "ceremony_type_limit" in data
        assert "cross_component_deps" in data
        assert "cross_component_dep_limit" in data
        assert "overall_status" in data
        assert "active_breaches" in data
        assert "last_updated" in data

    @pytest.mark.asyncio
    async def test_overall_status_is_worst(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that overall status is worst of all dimensions."""
        calculator = ComplexityCalculatorStub.with_breached_adr_count()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        data = await service.get_dashboard_data()

        assert data["overall_status"] == "breached"

    @pytest.mark.asyncio
    async def test_active_breaches_count(
        self,
        service: ComplexityBudgetService,
        repository: ComplexityBudgetRepositoryStub,
    ) -> None:
        """Test that active breaches are counted correctly."""
        # Add some unresolved breaches
        for _ in range(3):
            breach = ComplexityBudgetBreachedPayload(
                breach_id=uuid4(),
                dimension=ComplexityDimension.ADR_COUNT,
                limit=ADR_LIMIT,
                actual_value=18,
                breached_at=datetime.now(timezone.utc),
                requires_governance_ceremony=True,
            )
            repository.add_breach(breach)

        data = await service.get_dashboard_data()

        assert data["active_breaches"] == 3
