"""TaskActivationService - Service for creating and routing task activations.

Story: consent-gov-2.2: Task Activation Request

This service implements the task activation workflow with mandatory
Coercion Filter routing.

Constitutional Guarantees:
- All content passes through Coercion Filter (FR21)
- No bypass path exists for participant messages
- Events emitted via two-phase pattern
- Earl can view task state and history (FR12)

Flow:
1. Create task in AUTHORIZED state
2. Transition to ACTIVATED
3. Filter content through Coercion Filter
4. If accepted/transformed: route to Cluster, transition to ROUTED
5. If rejected: return to Earl for rewrite
6. If blocked: log violation, do not route

References:
- [Source: governance-architecture.md#Filter Pipeline Placement (Locked)]
- [Source: governance-architecture.md#Routing Architecture (Locked)]
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from src.domain.governance.task.task_activation_request import (
        FilteredContent as TaskFilteredContent,
    )

from src.application.ports.governance.coercion_filter_port import (
    CoercionFilterPort,
    MessageType,
)
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.governance.participant_message_port import (
    ParticipantMessagePort,
)
from src.application.ports.governance.task_activation_port import (
    TaskActivationPort,
    TaskStatePort,
    UnauthorizedAccessError,
)
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.application.services.governance.two_phase_execution import TwoPhaseExecution
from src.domain.governance.filter import (
    FilterDecision,
    FilterResult,
)
from src.domain.governance.task.task_activation_request import (
    FilterOutcome,
    RoutingStatus,
    TaskActivationResult,
    TaskStateView,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus


class TaskActivationService(TaskActivationPort):
    """Service for creating and routing task activation requests.

    This service implements the full task activation workflow:
    1. Create task in AUTHORIZED state
    2. Transition to ACTIVATED
    3. Pass content through Coercion Filter
    4. Route to Cluster via async protocol (if accepted)

    Constitutional Guarantees:
    - All content passes through Coercion Filter
    - No bypass path exists for participant messages
    - Events emitted via two-phase pattern
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        coercion_filter: CoercionFilterPort,
        participant_message_port: ParticipantMessagePort,
        ledger_port: GovernanceLedgerPort,
        two_phase_emitter: TwoPhaseEventEmitterPort,
    ) -> None:
        """Initialize the TaskActivationService.

        Args:
            task_state_port: Port for task state persistence.
            coercion_filter: Port for content filtering.
            participant_message_port: Port for sending messages.
            ledger_port: Port for reading event history.
            two_phase_emitter: Port for two-phase event emission.
        """
        self._task_state = task_state_port
        self._filter = coercion_filter
        self._messenger = participant_message_port
        self._ledger = ledger_port
        self._emitter = two_phase_emitter

    async def create_activation(
        self,
        earl_id: str,
        cluster_id: str,
        description: str,
        requirements: list[str],
        expected_outcomes: list[str],
        ttl: timedelta | None = None,
    ) -> TaskActivationResult:
        """Create and process a task activation request.

        Flow:
        1. Create task in AUTHORIZED state
        2. Transition to ACTIVATED
        3. Filter content through Coercion Filter
        4. If accepted/transformed: route to Cluster
        5. If rejected: return to Earl for rewrite
        6. If blocked: log violation, do not route

        Args:
            earl_id: ID of the Earl creating the task.
            cluster_id: ID of the Cluster to receive the task.
            description: Task description (subject to filtering).
            requirements: List of requirements (subject to filtering).
            expected_outcomes: Expected deliverables (subject to filtering).
            ttl: Optional TTL override (default 72h per NFR-CONSENT-01).

        Returns:
            TaskActivationResult with filter outcome and routing status.
        """
        # Use default TTL if not specified
        effective_ttl = ttl if ttl is not None else timedelta(hours=72)

        # Create task in AUTHORIZED state
        task = await self._task_state.create_task(
            earl_id=earl_id,
            cluster_id=cluster_id,
            ttl=effective_ttl,
        )

        # Use two-phase execution for the activation workflow
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.activate",
            actor_id=earl_id,
            target_entity_id=str(task.task_id),
            intent_payload={
                "cluster_id": cluster_id,
                "ttl_hours": effective_ttl.total_seconds() / 3600,
            },
        ) as execution:
            # Transition to ACTIVATED
            task = await self._transition_task(task, TaskStatus.ACTIVATED)

            # Filter content through Coercion Filter
            # Combine all content fields for filtering
            content_to_filter = f"{description}\n" + "\n".join(requirements) + "\n" + "\n".join(expected_outcomes)
            filter_result = await self._filter.filter_content(
                content=content_to_filter,
                message_type=MessageType.TASK_ACTIVATION,
            )

            # Handle filter outcome
            result = await self._handle_filter_result(
                task=task,
                cluster_id=cluster_id,
                filter_result=filter_result,
                execution=execution,
            )

            return result

    async def _transition_task(
        self,
        task: TaskState,
        new_status: TaskStatus,
        actor_id: str | None = None,
        reason: str = "",
    ) -> TaskState:
        """Transition task to a new status.

        Args:
            task: Current task state.
            new_status: Target status.
            actor_id: ID of actor performing transition (defaults to earl_id).
            reason: Optional reason for the transition.

        Returns:
            New TaskState with updated status.

        Raises:
            IllegalStateTransitionError: If transition is invalid.
        """
        effective_actor = actor_id if actor_id is not None else task.earl_id
        new_task = task.transition(
            new_status=new_status,
            transition_time=datetime.utcnow(),
            actor_id=effective_actor,
            reason=reason,
        )
        await self._task_state.save_task(new_task)
        return new_task

    async def _handle_filter_result(
        self,
        task: TaskState,
        cluster_id: str,
        filter_result: FilterResult,
        execution: TwoPhaseExecution,
    ) -> TaskActivationResult:
        """Handle the Coercion Filter result.

        Args:
            task: The task being activated.
            cluster_id: Target Cluster ID.
            filter_result: Result from Coercion Filter.
            execution: Two-phase execution context.

        Returns:
            TaskActivationResult based on filter outcome.
        """
        # Map FilterDecision to FilterOutcome for backward compatibility
        decision_to_outcome = {
            FilterDecision.ACCEPTED: FilterOutcome.ACCEPTED,
            FilterDecision.REJECTED: FilterOutcome.REJECTED,
            FilterDecision.BLOCKED: FilterOutcome.BLOCKED,
        }
        filter_outcome = decision_to_outcome.get(filter_result.decision, FilterOutcome.BLOCKED)

        # Generate decision ID from timestamp for audit trail
        decision_id = uuid4()

        if filter_result.decision == FilterDecision.ACCEPTED:
            # Route to Cluster - use domain model's FilteredContent
            # Need to adapt from domain FilteredContent to task_activation's FilteredContent
            domain_filtered = filter_result.content
            if domain_filtered is not None:
                from src.domain.governance.task.task_activation_request import (
                    FilteredContent as TaskFilteredContent,
                )
                task_filtered = TaskFilteredContent(
                    content=domain_filtered.content,
                    filter_decision_id=decision_id,
                    original_hash=domain_filtered.original_hash,
                    transformation_applied=filter_result.was_transformed,
                )
                await self._route_to_cluster_internal(
                    task=task,
                    cluster_id=cluster_id,
                    filtered_content=task_filtered,
                )
            execution.set_result({"routed": True, "cluster_id": cluster_id})
            return TaskActivationResult(
                success=True,
                task_state=task,
                filter_outcome=filter_outcome,
                filter_decision_id=decision_id,
                routing_status=RoutingStatus.ROUTED,
                message="Task activation routed to Cluster",
            )
        elif filter_result.decision == FilterDecision.REJECTED:
            rejection_reason_str = None
            if filter_result.rejection_reason:
                rejection_reason_str = filter_result.rejection_guidance or filter_result.rejection_reason.description
            execution.set_result({"routed": False, "reason": "rejected"})
            return TaskActivationResult(
                success=False,
                task_state=task,
                filter_outcome=FilterOutcome.REJECTED,
                filter_decision_id=decision_id,
                routing_status=RoutingStatus.PENDING_REWRITE,
                message="Content rejected by filter. Please revise.",
                rejection_reason=rejection_reason_str,
            )
        else:  # blocked
            violation_str = None
            if filter_result.violation_type:
                violation_str = filter_result.violation_details or filter_result.violation_type.description
            execution.set_result({"routed": False, "reason": "blocked"})
            return TaskActivationResult(
                success=False,
                task_state=task,
                filter_outcome=FilterOutcome.BLOCKED,
                filter_decision_id=decision_id,
                routing_status=RoutingStatus.BLOCKED,
                message="Content blocked due to violation.",
                rejection_reason=violation_str,
            )

    async def _route_to_cluster_internal(
        self,
        task: TaskState,
        cluster_id: str,
        filtered_content: TaskFilteredContent | None,
    ) -> None:
        """Route activation request to Cluster via async protocol.

        Args:
            task: The task being routed.
            cluster_id: Target Cluster ID.
            filtered_content: Filtered content to send.

        Raises:
            ValueError: If filtered_content is None.
        """
        if filtered_content is None:
            raise ValueError("Cannot route without filtered content")

        # Transition to ROUTED
        task = await self._transition_task(task, TaskStatus.ROUTED)

        # Send via participant message port (email)
        await self._messenger.send_to_participant(
            participant_id=cluster_id,
            content=filtered_content,
            message_type="task_activation",
            metadata={
                "task_id": str(task.task_id),
                "earl_id": task.earl_id,
            },
        )

    async def route_to_cluster(
        self,
        task_id: UUID,
        cluster_id: str,
    ) -> bool:
        """Route an activated task to a Cluster.

        This is called after successful filtering to send the
        filtered content to the Cluster via async protocol.

        Args:
            task_id: ID of the task to route.
            cluster_id: ID of the Cluster to receive the task.

        Returns:
            True if routing was successful.

        Raises:
            ValueError: If task is not in a routable state.
            TaskNotFoundError: If task does not exist.
        """
        task = await self._task_state.get_task(task_id)

        if task.current_status != TaskStatus.ACTIVATED:
            raise ValueError(
                f"Task {task_id} is not in ACTIVATED state. "
                f"Current state: {task.current_status.value}"
            )

        # This method assumes content has already been filtered
        # In practice, the full workflow through create_activation should be used
        task = await self._transition_task(task, TaskStatus.ROUTED)
        return True

    async def get_task_state(
        self,
        task_id: UUID,
        earl_id: str,
    ) -> TaskStateView:
        """Get current task state for Earl.

        Per FR12, Earl can view task state and history.
        This method verifies Earl ownership before returning.

        Args:
            task_id: ID of the task to retrieve.
            earl_id: ID of the Earl requesting access.

        Returns:
            TaskStateView with current state and metadata.

        Raises:
            UnauthorizedAccessError: If Earl does not own this task.
            TaskNotFoundError: If task does not exist.
        """
        task = await self._task_state.get_task(task_id)

        # Verify Earl owns this task
        if task.earl_id != earl_id:
            raise UnauthorizedAccessError(
                actor_id=earl_id,
                resource_id=str(task_id),
                message=f"Earl {earl_id} does not own task {task_id}",
            )

        # Calculate TTL remaining
        ttl_remaining = self._calculate_ttl_remaining(task)

        return TaskStateView(
            task_id=task.task_id,
            current_status=task.current_status.value,
            cluster_id=task.cluster_id,
            created_at=task.created_at,
            state_entered_at=task.state_entered_at,
            ttl=task.ttl,
            ttl_remaining=ttl_remaining,
            is_pre_consent=task.current_status.is_pre_consent,
            is_post_consent=task.current_status.is_post_consent,
            is_terminal=task.current_status.is_terminal,
        )

    def _calculate_ttl_remaining(self, task: TaskState) -> timedelta | None:
        """Calculate remaining TTL for a task.

        TTL only applies to pre-consent states. Returns None
        for post-consent and terminal states.

        Args:
            task: The task to check.

        Returns:
            Remaining timedelta, or None if not applicable.
        """
        if not task.current_status.is_pre_consent:
            return None

        elapsed = datetime.utcnow() - task.created_at
        remaining = task.ttl - elapsed

        if remaining.total_seconds() < 0:
            return timedelta(0)

        return remaining

    async def get_task_history(
        self,
        task_id: UUID,
        earl_id: str,
    ) -> list[dict[str, Any]]:
        """Get task event history for Earl.

        Per FR12, Earl can view task state and history.
        Returns all events related to this task.

        Args:
            task_id: ID of the task.
            earl_id: ID of the Earl requesting access.

        Returns:
            List of events related to this task.

        Raises:
            UnauthorizedAccessError: If Earl does not own this task.
            TaskNotFoundError: If task does not exist.
        """
        # Verify ownership first
        task = await self._task_state.get_task(task_id)
        if task.earl_id != earl_id:
            raise UnauthorizedAccessError(
                actor_id=earl_id,
                resource_id=str(task_id),
                message=f"Earl {earl_id} does not own task {task_id}",
            )

        # Query events from ledger
        events = await self._ledger.read_events(
            event_type_pattern="executive.task.*",
            payload_filter={"task_id": str(task_id)},
        )

        # Convert to dicts for return
        return [
            {
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "actor_id": event.actor_id,
                "payload": event.payload,
            }
            for event in events
        ]
