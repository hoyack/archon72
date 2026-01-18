"""TaskTimeoutService - Automatic task state transitions based on timeouts.

Story: consent-gov-2.5: Task TTL & Auto-Transitions

This service implements the TaskTimeoutPort interface for processing
automatic task state transitions when timeouts expire.

Constitutional Guarantees:
- Every timeout MUST emit an explicit event (no silent expiry)
- Auto-transitions use "system" as actor (no Cluster blame)
- NO penalty attribution on any timeout
- All transitions are witnessed in the ledger

Golden Rule: Failure is allowed; silence is not.

Timeout Scenarios:
1. Activation TTL (72h): ROUTED → DECLINED (ttl_expired)
2. Acceptance Inactivity (48h): ACCEPTED → IN_PROGRESS (auto_started)
3. Reporting Timeout (7d): IN_PROGRESS → QUARANTINED (reporting_timeout)

References:
- FR8: Auto-decline after TTL expiration with no failure attribution
- FR9: Auto-transition accepted → in_progress after inactivity
- FR10: Auto-quarantine tasks exceeding reporting timeout
- NFR-CONSENT-01: TTL expiration → declined state
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from uuid import UUID, uuid4

from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.governance.task_activation_port import TaskStatePort
from src.application.ports.governance.task_timeout_port import (
    TaskTimeoutConfig,
    TaskTimeoutPort,
    TimeoutProcessingResult,
    TimeoutSchedulerPort,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.task.task_state import TaskState, TaskStatus

logger = logging.getLogger(__name__)


# System actor constant - timeouts are SYSTEM actions, not Cluster actions
SYSTEM_ACTOR = "system"


class TaskTimeoutService(TaskTimeoutPort):
    """Service for automatic task timeout processing.

    This service handles all automatic task state transitions based on
    configurable timeouts. It enforces the Golden Rule: "Failure is
    allowed; silence is not."

    Constitutional Guarantees:
    - Every timeout MUST emit an explicit event (no silent expiry)
    - Actor is always "system" (not the Cluster)
    - penalty_incurred is always false
    - All events are witnessed in the ledger

    Attributes:
        _task_state: Port for task state persistence.
        _ledger: Port for event ledger operations.
        _time: Time authority for timestamps.
        _config: Timeout configuration values.
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        ledger_port: GovernanceLedgerPort,
        time_authority: TimeAuthorityProtocol,
        config: TaskTimeoutConfig | None = None,
    ) -> None:
        """Initialize the TaskTimeoutService.

        Args:
            task_state_port: Port for task state persistence.
            ledger_port: Port for event ledger operations.
            time_authority: Time authority for timestamps.
            config: Optional timeout configuration (defaults applied if None).
        """
        self._task_state = task_state_port
        self._ledger = ledger_port
        self._time = time_authority
        self._config = config or TaskTimeoutConfig()

    async def process_all_timeouts(self) -> TimeoutProcessingResult:
        """Process all timeout scenarios in one batch.

        This is the main entry point for timeout processing.
        It processes all three timeout scenarios and aggregates results.

        Constitutional Guarantee:
        - All transitions emit events with "system" as actor
        - NO penalty attribution on any transition
        - No silent expirations - every timeout is witnessed

        Returns:
            TimeoutProcessingResult with lists of transitioned task IDs.
        """
        result = TimeoutProcessingResult()

        # Process each timeout type, capturing errors
        try:
            declined = await self.process_activation_timeouts()
            result = TimeoutProcessingResult(
                declined=declined,
                started=result.started,
                quarantined=result.quarantined,
                errors=result.errors,
            )
        except Exception as e:
            logger.error(f"Error processing activation timeouts: {e}")
            # Continue processing other timeouts

        try:
            started = await self.process_acceptance_timeouts()
            result = TimeoutProcessingResult(
                declined=result.declined,
                started=started,
                quarantined=result.quarantined,
                errors=result.errors,
            )
        except Exception as e:
            logger.error(f"Error processing acceptance timeouts: {e}")

        try:
            quarantined = await self.process_reporting_timeouts()
            result = TimeoutProcessingResult(
                declined=result.declined,
                started=result.started,
                quarantined=quarantined,
                errors=result.errors,
            )
        except Exception as e:
            logger.error(f"Error processing reporting timeouts: {e}")

        logger.info(
            f"Timeout processing complete: "
            f"{len(result.declined)} declined, "
            f"{len(result.started)} started, "
            f"{len(result.quarantined)} quarantined"
        )

        return result

    async def process_activation_timeouts(self) -> list[UUID]:
        """Process tasks past activation TTL.

        Finds all tasks in ROUTED state past their TTL and transitions
        them to DECLINED with reason "ttl_expired".

        Per FR8: Auto-decline after TTL expiration with no failure attribution.
        Per NFR-CONSENT-01: TTL expiration → declined state.

        Constitutional Guarantee:
        - Emits "executive.task.auto_declined" event
        - Actor is "system" (not the Cluster)
        - Reason is "ttl_expired" (not "failure")
        - penalty_incurred is false

        Returns:
            List of task IDs that were auto-declined.
        """
        now = self._time.now()
        declined_ids: list[UUID] = []

        # Query all tasks in ROUTED state
        # We need to check each task's TTL individually since they may differ
        routed_tasks = await self._get_tasks_by_status(TaskStatus.ROUTED)

        for task in routed_tasks:
            if task.is_ttl_expired(now):
                try:
                    await self._auto_decline(task, now)
                    declined_ids.append(task.task_id)
                except Exception as e:
                    logger.error(f"Failed to auto-decline task {task.task_id}: {e}")

        if declined_ids:
            logger.info(f"Auto-declined {len(declined_ids)} tasks (TTL expired)")

        return declined_ids

    async def process_acceptance_timeouts(self) -> list[UUID]:
        """Process tasks inactive after acceptance.

        Finds all tasks in ACCEPTED state past their inactivity timeout
        and transitions them to IN_PROGRESS with reason "acceptance_inactivity".

        Per FR9: Auto-transition accepted → in_progress after inactivity.
        Rationale: Cluster accepted, assumed to be working.

        Constitutional Guarantee:
        - Emits "executive.task.auto_started" event
        - Actor is "system" (not the Cluster)
        - This is procedural, not punitive

        Returns:
            List of task IDs that were auto-started.
        """
        now = self._time.now()
        started_ids: list[UUID] = []

        # Query all tasks in ACCEPTED state
        accepted_tasks = await self._get_tasks_by_status(TaskStatus.ACCEPTED)

        for task in accepted_tasks:
            # Check if past inactivity threshold (using state_entered_at)
            elapsed = now - task.state_entered_at
            if elapsed >= self._config.acceptance_inactivity:
                try:
                    await self._auto_start(task, now)
                    started_ids.append(task.task_id)
                except Exception as e:
                    logger.error(f"Failed to auto-start task {task.task_id}: {e}")

        if started_ids:
            logger.info(
                f"Auto-started {len(started_ids)} tasks (acceptance inactivity)"
            )

        return started_ids

    async def process_reporting_timeouts(self) -> list[UUID]:
        """Process tasks past reporting deadline.

        Finds all tasks in IN_PROGRESS state past their reporting timeout
        and transitions them to QUARANTINED with reason "reporting_timeout".

        Per FR10: Auto-quarantine tasks exceeding reporting timeout.
        Rationale: Silence isn't failure, it's unknown. Quarantine for investigation.

        Constitutional Guarantee:
        - Emits "executive.task.auto_quarantined" event
        - Actor is "system" (not the Cluster)
        - NO penalty attribution (silence isn't negligence)
        - penalty_incurred is false

        Returns:
            List of task IDs that were auto-quarantined.
        """
        now = self._time.now()
        quarantined_ids: list[UUID] = []

        # Query all tasks in IN_PROGRESS state
        in_progress_tasks = await self._get_tasks_by_status(TaskStatus.IN_PROGRESS)

        for task in in_progress_tasks:
            if task.is_reporting_expired(now):
                try:
                    await self._auto_quarantine(task, now)
                    quarantined_ids.append(task.task_id)
                except Exception as e:
                    logger.error(f"Failed to auto-quarantine task {task.task_id}: {e}")

        if quarantined_ids:
            logger.info(
                f"Auto-quarantined {len(quarantined_ids)} tasks (reporting timeout)"
            )

        return quarantined_ids

    def get_config(self) -> TaskTimeoutConfig:
        """Get the current timeout configuration.

        Returns:
            Current TaskTimeoutConfig with all timeout values.
        """
        return self._config

    # =========================================================================
    # Private Methods - Auto-Transition Implementations
    # =========================================================================

    async def _auto_decline(self, task: TaskState, now: datetime) -> None:
        """Auto-decline a task due to TTL expiration.

        Constitutional Guarantee:
        - Actor is "system" (not the Cluster)
        - Reason is "ttl_expired" (not "failure")
        - penalty_incurred is false
        - NO negative attribution recorded

        Args:
            task: The task to auto-decline.
            now: Current timestamp.
        """
        # Transition state
        new_task = task.transition(
            new_status=TaskStatus.DECLINED,
            transition_time=now,
            actor_id=SYSTEM_ACTOR,
            reason="ttl_expired",
        )
        await self._task_state.save_task(new_task)

        # Emit event - Golden Rule: no silent expiry
        await self._emit_auto_declined_event(task, now)

    async def _auto_start(self, task: TaskState, now: datetime) -> None:
        """Auto-start a task due to acceptance inactivity.

        Constitutional Guarantee:
        - Actor is "system" (not the Cluster)
        - This is procedural, not punitive
        - Cluster accepted, assumed working

        Args:
            task: The task to auto-start.
            now: Current timestamp.
        """
        # Transition state
        new_task = task.transition(
            new_status=TaskStatus.IN_PROGRESS,
            transition_time=now,
            actor_id=SYSTEM_ACTOR,
            reason="acceptance_inactivity",
        )
        await self._task_state.save_task(new_task)

        # Emit event - Golden Rule: no silent expiry
        await self._emit_auto_started_event(task, now)

    async def _auto_quarantine(self, task: TaskState, now: datetime) -> None:
        """Auto-quarantine a task due to reporting timeout.

        Constitutional Guarantee:
        - Actor is "system" (not the Cluster)
        - Reason is "reporting_timeout" (not "failure")
        - penalty_incurred is false
        - Quarantine for investigation, not punishment

        Args:
            task: The task to auto-quarantine.
            now: Current timestamp.
        """
        # Transition state
        new_task = task.transition(
            new_status=TaskStatus.QUARANTINED,
            transition_time=now,
            actor_id=SYSTEM_ACTOR,
            reason="reporting_timeout",
        )
        await self._task_state.save_task(new_task)

        # Emit event - Golden Rule: no silent expiry
        await self._emit_auto_quarantined_event(task, now)

    # =========================================================================
    # Private Methods - Event Emission (Golden Rule Enforcement)
    # =========================================================================

    async def _emit_auto_declined_event(
        self,
        task: TaskState,
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.auto_declined event.

        CONSTITUTIONAL GUARANTEE:
        - Actor is "system" (not the Cluster)
        - penalty_incurred is ALWAYS false
        - Reason is "ttl_expired" (not "failure")

        This event MUST be emitted for every TTL expiration.
        Golden Rule: Failure is allowed; silence is not.

        Args:
            task: The auto-declined task.
            timestamp: Event timestamp.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.auto_declined",
            timestamp=timestamp,
            actor_id=SYSTEM_ACTOR,  # NOT the Cluster
            trace_id=str(task.task_id),
            payload={
                "task_id": str(task.task_id),
                "cluster_id": task.cluster_id,  # For reference only
                "reason": "ttl_expired",  # NOT "failure" or "penalty"
                "ttl_hours": int(task.ttl.total_seconds() / 3600),
                "expired_at": timestamp.isoformat(),
                "penalty_incurred": False,  # CONSTITUTIONAL GUARANTEE
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)

    async def _emit_auto_started_event(
        self,
        task: TaskState,
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.auto_started event.

        CONSTITUTIONAL GUARANTEE:
        - Actor is "system" (not the Cluster)
        - This is procedural, not punitive

        This event MUST be emitted for every acceptance inactivity timeout.
        Golden Rule: Failure is allowed; silence is not.

        Args:
            task: The auto-started task.
            timestamp: Event timestamp.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.auto_started",
            timestamp=timestamp,
            actor_id=SYSTEM_ACTOR,
            trace_id=str(task.task_id),
            payload={
                "task_id": str(task.task_id),
                "cluster_id": task.cluster_id,
                "reason": "acceptance_inactivity",
                "inactivity_hours": int(
                    self._config.acceptance_inactivity.total_seconds() / 3600
                ),
                "started_at": timestamp.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)

    async def _emit_auto_quarantined_event(
        self,
        task: TaskState,
        timestamp: datetime,
    ) -> None:
        """Emit executive.task.auto_quarantined event.

        CONSTITUTIONAL GUARANTEE:
        - Actor is "system" (not the Cluster)
        - penalty_incurred is ALWAYS false
        - Reason is "reporting_timeout" (not "failure")

        This event MUST be emitted for every reporting timeout.
        Golden Rule: Failure is allowed; silence is not.

        Args:
            task: The auto-quarantined task.
            timestamp: Event timestamp.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.auto_quarantined",
            timestamp=timestamp,
            actor_id=SYSTEM_ACTOR,  # NOT the Cluster
            trace_id=str(task.task_id),
            payload={
                "task_id": str(task.task_id),
                "cluster_id": task.cluster_id,  # For reference only
                "reason": "reporting_timeout",  # NOT "failure" or "penalty"
                "timeout_days": int(
                    self._config.reporting_timeout.total_seconds() / 86400
                ),
                "quarantined_at": timestamp.isoformat(),
                "penalty_incurred": False,  # CONSTITUTIONAL GUARANTEE
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)

    # =========================================================================
    # Private Methods - Task Queries
    # =========================================================================

    async def _get_tasks_by_status(self, status: TaskStatus) -> list[TaskState]:
        """Get all tasks with a specific status.

        This is a helper to query tasks for timeout processing.
        The actual filtering by timeout is done after retrieval since
        each task may have different timeout values.

        Args:
            status: The status to filter by.

        Returns:
            List of TaskState objects in the specified status.
        """
        return await self._task_state.get_tasks_by_status(status)


class TaskTimeoutScheduler(TimeoutSchedulerPort):
    """Scheduler for periodic timeout processing.

    This scheduler runs the TaskTimeoutService at configured intervals
    in a non-blocking background task.

    Attributes:
        _timeout_service: The timeout service to run.
        _config: Timeout configuration (for interval).
        _running: Whether the scheduler is currently active.
        _task: The background asyncio task.
        _last_result: Result of the last processing run.
    """

    def __init__(
        self,
        timeout_service: TaskTimeoutPort,
        config: TaskTimeoutConfig | None = None,
    ) -> None:
        """Initialize the scheduler.

        Args:
            timeout_service: The timeout service to run periodically.
            config: Optional timeout configuration (uses service config if None).
        """
        self._timeout_service = timeout_service
        self._config = config or timeout_service.get_config()
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_result: TimeoutProcessingResult | None = None

    async def start(self) -> None:
        """Start the periodic timeout processing.

        Begins running timeout checks at the configured interval.
        This is non-blocking - the scheduler runs in a background task.
        """
        if self._running:
            logger.warning("TaskTimeoutScheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"TaskTimeoutScheduler started with interval "
            f"{self._config.processor_interval}"
        )

    async def stop(self) -> None:
        """Stop the periodic timeout processing.

        Gracefully stops the scheduler, completing any in-progress
        processing before returning.
        """
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("TaskTimeoutScheduler stopped")

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is currently running.

        Returns:
            True if scheduler is actively processing timeouts.
        """
        return self._running

    @property
    def last_run_result(self) -> TimeoutProcessingResult | None:
        """Get the result of the last processing run.

        Returns:
            TimeoutProcessingResult from last run, or None if never run.
        """
        return self._last_result

    async def _run_loop(self) -> None:
        """Main processing loop - runs at configured interval."""
        interval_seconds = self._config.processor_interval.total_seconds()

        while self._running:
            try:
                self._last_result = await self._timeout_service.process_all_timeouts()

                if self._last_result.total_processed > 0:
                    logger.info(
                        f"Timeout processing: "
                        f"{self._last_result.total_processed} tasks transitioned"
                    )

            except Exception as e:
                logger.error(f"Error in timeout processing loop: {e}")

            # Wait for next interval
            await asyncio.sleep(interval_seconds)
