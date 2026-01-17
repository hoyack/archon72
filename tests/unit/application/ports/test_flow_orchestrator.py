"""Unit tests for Flow Orchestrator port (Epic 8, Story 8.2).

Tests domain models, routing maps, helper functions, and protocol definition
for the Flow Orchestrator that coordinates governance branch services.

Per Government PRD FR-GOV-23: Governance Flow - 7 canonical steps coordinated.
Per CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
Per CT-12: Witnessing creates accountability → All transitions witnessed
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.flow_orchestrator import (
    ERROR_TYPE_MAP,
    STATE_BRANCH_MAP,
    STATE_SERVICE_MAP,
    BranchResult,
    ErrorEscalationStrategy,
    EscalationRecord,
    FlowOrchestratorProtocol,
    GovernanceBranch,
    HandleCompletionRequest,
    HandleCompletionResult,
    MotionBlockReason,
    MotionPipelineState,
    PipelineStatus,
    ProcessMotionRequest,
    ProcessMotionResult,
    RouteMotionRequest,
    RouteMotionResult,
    RoutingDecision,
    get_branch_for_state,
    get_escalation_strategy,
    get_service_for_state,
    is_blocking_error,
    is_retryable_error,
)
from src.application.ports.governance_state_machine import GovernanceState


# =============================================================================
# GovernanceBranch Enum Tests
# =============================================================================


class TestGovernanceBranch:
    """Tests for GovernanceBranch enum."""

    def test_has_all_required_branches(self) -> None:
        """Verify all 7 governance branches are defined."""
        expected_branches = {
            "legislative",
            "deliberative",
            "executive",
            "administrative",
            "judicial",
            "witness",
            "advisory",
        }
        actual_branches = {b.value for b in GovernanceBranch}
        assert actual_branches == expected_branches

    def test_legislative_is_king_branch(self) -> None:
        """Verify legislative branch value."""
        assert GovernanceBranch.LEGISLATIVE.value == "legislative"

    def test_deliberative_is_conclave_branch(self) -> None:
        """Verify deliberative branch value."""
        assert GovernanceBranch.DELIBERATIVE.value == "deliberative"

    def test_executive_is_president_branch(self) -> None:
        """Verify executive branch value."""
        assert GovernanceBranch.EXECUTIVE.value == "executive"

    def test_administrative_is_duke_earl_branch(self) -> None:
        """Verify administrative branch value."""
        assert GovernanceBranch.ADMINISTRATIVE.value == "administrative"

    def test_judicial_is_prince_branch(self) -> None:
        """Verify judicial branch value."""
        assert GovernanceBranch.JUDICIAL.value == "judicial"

    def test_witness_is_knight_branch(self) -> None:
        """Verify witness branch value."""
        assert GovernanceBranch.WITNESS.value == "witness"

    def test_advisory_is_marquis_branch(self) -> None:
        """Verify advisory branch value."""
        assert GovernanceBranch.ADVISORY.value == "advisory"


# =============================================================================
# ErrorEscalationStrategy Enum Tests
# =============================================================================


class TestErrorEscalationStrategy:
    """Tests for ErrorEscalationStrategy enum."""

    def test_has_all_required_strategies(self) -> None:
        """Verify all escalation strategies are defined."""
        expected_strategies = {
            "return_to_previous",
            "conclave_review",
            "halt_and_alert",
            "retry_with_backoff",
        }
        actual_strategies = {s.value for s in ErrorEscalationStrategy}
        assert actual_strategies == expected_strategies

    def test_return_to_previous_for_validation_errors(self) -> None:
        """Verify validation errors use RETURN_TO_PREVIOUS."""
        strategy = get_escalation_strategy("validation_error")
        assert strategy == ErrorEscalationStrategy.RETURN_TO_PREVIOUS

    def test_conclave_review_for_permission_errors(self) -> None:
        """Verify permission errors use CONCLAVE_REVIEW."""
        strategy = get_escalation_strategy("permission_error")
        assert strategy == ErrorEscalationStrategy.CONCLAVE_REVIEW

    def test_halt_and_alert_for_system_errors(self) -> None:
        """Verify system errors use HALT_AND_ALERT."""
        strategy = get_escalation_strategy("system_error")
        assert strategy == ErrorEscalationStrategy.HALT_AND_ALERT

    def test_retry_for_timeout_errors(self) -> None:
        """Verify timeout errors use RETRY_WITH_BACKOFF."""
        strategy = get_escalation_strategy("timeout_error")
        assert strategy == ErrorEscalationStrategy.RETRY_WITH_BACKOFF


# =============================================================================
# MotionBlockReason Enum Tests
# =============================================================================


class TestMotionBlockReason:
    """Tests for MotionBlockReason enum."""

    def test_has_all_required_reasons(self) -> None:
        """Verify all block reasons are defined."""
        expected_reasons = {
            "awaiting_deliberation",
            "awaiting_resources",
            "awaiting_execution",
            "awaiting_judgment",
            "error_escalation",
            "conclave_review",
            "system_halt",
            "timeout",
        }
        actual_reasons = {r.value for r in MotionBlockReason}
        assert actual_reasons == expected_reasons


# =============================================================================
# State Routing Maps Tests
# =============================================================================


class TestStateServiceMap:
    """Tests for STATE_SERVICE_MAP routing configuration."""

    def test_introduced_routes_to_conclave(self) -> None:
        """Verify INTRODUCED state routes to conclave service."""
        assert STATE_SERVICE_MAP[GovernanceState.INTRODUCED] == "conclave_service"

    def test_deliberating_routes_to_conclave(self) -> None:
        """Verify DELIBERATING state routes to conclave service."""
        assert STATE_SERVICE_MAP[GovernanceState.DELIBERATING] == "conclave_service"

    def test_ratified_routes_to_president(self) -> None:
        """Verify RATIFIED state routes to president service."""
        assert STATE_SERVICE_MAP[GovernanceState.RATIFIED] == "president_service"

    def test_planning_routes_to_duke(self) -> None:
        """Verify PLANNING state routes to duke service."""
        assert STATE_SERVICE_MAP[GovernanceState.PLANNING] == "duke_service"

    def test_executing_routes_to_prince(self) -> None:
        """Verify EXECUTING state routes to prince service."""
        assert STATE_SERVICE_MAP[GovernanceState.EXECUTING] == "prince_service"

    def test_judging_routes_to_knight(self) -> None:
        """Verify JUDGING state routes to knight witness service."""
        assert STATE_SERVICE_MAP[GovernanceState.JUDGING] == "knight_witness_service"

    def test_witnessing_routes_to_conclave(self) -> None:
        """Verify WITNESSING state routes to conclave for acknowledgment."""
        assert STATE_SERVICE_MAP[GovernanceState.WITNESSING] == "conclave_service"

    def test_terminal_states_not_in_map(self) -> None:
        """Verify terminal states are not in the routing map."""
        assert GovernanceState.REJECTED not in STATE_SERVICE_MAP
        assert GovernanceState.ACKNOWLEDGED not in STATE_SERVICE_MAP


class TestStateBranchMap:
    """Tests for STATE_BRANCH_MAP routing configuration."""

    def test_introduced_is_deliberative(self) -> None:
        """Verify INTRODUCED state belongs to deliberative branch."""
        assert STATE_BRANCH_MAP[GovernanceState.INTRODUCED] == GovernanceBranch.DELIBERATIVE

    def test_ratified_is_executive(self) -> None:
        """Verify RATIFIED state belongs to executive branch."""
        assert STATE_BRANCH_MAP[GovernanceState.RATIFIED] == GovernanceBranch.EXECUTIVE

    def test_planning_is_administrative(self) -> None:
        """Verify PLANNING state belongs to administrative branch."""
        assert STATE_BRANCH_MAP[GovernanceState.PLANNING] == GovernanceBranch.ADMINISTRATIVE

    def test_executing_is_judicial(self) -> None:
        """Verify EXECUTING state belongs to judicial branch."""
        assert STATE_BRANCH_MAP[GovernanceState.EXECUTING] == GovernanceBranch.JUDICIAL

    def test_judging_is_witness(self) -> None:
        """Verify JUDGING state belongs to witness branch."""
        assert STATE_BRANCH_MAP[GovernanceState.JUDGING] == GovernanceBranch.WITNESS


class TestErrorTypeMap:
    """Tests for ERROR_TYPE_MAP escalation configuration."""

    def test_validation_error_returns_to_previous(self) -> None:
        """Verify validation_error maps to RETURN_TO_PREVIOUS."""
        assert ERROR_TYPE_MAP["validation_error"] == ErrorEscalationStrategy.RETURN_TO_PREVIOUS

    def test_permission_error_goes_to_conclave(self) -> None:
        """Verify permission_error maps to CONCLAVE_REVIEW."""
        assert ERROR_TYPE_MAP["permission_error"] == ErrorEscalationStrategy.CONCLAVE_REVIEW

    def test_compliance_error_goes_to_conclave(self) -> None:
        """Verify compliance_error maps to CONCLAVE_REVIEW."""
        assert ERROR_TYPE_MAP["compliance_error"] == ErrorEscalationStrategy.CONCLAVE_REVIEW

    def test_rank_violation_goes_to_conclave(self) -> None:
        """Verify rank_violation maps to CONCLAVE_REVIEW."""
        assert ERROR_TYPE_MAP["rank_violation"] == ErrorEscalationStrategy.CONCLAVE_REVIEW

    def test_system_error_halts(self) -> None:
        """Verify system_error maps to HALT_AND_ALERT."""
        assert ERROR_TYPE_MAP["system_error"] == ErrorEscalationStrategy.HALT_AND_ALERT

    def test_timeout_error_retries(self) -> None:
        """Verify timeout_error maps to RETRY_WITH_BACKOFF."""
        assert ERROR_TYPE_MAP["timeout_error"] == ErrorEscalationStrategy.RETRY_WITH_BACKOFF


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestGetServiceForState:
    """Tests for get_service_for_state helper."""

    def test_returns_service_for_valid_state(self) -> None:
        """Verify returns correct service for mapped state."""
        service = get_service_for_state(GovernanceState.INTRODUCED)
        assert service == "conclave_service"

    def test_returns_none_for_terminal_state(self) -> None:
        """Verify returns None for terminal states."""
        service = get_service_for_state(GovernanceState.REJECTED)
        assert service is None


class TestGetBranchForState:
    """Tests for get_branch_for_state helper."""

    def test_returns_branch_for_valid_state(self) -> None:
        """Verify returns correct branch for mapped state."""
        branch = get_branch_for_state(GovernanceState.PLANNING)
        assert branch == GovernanceBranch.ADMINISTRATIVE

    def test_returns_none_for_terminal_state(self) -> None:
        """Verify returns None for terminal states."""
        branch = get_branch_for_state(GovernanceState.ACKNOWLEDGED)
        assert branch is None


class TestGetEscalationStrategy:
    """Tests for get_escalation_strategy helper."""

    def test_returns_strategy_for_known_error(self) -> None:
        """Verify returns mapped strategy for known error type."""
        strategy = get_escalation_strategy("validation_error")
        assert strategy == ErrorEscalationStrategy.RETURN_TO_PREVIOUS

    def test_defaults_to_halt_for_unknown_error(self) -> None:
        """Verify defaults to HALT_AND_ALERT for unknown error types."""
        strategy = get_escalation_strategy("unknown_error_type")
        assert strategy == ErrorEscalationStrategy.HALT_AND_ALERT


class TestIsRetryableError:
    """Tests for is_retryable_error helper."""

    def test_timeout_error_is_retryable(self) -> None:
        """Verify timeout errors are retryable."""
        assert is_retryable_error("timeout_error") is True

    def test_transient_error_is_retryable(self) -> None:
        """Verify transient errors are retryable."""
        assert is_retryable_error("transient_error") is True

    def test_system_error_not_retryable(self) -> None:
        """Verify system errors are not retryable."""
        assert is_retryable_error("system_error") is False

    def test_permission_error_not_retryable(self) -> None:
        """Verify permission errors are not retryable."""
        assert is_retryable_error("permission_error") is False


class TestIsBlockingError:
    """Tests for is_blocking_error helper."""

    def test_system_error_is_blocking(self) -> None:
        """Verify system errors block the pipeline."""
        assert is_blocking_error("system_error") is True

    def test_permission_error_is_blocking(self) -> None:
        """Verify permission errors block the pipeline."""
        assert is_blocking_error("permission_error") is True

    def test_timeout_error_not_blocking(self) -> None:
        """Verify timeout errors don't block (they retry)."""
        assert is_blocking_error("timeout_error") is False

    def test_validation_error_not_blocking(self) -> None:
        """Verify validation errors don't block (they return)."""
        assert is_blocking_error("validation_error") is False


# =============================================================================
# Domain Model Tests
# =============================================================================


class TestBranchResult:
    """Tests for BranchResult domain model."""

    def test_create_successful_result(self) -> None:
        """Test creating a successful branch result."""
        motion_id = uuid4()
        result = BranchResult.create(
            motion_id=motion_id,
            branch=GovernanceBranch.DELIBERATIVE,
            success=True,
            output={"deliberation": "complete"},
            next_state=GovernanceState.RATIFIED,
        )

        assert result.motion_id == motion_id
        assert result.branch == GovernanceBranch.DELIBERATIVE
        assert result.success is True
        assert result.output == {"deliberation": "complete"}
        assert result.next_state == GovernanceState.RATIFIED
        assert result.error is None

    def test_create_failed_result(self) -> None:
        """Test creating a failed branch result."""
        motion_id = uuid4()
        result = BranchResult.create(
            motion_id=motion_id,
            branch=GovernanceBranch.JUDICIAL,
            success=False,
            output={},
            error="Compliance check failed",
            error_type="compliance_error",
        )

        assert result.success is False
        assert result.error == "Compliance check failed"
        assert result.error_type == "compliance_error"
        assert result.next_state is None

    def test_has_unique_result_id(self) -> None:
        """Verify each result gets unique ID."""
        result1 = BranchResult.create(
            motion_id=uuid4(),
            branch=GovernanceBranch.EXECUTIVE,
            success=True,
            output={},
        )
        result2 = BranchResult.create(
            motion_id=uuid4(),
            branch=GovernanceBranch.EXECUTIVE,
            success=True,
            output={},
        )
        assert result1.result_id != result2.result_id

    def test_has_completion_timestamp(self) -> None:
        """Verify result has completion timestamp."""
        result = BranchResult.create(
            motion_id=uuid4(),
            branch=GovernanceBranch.WITNESS,
            success=True,
            output={},
        )
        assert isinstance(result.completed_at, datetime)
        assert result.completed_at.tzinfo == timezone.utc

    def test_is_frozen(self) -> None:
        """Verify BranchResult is immutable."""
        result = BranchResult.create(
            motion_id=uuid4(),
            branch=GovernanceBranch.EXECUTIVE,
            success=True,
            output={},
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestMotionPipelineState:
    """Tests for MotionPipelineState domain model."""

    def test_create_basic_state(self) -> None:
        """Test creating a basic pipeline state."""
        motion_id = uuid4()
        state = MotionPipelineState.create(
            motion_id=motion_id,
            current_state=GovernanceState.DELIBERATING,
            next_action="Awaiting Conclave decision",
        )

        assert state.motion_id == motion_id
        assert state.current_state == GovernanceState.DELIBERATING
        assert state.next_action == "Awaiting Conclave decision"
        assert state.blocking_issues == ()
        assert state.retry_count == 0

    def test_create_with_blocking_issues(self) -> None:
        """Test creating state with blocking issues."""
        state = MotionPipelineState.create(
            motion_id=uuid4(),
            current_state=GovernanceState.PLANNING,
            next_action="Resolve blocking issues",
            blocking_issues=("Missing resources", "Pending approval"),
        )

        assert len(state.blocking_issues) == 2
        assert "Missing resources" in state.blocking_issues

    def test_is_blocked_property(self) -> None:
        """Test is_blocked property."""
        unblocked = MotionPipelineState.create(
            motion_id=uuid4(),
            current_state=GovernanceState.EXECUTING,
            next_action="Continue execution",
        )
        assert unblocked.is_blocked is False

        blocked = MotionPipelineState.create(
            motion_id=uuid4(),
            current_state=GovernanceState.PLANNING,
            next_action="Awaiting resolution",
            blocking_issues=("Resource unavailable",),
        )
        assert blocked.is_blocked is True

    def test_time_in_state_property(self) -> None:
        """Test time_in_state calculation."""
        state = MotionPipelineState.create(
            motion_id=uuid4(),
            current_state=GovernanceState.JUDGING,
            next_action="Awaiting judgment",
        )

        time_in_state = state.time_in_state
        assert isinstance(time_in_state, timedelta)
        assert time_in_state.total_seconds() >= 0

    def test_is_frozen(self) -> None:
        """Verify MotionPipelineState is immutable."""
        state = MotionPipelineState.create(
            motion_id=uuid4(),
            current_state=GovernanceState.WITNESSING,
            next_action="Awaiting witness",
        )
        with pytest.raises(AttributeError):
            state.retry_count = 5  # type: ignore[misc]


class TestPipelineStatus:
    """Tests for PipelineStatus domain model."""

    def test_create_basic_status(self) -> None:
        """Test creating a basic pipeline status."""
        status = PipelineStatus.create(
            active_motions=10,
            motions_by_state={
                GovernanceState.DELIBERATING: 3,
                GovernanceState.PLANNING: 4,
                GovernanceState.EXECUTING: 3,
            },
            blocked_motions=(),
            oldest_motion_age=timedelta(hours=48),
            recent_completions=5,
            recent_failures=1,
        )

        assert status.active_motions == 10
        assert status.motions_by_state[GovernanceState.DELIBERATING] == 3
        assert status.recent_completions == 5
        assert status.recent_failures == 1

    def test_create_with_blocked_motions(self) -> None:
        """Test creating status with blocked motions."""
        blocked1 = uuid4()
        blocked2 = uuid4()

        status = PipelineStatus.create(
            active_motions=5,
            motions_by_state={GovernanceState.PLANNING: 5},
            blocked_motions=(blocked1, blocked2),
            oldest_motion_age=timedelta(days=7),
            recent_completions=0,
            recent_failures=2,
        )

        assert len(status.blocked_motions) == 2
        assert blocked1 in status.blocked_motions

    def test_has_query_timestamp(self) -> None:
        """Verify status has query timestamp."""
        status = PipelineStatus.create(
            active_motions=0,
            motions_by_state={},
            blocked_motions=(),
            oldest_motion_age=timedelta(0),
            recent_completions=0,
            recent_failures=0,
        )
        assert isinstance(status.queried_at, datetime)
        assert status.queried_at.tzinfo == timezone.utc

    def test_is_frozen(self) -> None:
        """Verify PipelineStatus is immutable."""
        status = PipelineStatus.create(
            active_motions=1,
            motions_by_state={},
            blocked_motions=(),
            oldest_motion_age=timedelta(hours=1),
            recent_completions=0,
            recent_failures=0,
        )
        with pytest.raises(AttributeError):
            status.active_motions = 100  # type: ignore[misc]


class TestRoutingDecision:
    """Tests for RoutingDecision domain model."""

    def test_create_decision(self) -> None:
        """Test creating a routing decision."""
        motion_id = uuid4()
        decision = RoutingDecision.create(
            motion_id=motion_id,
            from_state=GovernanceState.RATIFIED,
            target_service="president_service",
            target_branch=GovernanceBranch.EXECUTIVE,
            reason="Motion ratified, routing to President for planning",
        )

        assert decision.motion_id == motion_id
        assert decision.from_state == GovernanceState.RATIFIED
        assert decision.target_service == "president_service"
        assert decision.target_branch == GovernanceBranch.EXECUTIVE
        assert "planning" in decision.reason

    def test_has_unique_decision_id(self) -> None:
        """Verify each decision gets unique ID."""
        decision1 = RoutingDecision.create(
            motion_id=uuid4(),
            from_state=GovernanceState.INTRODUCED,
            target_service="conclave_service",
            target_branch=GovernanceBranch.DELIBERATIVE,
            reason="Test routing",
        )
        decision2 = RoutingDecision.create(
            motion_id=uuid4(),
            from_state=GovernanceState.INTRODUCED,
            target_service="conclave_service",
            target_branch=GovernanceBranch.DELIBERATIVE,
            reason="Test routing",
        )
        assert decision1.decision_id != decision2.decision_id

    def test_is_frozen(self) -> None:
        """Verify RoutingDecision is immutable."""
        decision = RoutingDecision.create(
            motion_id=uuid4(),
            from_state=GovernanceState.PLANNING,
            target_service="duke_service",
            target_branch=GovernanceBranch.ADMINISTRATIVE,
            reason="Routing to Duke",
        )
        with pytest.raises(AttributeError):
            decision.reason = "Modified reason"  # type: ignore[misc]


class TestEscalationRecord:
    """Tests for EscalationRecord domain model."""

    def test_create_escalation(self) -> None:
        """Test creating an escalation record."""
        motion_id = uuid4()
        escalation = EscalationRecord.create(
            motion_id=motion_id,
            error_type="permission_error",
            strategy=ErrorEscalationStrategy.CONCLAVE_REVIEW,
            original_error="Archon lacks required rank",
            action_taken="Referred to Conclave for review",
        )

        assert escalation.motion_id == motion_id
        assert escalation.error_type == "permission_error"
        assert escalation.strategy == ErrorEscalationStrategy.CONCLAVE_REVIEW
        assert "lacks required rank" in escalation.original_error
        assert escalation.resolved is False
        assert escalation.resolved_at is None

    def test_has_unique_escalation_id(self) -> None:
        """Verify each escalation gets unique ID."""
        escalation1 = EscalationRecord.create(
            motion_id=uuid4(),
            error_type="system_error",
            strategy=ErrorEscalationStrategy.HALT_AND_ALERT,
            original_error="Database connection failed",
            action_taken="System halted, alert sent",
        )
        escalation2 = EscalationRecord.create(
            motion_id=uuid4(),
            error_type="system_error",
            strategy=ErrorEscalationStrategy.HALT_AND_ALERT,
            original_error="Database connection failed",
            action_taken="System halted, alert sent",
        )
        assert escalation1.escalation_id != escalation2.escalation_id

    def test_has_escalation_timestamp(self) -> None:
        """Verify escalation has timestamp."""
        escalation = EscalationRecord.create(
            motion_id=uuid4(),
            error_type="timeout_error",
            strategy=ErrorEscalationStrategy.RETRY_WITH_BACKOFF,
            original_error="Service timeout",
            action_taken="Scheduled retry with backoff",
        )
        assert isinstance(escalation.escalated_at, datetime)
        assert escalation.escalated_at.tzinfo == timezone.utc

    def test_is_frozen(self) -> None:
        """Verify EscalationRecord is immutable."""
        escalation = EscalationRecord.create(
            motion_id=uuid4(),
            error_type="validation_error",
            strategy=ErrorEscalationStrategy.RETURN_TO_PREVIOUS,
            original_error="Invalid input",
            action_taken="Returned to previous step",
        )
        with pytest.raises(AttributeError):
            escalation.resolved = True  # type: ignore[misc]


# =============================================================================
# Request/Response Model Tests
# =============================================================================


class TestProcessMotionRequest:
    """Tests for ProcessMotionRequest model."""

    def test_create_basic_request(self) -> None:
        """Test creating a basic process motion request."""
        motion_id = uuid4()
        request = ProcessMotionRequest(
            motion_id=motion_id,
            triggered_by="ARCHON:KING:001",
        )

        assert request.motion_id == motion_id
        assert request.triggered_by == "ARCHON:KING:001"
        assert request.force is False

    def test_create_forced_request(self) -> None:
        """Test creating a forced process motion request."""
        request = ProcessMotionRequest(
            motion_id=uuid4(),
            triggered_by="ARCHON:KING:001",
            force=True,
        )
        assert request.force is True

    def test_is_frozen(self) -> None:
        """Verify ProcessMotionRequest is immutable."""
        request = ProcessMotionRequest(
            motion_id=uuid4(),
            triggered_by="ARCHON:KING:001",
        )
        with pytest.raises(AttributeError):
            request.force = True  # type: ignore[misc]


class TestProcessMotionResult:
    """Tests for ProcessMotionResult model."""

    def test_successful_result(self) -> None:
        """Test creating a successful result."""
        decision = RoutingDecision.create(
            motion_id=uuid4(),
            from_state=GovernanceState.INTRODUCED,
            target_service="conclave_service",
            target_branch=GovernanceBranch.DELIBERATIVE,
            reason="Routing for deliberation",
        )

        result = ProcessMotionResult(
            success=True,
            routing_decision=decision,
            new_state=GovernanceState.DELIBERATING,
        )

        assert result.success is True
        assert result.routing_decision is not None
        assert result.new_state == GovernanceState.DELIBERATING
        assert result.error is None

    def test_failed_result(self) -> None:
        """Test creating a failed result."""
        result = ProcessMotionResult(
            success=False,
            error="Motion not found",
        )

        assert result.success is False
        assert result.error == "Motion not found"
        assert result.routing_decision is None


class TestRouteMotionRequest:
    """Tests for RouteMotionRequest model."""

    def test_create_route_request(self) -> None:
        """Test creating a route motion request."""
        motion_id = uuid4()
        request = RouteMotionRequest(
            motion_id=motion_id,
            target_state=GovernanceState.PLANNING,
            triggered_by="ARCHON:PRESIDENT:001",
        )

        assert request.motion_id == motion_id
        assert request.target_state == GovernanceState.PLANNING
        assert request.triggered_by == "ARCHON:PRESIDENT:001"


class TestHandleCompletionRequest:
    """Tests for HandleCompletionRequest model."""

    def test_create_completion_request(self) -> None:
        """Test creating a handle completion request."""
        motion_id = uuid4()
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

        assert request.motion_id == motion_id
        assert request.branch_result.success is True
        assert request.triggered_by == "ARCHON:CONCLAVE:001"


class TestHandleCompletionResult:
    """Tests for HandleCompletionResult model."""

    def test_successful_transition(self) -> None:
        """Test result with successful transition."""
        result = HandleCompletionResult(
            success=True,
            transition_triggered=True,
            new_state=GovernanceState.PLANNING,
        )

        assert result.success is True
        assert result.transition_triggered is True
        assert result.new_state == GovernanceState.PLANNING

    def test_failed_with_escalation(self) -> None:
        """Test result with escalation."""
        escalation = EscalationRecord.create(
            motion_id=uuid4(),
            error_type="system_error",
            strategy=ErrorEscalationStrategy.HALT_AND_ALERT,
            original_error="Critical failure",
            action_taken="Pipeline halted",
        )

        result = HandleCompletionResult(
            success=False,
            error="Critical failure",
            escalation=escalation,
        )

        assert result.success is False
        assert result.escalation is not None
        assert result.escalation.strategy == ErrorEscalationStrategy.HALT_AND_ALERT


# =============================================================================
# Protocol Tests
# =============================================================================


class TestFlowOrchestratorProtocol:
    """Tests for FlowOrchestratorProtocol definition."""

    def test_protocol_has_process_motion_method(self) -> None:
        """Verify protocol defines process_motion method."""
        assert hasattr(FlowOrchestratorProtocol, "process_motion")

    def test_protocol_has_route_to_branch_method(self) -> None:
        """Verify protocol defines route_to_branch method."""
        assert hasattr(FlowOrchestratorProtocol, "route_to_branch")

    def test_protocol_has_handle_completion_method(self) -> None:
        """Verify protocol defines handle_completion method."""
        assert hasattr(FlowOrchestratorProtocol, "handle_completion")

    def test_protocol_has_get_pipeline_status_method(self) -> None:
        """Verify protocol defines get_pipeline_status method."""
        assert hasattr(FlowOrchestratorProtocol, "get_pipeline_status")

    def test_protocol_has_get_motion_status_method(self) -> None:
        """Verify protocol defines get_motion_status method."""
        assert hasattr(FlowOrchestratorProtocol, "get_motion_status")

    def test_protocol_has_get_blocked_motions_method(self) -> None:
        """Verify protocol defines get_blocked_motions method."""
        assert hasattr(FlowOrchestratorProtocol, "get_blocked_motions")

    def test_protocol_has_escalate_error_method(self) -> None:
        """Verify protocol defines escalate_error method."""
        assert hasattr(FlowOrchestratorProtocol, "escalate_error")

    def test_protocol_has_resolve_escalation_method(self) -> None:
        """Verify protocol defines resolve_escalation method."""
        assert hasattr(FlowOrchestratorProtocol, "resolve_escalation")

    def test_protocol_has_retry_motion_method(self) -> None:
        """Verify protocol defines retry_motion method."""
        assert hasattr(FlowOrchestratorProtocol, "retry_motion")

    def test_protocol_is_abstract(self) -> None:
        """Verify protocol cannot be instantiated directly."""
        with pytest.raises(TypeError):
            FlowOrchestratorProtocol()  # type: ignore[abstract]
