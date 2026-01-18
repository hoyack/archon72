"""Flow Orchestrator Service (Epic 8, Story 8.2, FR-GOV-23).

This service coordinates all branch services through the 7-step
canonical governance flow.

Per Government PRD FR-GOV-23: Governance Flow - 7 canonical steps:
King→Conclave→President→Duke/Earl→Prince→Knight→Conclave.
No step may be skipped, no role may be collapsed.

Per CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
Per CT-12: Witnessing creates accountability → All transitions witnessed
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from structlog import get_logger

from src.application.ports.flow_orchestrator import (
    ErrorEscalationStrategy,
    EscalationRecord,
    FlowOrchestratorProtocol,
    GovernanceBranch,
    HandleCompletionRequest,
    HandleCompletionResult,
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
)
from src.application.ports.governance_state_machine import (
    GovernanceState,
    GovernanceStateMachineProtocol,
    TransitionRequest,
    is_terminal_state,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
)
from src.application.services.base import LoggingMixin
from src.application.services.role_collapse_detection_service import (
    RoleCollapseDetectionService,
    RoleCollapseError,
    RoleCollapseViolation,
)

logger = get_logger(__name__)


class FlowOrchestratorService(FlowOrchestratorProtocol, LoggingMixin):
    """Implementation of the Flow Orchestrator service.

    This service coordinates all governance branch services through
    the 7-step canonical flow, enforcing FR-GOV-23 requirements.

    Architecture:
    - Uses GovernanceStateMachineProtocol for state management
    - Uses KnightWitnessProtocol for witnessing all transitions
    - Maintains in-memory pipeline state (production would use repository)

    Per CT-11: Errors are escalated, never silently ignored.
    Per CT-12: All transitions are witnessed by Knight.
    """

    def __init__(
        self,
        state_machine: GovernanceStateMachineProtocol,
        knight_witness: KnightWitnessProtocol | None = None,
        role_collapse_detector: RoleCollapseDetectionService | None = None,
        verbose: bool = False,
        max_retry_attempts: int = 3,
        retry_backoff_seconds: tuple[int, ...] = (5, 30, 300),
    ) -> None:
        """Initialize the Flow Orchestrator service.

        Args:
            state_machine: Governance state machine for state management
            knight_witness: Knight witness for recording transitions (optional)
            role_collapse_detector: Role collapse detection service (optional, per Story 8.4)
            verbose: Enable verbose logging
            max_retry_attempts: Maximum retry attempts for transient errors
            retry_backoff_seconds: Backoff intervals for retries
        """
        self._state_machine = state_machine
        self._knight_witness = knight_witness
        self._role_collapse_detector = role_collapse_detector
        self._verbose = verbose
        self._max_retry_attempts = max_retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

        self._init_logger(component="governance")

        # In-memory pipeline state (would be repository in production)
        self._motion_states: dict[UUID, MotionPipelineState] = {}
        self._escalations: dict[UUID, EscalationRecord] = {}
        self._routing_history: dict[UUID, list[RoutingDecision]] = {}

        # Statistics
        self._total_processed: int = 0
        self._completions_24h: list[datetime] = []
        self._failures_24h: list[datetime] = []

        if self._verbose:
            self._log.info("flow_orchestrator_initialized")

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
        log = self._log_operation(
            "process_motion",
            motion_id=str(request.motion_id),
            triggered_by=request.triggered_by,
        )
        log.debug("processing_motion")

        # Get current state from state machine
        current_state = await self._state_machine.get_current_state(request.motion_id)
        if current_state is None:
            log.warning("motion_not_found")
            return ProcessMotionResult(
                success=False,
                error=f"Motion {request.motion_id} not found in state machine",
            )

        # Check if motion is in terminal state
        if is_terminal_state(current_state):
            log.info(
                "motion_in_terminal_state",
                current_state=current_state.value,
            )
            return ProcessMotionResult(
                success=False,
                error=f"Motion is in terminal state {current_state.value}",
            )

        # Check if motion is blocked (unless forced)
        pipeline_state = self._motion_states.get(request.motion_id)
        if pipeline_state and pipeline_state.is_blocked and not request.force:
            log.warning(
                "motion_blocked",
                blocking_issues=pipeline_state.blocking_issues,
            )
            return ProcessMotionResult(
                success=False,
                error=f"Motion is blocked: {', '.join(pipeline_state.blocking_issues)}",
            )

        # Route to appropriate branch
        route_request = RouteMotionRequest(
            motion_id=request.motion_id,
            target_state=current_state,
            triggered_by=request.triggered_by,
        )

        route_result = await self.route_to_branch(route_request)
        if not route_result.success:
            return ProcessMotionResult(
                success=False,
                error=route_result.error,
            )

        # Update pipeline state, preserving retry_count if exists
        service_name = get_service_for_state(current_state) or "unknown"
        existing_state = self._motion_states.get(request.motion_id)
        retry_count = existing_state.retry_count if existing_state else 0

        self._motion_states[request.motion_id] = MotionPipelineState(
            motion_id=request.motion_id,
            current_state=current_state,
            entered_state_at=datetime.now(timezone.utc),
            expected_completion=None,
            blocking_issues=(),
            next_action=f"Processing by {service_name}",
            retry_count=retry_count,
            last_error=existing_state.last_error if existing_state else None,
        )

        self._total_processed += 1

        log.info(
            "motion_processed",
            current_state=current_state.value,
            routed_to=route_result.decision.target_service
            if route_result.decision
            else None,
        )

        return ProcessMotionResult(
            success=True,
            routing_decision=route_result.decision,
            new_state=current_state,
        )

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
            Per Story 8.4: Pre-routing role collapse check.
        """
        log = self._log_operation(
            "route_to_branch",
            motion_id=str(request.motion_id),
            target_state=request.target_state.value,
        )
        log.debug("routing_motion")

        # Get service for state
        target_service = get_service_for_state(request.target_state)
        if target_service is None:
            log.warning("no_service_for_state")
            return RouteMotionResult(
                success=False,
                error=f"No service mapped for state {request.target_state.value}",
            )

        # Get branch for state
        target_branch = get_branch_for_state(request.target_state)
        if target_branch is None:
            target_branch = GovernanceBranch.DELIBERATIVE  # Default

        # Per Story 8.4 AC2/AC5: Pre-routing role collapse check
        if self._role_collapse_detector:
            try:
                collapse_result = await self._check_role_collapse(
                    archon_id=request.triggered_by,
                    motion_id=request.motion_id,
                    proposed_branch=target_branch,
                )
                if collapse_result:
                    # Role collapse detected - reject routing
                    log.warning(
                        "role_collapse_detected",
                        archon_id=request.triggered_by,
                        proposed_branch=target_branch.value,
                        rule=collapse_result.conflict_rule,
                    )
                    # Witness the violation
                    await self._witness_role_collapse(
                        collapse_result, request.triggered_by
                    )
                    return RouteMotionResult(
                        success=False,
                        error=f"Role collapse violation: {collapse_result.conflict_rule}",
                    )
            except RoleCollapseError as e:
                log.error(
                    "role_collapse_error",
                    archon_id=request.triggered_by,
                    error=str(e),
                )
                await self._witness_role_collapse(e.violation, request.triggered_by)
                return RouteMotionResult(
                    success=False,
                    error=str(e),
                )

        # Create routing decision
        decision = RoutingDecision.create(
            motion_id=request.motion_id,
            from_state=request.target_state,
            target_service=target_service,
            target_branch=target_branch,
            reason=f"Routing from state {request.target_state.value} per FR-GOV-23",
            timestamp=datetime.now(timezone.utc),
        )

        # Record routing history
        if request.motion_id not in self._routing_history:
            self._routing_history[request.motion_id] = []
        self._routing_history[request.motion_id].append(decision)

        # Witness the routing
        await self._witness_routing(decision, request.triggered_by)

        log.info(
            "motion_routed",
            target_service=target_service,
            target_branch=target_branch.value,
        )

        return RouteMotionResult(
            success=True,
            decision=decision,
        )

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
        log = self._log_operation(
            "handle_completion",
            motion_id=str(request.motion_id),
            branch=request.branch_result.branch.value,
            success=request.branch_result.success,
        )
        log.debug("handling_completion")

        branch_result = request.branch_result

        # Handle failure
        if not branch_result.success:
            log.warning(
                "branch_failure",
                error=branch_result.error,
                error_type=branch_result.error_type,
            )

            # Track failure
            self._failures_24h.append(datetime.now(timezone.utc))
            self._prune_24h_stats()

            # Escalate error
            escalation = await self.escalate_error(
                motion_id=request.motion_id,
                error_type=branch_result.error_type or "unknown_error",
                error_message=branch_result.error or "Unknown error",
                triggered_by=request.triggered_by,
            )

            # Update pipeline state with blocking issue
            current_state = await self._state_machine.get_current_state(
                request.motion_id
            )
            self._motion_states[request.motion_id] = MotionPipelineState.create(
                motion_id=request.motion_id,
                current_state=current_state or GovernanceState.INTRODUCED,
                next_action="Awaiting escalation resolution",
                blocking_issues=(branch_result.error or "Branch failure",),
                timestamp=datetime.now(timezone.utc),
            )

            return HandleCompletionResult(
                success=False,
                error=branch_result.error,
                escalation=escalation,
            )

        # Handle success - trigger state transition
        if branch_result.next_state is None:
            log.warning("no_next_state_specified")
            return HandleCompletionResult(
                success=True,
                transition_triggered=False,
                error="Branch succeeded but no next state specified",
            )

        # Request state transition
        transition_request = TransitionRequest(
            motion_id=request.motion_id,
            to_state=branch_result.next_state,
            triggered_by=request.triggered_by,
            reason=f"Branch {branch_result.branch.value} completed successfully",
        )

        transition_result = await self._state_machine.transition(transition_request)

        if not transition_result.success:
            log.error(
                "transition_failed",
                error=transition_result.error,
            )
            return HandleCompletionResult(
                success=False,
                error=f"State transition failed: {transition_result.error}",
            )

        # Track completion
        self._completions_24h.append(datetime.now(timezone.utc))
        self._prune_24h_stats()

        # Update pipeline state
        self._motion_states[request.motion_id] = MotionPipelineState.create(
            motion_id=request.motion_id,
            current_state=branch_result.next_state,
            next_action=f"Transitioned to {branch_result.next_state.value}",
            timestamp=datetime.now(timezone.utc),
        )

        # Route to next branch if not terminal
        next_routing: RoutingDecision | None = None
        if not is_terminal_state(branch_result.next_state):
            route_result = await self.route_to_branch(
                RouteMotionRequest(
                    motion_id=request.motion_id,
                    target_state=branch_result.next_state,
                    triggered_by=request.triggered_by,
                )
            )
            if route_result.success:
                next_routing = route_result.decision

        log.info(
            "completion_handled",
            new_state=branch_result.next_state.value,
            transition_triggered=True,
        )

        return HandleCompletionResult(
            success=True,
            transition_triggered=True,
            new_state=branch_result.next_state,
            next_routing=next_routing,
        )

    async def get_pipeline_status(self) -> PipelineStatus:
        """Get current pipeline status.

        Returns aggregate statistics about all motions
        in the pipeline.

        Returns:
            PipelineStatus with aggregate stats
        """
        self._prune_24h_stats()

        # Count motions by state
        motions_by_state: dict[GovernanceState, int] = {}
        blocked_motions: list[UUID] = []
        oldest_motion_age = timedelta(0)

        for motion_id, state in self._motion_states.items():
            current_state = state.current_state
            motions_by_state[current_state] = motions_by_state.get(current_state, 0) + 1

            if state.is_blocked:
                blocked_motions.append(motion_id)

            now = datetime.now(timezone.utc)
            time_in_state = state.time_in_state(now)
            if time_in_state > oldest_motion_age:
                oldest_motion_age = time_in_state

        return PipelineStatus.create(
            active_motions=len(self._motion_states),
            motions_by_state=motions_by_state,
            blocked_motions=tuple(blocked_motions),
            oldest_motion_age=oldest_motion_age,
            recent_completions=len(self._completions_24h),
            recent_failures=len(self._failures_24h),
            total_processed=self._total_processed,
            timestamp=datetime.now(timezone.utc),
        )

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
        return self._motion_states.get(motion_id)

    async def get_blocked_motions(self) -> list[MotionPipelineState]:
        """Get all blocked motions.

        Returns:
            List of blocked motion states
        """
        return [state for state in self._motion_states.values() if state.is_blocked]

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
        log = self._log_operation(
            "escalate_error",
            motion_id=str(motion_id),
            error_type=error_type,
        )

        # Determine escalation strategy
        strategy = get_escalation_strategy(error_type)

        # Determine action based on strategy
        action_taken = self._determine_escalation_action(strategy, motion_id)

        # Create escalation record
        escalation = EscalationRecord.create(
            motion_id=motion_id,
            error_type=error_type,
            strategy=strategy,
            original_error=error_message,
            action_taken=action_taken,
            timestamp=datetime.now(timezone.utc),
        )

        self._escalations[escalation.escalation_id] = escalation

        # Witness the escalation
        await self._witness_escalation(escalation, triggered_by)

        # Update pipeline state if blocking
        if is_blocking_error(error_type):
            current_state = await self._state_machine.get_current_state(motion_id)
            blocking_reason = f"Escalation: {strategy.value}"
            self._motion_states[motion_id] = MotionPipelineState.create(
                motion_id=motion_id,
                current_state=current_state or GovernanceState.INTRODUCED,
                next_action="Awaiting escalation resolution",
                blocking_issues=(blocking_reason,),
                timestamp=datetime.now(timezone.utc),
            )

        log.warning(
            "error_escalated",
            strategy=strategy.value,
            action_taken=action_taken,
        )

        return escalation

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
        log = self._log_operation(
            "resolve_escalation",
            escalation_id=str(escalation_id),
            resolved_by=resolved_by,
        )

        escalation = self._escalations.get(escalation_id)
        if escalation is None:
            log.warning("escalation_not_found")
            return False

        # Mark as resolved (create new record since frozen)
        resolved_escalation = EscalationRecord(
            escalation_id=escalation.escalation_id,
            motion_id=escalation.motion_id,
            error_type=escalation.error_type,
            strategy=escalation.strategy,
            original_error=escalation.original_error,
            action_taken=escalation.action_taken,
            escalated_at=escalation.escalated_at,
            resolved=True,
            resolved_at=datetime.now(timezone.utc),
        )

        self._escalations[escalation_id] = resolved_escalation

        # Clear blocking issues from motion
        motion_state = self._motion_states.get(escalation.motion_id)
        if motion_state:
            current_state = motion_state.current_state
            self._motion_states[escalation.motion_id] = MotionPipelineState.create(
                motion_id=escalation.motion_id,
                current_state=current_state,
                next_action=f"Escalation resolved: {resolution_notes}",
                blocking_issues=(),  # Clear blocking
                timestamp=datetime.now(timezone.utc),
            )

        # Witness resolution
        await self._witness_escalation_resolution(
            resolved_escalation, resolved_by, resolution_notes
        )

        log.info(
            "escalation_resolved",
            resolution_notes=resolution_notes,
        )

        return True

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
        log = self._log_operation(
            "retry_motion",
            motion_id=str(motion_id),
            triggered_by=triggered_by,
        )

        # Get current pipeline state
        pipeline_state = self._motion_states.get(motion_id)
        if pipeline_state is None:
            log.warning("motion_not_in_pipeline")
            return ProcessMotionResult(
                success=False,
                error=f"Motion {motion_id} not found in pipeline",
            )

        # Check retry count
        if pipeline_state.retry_count >= self._max_retry_attempts:
            log.error(
                "max_retries_exceeded",
                retry_count=pipeline_state.retry_count,
            )
            return ProcessMotionResult(
                success=False,
                error=f"Maximum retry attempts ({self._max_retry_attempts}) exceeded",
            )

        # Update retry count
        new_state = MotionPipelineState(
            motion_id=motion_id,
            current_state=pipeline_state.current_state,
            entered_state_at=pipeline_state.entered_state_at,
            expected_completion=pipeline_state.expected_completion,
            blocking_issues=(),  # Clear blocking for retry
            next_action=f"Retry attempt {pipeline_state.retry_count + 1}",
            retry_count=pipeline_state.retry_count + 1,
            last_error=pipeline_state.last_error,
        )
        self._motion_states[motion_id] = new_state

        # Process motion with force flag
        request = ProcessMotionRequest(
            motion_id=motion_id,
            triggered_by=triggered_by,
            force=True,
        )

        log.info(
            "motion_retry_initiated",
            retry_count=new_state.retry_count,
        )

        return await self.process_motion(request)

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _determine_escalation_action(
        self,
        strategy: ErrorEscalationStrategy,
        motion_id: UUID,
    ) -> str:
        """Determine action to take based on escalation strategy.

        Args:
            strategy: Escalation strategy
            motion_id: Motion being escalated

        Returns:
            Description of action taken
        """
        if strategy == ErrorEscalationStrategy.RETURN_TO_PREVIOUS:
            return f"Motion {motion_id} returned to previous step for correction"
        elif strategy == ErrorEscalationStrategy.CONCLAVE_REVIEW:
            return f"Motion {motion_id} referred to Conclave for review"
        elif strategy == ErrorEscalationStrategy.HALT_AND_ALERT:
            return f"Pipeline HALTED for motion {motion_id} - system error requires intervention"
        elif strategy == ErrorEscalationStrategy.RETRY_WITH_BACKOFF:
            return f"Motion {motion_id} scheduled for retry with exponential backoff"
        else:
            return f"Motion {motion_id} escalated with unknown strategy"

    def _prune_24h_stats(self) -> None:
        """Prune statistics older than 24 hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        self._completions_24h = [t for t in self._completions_24h if t > cutoff]
        self._failures_24h = [t for t in self._failures_24h if t > cutoff]

    async def _witness_routing(
        self,
        decision: RoutingDecision,
        triggered_by: str,
    ) -> None:
        """Witness a routing decision through Knight.

        Args:
            decision: Routing decision made
            triggered_by: Archon ID who triggered routing
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            event_type="motion_routed",
            event_id=decision.decision_id,
            description=f"Motion {decision.motion_id} routed to {decision.target_service}",
            participants=[triggered_by],
            target_id=str(decision.motion_id),
            target_type="motion",
            metadata={
                "from_state": decision.from_state.value,
                "target_service": decision.target_service,
                "target_branch": decision.target_branch.value,
            },
        )

        self._knight_witness.observe(context)

    async def _witness_escalation(
        self,
        escalation: EscalationRecord,
        triggered_by: str,
    ) -> None:
        """Witness an error escalation through Knight.

        Per CT-11: Silent failure destroys legitimacy.

        Args:
            escalation: Escalation record
            triggered_by: Archon ID who reported error
        """
        if not self._knight_witness:
            if self._verbose:
                self._log.warning(
                    "escalation_not_witnessed_no_knight",
                    escalation_id=str(escalation.escalation_id),
                )
            return

        violation = ViolationRecord(
            violation_type=f"error_escalation:{escalation.error_type}",
            violator_id=escalation.escalation_id,  # Using escalation_id as identifier
            violator_name=triggered_by,
            violator_rank="unknown",  # Flow orchestrator doesn't track ranks
            description=f"Error escalated: {escalation.original_error}",
            target_id=str(escalation.motion_id),
            target_type="motion",
            prd_reference="NFR-GOV-7",
            requires_acknowledgment=True,
            metadata={
                "escalation_id": str(escalation.escalation_id),
                "strategy": escalation.strategy.value,
                "action_taken": escalation.action_taken,
            },
        )

        self._knight_witness.record_violation(violation)

    async def _witness_escalation_resolution(
        self,
        escalation: EscalationRecord,
        resolved_by: str,
        resolution_notes: str,
    ) -> None:
        """Witness an escalation resolution through Knight.

        Args:
            escalation: Resolved escalation record
            resolved_by: Archon ID who resolved
            resolution_notes: Notes on resolution
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            event_type="escalation_resolved",
            event_id=escalation.escalation_id,
            description=f"Escalation {escalation.escalation_id} resolved: {resolution_notes}",
            participants=[resolved_by],
            target_id=str(escalation.motion_id),
            target_type="motion",
            metadata={
                "original_error_type": escalation.error_type,
                "resolution_notes": resolution_notes,
            },
        )

        self._knight_witness.observe(context)

    async def _check_role_collapse(
        self,
        archon_id: str,
        motion_id: UUID,
        proposed_branch: GovernanceBranch,
    ) -> RoleCollapseViolation | None:
        """Check for role collapse before routing.

        Per Story 8.4 AC1/AC4/AC5: Pre-routing collapse check.
        Per PRD §2.1: No entity may define intent, execute it, AND judge it.

        Args:
            archon_id: The Archon triggering the action
            motion_id: The motion being acted upon
            proposed_branch: The branch being routed to

        Returns:
            RoleCollapseViolation if detected, None otherwise
        """
        if not self._role_collapse_detector:
            return None

        # Convert flow orchestrator branch to detection service branch
        from src.application.ports.branch_action_tracker import (
            GovernanceBranch as TrackerBranch,
        )

        try:
            tracker_branch = TrackerBranch(proposed_branch.value)
        except ValueError:
            # Branch not tracked (e.g., deliberative is not a conflicting branch)
            return None

        # Check for collapse
        result = await self._role_collapse_detector.detect_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=tracker_branch,
        )

        if result.has_collapse and result.violation:
            return result.violation

        return None

    async def _witness_role_collapse(
        self,
        violation: RoleCollapseViolation,
        triggered_by: str,
    ) -> None:
        """Witness a role collapse violation through Knight.

        Per CT-12: Witnessing creates accountability.
        Per Story 8.4 AC2: Role collapse attempts must be witnessed as violation.

        Args:
            violation: Role collapse violation record
            triggered_by: Archon ID who attempted the collapse
        """
        if not self._knight_witness:
            if self._verbose:
                self._log.warning(
                    "role_collapse_not_witnessed_no_knight",
                    violation_id=str(violation.violation_id),
                )
            return

        # Record as a violation per AC2
        violation_record = ViolationRecord(
            violation_type="role_collapse_attempt",
            violator_id=violation.violation_id,
            violator_name=triggered_by,
            violator_rank="unknown",  # Flow orchestrator doesn't track ranks
            description=f"Role collapse violation: {violation.conflict_rule}",
            target_id=str(violation.motion_id),
            target_type="motion",
            prd_reference=violation.prd_reference,
            requires_acknowledgment=True,
            metadata={
                "violation_id": str(violation.violation_id),
                "existing_branches": [b.value for b in violation.existing_branches],
                "attempted_branch": violation.attempted_branch.value,
                "severity": violation.severity.value,
                "escalated_to_conclave": violation.escalated_to_conclave,
            },
        )

        self._knight_witness.record_violation(violation_record)

        # Also create audit entry if detector is available
        if self._role_collapse_detector:
            witness_id = None
            # Get witness statement ID if available
            try:
                statements = self._knight_witness.get_statements_for_target(
                    str(violation.motion_id)
                )
                if statements:
                    witness_id = statements[-1].statement_id
            except Exception:
                pass

            self._role_collapse_detector.record_audit_entry(
                violation=violation,
                witness_statement_id=witness_id,
            )

        self._log.warning(
            "role_collapse_witnessed",
            violation_id=str(violation.violation_id),
            archon_id=violation.archon_id,
            motion_id=str(violation.motion_id),
            rule=violation.conflict_rule,
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_flow_orchestrator_service(
    state_machine: GovernanceStateMachineProtocol,
    knight_witness: KnightWitnessProtocol | None = None,
    role_collapse_detector: RoleCollapseDetectionService | None = None,
    verbose: bool = False,
) -> FlowOrchestratorService:
    """Factory function to create a FlowOrchestratorService.

    Args:
        state_machine: Governance state machine
        knight_witness: Knight witness (optional)
        role_collapse_detector: Role collapse detector (optional, per Story 8.4)
        verbose: Enable verbose logging

    Returns:
        Configured FlowOrchestratorService instance
    """
    return FlowOrchestratorService(
        state_machine=state_machine,
        knight_witness=knight_witness,
        role_collapse_detector=role_collapse_detector,
        verbose=verbose,
    )
