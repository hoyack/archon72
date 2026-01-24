"""TaskReminderService - Sends neutral reminders at TTL milestones.

Story: consent-gov-2.6: Task Reminders

This service implements the TaskReminderPort interface for sending
neutral reminders to Clusters at TTL milestones. All reminders MUST
pass through the Coercion Filter before delivery.

Constitutional Guarantees:
- All reminders pass through Coercion Filter (FR11, AC3)
- Reminder content is informational, NOT pressuring (AC4)
- Duplicate reminders prevented for same milestone (AC9)
- Events emitted for each reminder (AC5)
- Uses FilteredContent type (AC8)

Reminder Milestones:
- 50% TTL (36h for 72h TTL): First reminder
- 90% TTL (64.8h for 72h TTL): Final reminder

Golden Rule: Failure is allowed; silence is not.
Every reminder attempt MUST emit an event regardless of filter outcome.

References:
- FR11: Neutral reminders at TTL milestones
- NFR-CONST-05: No path bypasses Coercion Filter
- NFR-UX-01: Anti-engagement (neutral tone)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from src.application.ports.governance.coercion_filter_port import (
    CoercionFilterPort,
    MessageType,
)
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.governance.participant_message_port import (
    ParticipantMessagePort,
)
from src.application.ports.governance.task_activation_port import TaskStatePort
from src.application.ports.governance.task_reminder_port import (
    ReminderProcessingResult,
    ReminderSendResult,
    ReminderTrackingPort,
    TaskReminderPort,
)
from src.application.ports.governance.task_timeout_port import TaskTimeoutConfig
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.filter import FilterDecision, FilterResult
from src.domain.governance.task.reminder_milestone import ReminderMilestone
from src.domain.governance.task.reminder_template import (
    get_template_for_milestone,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus
from src.domain.ports.time_authority import TimeAuthorityProtocol

logger = logging.getLogger(__name__)


# System actor constant - reminders are SYSTEM actions
SYSTEM_ACTOR = "system"

# Content type for filtering
CONTENT_TYPE_REMINDER = "task_reminder"


class TaskReminderService(TaskReminderPort):
    """Service for sending neutral task reminders at TTL milestones.

    This service handles reminder generation, filtering, and delivery.
    It enforces the constitutional guarantee that all reminders pass
    through the Coercion Filter.

    Constitutional Guarantees:
    - Every reminder passes through Coercion Filter (no bypass)
    - Content is neutral and informational
    - Events emitted for all attempts (Golden Rule)
    - Duplicates prevented via tracking

    Attributes:
        _task_state: Port for task state queries.
        _filter: Port for Coercion Filter.
        _tracking: Port for reminder tracking.
        _messenger: Port for message delivery.
        _ledger: Port for event ledger.
        _time: Time authority for timestamps.
        _config: Timeout configuration for TTL values.
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        coercion_filter_port: CoercionFilterPort,
        reminder_tracking_port: ReminderTrackingPort,
        message_port: ParticipantMessagePort,
        ledger_port: GovernanceLedgerPort,
        time_authority: TimeAuthorityProtocol,
        config: TaskTimeoutConfig | None = None,
    ) -> None:
        """Initialize the TaskReminderService.

        Args:
            task_state_port: Port for task state queries.
            coercion_filter_port: Port for content filtering.
            reminder_tracking_port: Port for tracking sent reminders.
            message_port: Port for message delivery to Clusters.
            ledger_port: Port for event ledger operations.
            time_authority: Time authority for timestamps.
            config: Optional timeout configuration (defaults applied if None).
        """
        self._task_state = task_state_port
        self._filter = coercion_filter_port
        self._tracking = reminder_tracking_port
        self._messenger = message_port
        self._ledger = ledger_port
        self._time = time_authority
        self._config = config or TaskTimeoutConfig()

    async def process_all_reminders(self) -> ReminderProcessingResult:
        """Process all pending reminders across all tasks.

        This is the main entry point for reminder processing.
        It finds tasks at milestone thresholds and sends reminders.

        Flow:
        1. Find tasks at 50% TTL that haven't received halfway reminder
        2. Find tasks at 90% TTL that haven't received final reminder
        3. For each: generate content, filter, send if accepted
        4. Track sent milestones to prevent duplicates

        Constitutional Guarantee:
        - All reminders pass through Coercion Filter
        - No reminders sent if filter blocks
        - Events emitted for each reminder

        Returns:
            ReminderProcessingResult with all processing outcomes.
        """
        result = ReminderProcessingResult()
        errors: list[tuple[UUID, str]] = []

        # Process 50% TTL reminders
        try:
            halfway_results = await self._process_milestone(ReminderMilestone.HALFWAY)
            result = ReminderProcessingResult(
                halfway_results=halfway_results,
                final_results=result.final_results,
                skipped_actioned=result.skipped_actioned,
                skipped_duplicate=result.skipped_duplicate,
                errors=errors,
            )
        except Exception as e:
            logger.error(f"Error processing 50% TTL reminders: {e}")
            errors.append((UUID(int=0), f"halfway_processing: {e}"))

        # Process 90% TTL reminders
        try:
            final_results = await self._process_milestone(ReminderMilestone.FINAL)
            result = ReminderProcessingResult(
                halfway_results=result.halfway_results,
                final_results=final_results,
                skipped_actioned=result.skipped_actioned,
                skipped_duplicate=result.skipped_duplicate,
                errors=errors,
            )
        except Exception as e:
            logger.error(f"Error processing 90% TTL reminders: {e}")
            errors.append((UUID(int=0), f"final_processing: {e}"))

        if result.total_sent > 0:
            logger.info(
                f"Reminder processing complete: "
                f"{result.total_sent} sent, {result.total_blocked} blocked, "
                f"{result.total_skipped} skipped"
            )

        return result

    async def send_milestone_reminder(
        self,
        task_id: UUID,
        milestone: ReminderMilestone,
    ) -> ReminderSendResult:
        """Send a reminder for a specific task and milestone.

        This method:
        1. Retrieves task state
        2. Generates neutral reminder content
        3. Passes through Coercion Filter
        4. Sends to Cluster if accepted
        5. Emits event regardless of filter outcome
        6. Tracks milestone as sent if delivered

        Per AC3: Reminders MUST pass through Coercion Filter.
        Per AC8: Reminder uses FilteredContent type.

        Args:
            task_id: ID of the task.
            milestone: Which milestone reminder to send.

        Returns:
            ReminderSendResult with outcome details.
        """
        now = self._time.now()

        # Get task state
        task = await self._task_state.get_task(task_id)

        # Calculate remaining time
        ttl_remaining = self._calculate_ttl_remaining(task, now)

        # Generate reminder content from template
        template = get_template_for_milestone(milestone)
        reminder_content = template.format(
            task_id=str(task_id),
            ttl_remaining_hours=int(ttl_remaining.total_seconds() / 3600),
            cluster_id=task.cluster_id,
            earl_id=task.earl_id,
        )
        reminder_subject = template.format_subject(str(task_id))

        # MANDATORY: Pass through Coercion Filter
        filter_result = await self._filter_reminder_content(
            task=task,
            subject=reminder_subject,
            body=reminder_content,
            milestone=milestone,
        )

        # Determine if we can send based on FilterDecision
        filter_accepted = filter_result.decision == FilterDecision.ACCEPTED
        sent = False
        decision_id = uuid4()  # Generate a decision ID for audit trail

        if filter_accepted and filter_result.content is not None:
            # Send the filtered content
            try:
                await self._messenger.send_notification(
                    recipient_id=task.cluster_id or "",
                    subject=reminder_subject,
                    body=filter_result.content.content,
                    metadata={
                        "task_id": str(task_id),
                        "milestone": milestone.value,
                        "filter_decision_id": str(decision_id),
                    },
                )
                sent = True

                # Track the sent milestone
                await self._tracking.mark_milestone_sent(
                    task_id=task_id,
                    cluster_id=task.cluster_id or "",
                    milestone=milestone,
                    sent_at=now,
                )

            except Exception as e:
                logger.error(f"Failed to send reminder for task {task_id}: {e}")
                sent = False

        # Emit event - Golden Rule: always emit regardless of outcome
        await self._emit_reminder_event(
            task=task,
            milestone=milestone,
            filter_result=filter_result,
            sent=sent,
            timestamp=now,
            decision_id=decision_id,
        )

        # Determine blocked reason if not accepted
        blocked_reason = None
        if not filter_accepted:
            if filter_result.rejection_reason:
                blocked_reason = (
                    filter_result.rejection_guidance
                    or filter_result.rejection_reason.description
                )
            elif filter_result.violation_type:
                blocked_reason = (
                    filter_result.violation_details
                    or filter_result.violation_type.description
                )

        return ReminderSendResult(
            task_id=task_id,
            milestone=milestone,
            sent=sent,
            filter_accepted=filter_accepted,
            filter_decision_id=decision_id,
            blocked_reason=blocked_reason,
            sent_at=now if sent else None,
        )

    async def get_pending_reminders(
        self,
        milestone: ReminderMilestone,
    ) -> list[UUID]:
        """Get task IDs that need a reminder for this milestone.

        Finds tasks that:
        - Are in ROUTED status (awaiting acceptance)
        - Have reached the milestone threshold (50% or 90% TTL)
        - Have not yet received a reminder for this milestone
        - Have not already been actioned (accepted/declined)

        Per AC7: No reminder sent if task already responded to.
        Per AC9: No duplicate reminders for same milestone.

        Args:
            milestone: Which milestone to check for.

        Returns:
            List of task IDs needing reminders.
        """
        now = self._time.now()
        pending_ids: list[UUID] = []

        # Get all tasks in ROUTED state
        routed_tasks = await self._task_state.get_tasks_by_status(TaskStatus.ROUTED)

        for task in routed_tasks:
            # Check if task has reached milestone threshold
            if not self._is_at_milestone(task, milestone, now):
                continue

            # Check if milestone already sent
            if await self._tracking.has_milestone_sent(task.task_id, milestone):
                continue

            pending_ids.append(task.task_id)

        return pending_ids

    # =========================================================================
    # Private Methods - Milestone Processing
    # =========================================================================

    async def _process_milestone(
        self,
        milestone: ReminderMilestone,
    ) -> list[ReminderSendResult]:
        """Process all pending reminders for a specific milestone.

        Args:
            milestone: The milestone to process.

        Returns:
            List of ReminderSendResult for processed tasks.
        """
        pending_ids = await self.get_pending_reminders(milestone)
        results: list[ReminderSendResult] = []

        for task_id in pending_ids:
            try:
                result = await self.send_milestone_reminder(task_id, milestone)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Failed to process reminder for task {task_id} "
                    f"at {milestone.value}% TTL: {e}"
                )
                # Create error result
                results.append(
                    ReminderSendResult(
                        task_id=task_id,
                        milestone=milestone,
                        sent=False,
                        filter_accepted=False,
                        blocked_reason=str(e),
                    )
                )

        return results

    def _is_at_milestone(
        self,
        task: TaskState,
        milestone: ReminderMilestone,
        now: datetime,
    ) -> bool:
        """Check if task has reached the specified milestone.

        Args:
            task: The task state.
            milestone: The milestone to check.
            now: Current time.

        Returns:
            True if task has reached or passed the milestone.
        """
        elapsed = now - task.state_entered_at
        threshold_time = task.ttl * milestone.threshold

        return elapsed >= threshold_time

    def _calculate_ttl_remaining(
        self,
        task: TaskState,
        now: datetime,
    ) -> timedelta:
        """Calculate remaining TTL for a task.

        Args:
            task: The task state.
            now: Current time.

        Returns:
            Time remaining before TTL expires.
        """
        expiry_time = task.state_entered_at + task.ttl
        remaining = expiry_time - now

        # Don't return negative values
        if remaining < timedelta(0):
            return timedelta(0)

        return remaining

    # =========================================================================
    # Private Methods - Coercion Filter Integration
    # =========================================================================

    async def _filter_reminder_content(
        self,
        task: TaskState,
        subject: str,
        body: str,
        milestone: ReminderMilestone,
    ) -> FilterResult:
        """Pass reminder content through Coercion Filter.

        CONSTITUTIONAL GUARANTEE: No bypass path exists.
        All participant-facing content MUST pass through filter.

        Args:
            task: The task this reminder is for.
            subject: Email/notification subject.
            body: Reminder body text.
            milestone: The milestone this reminder is for.

        Returns:
            FilterResult with outcome and optional filtered content.
        """
        # Combine subject and body for filtering with new API
        combined_content = f"{subject}\n\n{body}"

        return await self._filter.filter_content(
            content=combined_content,
            message_type=MessageType.REMINDER,
        )

    # =========================================================================
    # Private Methods - Event Emission (Golden Rule Enforcement)
    # =========================================================================

    async def _emit_reminder_event(
        self,
        task: TaskState,
        milestone: ReminderMilestone,
        filter_result: FilterResult,
        sent: bool,
        timestamp: datetime,
        decision_id: UUID | None = None,
    ) -> None:
        """Emit executive.task.reminder_sent event.

        CONSTITUTIONAL GUARANTEE: Golden Rule enforcement.
        Every reminder attempt MUST emit an event, regardless of outcome.

        Per AC5: Event executive.task.reminder_sent emitted for each reminder.

        Args:
            task: The task this reminder is for.
            milestone: The milestone this reminder is for.
            filter_result: Result from Coercion Filter.
            sent: Whether the reminder was actually delivered.
            timestamp: Event timestamp.
            decision_id: The filter decision ID for audit trail.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.reminder_sent",
            timestamp=timestamp,
            actor_id=SYSTEM_ACTOR,
            trace_id=str(task.task_id),
            payload={
                "task_id": str(task.task_id),
                "cluster_id": task.cluster_id,
                "milestone_pct": milestone.percentage,
                "ttl_remaining_hours": int(
                    self._calculate_ttl_remaining(task, timestamp).total_seconds()
                    / 3600
                ),
                "filter_decision": filter_result.decision.value,
                "filter_decision_id": str(decision_id) if decision_id else str(uuid4()),
                "sent": sent,
                "sent_at": timestamp.isoformat() if sent else None,
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await self._ledger.append_event(event)


class TaskReminderScheduler:
    """Scheduler for periodic reminder processing.

    This scheduler runs the TaskReminderService at configured intervals
    in a non-blocking background task.

    Attributes:
        _reminder_service: The reminder service to run.
        _interval: How often to check for pending reminders.
        _running: Whether the scheduler is currently active.
        _task: The background asyncio task.
        _last_result: Result of the last processing run.
    """

    def __init__(
        self,
        reminder_service: TaskReminderPort,
        interval: timedelta | None = None,
    ) -> None:
        """Initialize the scheduler.

        Args:
            reminder_service: The reminder service to run periodically.
            interval: How often to check for reminders (default: 5 minutes).
        """
        self._reminder_service = reminder_service
        self._interval = interval or timedelta(minutes=5)
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_result: ReminderProcessingResult | None = None

    async def start(self) -> None:
        """Start the periodic reminder processing.

        Begins running reminder checks at the configured interval.
        This is non-blocking - the scheduler runs in a background task.
        """
        if self._running:
            logger.warning("TaskReminderScheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"TaskReminderScheduler started with interval {self._interval}")

    async def stop(self) -> None:
        """Stop the periodic reminder processing.

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

        logger.info("TaskReminderScheduler stopped")

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is currently running.

        Returns:
            True if scheduler is actively processing reminders.
        """
        return self._running

    @property
    def last_run_result(self) -> ReminderProcessingResult | None:
        """Get the result of the last processing run.

        Returns:
            ReminderProcessingResult from last run, or None if never run.
        """
        return self._last_result

    async def _run_loop(self) -> None:
        """Main processing loop - runs at configured interval."""
        interval_seconds = self._interval.total_seconds()

        while self._running:
            try:
                self._last_result = await self._reminder_service.process_all_reminders()

                if self._last_result.total_sent > 0:
                    logger.info(
                        f"Reminder processing: {self._last_result.total_sent} "
                        f"reminders sent"
                    )

            except Exception as e:
                logger.error(f"Error in reminder processing loop: {e}")

            # Wait for next interval
            await asyncio.sleep(interval_seconds)
