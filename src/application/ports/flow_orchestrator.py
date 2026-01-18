"""Flow Orchestrator Port (Epic 8, Story 8.2).

This module defines the protocol and domain models for the Flow Orchestrator
that coordinates all branch services through the 7-step canonical governance flow.

Per Government PRD FR-GOV-23: Governance Flow - 7 canonical steps:
King→Conclave→President→Duke/Earl→Prince→Knight→Conclave.
No step may be skipped, no role may be collapsed.

Per CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
Per CT-12: Witnessing creates accountability → All transitions witnessed

HARDENING-1: All timestamps must be provided via TimeAuthorityProtocol injection.
Factory methods require explicit timestamp parameters - no datetime.now() calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.governance_state_machine import GovernanceState

# =============================================================================
# Enums
# =============================================================================


class GovernanceBranch(Enum):
    """Branches of the governance system.

    Per Government PRD: Each branch has specific responsibilities
    in the 7-step canonical flow.
    """

    LEGISLATIVE = "legislative"  # King introduces motions
    DELIBERATIVE = "deliberative"  # Conclave deliberates
    EXECUTIVE = "executive"  # President plans execution
    ADMINISTRATIVE = "administrative"  # Duke/Earl execute
    JUDICIAL = "judicial"  # Prince judges compliance
    WITNESS = "witness"  # Knight witnesses
    ADVISORY = "advisory"  # Marquis advises (non-blocking)


class ErrorEscalationStrategy(Enum):
    """Strategies for handling branch service errors.

    Per NFR-GOV-7: Halt over degrade - Silent failure destroys legitimacy.
    """

    RETURN_TO_PREVIOUS = "return_to_previous"  # Validation errors
    CONCLAVE_REVIEW = "conclave_review"  # Permission/compliance errors
    HALT_AND_ALERT = "halt_and_alert"  # System errors
    RETRY_WITH_BACKOFF = "retry_with_backoff"  # Transient errors


class MotionBlockReason(Enum):
    """Reasons why a motion may be blocked in the pipeline."""

    AWAITING_DELIBERATION = "awaiting_deliberation"
    AWAITING_RESOURCES = "awaiting_resources"
    AWAITING_EXECUTION = "awaiting_execution"
    AWAITING_JUDGMENT = "awaiting_judgment"
    ERROR_ESCALATION = "error_escalation"
    CONCLAVE_REVIEW = "conclave_review"
    SYSTEM_HALT = "system_halt"
    TIMEOUT = "timeout"


# =============================================================================
# Routing Configuration
# =============================================================================


STATE_SERVICE_MAP: dict[GovernanceState, str] = {
    GovernanceState.INTRODUCED: "conclave_service",  # For deliberation
    GovernanceState.DELIBERATING: "conclave_service",  # Continue deliberation
    GovernanceState.RATIFIED: "president_service",  # For planning
    GovernanceState.PLANNING: "duke_service",  # For execution
    GovernanceState.EXECUTING: "prince_service",  # For compliance check
    GovernanceState.JUDGING: "knight_witness_service",  # For witnessing
    GovernanceState.WITNESSING: "conclave_service",  # For acknowledgment
}
"""Maps governance states to responsible service names."""


STATE_BRANCH_MAP: dict[GovernanceState, GovernanceBranch] = {
    GovernanceState.INTRODUCED: GovernanceBranch.DELIBERATIVE,
    GovernanceState.DELIBERATING: GovernanceBranch.DELIBERATIVE,
    GovernanceState.RATIFIED: GovernanceBranch.EXECUTIVE,
    GovernanceState.PLANNING: GovernanceBranch.ADMINISTRATIVE,
    GovernanceState.EXECUTING: GovernanceBranch.JUDICIAL,
    GovernanceState.JUDGING: GovernanceBranch.WITNESS,
    GovernanceState.WITNESSING: GovernanceBranch.DELIBERATIVE,
}
"""Maps governance states to responsible branch."""


ERROR_TYPE_MAP: dict[str, ErrorEscalationStrategy] = {
    "validation_error": ErrorEscalationStrategy.RETURN_TO_PREVIOUS,
    "permission_error": ErrorEscalationStrategy.CONCLAVE_REVIEW,
    "compliance_error": ErrorEscalationStrategy.CONCLAVE_REVIEW,
    "rank_violation": ErrorEscalationStrategy.CONCLAVE_REVIEW,
    "system_error": ErrorEscalationStrategy.HALT_AND_ALERT,
    "timeout_error": ErrorEscalationStrategy.RETRY_WITH_BACKOFF,
    "transient_error": ErrorEscalationStrategy.RETRY_WITH_BACKOFF,
}
"""Maps error types to escalation strategies."""


# =============================================================================
# Domain Models
# =============================================================================


@dataclass(frozen=True)
class BranchResult:
    """Result from a branch service completing work.

    Attributes:
        result_id: Unique identifier for this result
        motion_id: UUID of the motion being processed
        branch: Which governance branch processed this
        success: Whether the branch work succeeded
        output: Output data from the branch service
        next_state: Suggested next state (if success)
        error: Error message if failed
        error_type: Type of error for escalation routing
        completed_at: When the branch work completed
    """

    result_id: UUID
    motion_id: UUID
    branch: GovernanceBranch
    success: bool
    output: dict[str, Any]
    next_state: GovernanceState | None
    completed_at: datetime
    error: str | None = None
    error_type: str | None = None

    @classmethod
    def create(
        cls,
        motion_id: UUID,
        branch: GovernanceBranch,
        success: bool,
        output: dict[str, Any],
        timestamp: datetime,
        next_state: GovernanceState | None = None,
        error: str | None = None,
        error_type: str | None = None,
    ) -> "BranchResult":
        """Create a new BranchResult.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            motion_id: Motion UUID
            branch: Governance branch
            success: Whether successful
            output: Output data
            timestamp: Current time from TimeAuthorityProtocol
            next_state: Suggested next state
            error: Error message
            error_type: Error classification

        Returns:
            New BranchResult instance
        """
        return cls(
            result_id=uuid4(),
            motion_id=motion_id,
            branch=branch,
            success=success,
            output=output,
            next_state=next_state,
            completed_at=timestamp,
            error=error,
            error_type=error_type,
        )


@dataclass(frozen=True)
class MotionPipelineState:
    """Pipeline state for a single motion.

    Tracks the current position and status of a motion
    as it flows through the governance pipeline.

    Attributes:
        motion_id: UUID of the motion
        current_state: Current governance state
        entered_state_at: When it entered this state
        expected_completion: Expected completion time
        blocking_issues: List of blocking issues
        next_action: Description of next expected action
        retry_count: Number of retries attempted
        last_error: Most recent error if any
    """

    motion_id: UUID
    current_state: GovernanceState
    entered_state_at: datetime
    expected_completion: datetime | None
    blocking_issues: tuple[str, ...]
    next_action: str
    retry_count: int = 0
    last_error: str | None = None

    @classmethod
    def create(
        cls,
        motion_id: UUID,
        current_state: GovernanceState,
        next_action: str,
        timestamp: datetime,
        expected_completion: datetime | None = None,
        blocking_issues: tuple[str, ...] | None = None,
    ) -> "MotionPipelineState":
        """Create a new MotionPipelineState.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            motion_id: Motion UUID
            current_state: Current state
            next_action: Next expected action
            timestamp: Current time from TimeAuthorityProtocol
            expected_completion: Expected completion time
            blocking_issues: Any blocking issues

        Returns:
            New MotionPipelineState instance
        """
        return cls(
            motion_id=motion_id,
            current_state=current_state,
            entered_state_at=timestamp,
            expected_completion=expected_completion,
            blocking_issues=blocking_issues or (),
            next_action=next_action,
        )

    @property
    def is_blocked(self) -> bool:
        """Check if motion is blocked."""
        return len(self.blocking_issues) > 0

    def time_in_state(self, current_time: datetime) -> timedelta:
        """Get time spent in current state.

        HARDENING-1: current_time must be provided via TimeAuthorityProtocol.

        Args:
            current_time: Current time from time_authority.now()

        Returns:
            Time spent in current state
        """
        return current_time - self.entered_state_at


@dataclass(frozen=True)
class PipelineStatus:
    """Current status of the governance pipeline.

    Provides aggregate statistics about all motions
    currently flowing through the pipeline.

    Attributes:
        active_motions: Total active motions
        motions_by_state: Count of motions per state
        blocked_motions: UUIDs of blocked motions
        oldest_motion_age: Age of oldest active motion
        recent_completions: Completions in last 24h
        recent_failures: Failures in last 24h
        total_processed: Total motions ever processed
        queried_at: When this status was generated
    """

    active_motions: int
    motions_by_state: dict[GovernanceState, int]
    blocked_motions: tuple[UUID, ...]
    oldest_motion_age: timedelta
    recent_completions: int
    recent_failures: int
    queried_at: datetime
    total_processed: int = 0

    @classmethod
    def create(
        cls,
        active_motions: int,
        motions_by_state: dict[GovernanceState, int],
        blocked_motions: tuple[UUID, ...],
        oldest_motion_age: timedelta,
        recent_completions: int,
        recent_failures: int,
        timestamp: datetime,
        total_processed: int = 0,
    ) -> "PipelineStatus":
        """Create a new PipelineStatus.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            active_motions: Active motion count
            motions_by_state: Counts by state
            blocked_motions: Blocked motion IDs
            oldest_motion_age: Oldest motion age
            recent_completions: Recent completion count
            recent_failures: Recent failure count
            timestamp: Current time from TimeAuthorityProtocol
            total_processed: Total processed count

        Returns:
            New PipelineStatus instance
        """
        return cls(
            active_motions=active_motions,
            motions_by_state=motions_by_state,
            blocked_motions=blocked_motions,
            oldest_motion_age=oldest_motion_age,
            recent_completions=recent_completions,
            recent_failures=recent_failures,
            queried_at=timestamp,
            total_processed=total_processed,
        )


@dataclass(frozen=True)
class RoutingDecision:
    """Decision about where to route a motion.

    Attributes:
        decision_id: Unique identifier for this decision
        motion_id: Motion being routed
        from_state: State motion is leaving
        target_service: Service to route to
        target_branch: Branch responsible
        reason: Reason for routing decision
        decided_at: When decision was made
    """

    decision_id: UUID
    motion_id: UUID
    from_state: GovernanceState
    target_service: str
    target_branch: GovernanceBranch
    reason: str
    decided_at: datetime

    @classmethod
    def create(
        cls,
        motion_id: UUID,
        from_state: GovernanceState,
        target_service: str,
        target_branch: GovernanceBranch,
        reason: str,
        timestamp: datetime,
    ) -> "RoutingDecision":
        """Create a new RoutingDecision.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            motion_id: Motion UUID
            from_state: Current state
            target_service: Target service name
            target_branch: Target branch
            reason: Routing reason
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New RoutingDecision instance
        """
        return cls(
            decision_id=uuid4(),
            motion_id=motion_id,
            from_state=from_state,
            target_service=target_service,
            target_branch=target_branch,
            reason=reason,
            decided_at=timestamp,
        )


@dataclass(frozen=True)
class EscalationRecord:
    """Record of an error escalation.

    Per NFR-GOV-7: Halt over degrade - errors must be escalated
    appropriately, never silently ignored.

    Attributes:
        escalation_id: Unique identifier
        motion_id: Motion that encountered error
        error_type: Classification of error
        strategy: Escalation strategy applied
        original_error: Original error message
        action_taken: Action taken in response
        escalated_at: When escalation occurred
        resolved: Whether escalation is resolved
        resolved_at: When resolved (if applicable)
    """

    escalation_id: UUID
    motion_id: UUID
    error_type: str
    strategy: ErrorEscalationStrategy
    original_error: str
    action_taken: str
    escalated_at: datetime
    resolved: bool = False
    resolved_at: datetime | None = None

    @classmethod
    def create(
        cls,
        motion_id: UUID,
        error_type: str,
        strategy: ErrorEscalationStrategy,
        original_error: str,
        action_taken: str,
        timestamp: datetime,
    ) -> "EscalationRecord":
        """Create a new EscalationRecord.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            motion_id: Motion UUID
            error_type: Error classification
            strategy: Escalation strategy
            original_error: Original error
            action_taken: Action taken
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New EscalationRecord instance
        """
        return cls(
            escalation_id=uuid4(),
            motion_id=motion_id,
            error_type=error_type,
            strategy=strategy,
            original_error=original_error,
            action_taken=action_taken,
            escalated_at=timestamp,
        )


# =============================================================================
# Request/Response Models
# =============================================================================


@dataclass(frozen=True)
class ProcessMotionRequest:
    """Request to process a motion through the pipeline.

    Attributes:
        motion_id: UUID of the motion to process
        triggered_by: Archon ID triggering the process
        force: Force processing even if blocked
    """

    motion_id: UUID
    triggered_by: str
    force: bool = False


@dataclass(frozen=True)
class ProcessMotionResult:
    """Result of processing a motion.

    Attributes:
        success: Whether processing succeeded
        routing_decision: Where motion was routed
        new_state: New state after processing
        error: Error if failed
        escalation: Escalation record if error occurred
    """

    success: bool
    routing_decision: RoutingDecision | None = None
    new_state: GovernanceState | None = None
    error: str | None = None
    escalation: EscalationRecord | None = None


@dataclass(frozen=True)
class RouteMotionRequest:
    """Request to route a motion to a specific service.

    Attributes:
        motion_id: Motion to route
        target_state: Target state determining service
        triggered_by: Archon ID triggering routing
    """

    motion_id: UUID
    target_state: GovernanceState
    triggered_by: str


@dataclass(frozen=True)
class RouteMotionResult:
    """Result of routing a motion.

    Attributes:
        success: Whether routing succeeded
        decision: Routing decision made
        error: Error if failed
    """

    success: bool
    decision: RoutingDecision | None = None
    error: str | None = None


@dataclass(frozen=True)
class HandleCompletionRequest:
    """Request to handle branch completion.

    Attributes:
        motion_id: Motion that completed branch work
        branch_result: Result from branch service
        triggered_by: Archon ID handling completion
    """

    motion_id: UUID
    branch_result: BranchResult
    triggered_by: str


@dataclass(frozen=True)
class HandleCompletionResult:
    """Result of handling branch completion.

    Attributes:
        success: Whether handling succeeded
        transition_triggered: Whether state transition occurred
        new_state: New state after transition
        next_routing: Next routing decision if applicable
        error: Error if failed
        escalation: Escalation record if error occurred
    """

    success: bool
    transition_triggered: bool = False
    new_state: GovernanceState | None = None
    next_routing: RoutingDecision | None = None
    error: str | None = None
    escalation: EscalationRecord | None = None


# =============================================================================
# Protocol Definition
# =============================================================================


class FlowOrchestratorProtocol(ABC):
    """Protocol for the Flow Orchestrator service.

    The Flow Orchestrator coordinates all branch services through
    the 7-step canonical governance flow.

    Per FR-GOV-23: The orchestrator ensures:
    - Motions are routed to correct branch based on state
    - State transitions are triggered on completion
    - All transitions are witnessed
    - Errors are escalated appropriately
    - Pipeline status is visible

    Per CT-11: Silent failure destroys legitimacy - errors must
    be escalated, never silently ignored.

    Per CT-12: Witnessing creates accountability - all transitions
    must be witnessed by Knight.
    """

    @abstractmethod
    async def process_motion(
        self,
        request: ProcessMotionRequest,
    ) -> ProcessMotionResult:
        """Process a motion through the pipeline.

        Determines current state and routes to appropriate
        branch service for processing.

        Args:
            request: Process motion request

        Returns:
            ProcessMotionResult with routing decision

        Note:
            Per FR-GOV-23: Routes based on canonical flow.
        """
        ...

    @abstractmethod
    async def route_to_branch(
        self,
        request: RouteMotionRequest,
    ) -> RouteMotionResult:
        """Route a motion to a specific branch service.

        Args:
            request: Route motion request

        Returns:
            RouteMotionResult with decision

        Note:
            Per FR-GOV-23: Determines service from state.
        """
        ...

    @abstractmethod
    async def handle_completion(
        self,
        request: HandleCompletionRequest,
    ) -> HandleCompletionResult:
        """Handle completion of branch service work.

        Processes the branch result, triggers state transition
        if successful, and routes to next service.

        Args:
            request: Handle completion request

        Returns:
            HandleCompletionResult with transition details

        Note:
            Per CT-12: Transition is witnessed.
            Per CT-11: Errors are escalated.
        """
        ...

    @abstractmethod
    async def get_pipeline_status(self) -> PipelineStatus:
        """Get current pipeline status.

        Returns aggregate statistics about all motions
        in the pipeline.

        Returns:
            PipelineStatus with aggregate stats
        """
        ...

    @abstractmethod
    async def get_motion_status(
        self,
        motion_id: UUID,
    ) -> MotionPipelineState | None:
        """Get status of a specific motion.

        Args:
            motion_id: UUID of motion to check

        Returns:
            MotionPipelineState if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_blocked_motions(self) -> list[MotionPipelineState]:
        """Get all blocked motions.

        Returns:
            List of blocked motion states
        """
        ...

    @abstractmethod
    async def escalate_error(
        self,
        motion_id: UUID,
        error_type: str,
        error_message: str,
        triggered_by: str,
    ) -> EscalationRecord:
        """Escalate an error per the escalation strategy.

        Per NFR-GOV-7: Halt over degrade - errors must be
        escalated appropriately.

        Args:
            motion_id: Motion with error
            error_type: Classification of error
            error_message: Error message
            triggered_by: Archon ID reporting error

        Returns:
            EscalationRecord documenting the escalation
        """
        ...

    @abstractmethod
    async def resolve_escalation(
        self,
        escalation_id: UUID,
        resolved_by: str,
        resolution_notes: str,
    ) -> bool:
        """Resolve an escalation.

        Args:
            escalation_id: Escalation to resolve
            resolved_by: Archon ID resolving
            resolution_notes: Notes on resolution

        Returns:
            True if resolved successfully
        """
        ...

    @abstractmethod
    async def retry_motion(
        self,
        motion_id: UUID,
        triggered_by: str,
    ) -> ProcessMotionResult:
        """Retry processing a motion.

        Used after transient errors or manual intervention.

        Args:
            motion_id: Motion to retry
            triggered_by: Archon ID triggering retry

        Returns:
            ProcessMotionResult from retry attempt
        """
        ...


# =============================================================================
# Helper Functions
# =============================================================================


def get_service_for_state(state: GovernanceState) -> str | None:
    """Get the service name for a governance state.

    Args:
        state: Governance state

    Returns:
        Service name, or None if no service for state
    """
    return STATE_SERVICE_MAP.get(state)


def get_branch_for_state(state: GovernanceState) -> GovernanceBranch | None:
    """Get the branch for a governance state.

    Args:
        state: Governance state

    Returns:
        Governance branch, or None if no branch for state
    """
    return STATE_BRANCH_MAP.get(state)


def get_escalation_strategy(error_type: str) -> ErrorEscalationStrategy:
    """Get the escalation strategy for an error type.

    Args:
        error_type: Error classification

    Returns:
        Escalation strategy (defaults to HALT_AND_ALERT)
    """
    return ERROR_TYPE_MAP.get(error_type, ErrorEscalationStrategy.HALT_AND_ALERT)


def is_retryable_error(error_type: str) -> bool:
    """Check if an error type is retryable.

    Args:
        error_type: Error classification

    Returns:
        True if error is retryable
    """
    strategy = get_escalation_strategy(error_type)
    return strategy == ErrorEscalationStrategy.RETRY_WITH_BACKOFF


def is_blocking_error(error_type: str) -> bool:
    """Check if an error type blocks the pipeline.

    Args:
        error_type: Error classification

    Returns:
        True if error blocks pipeline
    """
    strategy = get_escalation_strategy(error_type)
    return strategy in {
        ErrorEscalationStrategy.HALT_AND_ALERT,
        ErrorEscalationStrategy.CONCLAVE_REVIEW,
    }
