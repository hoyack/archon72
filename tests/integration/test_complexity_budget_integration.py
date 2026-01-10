"""Integration tests for Complexity Budget Dashboard (Story 8.6, CT-14, RT-6, SC-3).

Tests for the complexity budget feature including:
- AC1: Three-dimension tracking (ADRs ≤15, ceremony types ≤10, cross-component deps ≤20)
- AC2: Status thresholds (within_budget <80%, warning 80-99%, breached ≥100%)
- AC3: Breach = constitutional event requiring governance ceremony (RT-6)
- AC4: Automatic escalation of unresolved breaches after 7/14 days
- AC5: Historical trend data accessible via dashboard

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event, not just alert.
- SC-3: Self-consistency finding - complexity budget dashboard required.
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST.
- CT-12: Witnessing creates accountability -> All breach events MUST be witnessed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.complexity_budget_escalation_service import (
    ESCALATION_PERIOD_DAYS,
    SECOND_ESCALATION_PERIOD_DAYS,
    ComplexityBudgetEscalationService,
)
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
    WARNING_THRESHOLD_PERCENT,
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


class TestBudgetLimitsAndThresholds:
    """Integration tests for AC1/AC2: Budget limits and status thresholds."""

    @pytest.mark.asyncio
    async def test_adr_limit_is_15(self) -> None:
        """Test that ADR limit is 15 per CT-14."""
        assert ADR_LIMIT == 15

    @pytest.mark.asyncio
    async def test_ceremony_type_limit_is_10(self) -> None:
        """Test that ceremony type limit is 10 per CT-14."""
        assert CEREMONY_TYPE_LIMIT == 10

    @pytest.mark.asyncio
    async def test_cross_component_dep_limit_is_20(self) -> None:
        """Test that cross-component dependency limit is 20 per CT-14."""
        assert CROSS_COMPONENT_DEP_LIMIT == 20

    @pytest.mark.asyncio
    async def test_warning_threshold_is_80_percent(self) -> None:
        """Test that warning threshold is 80% per AC2."""
        assert WARNING_THRESHOLD_PERCENT == 80.0

    @pytest.mark.asyncio
    async def test_within_budget_status_below_80_percent(self) -> None:
        """Test that values below 80% show WITHIN_BUDGET status (AC2)."""
        # 11/15 = 73.3% for ADRs
        snapshot = ComplexitySnapshot.create(
            adr_count=11,
            ceremony_types=7,  # 70%
            cross_component_deps=15,  # 75%
        )

        adr_budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
        ceremony_budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
        deps_budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)

        assert adr_budget.status == ComplexityBudgetStatus.WITHIN_BUDGET
        assert ceremony_budget.status == ComplexityBudgetStatus.WITHIN_BUDGET
        assert deps_budget.status == ComplexityBudgetStatus.WITHIN_BUDGET

    @pytest.mark.asyncio
    async def test_warning_status_between_80_and_99_percent(self) -> None:
        """Test that values 80-99% show WARNING status (AC2)."""
        # 12/15 = 80% exactly, 14/15 = 93.3%
        snapshot = ComplexitySnapshot.create(
            adr_count=12,  # 80%
            ceremony_types=9,  # 90%
            cross_component_deps=18,  # 90%
        )

        adr_budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
        ceremony_budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
        deps_budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)

        assert adr_budget.status == ComplexityBudgetStatus.WARNING
        assert ceremony_budget.status == ComplexityBudgetStatus.WARNING
        assert deps_budget.status == ComplexityBudgetStatus.WARNING

    @pytest.mark.asyncio
    async def test_breached_status_at_or_over_100_percent(self) -> None:
        """Test that values at/over 100% show BREACHED status (AC2)."""
        snapshot = ComplexitySnapshot.create(
            adr_count=15,  # 100% exactly
            ceremony_types=11,  # 110%
            cross_component_deps=25,  # 125%
        )

        adr_budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
        ceremony_budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
        deps_budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)

        assert adr_budget.status == ComplexityBudgetStatus.BREACHED
        assert ceremony_budget.status == ComplexityBudgetStatus.BREACHED
        assert deps_budget.status == ComplexityBudgetStatus.BREACHED


class TestBreachDetectionAndRecording:
    """Integration tests for AC2/AC3: Breach detection and constitutional events."""

    @pytest.fixture
    def repository(self) -> ComplexityBudgetRepositoryStub:
        """Create repository stub."""
        return ComplexityBudgetRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        return HaltCheckerStub(force_halted=False)

    @pytest.mark.asyncio
    async def test_breach_detection_creates_constitutional_event(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that breaches create constitutional events per RT-6."""
        calculator = ComplexityCalculatorStub.with_breached_adr_count()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        breaches = await service.detect_and_record_breaches()

        # Breach should be detected and recorded
        assert len(breaches) == 1
        assert breaches[0].dimension == ComplexityDimension.ADR_COUNT
        assert breaches[0].requires_governance_ceremony is True

        # Event should be witnessed (CT-12)
        event_writer.write_event.assert_called()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE
        assert call_kwargs["agent_id"] == COMPLEXITY_BUDGET_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_breach_requires_governance_ceremony(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that unresolved breach blocks operations until approved (RT-6)."""
        calculator = ComplexityCalculatorStub.with_default_values()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Add an unresolved breach
        breach = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
            breached_at=datetime.now(timezone.utc),
            requires_governance_ceremony=True,
        )
        repository.add_breach(breach)

        # Attempting to proceed without approval should raise
        with pytest.raises(ComplexityBudgetApprovalRequiredError) as exc_info:
            await service.require_governance_approval(ComplexityDimension.ADR_COUNT)

        assert exc_info.value.dimension == ComplexityDimension.ADR_COUNT
        assert exc_info.value.breach_id == breach.breach_id

    @pytest.mark.asyncio
    async def test_halt_check_first_on_breach_recording(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that halt check is performed before breach recording (CT-11)."""
        calculator = ComplexityCalculatorStub.with_all_breached()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Halt the system
        halt_checker.set_halted(True, "Constitutional crisis")

        # Detection should fail with halt error
        with pytest.raises(SystemHaltedError):
            await service.detect_and_record_breaches()

        # No events should be written
        event_writer.write_event.assert_not_called()


class TestAutomaticEscalation:
    """Integration tests for AC4: Automatic escalation of unresolved breaches."""

    @pytest.fixture
    def repository(self) -> ComplexityBudgetRepositoryStub:
        """Create repository stub."""
        return ComplexityBudgetRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        return HaltCheckerStub(force_halted=False)

    @pytest.mark.asyncio
    async def test_escalation_after_7_days(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that breaches escalate after 7 days without resolution (AC4)."""
        assert ESCALATION_PERIOD_DAYS == 7

        service = ComplexityBudgetEscalationService(
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Add a breach from 8 days ago
        breach = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
            breached_at=datetime.now(timezone.utc) - timedelta(days=8),
            requires_governance_ceremony=True,
        )
        repository.add_breach(breach)

        # Check for pending escalations
        pending = await service.check_pending_breaches()
        assert len(pending) == 1

        # Escalate
        escalations = await service.escalate_all_pending()
        assert len(escalations) == 1
        assert escalations[0].escalation_level == 1

    @pytest.mark.asyncio
    async def test_second_level_escalation_after_14_days(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that breaches get level 2 escalation after 14 days (AC4)."""
        assert SECOND_ESCALATION_PERIOD_DAYS == 14

        service = ComplexityBudgetEscalationService(
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Add a breach from 15 days ago
        breach = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
            breached_at=datetime.now(timezone.utc) - timedelta(days=15),
            requires_governance_ceremony=True,
        )
        repository.add_breach(breach)

        # Escalate
        escalation = await service.escalate_breach(breach.breach_id)
        assert escalation.escalation_level == 2
        assert escalation.days_without_resolution >= 15

    @pytest.mark.asyncio
    async def test_resolved_breaches_not_escalated(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that resolved breaches are not escalated."""
        service = ComplexityBudgetEscalationService(
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Add an old breach and resolve it
        breach = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=ADR_LIMIT,
            actual_value=18,
            breached_at=datetime.now(timezone.utc) - timedelta(days=10),
            requires_governance_ceremony=True,
        )
        repository.add_breach(breach)
        await repository.mark_breach_resolved(breach.breach_id)

        # No pending escalations
        pending = await service.check_pending_breaches()
        assert len(pending) == 0


class TestDashboardData:
    """Integration tests for AC5: Dashboard data and historical trends."""

    @pytest.fixture
    def repository(self) -> ComplexityBudgetRepositoryStub:
        """Create repository stub."""
        return ComplexityBudgetRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        return HaltCheckerStub(force_halted=False)

    @pytest.mark.asyncio
    async def test_dashboard_shows_all_dimensions(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that dashboard shows all three complexity dimensions (AC1)."""
        calculator = ComplexityCalculatorStub.with_default_values()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        data = await service.get_dashboard_data()

        # All dimensions present
        assert "adr_count" in data
        assert "adr_limit" in data
        assert "adr_utilization" in data
        assert "adr_status" in data

        assert "ceremony_types" in data
        assert "ceremony_type_limit" in data
        assert "ceremony_type_utilization" in data
        assert "ceremony_type_status" in data

        assert "cross_component_deps" in data
        assert "cross_component_dep_limit" in data
        assert "cross_component_dep_utilization" in data
        assert "cross_component_dep_status" in data

        # Limits are correct
        assert data["adr_limit"] == ADR_LIMIT
        assert data["ceremony_type_limit"] == CEREMONY_TYPE_LIMIT
        assert data["cross_component_dep_limit"] == CROSS_COMPONENT_DEP_LIMIT

    @pytest.mark.asyncio
    async def test_dashboard_shows_overall_status(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that dashboard shows worst-case overall status."""
        calculator = ComplexityCalculatorStub.with_breached_adr_count()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        data = await service.get_dashboard_data()

        # Overall status should be BREACHED (worst of all)
        assert data["overall_status"] == "breached"

    @pytest.mark.asyncio
    async def test_dashboard_shows_active_breach_count(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that dashboard shows count of active breaches (RT-6)."""
        calculator = ComplexityCalculatorStub.with_default_values()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Add some unresolved breaches
        for i in range(3):
            breach = ComplexityBudgetBreachedPayload(
                breach_id=uuid4(),
                dimension=ComplexityDimension.ADR_COUNT,
                limit=ADR_LIMIT,
                actual_value=18 + i,
                breached_at=datetime.now(timezone.utc),
                requires_governance_ceremony=True,
            )
            repository.add_breach(breach)

        data = await service.get_dashboard_data()

        assert data["active_breaches"] == 3

    @pytest.mark.asyncio
    async def test_historical_snapshots_accessible(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that historical trend data is accessible (AC5)."""
        calculator = ComplexityCalculatorStub.with_default_values()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Add some historical snapshots
        now = datetime.now(timezone.utc)
        for days_ago in [7, 5, 3, 1]:
            snapshot = ComplexitySnapshot(
                snapshot_id=uuid4(),
                adr_count=10 + days_ago,
                ceremony_types=5,
                cross_component_deps=15,
                timestamp=now - timedelta(days=days_ago),
            )
            repository.add_snapshot(snapshot)

        # Query by date range
        start = now - timedelta(days=6)
        end = now
        snapshots = await service.get_snapshots_in_range(start, end)

        # Should get 3 snapshots (5, 3, 1 days ago)
        assert len(snapshots) == 3


class TestConstitutionalConstraints:
    """Integration tests verifying constitutional constraints are enforced."""

    @pytest.fixture
    def repository(self) -> ComplexityBudgetRepositoryStub:
        """Create repository stub."""
        return ComplexityBudgetRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create halt checker stub."""
        return HaltCheckerStub(force_halted=False)

    @pytest.mark.asyncio
    async def test_ct14_complexity_is_tracked(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that complexity is actively tracked per CT-14."""
        calculator = ComplexityCalculatorStub.with_default_values()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Can check all budgets
        snapshot = await service.check_all_budgets()
        assert snapshot.adr_count >= 0
        assert snapshot.ceremony_types >= 0
        assert snapshot.cross_component_deps >= 0

        # Can get budget status
        status = await service.get_budget_status()
        assert ComplexityDimension.ADR_COUNT in status
        assert ComplexityDimension.CEREMONY_TYPES in status
        assert ComplexityDimension.CROSS_COMPONENT_DEPS in status

    @pytest.mark.asyncio
    async def test_rt6_breach_is_constitutional_event(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that breach creates constitutional event, not just alert (RT-6)."""
        calculator = ComplexityCalculatorStub.with_breached_ceremony_types()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        breaches = await service.detect_and_record_breaches()

        # Breach creates a constitutional event requiring governance ceremony
        assert len(breaches) == 1
        assert breaches[0].requires_governance_ceremony is True

        # Event is recorded
        assert repository.get_breach_count() == 1

    @pytest.mark.asyncio
    async def test_ct11_halt_check_first(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that halt is checked before write operations (CT-11)."""
        calculator = ComplexityCalculatorStub.with_default_values()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Halt the system
        halt_checker.set_halted(True, "Test halt")

        # All write operations should fail
        snapshot = ComplexitySnapshot.create(
            adr_count=5,
            ceremony_types=3,
            cross_component_deps=10,
        )

        with pytest.raises(SystemHaltedError):
            await service.record_snapshot(snapshot)

        with pytest.raises(SystemHaltedError):
            await service.detect_and_record_breaches()

    @pytest.mark.asyncio
    async def test_ct12_breach_events_witnessed(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that all breach events are witnessed (CT-12)."""
        calculator = ComplexityCalculatorStub.with_all_breached()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        await service.detect_and_record_breaches()

        # All 3 breaches should be witnessed
        assert event_writer.write_event.call_count == 3

        # Each call should use the event writer with proper type and agent
        for call in event_writer.write_event.call_args_list:
            kwargs = call.kwargs
            assert kwargs["event_type"] == COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE
            assert kwargs["agent_id"] == COMPLEXITY_BUDGET_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_sc3_dashboard_available(
        self,
        repository: ComplexityBudgetRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that complexity budget dashboard is available (SC-3)."""
        calculator = ComplexityCalculatorStub.with_warning_values()
        service = ComplexityBudgetService(
            calculator=calculator,
            repository=repository,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        data = await service.get_dashboard_data()

        # Dashboard data is complete
        assert "adr_count" in data
        assert "adr_limit" in data
        assert "adr_utilization" in data
        assert "adr_status" in data
        assert "overall_status" in data
        assert "active_breaches" in data
        assert "last_updated" in data

        # Status reflects warning level
        assert data["overall_status"] == "warning"
