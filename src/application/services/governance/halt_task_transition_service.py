"""Halt Task Transition Service - Orchestrates task state transitions on halt.

Story: consent-gov-4.3: Task State Transitions on Halt

This service orchestrates the transition of all active tasks to deterministic
states when a system halt is triggered. It implements the HaltTaskTransitionPort
interface and provides the core logic for consent-based task handling.

Consent Boundary:
- Pre-consent tasks (AUTHORIZED, ACTIVATED, ROUTED) → NULLIFIED
- Post-consent tasks (ACCEPTED, IN_PROGRESS, REPORTED, AGGREGATED) → QUARANTINED
- Terminal tasks (COMPLETED, DECLINED, QUARANTINED, NULLIFIED) → UNCHANGED

Constitutional Guarantees:
- FR24: Pre-consent tasks transition to nullified
- FR25: Post-consent tasks transition to quarantined
- FR26: Completed tasks remain unchanged
- FR27: State transitions are atomic (no partial transitions)
- NFR-ATOMIC-01: Atomic transitions
- NFR-REL-03: In-flight tasks resolve deterministically

Event Types Emitted:
- executive.task.nullified_on_halt: Pre-consent task nullified
- executive.task.quarantined_on_halt: Post-consent task quarantined
- executive.task.preserved_on_halt: Terminal task preserved (audit only)

References:
- [Source: governance-architecture.md#Task State Projection]
- [Source: governance-prd.md#FR22-FR27]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.governance.halt_task_transition_port import (
    ConcurrentModificationError,
    HaltTaskTransitionPort,
    HaltTransitionResult,
    HaltTransitionType,
    TaskStateCategory,
    TaskTransitionRecord,
)
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.task.task_state import TaskStatus
from src.domain.governance.task.task_state_rules import TaskTransitionRules

if TYPE_CHECKING:
    from datetime import datetime

    from src.application.ports.governance.ledger_port import GovernanceLedgerPort
    from src.domain.ports.time_authority import TimeAuthorityProtocol

logger = get_logger(__name__)


class TaskStateQueryPort(Protocol):
    """Protocol for querying and updating task state.

    This port is used by HaltTaskTransitionService to:
    1. Query all active (non-terminal) tasks
    2. Atomically transition individual tasks

    Implementations should use optimistic locking for atomic transitions.
    """

    async def get_active_tasks(self) -> list[tuple[UUID, str]]:
        """Get all active (non-terminal) tasks.

        Returns:
            List of (task_id, current_status) tuples for non-terminal tasks.
        """
        ...

    async def atomic_transition(
        self,
        task_id: UUID,
        from_status: str,
        to_status: str,
    ) -> None:
        """Atomically transition a single task.

        Uses optimistic locking - if current status doesn't match from_status,
        raises ConcurrentModificationError.

        Args:
            task_id: ID of task to transition.
            from_status: Expected current status.
            to_status: Target status.

        Raises:
            ConcurrentModificationError: If task state changed.
        """
        ...


class HaltTaskTransitionService(HaltTaskTransitionPort):
    """Service for transitioning tasks on system halt.

    This service implements the HaltTaskTransitionPort interface and provides
    the core logic for transitioning all active tasks when a halt is triggered.

    Per FR24-FR26, tasks are categorized by their consent state:
    - Pre-consent → nullified (safe to cancel, Cluster never agreed)
    - Post-consent → quarantined (preserve work for review)
    - Terminal → unchanged (already finished)

    Thread Safety:
    - Uses atomic transitions with optimistic locking
    - Event emission is async-safe
    - No shared mutable state

    Example:
        >>> service = HaltTaskTransitionService(
        ...     task_state_port=task_state_port,
        ...     ledger=ledger,
        ...     time_authority=time_authority,
        ... )
        >>> result = await service.transition_all_tasks_on_halt(
        ...     halt_correlation_id=halt_status.correlation_id,
        ... )
        >>> print(f"Nullified: {result.nullified_count}, Quarantined: {result.quarantined_count}")
    """

    def __init__(
        self,
        task_state_port: TaskStateQueryPort,
        ledger: GovernanceLedgerPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize HaltTaskTransitionService.

        Args:
            task_state_port: Port for querying and updating task state.
            ledger: Ledger for event emission.
            time_authority: Time authority for timestamps.
        """
        self._task_state = task_state_port
        self._ledger = ledger
        self._time = time_authority

    async def transition_all_tasks_on_halt(
        self,
        halt_correlation_id: UUID,
    ) -> HaltTransitionResult:
        """Transition all active tasks to halt states.

        Per FR24-FR27:
        - Pre-consent tasks → nullified
        - Post-consent tasks → quarantined
        - Terminal tasks → unchanged (but recorded for audit)

        This method:
        1. Queries all non-terminal tasks
        2. Categorizes each by consent state
        3. Applies appropriate transition atomically
        4. Emits events with halt correlation
        5. Returns aggregated result

        Args:
            halt_correlation_id: ID linking to the halt event.

        Returns:
            HaltTransitionResult with counts and individual records.

        Note:
            Individual task failures are recorded but do not stop processing.
            This ensures maximum task coverage even if some fail.
        """
        triggered_at = self._time.now()
        records: list[TaskTransitionRecord] = []

        nullified_count = 0
        quarantined_count = 0
        preserved_count = 0
        failed_count = 0

        logger.info(
            "halt_task_transition_started",
            halt_correlation_id=str(halt_correlation_id),
            triggered_at=triggered_at.isoformat(),
        )

        # Get all active tasks
        active_tasks = await self.get_active_tasks()

        logger.info(
            "halt_task_transition_tasks_found",
            halt_correlation_id=str(halt_correlation_id),
            task_count=len(active_tasks),
        )

        # Process each task
        for task_id, current_status_str in active_tasks:
            try:
                # Parse status
                try:
                    current_status = TaskStatus(current_status_str)
                except ValueError:
                    # Unknown status - treat as failed
                    logger.error(
                        "halt_task_transition_unknown_status",
                        task_id=str(task_id),
                        status=current_status_str,
                        halt_correlation_id=str(halt_correlation_id),
                    )
                    records.append(
                        self._create_failed_record(
                            task_id=task_id,
                            previous_status=current_status_str,
                            halt_correlation_id=halt_correlation_id,
                            error_message=f"Unknown status: {current_status_str}",
                        )
                    )
                    failed_count += 1
                    continue

                # Categorize by consent state
                category = self._categorize_task(current_status)

                # Get target status for halt
                target_status = TaskTransitionRules.get_halt_target(current_status)

                if category == TaskStateCategory.PRE_CONSENT:
                    # Pre-consent → nullified
                    record = await self._nullify_task(
                        task_id=task_id,
                        current_status=current_status,
                        target_status=target_status,
                        halt_correlation_id=halt_correlation_id,
                    )
                    records.append(record)
                    if record.is_success:
                        nullified_count += 1
                    else:
                        failed_count += 1

                elif category == TaskStateCategory.POST_CONSENT:
                    # Post-consent → quarantined
                    record = await self._quarantine_task(
                        task_id=task_id,
                        current_status=current_status,
                        target_status=target_status,
                        halt_correlation_id=halt_correlation_id,
                    )
                    records.append(record)
                    if record.is_success:
                        quarantined_count += 1
                    else:
                        failed_count += 1

                elif category == TaskStateCategory.TERMINAL:
                    # Terminal → unchanged (audit only)
                    record = await self._preserve_task(
                        task_id=task_id,
                        current_status=current_status,
                        halt_correlation_id=halt_correlation_id,
                    )
                    records.append(record)
                    preserved_count += 1

            except Exception as e:
                # Catch-all for unexpected errors
                logger.error(
                    "halt_task_transition_unexpected_error",
                    task_id=str(task_id),
                    status=current_status_str,
                    error=str(e),
                    halt_correlation_id=str(halt_correlation_id),
                )
                records.append(
                    self._create_failed_record(
                        task_id=task_id,
                        previous_status=current_status_str,
                        halt_correlation_id=halt_correlation_id,
                        error_message=str(e),
                    )
                )
                failed_count += 1

        completed_at = self._time.now()

        result = HaltTransitionResult(
            halt_correlation_id=halt_correlation_id,
            triggered_at=triggered_at,
            completed_at=completed_at,
            nullified_count=nullified_count,
            quarantined_count=quarantined_count,
            preserved_count=preserved_count,
            failed_count=failed_count,
            total_processed=len(active_tasks),
            transition_records=tuple(records),
        )

        # Emit summary event
        await self._emit_transition_summary(result)

        logger.info(
            "halt_task_transition_completed",
            halt_correlation_id=str(halt_correlation_id),
            nullified=nullified_count,
            quarantined=quarantined_count,
            preserved=preserved_count,
            failed=failed_count,
            total=len(active_tasks),
            execution_ms=result.execution_ms,
        )

        return result

    async def get_active_tasks(self) -> list[tuple[UUID, str]]:
        """Get all active (non-terminal) tasks.

        Delegates to task state port.

        Returns:
            List of (task_id, current_status) tuples.
        """
        return await self._task_state.get_active_tasks()

    async def atomic_transition(
        self,
        task_id: UUID,
        from_status: str,
        to_status: str,
        halt_correlation_id: UUID,
        transitioned_at: datetime,
    ) -> None:
        """Atomically transition a single task.

        Delegates to task state port with optimistic locking.

        Args:
            task_id: ID of task to transition.
            from_status: Expected current status.
            to_status: Target status.
            halt_correlation_id: ID linking to halt event.
            transitioned_at: Timestamp of transition.

        Raises:
            ConcurrentModificationError: If task state changed.
        """
        await self._task_state.atomic_transition(
            task_id=task_id,
            from_status=from_status,
            to_status=to_status,
        )

    def _categorize_task(self, status: TaskStatus) -> TaskStateCategory:
        """Categorize task by consent state.

        Per FR24-FR26: Category determines halt behavior.

        Args:
            status: Current task status.

        Returns:
            TaskStateCategory for the status.
        """
        if status.is_pre_consent:
            return TaskStateCategory.PRE_CONSENT
        elif status.is_post_consent:
            return TaskStateCategory.POST_CONSENT
        else:
            return TaskStateCategory.TERMINAL

    async def _nullify_task(
        self,
        task_id: UUID,
        current_status: TaskStatus,
        target_status: TaskStatus | None,
        halt_correlation_id: UUID,
    ) -> TaskTransitionRecord:
        """Nullify a pre-consent task.

        Per FR24: Pre-consent tasks transition to nullified.
        No penalty to Cluster (they never consented).

        Args:
            task_id: ID of task to nullify.
            current_status: Current task status.
            target_status: Target status (NULLIFIED).
            halt_correlation_id: ID linking to halt event.

        Returns:
            TaskTransitionRecord with transition details.
        """
        transitioned_at = self._time.now()

        if target_status is None:
            # Should not happen for pre-consent, but handle gracefully
            return self._create_failed_record(
                task_id=task_id,
                previous_status=current_status.value,
                halt_correlation_id=halt_correlation_id,
                error_message="No halt target for pre-consent status",
            )

        try:
            # Atomic transition
            await self._task_state.atomic_transition(
                task_id=task_id,
                from_status=current_status.value,
                to_status=target_status.value,
            )

            # Emit event
            await self._emit_nullified_event(
                task_id=task_id,
                previous_status=current_status.value,
                halt_correlation_id=halt_correlation_id,
                transitioned_at=transitioned_at,
            )

            logger.debug(
                "task_nullified_on_halt",
                task_id=str(task_id),
                previous_status=current_status.value,
                halt_correlation_id=str(halt_correlation_id),
            )

            return TaskTransitionRecord(
                task_id=task_id,
                previous_status=current_status.value,
                new_status=target_status.value,
                category=TaskStateCategory.PRE_CONSENT,
                transition_type=HaltTransitionType.NULLIFIED,
                transitioned_at=transitioned_at,
                halt_correlation_id=halt_correlation_id,
            )

        except ConcurrentModificationError as e:
            logger.warning(
                "task_nullify_concurrent_modification",
                task_id=str(task_id),
                expected=current_status.value,
                error=str(e),
                halt_correlation_id=str(halt_correlation_id),
            )
            return TaskTransitionRecord(
                task_id=task_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                category=TaskStateCategory.PRE_CONSENT,
                transition_type=HaltTransitionType.FAILED,
                transitioned_at=transitioned_at,
                halt_correlation_id=halt_correlation_id,
                error_message=str(e),
            )

    async def _quarantine_task(
        self,
        task_id: UUID,
        current_status: TaskStatus,
        target_status: TaskStatus | None,
        halt_correlation_id: UUID,
    ) -> TaskTransitionRecord:
        """Quarantine a post-consent task.

        Per FR25: Post-consent tasks transition to quarantined.
        Preserves work for review after halt resolution.

        Args:
            task_id: ID of task to quarantine.
            current_status: Current task status.
            target_status: Target status (QUARANTINED).
            halt_correlation_id: ID linking to halt event.

        Returns:
            TaskTransitionRecord with transition details.
        """
        transitioned_at = self._time.now()

        if target_status is None:
            return self._create_failed_record(
                task_id=task_id,
                previous_status=current_status.value,
                halt_correlation_id=halt_correlation_id,
                error_message="No halt target for post-consent status",
            )

        try:
            # Atomic transition
            await self._task_state.atomic_transition(
                task_id=task_id,
                from_status=current_status.value,
                to_status=target_status.value,
            )

            # Emit event
            await self._emit_quarantined_event(
                task_id=task_id,
                previous_status=current_status.value,
                halt_correlation_id=halt_correlation_id,
                transitioned_at=transitioned_at,
            )

            logger.debug(
                "task_quarantined_on_halt",
                task_id=str(task_id),
                previous_status=current_status.value,
                halt_correlation_id=str(halt_correlation_id),
            )

            return TaskTransitionRecord(
                task_id=task_id,
                previous_status=current_status.value,
                new_status=target_status.value,
                category=TaskStateCategory.POST_CONSENT,
                transition_type=HaltTransitionType.QUARANTINED,
                transitioned_at=transitioned_at,
                halt_correlation_id=halt_correlation_id,
            )

        except ConcurrentModificationError as e:
            logger.warning(
                "task_quarantine_concurrent_modification",
                task_id=str(task_id),
                expected=current_status.value,
                error=str(e),
                halt_correlation_id=str(halt_correlation_id),
            )
            return TaskTransitionRecord(
                task_id=task_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                category=TaskStateCategory.POST_CONSENT,
                transition_type=HaltTransitionType.FAILED,
                transitioned_at=transitioned_at,
                halt_correlation_id=halt_correlation_id,
                error_message=str(e),
            )

    async def _preserve_task(
        self,
        task_id: UUID,
        current_status: TaskStatus,
        halt_correlation_id: UUID,
    ) -> TaskTransitionRecord:
        """Preserve a terminal task (no state change).

        Per FR26: Terminal tasks remain unchanged.
        Emit audit event to record the preservation.

        Args:
            task_id: ID of task to preserve.
            current_status: Current task status (terminal).
            halt_correlation_id: ID linking to halt event.

        Returns:
            TaskTransitionRecord with preservation details.
        """
        transitioned_at = self._time.now()

        # No state transition needed - just emit audit event
        await self._emit_preserved_event(
            task_id=task_id,
            status=current_status.value,
            halt_correlation_id=halt_correlation_id,
            recorded_at=transitioned_at,
        )

        logger.debug(
            "task_preserved_on_halt",
            task_id=str(task_id),
            status=current_status.value,
            halt_correlation_id=str(halt_correlation_id),
        )

        return TaskTransitionRecord(
            task_id=task_id,
            previous_status=current_status.value,
            new_status=current_status.value,
            category=TaskStateCategory.TERMINAL,
            transition_type=HaltTransitionType.PRESERVED,
            transitioned_at=transitioned_at,
            halt_correlation_id=halt_correlation_id,
        )

    def _create_failed_record(
        self,
        task_id: UUID,
        previous_status: str,
        halt_correlation_id: UUID,
        error_message: str,
    ) -> TaskTransitionRecord:
        """Create a failed transition record.

        Args:
            task_id: ID of task that failed.
            previous_status: Status when failure occurred.
            halt_correlation_id: ID linking to halt event.
            error_message: Error description.

        Returns:
            TaskTransitionRecord with FAILED transition type.
        """
        return TaskTransitionRecord(
            task_id=task_id,
            previous_status=previous_status,
            new_status=previous_status,
            category=TaskStateCategory.TERMINAL,  # Unknown category
            transition_type=HaltTransitionType.FAILED,
            transitioned_at=self._time.now(),
            halt_correlation_id=halt_correlation_id,
            error_message=error_message,
        )

    async def _emit_nullified_event(
        self,
        task_id: UUID,
        previous_status: str,
        halt_correlation_id: UUID,
        transitioned_at: datetime,
    ) -> None:
        """Emit executive.task.nullified_on_halt event.

        Per AC6: Events include halt correlation ID.

        Args:
            task_id: ID of nullified task.
            previous_status: Status before nullification.
            halt_correlation_id: ID linking to halt event.
            transitioned_at: When transition occurred.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.nullified_on_halt",
            timestamp=transitioned_at,
            actor_id="system",
            trace_id=str(halt_correlation_id),
            payload={
                "task_id": str(task_id),
                "previous_state": previous_status,
                "new_state": TaskStatus.NULLIFIED.value,
                "halt_correlation_id": str(halt_correlation_id),
                "reason": "system_halt_pre_consent",
                "transitioned_at": transitioned_at.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        await self._ledger.append_event(event)

    async def _emit_quarantined_event(
        self,
        task_id: UUID,
        previous_status: str,
        halt_correlation_id: UUID,
        transitioned_at: datetime,
    ) -> None:
        """Emit executive.task.quarantined_on_halt event.

        Per AC6: Events include halt correlation ID.

        Args:
            task_id: ID of quarantined task.
            previous_status: Status before quarantine.
            halt_correlation_id: ID linking to halt event.
            transitioned_at: When transition occurred.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.quarantined_on_halt",
            timestamp=transitioned_at,
            actor_id="system",
            trace_id=str(halt_correlation_id),
            payload={
                "task_id": str(task_id),
                "previous_state": previous_status,
                "new_state": TaskStatus.QUARANTINED.value,
                "halt_correlation_id": str(halt_correlation_id),
                "reason": "system_halt_post_consent",
                "work_preserved": True,
                "transitioned_at": transitioned_at.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        await self._ledger.append_event(event)

    async def _emit_preserved_event(
        self,
        task_id: UUID,
        status: str,
        halt_correlation_id: UUID,
        recorded_at: datetime,
    ) -> None:
        """Emit executive.task.preserved_on_halt event.

        Per AC6: Events include halt correlation ID.
        Per AC8: Audit trail preserved for terminal tasks.

        Args:
            task_id: ID of preserved task.
            status: Terminal status (unchanged).
            halt_correlation_id: ID linking to halt event.
            recorded_at: When preservation was recorded.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.preserved_on_halt",
            timestamp=recorded_at,
            actor_id="system",
            trace_id=str(halt_correlation_id),
            payload={
                "task_id": str(task_id),
                "state": status,
                "halt_correlation_id": str(halt_correlation_id),
                "reason": "terminal_state_unchanged",
                "recorded_at": recorded_at.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        await self._ledger.append_event(event)

    async def _emit_transition_summary(
        self,
        result: HaltTransitionResult,
    ) -> None:
        """Emit summary event for all halt transitions.

        Per AC8: Audit trail preserved.

        Args:
            result: Aggregated transition result.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.halt_transitions_completed",
            timestamp=result.completed_at,
            actor_id="system",
            trace_id=str(result.halt_correlation_id),
            payload=result.to_dict(),
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        await self._ledger.append_event(event)
