"""Obligation release service for consent-based governance.

Story: consent-gov-7.2: Obligation Release

This module implements the ObligationReleaseService for releasing all
obligations when a Cluster exits the system.

Constitutional Truths Honored:
- Golden Rule: Refusal is penalty-free → NO penalty methods exist
- FR44: All obligations released on exit
- CT-12: Witnessing creates accountability → Knight observes releases

Key Design Principles:
1. Pre-consent tasks are NULLIFIED (as if never happened)
2. Post-consent tasks are RELEASED (work preserved)
3. NO penalties of any kind
4. All releases are witnessed by Knight

NO PENALTY PRINCIPLE (structural enforcement):
    The following methods DO NOT EXIST:
    - apply_penalty()
    - reduce_standing()
    - mark_early_exit()
    - penalize()
    - decrease_reputation()

    These methods are not stubbed or disabled - they simply
    do not exist. This makes penalties structurally impossible.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from src.domain.governance.exit.release_type import ReleaseType
from src.domain.governance.exit.obligation_release import (
    ObligationRelease,
    ReleaseResult,
)
from src.domain.governance.task.task_state import TaskStatus


# Event type constants
OBLIGATIONS_RELEASED_EVENT = "custodial.obligations.released"
TASK_NULLIFIED_ON_EXIT_EVENT = "executive.task.nullified_on_exit"
TASK_RELEASED_ON_EXIT_EVENT = "executive.task.released_on_exit"
PENDING_REQUESTS_CANCELLED_EVENT = "executive.pending_requests.cancelled"


# Mapping of task status to release type
RELEASE_CATEGORIES: dict[TaskStatus, ReleaseType] = {
    # Pre-consent (nullify - task voided, no work existed)
    TaskStatus.AUTHORIZED: ReleaseType.NULLIFIED_ON_EXIT,
    TaskStatus.ACTIVATED: ReleaseType.NULLIFIED_ON_EXIT,
    TaskStatus.ROUTED: ReleaseType.NULLIFIED_ON_EXIT,
    # Post-consent (release - work preserved for attribution)
    TaskStatus.ACCEPTED: ReleaseType.RELEASED_ON_EXIT,
    TaskStatus.IN_PROGRESS: ReleaseType.RELEASED_ON_EXIT,
    TaskStatus.REPORTED: ReleaseType.RELEASED_ON_EXIT,
    TaskStatus.AGGREGATED: ReleaseType.RELEASED_ON_EXIT,
}


class TimeAuthority(Protocol):
    """Protocol for time authority (injected dependency)."""

    def now(self):
        """Get current timestamp."""
        ...


class EventEmitter(Protocol):
    """Protocol for event emission (injected dependency)."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Emit an event to the ledger."""
        ...


class TaskStateQueryPort(Protocol):
    """Protocol for querying task states (injected dependency)."""

    async def get_tasks_for_cluster(
        self,
        cluster_id: UUID,
    ) -> list:
        """Get all tasks assigned to a cluster.

        Returns tasks in any state (including terminal).
        """
        ...

    async def transition_task(
        self,
        task_id: UUID,
        to_status: TaskStatus,
        reason: str,
    ) -> None:
        """Transition a task to a new status."""
        ...


class PendingRequestPort(Protocol):
    """Protocol for managing pending requests (injected dependency)."""

    async def cancel_pending_for_cluster(
        self,
        cluster_id: UUID,
    ) -> int:
        """Cancel all pending requests for a cluster.

        Returns count of requests cancelled.
        """
        ...


class ObligationReleaseService:
    """Handles obligation release on exit.

    Per FR44: System can release Cluster from all obligations on exit.
    Per Golden Rule: NO penalties of any kind.

    This service:
    1. Nullifies pre-consent tasks (AUTHORIZED, ACTIVATED, ROUTED)
    2. Releases post-consent tasks with work preserved (ACCEPTED, IN_PROGRESS, etc.)
    3. Cancels pending requests
    4. Emits events for Knight observation

    STRUCTURAL ABSENCE (Golden Rule enforcement):
        The following methods DO NOT EXIST:
        - apply_penalty()
        - reduce_standing()
        - mark_early_exit()
        - penalize()
        - decrease_reputation()
        - record_abandonment()

        If these methods are ever added, it is a CONSTITUTIONAL VIOLATION.
    """

    def __init__(
        self,
        task_state_port: TaskStateQueryPort,
        pending_request_port: PendingRequestPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ) -> None:
        """Initialize ObligationReleaseService.

        Args:
            task_state_port: Port for querying and transitioning tasks.
            pending_request_port: Port for cancelling pending requests.
            event_emitter: For emitting governance events.
            time_authority: For timestamp generation.
        """
        self._tasks = task_state_port
        self._pending = pending_request_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def release_all(
        self,
        cluster_id: UUID,
    ) -> ReleaseResult:
        """Release all obligations for a Cluster.

        Per FR44: System can release Cluster from all obligations on exit.
        Per Golden Rule: NO penalties applied.

        This method:
        1. Gets all tasks for the Cluster
        2. Nullifies pre-consent tasks (AUTHORIZED, ACTIVATED, ROUTED)
        3. Releases post-consent tasks (ACCEPTED, IN_PROGRESS, REPORTED, AGGREGATED)
        4. Cancels pending requests
        5. Emits `custodial.obligations.released` event

        Args:
            cluster_id: ID of the Cluster whose obligations to release.

        Returns:
            ReleaseResult with counts of nullified, released, and cancelled.
        """
        now = self._time.now()
        releases: list[ObligationRelease] = []

        # Get all tasks for cluster
        tasks = await self._tasks.get_tasks_for_cluster(cluster_id)

        nullified = 0
        released = 0

        for task in tasks:
            # Get task state
            task_status = self._get_task_status(task)

            # Skip terminal states (already finished)
            if task_status.is_terminal:
                continue

            # Determine release type
            release_type = RELEASE_CATEGORIES.get(task_status)
            if not release_type:
                continue

            task_id = self._get_task_id(task)

            if release_type == ReleaseType.NULLIFIED_ON_EXIT:
                await self._nullify_task(task_id, cluster_id, task_status, now)
                nullified += 1
                work_preserved = False
            else:
                await self._release_task(task_id, cluster_id, task_status, now)
                released += 1
                work_preserved = True

            releases.append(
                ObligationRelease(
                    release_id=uuid4(),
                    cluster_id=cluster_id,
                    task_id=task_id,
                    previous_state=task_status,
                    release_type=release_type,
                    released_at=now,
                    work_preserved=work_preserved,
                )
            )

        # Cancel pending requests
        pending_cancelled = await self._cancel_pending_requests(cluster_id)

        # Create result
        result = ReleaseResult(
            cluster_id=cluster_id,
            nullified_count=nullified,
            released_count=released,
            pending_cancelled=pending_cancelled,
            total_obligations=nullified + released,
            released_at=now,
        )

        # Emit release event
        await self._event_emitter.emit(
            event_type=OBLIGATIONS_RELEASED_EVENT,
            actor="system",
            payload={
                "cluster_id": str(cluster_id),
                "nullified_count": nullified,
                "released_count": released,
                "pending_cancelled": pending_cancelled,
                "total_obligations": result.total_obligations,
                "released_at": now.isoformat(),
            },
        )

        return result

    async def _nullify_task(
        self,
        task_id: UUID,
        cluster_id: UUID,
        previous_state: TaskStatus,
        now,
    ) -> None:
        """Nullify a pre-consent task.

        Per AC6: Pre-consent tasks transitioned to NULLIFIED.
        As if the task never happened - Cluster never agreed.

        Args:
            task_id: ID of the task to nullify.
            cluster_id: ID of the Cluster exiting.
            previous_state: Task state before nullification.
            now: Current timestamp.
        """
        await self._tasks.transition_task(
            task_id=task_id,
            to_status=TaskStatus.NULLIFIED,
            reason="cluster_exit_pre_consent",
        )

        await self._event_emitter.emit(
            event_type=TASK_NULLIFIED_ON_EXIT_EVENT,
            actor="system",
            payload={
                "task_id": str(task_id),
                "cluster_id": str(cluster_id),
                "previous_state": previous_state.value,
                "reason": "cluster_exit_pre_consent",
                "work_preserved": False,
            },
        )

    async def _release_task(
        self,
        task_id: UUID,
        cluster_id: UUID,
        previous_state: TaskStatus,
        now,
    ) -> None:
        """Release a post-consent task with work preserved.

        Per AC7: Post-consent tasks released with work preservation.
        Cluster's contribution is acknowledged even though task is incomplete.

        Args:
            task_id: ID of the task to release.
            cluster_id: ID of the Cluster exiting.
            previous_state: Task state before release.
            now: Current timestamp.
        """
        # Transition to QUARANTINED (work preserved but task stopped)
        await self._tasks.transition_task(
            task_id=task_id,
            to_status=TaskStatus.QUARANTINED,
            reason="cluster_exit_post_consent",
        )

        await self._event_emitter.emit(
            event_type=TASK_RELEASED_ON_EXIT_EVENT,
            actor="system",
            payload={
                "task_id": str(task_id),
                "cluster_id": str(cluster_id),
                "previous_state": previous_state.value,
                "reason": "cluster_exit_post_consent",
                "work_preserved": True,
            },
        )

    async def _cancel_pending_requests(
        self,
        cluster_id: UUID,
    ) -> int:
        """Cancel all pending requests for a Cluster.

        Per AC3: Pending requests cancelled.
        No future obligations will be created.

        Args:
            cluster_id: ID of the Cluster exiting.

        Returns:
            Count of pending requests cancelled.
        """
        cancelled = await self._pending.cancel_pending_for_cluster(cluster_id)

        if cancelled > 0:
            await self._event_emitter.emit(
                event_type=PENDING_REQUESTS_CANCELLED_EVENT,
                actor="system",
                payload={
                    "cluster_id": str(cluster_id),
                    "cancelled_count": cancelled,
                },
            )

        return cancelled

    def _get_task_status(self, task) -> TaskStatus:
        """Extract TaskStatus from a task object.

        Handles both TaskState objects and simple objects with current_status.
        """
        if hasattr(task, "current_status"):
            return task.current_status
        if hasattr(task, "status"):
            return task.status
        raise ValueError(f"Cannot determine status for task: {task}")

    def _get_task_id(self, task) -> UUID:
        """Extract task ID from a task object.

        Handles both TaskState objects and simple objects.
        """
        if hasattr(task, "task_id"):
            return task.task_id
        if hasattr(task, "id"):
            return task.id
        raise ValueError(f"Cannot determine ID for task: {task}")

    # ========================================================================
    # PENALTY METHODS - INTENTIONALLY DO NOT EXIST
    # ========================================================================
    #
    # The following methods DO NOT EXIST by design (Golden Rule):
    #
    # async def apply_penalty(self, cluster_id: UUID) -> None:
    #     '''Would apply penalty - VIOLATES Golden Rule'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def reduce_standing(self, cluster_id: UUID) -> None:
    #     '''Would reduce standing - NO STANDING SYSTEM EXISTS'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def mark_early_exit(self, cluster_id: UUID) -> None:
    #     '''Would mark early exit - VIOLATES Golden Rule'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def penalize(self, cluster_id: UUID) -> None:
    #     '''Would penalize - VIOLATES Golden Rule'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def decrease_reputation(self, cluster_id: UUID) -> None:
    #     '''Would decrease reputation - NO REPUTATION SYSTEM EXISTS'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def record_abandonment(self, cluster_id: UUID) -> None:
    #     '''Would record abandonment - VIOLATES Golden Rule'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # If these methods are ever added, Knight should observe and record
    # as a CONSTITUTIONAL VIOLATION.
    # ========================================================================
