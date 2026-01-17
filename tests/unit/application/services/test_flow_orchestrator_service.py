"""Unit tests for Flow Orchestrator Service (Epic 8, Story 8.2).

Tests the Flow Orchestrator service implementation for coordinating
governance branch services through the 7-step canonical flow.

Per Government PRD FR-GOV-23: Governance Flow - 7 canonical steps coordinated.
Per CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
Per CT-12: Witnessing creates accountability → All transitions witnessed
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.flow_orchestrator import (
    BranchResult,
    ErrorEscalationStrategy,
    GovernanceBranch,
    HandleCompletionRequest,
    ProcessMotionRequest,
    RouteMotionRequest,
)
from src.application.ports.governance_state_machine import (
    GovernanceState,
    TransitionResult,
)
from src.application.services.flow_orchestrator_service import (
    FlowOrchestratorService,
    create_flow_orchestrator_service,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_state_machine() -> AsyncMock:
    """Create a mock state machine."""
    mock = AsyncMock()
    mock.get_current_state = AsyncMock(return_value=GovernanceState.INTRODUCED)
    mock.transition = AsyncMock(return_value=TransitionResult(success=True))
    return mock


@pytest.fixture
def mock_knight_witness() -> MagicMock:
    """Create a mock Knight witness."""
    mock = MagicMock()
    mock.observe = MagicMock()
    mock.record_violation = MagicMock()
    return mock


@pytest.fixture
def service(mock_state_machine: AsyncMock) -> FlowOrchestratorService:
    """Create a flow orchestrator service with mock state machine."""
    return FlowOrchestratorService(
        state_machine=mock_state_machine,
        verbose=True,
    )


@pytest.fixture
def service_with_witness(
    mock_state_machine: AsyncMock,
    mock_knight_witness: AsyncMock,
) -> FlowOrchestratorService:
    """Create a flow orchestrator service with witness."""
    return FlowOrchestratorService(
        state_machine=mock_state_machine,
        knight_witness=mock_knight_witness,
        verbose=True,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestFlowOrchestratorServiceInit:
    """Tests for service initialization."""

    def test_creates_with_state_machine(
        self, mock_state_machine: AsyncMock
    ) -> None:
        """Test service creates with state machine."""
        service = FlowOrchestratorService(state_machine=mock_state_machine)
        assert service._state_machine is mock_state_machine

    def test_creates_with_knight_witness(
        self,
        mock_state_machine: AsyncMock,
        mock_knight_witness: AsyncMock,
    ) -> None:
        """Test service creates with Knight witness."""
        service = FlowOrchestratorService(
            state_machine=mock_state_machine,
            knight_witness=mock_knight_witness,
        )
        assert service._knight_witness is mock_knight_witness

    def test_initializes_empty_pipeline_state(
        self, mock_state_machine: AsyncMock
    ) -> None:
        """Test service initializes with empty pipeline state."""
        service = FlowOrchestratorService(state_machine=mock_state_machine)
        assert len(service._motion_states) == 0
        assert len(service._escalations) == 0

    def test_initializes_statistics(
        self, mock_state_machine: AsyncMock
    ) -> None:
        """Test service initializes statistics."""
        service = FlowOrchestratorService(state_machine=mock_state_machine)
        assert service._total_processed == 0
        assert len(service._completions_24h) == 0
        assert len(service._failures_24h) == 0

    def test_factory_function_creates_service(
        self, mock_state_machine: AsyncMock
    ) -> None:
        """Test factory function creates service."""
        service = create_flow_orchestrator_service(
            state_machine=mock_state_machine,
            verbose=True,
        )
        assert isinstance(service, FlowOrchestratorService)


# =============================================================================
# Process Motion Tests
# =============================================================================


class TestProcessMotion:
    """Tests for process_motion method."""

    @pytest.mark.asyncio
    async def test_process_motion_success(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test processing a motion successfully."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.INTRODUCED

        request = ProcessMotionRequest(
            motion_id=motion_id,
            triggered_by="ARCHON:KING:001",
        )

        result = await service.process_motion(request)

        assert result.success is True
        assert result.routing_decision is not None
        assert result.routing_decision.target_service == "conclave_service"

    @pytest.mark.asyncio
    async def test_process_motion_not_found(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test processing a motion that doesn't exist."""
        mock_state_machine.get_current_state.return_value = None

        request = ProcessMotionRequest(
            motion_id=uuid4(),
            triggered_by="ARCHON:KING:001",
        )

        result = await service.process_motion(request)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_process_motion_terminal_state(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test processing a motion in terminal state fails."""
        mock_state_machine.get_current_state.return_value = GovernanceState.ACKNOWLEDGED

        request = ProcessMotionRequest(
            motion_id=uuid4(),
            triggered_by="ARCHON:KING:001",
        )

        result = await service.process_motion(request)

        assert result.success is False
        assert "terminal state" in result.error.lower()

    @pytest.mark.asyncio
    async def test_process_motion_updates_pipeline_state(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test processing updates pipeline state."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.DELIBERATING

        request = ProcessMotionRequest(
            motion_id=motion_id,
            triggered_by="ARCHON:CONCLAVE:001",
        )

        await service.process_motion(request)

        assert motion_id in service._motion_states
        assert service._motion_states[motion_id].current_state == GovernanceState.DELIBERATING

    @pytest.mark.asyncio
    async def test_process_motion_increments_total_processed(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test processing increments total processed count."""
        initial_count = service._total_processed
        mock_state_machine.get_current_state.return_value = GovernanceState.INTRODUCED

        request = ProcessMotionRequest(
            motion_id=uuid4(),
            triggered_by="ARCHON:KING:001",
        )

        await service.process_motion(request)

        assert service._total_processed == initial_count + 1


# =============================================================================
# Route to Branch Tests
# =============================================================================


class TestRouteToBranch:
    """Tests for route_to_branch method."""

    @pytest.mark.asyncio
    async def test_route_introduced_to_conclave(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test INTRODUCED routes to conclave service."""
        request = RouteMotionRequest(
            motion_id=uuid4(),
            target_state=GovernanceState.INTRODUCED,
            triggered_by="ARCHON:KING:001",
        )

        result = await service.route_to_branch(request)

        assert result.success is True
        assert result.decision.target_service == "conclave_service"
        assert result.decision.target_branch == GovernanceBranch.DELIBERATIVE

    @pytest.mark.asyncio
    async def test_route_ratified_to_president(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test RATIFIED routes to president service."""
        request = RouteMotionRequest(
            motion_id=uuid4(),
            target_state=GovernanceState.RATIFIED,
            triggered_by="ARCHON:CONCLAVE:001",
        )

        result = await service.route_to_branch(request)

        assert result.success is True
        assert result.decision.target_service == "president_service"
        assert result.decision.target_branch == GovernanceBranch.EXECUTIVE

    @pytest.mark.asyncio
    async def test_route_planning_to_duke(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test PLANNING routes to duke service."""
        request = RouteMotionRequest(
            motion_id=uuid4(),
            target_state=GovernanceState.PLANNING,
            triggered_by="ARCHON:PRESIDENT:001",
        )

        result = await service.route_to_branch(request)

        assert result.success is True
        assert result.decision.target_service == "duke_service"
        assert result.decision.target_branch == GovernanceBranch.ADMINISTRATIVE

    @pytest.mark.asyncio
    async def test_route_executing_to_prince(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test EXECUTING routes to prince service."""
        request = RouteMotionRequest(
            motion_id=uuid4(),
            target_state=GovernanceState.EXECUTING,
            triggered_by="ARCHON:DUKE:001",
        )

        result = await service.route_to_branch(request)

        assert result.success is True
        assert result.decision.target_service == "prince_service"
        assert result.decision.target_branch == GovernanceBranch.JUDICIAL

    @pytest.mark.asyncio
    async def test_route_judging_to_knight(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test JUDGING routes to knight witness service."""
        request = RouteMotionRequest(
            motion_id=uuid4(),
            target_state=GovernanceState.JUDGING,
            triggered_by="ARCHON:PRINCE:001",
        )

        result = await service.route_to_branch(request)

        assert result.success is True
        assert result.decision.target_service == "knight_witness_service"
        assert result.decision.target_branch == GovernanceBranch.WITNESS

    @pytest.mark.asyncio
    async def test_route_terminal_state_fails(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test routing terminal state fails."""
        request = RouteMotionRequest(
            motion_id=uuid4(),
            target_state=GovernanceState.REJECTED,
            triggered_by="ARCHON:CONCLAVE:001",
        )

        result = await service.route_to_branch(request)

        assert result.success is False
        assert "no service mapped" in result.error.lower()

    @pytest.mark.asyncio
    async def test_route_records_history(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test routing records history."""
        motion_id = uuid4()
        request = RouteMotionRequest(
            motion_id=motion_id,
            target_state=GovernanceState.INTRODUCED,
            triggered_by="ARCHON:KING:001",
        )

        await service.route_to_branch(request)

        assert motion_id in service._routing_history
        assert len(service._routing_history[motion_id]) == 1


# =============================================================================
# Handle Completion Tests
# =============================================================================


class TestHandleCompletion:
    """Tests for handle_completion method."""

    @pytest.mark.asyncio
    async def test_handle_successful_completion(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test handling successful branch completion."""
        motion_id = uuid4()
        mock_state_machine.transition.return_value = TransitionResult(success=True)
        mock_state_machine.get_current_state.return_value = GovernanceState.RATIFIED

        branch_result = BranchResult.create(
            motion_id=motion_id,
            branch=GovernanceBranch.DELIBERATIVE,
            success=True,
            output={"votes": 72, "in_favor": 72},
            next_state=GovernanceState.RATIFIED,
        )

        request = HandleCompletionRequest(
            motion_id=motion_id,
            branch_result=branch_result,
            triggered_by="ARCHON:CONCLAVE:001",
        )

        result = await service.handle_completion(request)

        assert result.success is True
        assert result.transition_triggered is True
        assert result.new_state == GovernanceState.RATIFIED

    @pytest.mark.asyncio
    async def test_handle_completion_triggers_transition(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test completion triggers state machine transition."""
        motion_id = uuid4()
        mock_state_machine.transition.return_value = TransitionResult(success=True)

        branch_result = BranchResult.create(
            motion_id=motion_id,
            branch=GovernanceBranch.EXECUTIVE,
            success=True,
            output={},
            next_state=GovernanceState.PLANNING,
        )

        request = HandleCompletionRequest(
            motion_id=motion_id,
            branch_result=branch_result,
            triggered_by="ARCHON:PRESIDENT:001",
        )

        await service.handle_completion(request)

        mock_state_machine.transition.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_failure_escalates(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test handling branch failure escalates error."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.PLANNING

        branch_result = BranchResult.create(
            motion_id=motion_id,
            branch=GovernanceBranch.ADMINISTRATIVE,
            success=False,
            output={},
            error="Resource allocation failed",
            error_type="system_error",
        )

        request = HandleCompletionRequest(
            motion_id=motion_id,
            branch_result=branch_result,
            triggered_by="ARCHON:DUKE:001",
        )

        result = await service.handle_completion(request)

        assert result.success is False
        assert result.escalation is not None
        assert result.escalation.error_type == "system_error"
        assert result.escalation.strategy == ErrorEscalationStrategy.HALT_AND_ALERT

    @pytest.mark.asyncio
    async def test_handle_failure_tracks_24h_stats(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test failure increments 24h failure count."""
        mock_state_machine.get_current_state.return_value = GovernanceState.EXECUTING

        branch_result = BranchResult.create(
            motion_id=uuid4(),
            branch=GovernanceBranch.JUDICIAL,
            success=False,
            output={},
            error="Compliance check failed",
            error_type="compliance_error",
        )

        request = HandleCompletionRequest(
            motion_id=branch_result.motion_id,
            branch_result=branch_result,
            triggered_by="ARCHON:PRINCE:001",
        )

        initial_failures = len(service._failures_24h)
        await service.handle_completion(request)

        assert len(service._failures_24h) == initial_failures + 1

    @pytest.mark.asyncio
    async def test_handle_success_tracks_24h_stats(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test success increments 24h completion count."""
        mock_state_machine.transition.return_value = TransitionResult(success=True)

        branch_result = BranchResult.create(
            motion_id=uuid4(),
            branch=GovernanceBranch.WITNESS,
            success=True,
            output={},
            next_state=GovernanceState.ACKNOWLEDGED,
        )

        request = HandleCompletionRequest(
            motion_id=branch_result.motion_id,
            branch_result=branch_result,
            triggered_by="ARCHON:KNIGHT:001",
        )

        initial_completions = len(service._completions_24h)
        await service.handle_completion(request)

        assert len(service._completions_24h) == initial_completions + 1


# =============================================================================
# Pipeline Status Tests
# =============================================================================


class TestGetPipelineStatus:
    """Tests for get_pipeline_status method."""

    @pytest.mark.asyncio
    async def test_empty_pipeline_status(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test getting status of empty pipeline."""
        status = await service.get_pipeline_status()

        assert status.active_motions == 0
        assert len(status.motions_by_state) == 0
        assert len(status.blocked_motions) == 0

    @pytest.mark.asyncio
    async def test_pipeline_status_counts_motions(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test pipeline status counts motions correctly."""
        mock_state_machine.get_current_state.return_value = GovernanceState.INTRODUCED

        # Process multiple motions
        for _ in range(3):
            request = ProcessMotionRequest(
                motion_id=uuid4(),
                triggered_by="ARCHON:KING:001",
            )
            await service.process_motion(request)

        status = await service.get_pipeline_status()

        assert status.active_motions == 3

    @pytest.mark.asyncio
    async def test_pipeline_status_tracks_total_processed(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test pipeline status includes total processed."""
        mock_state_machine.get_current_state.return_value = GovernanceState.DELIBERATING

        for _ in range(5):
            request = ProcessMotionRequest(
                motion_id=uuid4(),
                triggered_by="ARCHON:CONCLAVE:001",
            )
            await service.process_motion(request)

        status = await service.get_pipeline_status()

        assert status.total_processed == 5


# =============================================================================
# Motion Status Tests
# =============================================================================


class TestGetMotionStatus:
    """Tests for get_motion_status method."""

    @pytest.mark.asyncio
    async def test_get_motion_status_exists(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test getting status of existing motion."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.PLANNING

        # Process motion first
        request = ProcessMotionRequest(
            motion_id=motion_id,
            triggered_by="ARCHON:PRESIDENT:001",
        )
        await service.process_motion(request)

        status = await service.get_motion_status(motion_id)

        assert status is not None
        assert status.motion_id == motion_id
        assert status.current_state == GovernanceState.PLANNING

    @pytest.mark.asyncio
    async def test_get_motion_status_not_found(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test getting status of non-existent motion returns None."""
        status = await service.get_motion_status(uuid4())
        assert status is None


# =============================================================================
# Blocked Motions Tests
# =============================================================================


class TestGetBlockedMotions:
    """Tests for get_blocked_motions method."""

    @pytest.mark.asyncio
    async def test_get_blocked_motions_empty(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test getting blocked motions when none blocked."""
        blocked = await service.get_blocked_motions()
        assert len(blocked) == 0

    @pytest.mark.asyncio
    async def test_get_blocked_motions_after_failure(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test blocked motions includes failed motions."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.EXECUTING

        # Create failure
        branch_result = BranchResult.create(
            motion_id=motion_id,
            branch=GovernanceBranch.JUDICIAL,
            success=False,
            output={},
            error="System error",
            error_type="system_error",
        )

        request = HandleCompletionRequest(
            motion_id=motion_id,
            branch_result=branch_result,
            triggered_by="ARCHON:PRINCE:001",
        )

        await service.handle_completion(request)

        blocked = await service.get_blocked_motions()

        assert len(blocked) == 1
        assert blocked[0].motion_id == motion_id


# =============================================================================
# Error Escalation Tests
# =============================================================================


class TestEscalateError:
    """Tests for escalate_error method."""

    @pytest.mark.asyncio
    async def test_escalate_validation_error(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test escalating validation error uses RETURN_TO_PREVIOUS."""
        motion_id = uuid4()

        escalation = await service.escalate_error(
            motion_id=motion_id,
            error_type="validation_error",
            error_message="Invalid input",
            triggered_by="ARCHON:DUKE:001",
        )

        assert escalation.strategy == ErrorEscalationStrategy.RETURN_TO_PREVIOUS
        assert "returned to previous" in escalation.action_taken.lower()

    @pytest.mark.asyncio
    async def test_escalate_permission_error(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test escalating permission error uses CONCLAVE_REVIEW."""
        motion_id = uuid4()

        escalation = await service.escalate_error(
            motion_id=motion_id,
            error_type="permission_error",
            error_message="Lacks required rank",
            triggered_by="ARCHON:EARL:001",
        )

        assert escalation.strategy == ErrorEscalationStrategy.CONCLAVE_REVIEW
        assert "conclave" in escalation.action_taken.lower()

    @pytest.mark.asyncio
    async def test_escalate_system_error(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test escalating system error uses HALT_AND_ALERT."""
        motion_id = uuid4()

        escalation = await service.escalate_error(
            motion_id=motion_id,
            error_type="system_error",
            error_message="Database failure",
            triggered_by="ARCHON:DUKE:001",
        )

        assert escalation.strategy == ErrorEscalationStrategy.HALT_AND_ALERT
        assert "halt" in escalation.action_taken.lower()

    @pytest.mark.asyncio
    async def test_escalate_stores_record(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test escalation stores record."""
        motion_id = uuid4()

        escalation = await service.escalate_error(
            motion_id=motion_id,
            error_type="timeout_error",
            error_message="Service timeout",
            triggered_by="ARCHON:EARL:001",
        )

        assert escalation.escalation_id in service._escalations

    @pytest.mark.asyncio
    async def test_escalate_witnesses_with_knight(
        self,
        service_with_witness: FlowOrchestratorService,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test escalation witnesses through Knight."""
        await service_with_witness.escalate_error(
            motion_id=uuid4(),
            error_type="system_error",
            error_message="Critical failure",
            triggered_by="ARCHON:DUKE:001",
        )

        mock_knight_witness.record_violation.assert_called_once()


# =============================================================================
# Resolve Escalation Tests
# =============================================================================


class TestResolveEscalation:
    """Tests for resolve_escalation method."""

    @pytest.mark.asyncio
    async def test_resolve_escalation_success(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test resolving an escalation."""
        motion_id = uuid4()

        # Create escalation first
        escalation = await service.escalate_error(
            motion_id=motion_id,
            error_type="permission_error",
            error_message="Test error",
            triggered_by="ARCHON:EARL:001",
        )

        # Resolve it
        result = await service.resolve_escalation(
            escalation_id=escalation.escalation_id,
            resolved_by="ARCHON:CONCLAVE:001",
            resolution_notes="Issue corrected",
        )

        assert result is True
        assert service._escalations[escalation.escalation_id].resolved is True

    @pytest.mark.asyncio
    async def test_resolve_escalation_not_found(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test resolving non-existent escalation fails."""
        result = await service.resolve_escalation(
            escalation_id=uuid4(),
            resolved_by="ARCHON:CONCLAVE:001",
            resolution_notes="Test",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_clears_blocking(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test resolving escalation clears blocking issues."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.PLANNING

        # Create escalation (blocks motion)
        escalation = await service.escalate_error(
            motion_id=motion_id,
            error_type="system_error",
            error_message="System failure",
            triggered_by="ARCHON:DUKE:001",
        )

        # Verify blocked
        assert service._motion_states[motion_id].is_blocked is True

        # Resolve escalation
        await service.resolve_escalation(
            escalation_id=escalation.escalation_id,
            resolved_by="ARCHON:CONCLAVE:001",
            resolution_notes="Fixed",
        )

        # Verify unblocked
        assert service._motion_states[motion_id].is_blocked is False


# =============================================================================
# Retry Motion Tests
# =============================================================================


class TestRetryMotion:
    """Tests for retry_motion method."""

    @pytest.mark.asyncio
    async def test_retry_motion_success(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test retrying a motion."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.PLANNING

        # First process to add to pipeline
        request = ProcessMotionRequest(
            motion_id=motion_id,
            triggered_by="ARCHON:PRESIDENT:001",
        )
        await service.process_motion(request)

        # Now retry
        result = await service.retry_motion(
            motion_id=motion_id,
            triggered_by="ARCHON:PRESIDENT:001",
        )

        assert result.success is True
        assert service._motion_states[motion_id].retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_motion_not_in_pipeline(
        self, service: FlowOrchestratorService
    ) -> None:
        """Test retrying motion not in pipeline fails."""
        result = await service.retry_motion(
            motion_id=uuid4(),
            triggered_by="ARCHON:PRESIDENT:001",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retry_motion_max_exceeded(
        self, service: FlowOrchestratorService, mock_state_machine: AsyncMock
    ) -> None:
        """Test retry fails when max attempts exceeded."""
        motion_id = uuid4()
        mock_state_machine.get_current_state.return_value = GovernanceState.EXECUTING

        # Process motion
        await service.process_motion(
            ProcessMotionRequest(
                motion_id=motion_id,
                triggered_by="ARCHON:DUKE:001",
            )
        )

        # Retry up to max
        for _ in range(service._max_retry_attempts):
            await service.retry_motion(motion_id, "ARCHON:DUKE:001")

        # One more should fail
        result = await service.retry_motion(motion_id, "ARCHON:DUKE:001")

        assert result.success is False
        assert "maximum retry" in result.error.lower()


# =============================================================================
# Witness Integration Tests
# =============================================================================


class TestWitnessIntegration:
    """Tests for Knight witness integration."""

    @pytest.mark.asyncio
    async def test_routing_witnessed(
        self,
        service_with_witness: FlowOrchestratorService,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test routing decisions are witnessed."""
        request = RouteMotionRequest(
            motion_id=uuid4(),
            target_state=GovernanceState.INTRODUCED,
            triggered_by="ARCHON:KING:001",
        )

        await service_with_witness.route_to_branch(request)

        mock_knight_witness.observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_escalation_resolution_witnessed(
        self,
        service_with_witness: FlowOrchestratorService,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test escalation resolution is witnessed."""
        # Create and resolve escalation
        escalation = await service_with_witness.escalate_error(
            motion_id=uuid4(),
            error_type="permission_error",
            error_message="Test",
            triggered_by="ARCHON:EARL:001",
        )

        await service_with_witness.resolve_escalation(
            escalation_id=escalation.escalation_id,
            resolved_by="ARCHON:CONCLAVE:001",
            resolution_notes="Resolved",
        )

        # Should have record_violation + observe calls
        assert mock_knight_witness.record_violation.call_count == 1
        assert mock_knight_witness.observe.call_count == 1
