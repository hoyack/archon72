"""TaskConsentService - Service for Cluster consent operations on tasks.

Story: consent-gov-2.3: Task Consent Operations

This service implements consent operations for Clusters on task activation
requests. It enforces constitutional guarantees around penalty-free refusal.

Constitutional Guarantees:
- Declining is ALWAYS penalty-free
- No standing/reputation tracking exists
- Halting in-progress tasks incurs no penalty
- Justification is NEVER required for decline or halt

Flow:
1. Cluster views pending requests (get_pending_requests)
2. Cluster accepts/declines/halts tasks
3. Events emitted via two-phase pattern
4. NO penalty tracking on any refusal

References:
- FR2: Cluster can view pending requests
- FR3: Cluster can accept request
- FR4: Cluster can decline without justification
- FR5: Cluster can halt without penalty
- Golden Rule: Refusal is penalty-free
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.governance.task_activation_port import TaskStatePort
from src.application.ports.governance.task_consent_port import (
    InvalidTaskStateError,
    PendingTaskView,
    TaskConsentPort,
    TaskConsentResult,
    UnauthorizedConsentError,
)
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.domain.ports.time_authority import TimeAuthorityProtocol
from src.application.services.governance.two_phase_execution import TwoPhaseExecution
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.task.task_state import TaskState, TaskStatus


class TaskConsentService(TaskConsentPort):
    """Service for Cluster consent operations on tasks.

    Constitutional Guarantees:
    - Declining is ALWAYS penalty-free
    - No standing/reputation tracking exists
    - Halting in-progress tasks incurs no penalty
    - Justification is NEVER required for decline

    This service implements the full consent workflow:
    1. View pending requests (ROUTED tasks for Cluster)
    2. Accept task (ROUTED -> ACCEPTED)
    3. Decline task (ROUTED/ACCEPTED -> DECLINED)
    4. Halt task (IN_PROGRESS -> QUARANTINED)

    All operations:
    - Use two-phase event emission for Knight observability
    - Record NO penalty information
    - Require NO justification for refusal
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        ledger_port: GovernanceLedgerPort,
        two_phase_emitter: TwoPhaseEventEmitterPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the TaskConsentService.

        Args:
            task_state_port: Port for task state persistence.
            ledger_port: Port for event ledger operations.
            two_phase_emitter: Port for two-phase event emission.
            time_authority: Time authority for timestamps.
        """
        self._task_state = task_state_port
        self._ledger = ledger_port
        self._emitter = two_phase_emitter
        self._time = time_authority

    async def get_pending_requests(
        self,
        cluster_id: str,
        limit: int = 100,
    ) -> list[PendingTaskView]:
        """Get pending task activation requests for a Cluster.

        Returns tasks in ROUTED state addressed to this Cluster,
        excluding expired requests.

        Per FR2: Cluster can view pending requests.

        Args:
            cluster_id: ID of the Cluster requesting pending tasks.
            limit: Maximum number of results (default 100).

        Returns:
            List of PendingTaskView objects for pending tasks.
        """
        # Query tasks in ROUTED state for this Cluster
        tasks = await self._task_state.get_tasks_by_state_and_cluster(
            status=TaskStatus.ROUTED,
            cluster_id=cluster_id,
            limit=limit,
        )

        now = self._time.now()
        result = []

        for task in tasks:
            # Filter out expired requests
            if self._is_ttl_expired(task, now):
                continue

            ttl_remaining = self._calculate_ttl_remaining(task, now)
            if ttl_remaining <= timedelta(0):
                continue

            result.append(
                PendingTaskView(
                    task_id=task.task_id,
                    earl_id=task.earl_id,
                    description_preview=await self._get_description_preview(
                        task.task_id
                    ),
                    ttl_remaining=ttl_remaining,
                    routed_at=task.state_entered_at,
                )
            )

        return result

    async def accept_task(
        self,
        task_id: UUID,
        cluster_id: str,
    ) -> TaskConsentResult:
        """Accept a task activation request.

        Per FR3: Cluster can accept a task activation request.

        Transitions: ROUTED -> ACCEPTED

        Emits: executive.task.accepted event

        Args:
            task_id: ID of the task to accept.
            cluster_id: ID of the Cluster accepting.

        Returns:
            TaskConsentResult with new task state.

        Raises:
            UnauthorizedConsentError: If Cluster is not the recipient.
            InvalidTaskStateError: If task is not in ROUTED state.
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.accept",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={},
        ) as execution:
            task = await self._task_state.get_task(task_id)

            # Validate Cluster is the intended recipient
            if task.cluster_id != cluster_id:
                raise UnauthorizedConsentError(
                    cluster_id=cluster_id,
                    task_id=task_id,
                    message=f"Cluster {cluster_id} is not the recipient of task {task_id}",
                )

            # Validate task is in ROUTED state
            if task.current_status != TaskStatus.ROUTED:
                raise InvalidTaskStateError(
                    task_id=task_id,
                    current_state=task.current_status.value,
                    operation="accept",
                )

            # Transition to ACCEPTED
            now = self._time.now()
            new_task = task.transition(
                new_status=TaskStatus.ACCEPTED,
                transition_time=now,
                actor_id=cluster_id,
            )
            await self._task_state.save_task(new_task)

            # Emit event
            await self._emit_accepted_event(new_task, cluster_id, now)

            execution.set_result({"accepted": True})
            return TaskConsentResult(
                success=True,
                task_state=new_task,
                operation="accepted",
                message="Task accepted successfully",
            )

        raise RuntimeError("Task acceptance failed")

    async def decline_task(
        self,
        task_id: UUID,
        cluster_id: str,
        # NOTE: No justification parameter - intentionally omitted (FR4)
    ) -> TaskConsentResult:
        """Decline a task activation request.

        Constitutional Guarantee:
        - NO justification required (FR4 explicit)
        - NO penalty incurred
        - NO standing reduction
        - NO negative attribution recorded

        Per FR4: Cluster can decline without justification.

        Transitions: ROUTED -> DECLINED or ACCEPTED -> DECLINED

        Emits: executive.task.declined event with reason "explicit_decline"

        Args:
            task_id: ID of the task to decline.
            cluster_id: ID of the Cluster declining.

        Returns:
            TaskConsentResult with new task state.

        Raises:
            UnauthorizedConsentError: If Cluster is not the recipient.
            InvalidTaskStateError: If task is not in valid state for decline.
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.decline",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={},
        ) as execution:
            task = await self._task_state.get_task(task_id)

            # Validate Cluster is the intended recipient
            if task.cluster_id != cluster_id:
                raise UnauthorizedConsentError(
                    cluster_id=cluster_id,
                    task_id=task_id,
                    message=f"Cluster {cluster_id} is not the recipient of task {task_id}",
                )

            # Validate task is in valid state for decline
            if task.current_status not in {TaskStatus.ROUTED, TaskStatus.ACCEPTED}:
                raise InvalidTaskStateError(
                    task_id=task_id,
                    current_state=task.current_status.value,
                    operation="decline",
                )

            # Transition to DECLINED
            now = self._time.now()
            new_task = task.transition(
                new_status=TaskStatus.DECLINED,
                transition_time=now,
                actor_id=cluster_id,
            )
            await self._task_state.save_task(new_task)

            # Emit event - NO penalty information recorded
            await self._emit_declined_event(
                task=new_task,
                cluster_id=cluster_id,
                reason="explicit_decline",  # Not "failure" or "penalty"
                timestamp=now,
            )

            execution.set_result({"declined": True})
            return TaskConsentResult(
                success=True,
                task_state=new_task,
                operation="declined",
                message="Task declined successfully",
            )

        raise RuntimeError("Task decline failed")

    async def halt_task(
        self,
        task_id: UUID,
        cluster_id: str,
        # NOTE: No justification required - halting is penalty-free (FR5)
    ) -> TaskConsentResult:
        """Halt an in-progress task.

        Constitutional Guarantee:
        - Halting incurs NO penalty (FR5)
        - Task transitions to QUARANTINED (safe state)
        - NO negative attribution recorded
        - NO justification required

        Per FR5: Cluster can halt without penalty.

        Transitions: IN_PROGRESS -> QUARANTINED

        Emits: executive.task.halted event with penalty_incurred=false

        Args:
            task_id: ID of the task to halt.
            cluster_id: ID of the Cluster halting.

        Returns:
            TaskConsentResult with new task state.

        Raises:
            UnauthorizedConsentError: If Cluster is not the worker.
            InvalidTaskStateError: If task is not IN_PROGRESS.
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.halt",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={},
        ) as execution:
            task = await self._task_state.get_task(task_id)

            # Validate Cluster is the worker
            if task.cluster_id != cluster_id:
                raise UnauthorizedConsentError(
                    cluster_id=cluster_id,
                    task_id=task_id,
                    message=f"Cluster {cluster_id} is not working on task {task_id}",
                )

            # Validate task is in IN_PROGRESS state
            if task.current_status != TaskStatus.IN_PROGRESS:
                raise InvalidTaskStateError(
                    task_id=task_id,
                    current_state=task.current_status.value,
                    operation="halt",
                )

            # Transition to QUARANTINED (not "failed" - important distinction)
            now = self._time.now()
            new_task = task.transition(
                new_status=TaskStatus.QUARANTINED,
                transition_time=now,
                actor_id=cluster_id,
            )
            await self._task_state.save_task(new_task)

            # Emit event - explicitly NO penalty
            await self._emit_halted_event(
                task=new_task,
                cluster_id=cluster_id,
                reason="cluster_initiated_halt",
                timestamp=now,
            )

            execution.set_result({"halted": True})
            return TaskConsentResult(
                success=True,
                task_state=new_task,
                operation="halted",
                message="Task halted successfully",
            )

        raise RuntimeError("Task halt failed")

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _is_ttl_expired(self, task: TaskState, now: datetime) -> bool:
        """Check if task TTL has expired.

        Args:
            task: Task to check.
            now: Current time.

        Returns:
            True if TTL has expired.
        """
        return task.is_ttl_expired(now)

    def _calculate_ttl_remaining(
        self,
        task: TaskState,
        now: datetime,
    ) -> timedelta:
        """Calculate remaining TTL for a task.

        Args:
            task: Task to check.
            now: Current time.

        Returns:
            Remaining timedelta (may be negative if expired).
        """
        elapsed = now - task.state_entered_at
        return task.ttl - elapsed

    async def _get_description_preview(self, task_id: UUID) -> str:
        """Get description preview from task activation event.

        Args:
            task_id: Task ID to get description for.

        Returns:
            First 200 characters of task description.
        """
        # Query the activation event from ledger
        events = await self._ledger.read_events(
            event_type_pattern="executive.task.activate*",
            payload_filter={"task_id": str(task_id)},
            limit=1,
        )

        if events:
            description = events[0].payload.get("description", "")
            return description[:200] if len(description) > 200 else description

        return ""

    async def _emit_accepted_event(
        self,
        task: TaskState,
        cluster_id: str,
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.accepted event.

        Args:
            task: The accepted task.
            cluster_id: ID of the accepting Cluster.
            timestamp: Event timestamp.
        """
        from uuid import uuid4

        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=timestamp,
            actor_id=cluster_id,
            trace_id=str(task.task_id),
            payload={
                "task_id": str(task.task_id),
                "cluster_id": cluster_id,
                "accepted_at": timestamp.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)

    async def _emit_declined_event(
        self,
        task: TaskState,
        cluster_id: str,
        reason: str,
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.declined event.

        CONSTITUTIONAL GUARANTEE:
        - penalty_incurred is ALWAYS false
        - reason is NEVER "failure" or "penalty"

        Args:
            task: The declined task.
            cluster_id: ID of the declining Cluster.
            reason: Decline reason (always "explicit_decline").
            timestamp: Event timestamp.
        """
        from uuid import uuid4

        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.declined",
            timestamp=timestamp,
            actor_id=cluster_id,
            trace_id=str(task.task_id),
            payload={
                "task_id": str(task.task_id),
                "cluster_id": cluster_id,
                "declined_at": timestamp.isoformat(),
                "reason": reason,
                "penalty_incurred": False,  # CONSTITUTIONAL GUARANTEE
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)

    async def _emit_halted_event(
        self,
        task: TaskState,
        cluster_id: str,
        reason: str,
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.halted event.

        CONSTITUTIONAL GUARANTEE:
        - penalty_incurred is ALWAYS false (FR5)

        Args:
            task: The halted task.
            cluster_id: ID of the halting Cluster.
            reason: Halt reason (always "cluster_initiated_halt").
            timestamp: Event timestamp.
        """
        from uuid import uuid4

        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.halted",
            timestamp=timestamp,
            actor_id=cluster_id,
            trace_id=str(task.task_id),
            payload={
                "task_id": str(task.task_id),
                "cluster_id": cluster_id,
                "halted_at": timestamp.isoformat(),
                "reason": reason,
                "penalty_incurred": False,  # CONSTITUTIONAL GUARANTEE (FR5)
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)
