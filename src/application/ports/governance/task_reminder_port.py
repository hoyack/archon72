"""TaskReminderPort - Interface for neutral task reminder operations.

Story: consent-gov-2.6: Task Reminders

This port defines the contract for sending neutral reminders at TTL milestones.
All reminders MUST pass through the Coercion Filter before delivery.

Constitutional Guarantees:
- All reminders pass through Coercion Filter (FR11, AC3)
- Reminder content is informational, NOT pressuring (AC4)
- Duplicate reminders prevented for same milestone (AC9)
- Events emitted for each reminder sent (AC5)

Reminder Milestones:
- 50% TTL (36h for 72h TTL): First reminder
- 90% TTL (64.8h for 72h TTL): Final reminder

References:
- FR11: Neutral reminders at TTL milestones
- NFR-CONST-05: No path bypasses Coercion Filter
- NFR-UX-01: Anti-engagement (neutral tone)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable
from uuid import UUID


class ReminderMilestone(str, Enum):
    """TTL milestone percentages for reminders.

    These milestones define when reminders should be sent.
    Values represent percentage of TTL elapsed.
    """

    HALFWAY = "50"
    """50% of TTL elapsed - first reminder."""

    FINAL = "90"
    """90% of TTL elapsed - final reminder."""

    @property
    def percentage(self) -> int:
        """Get the percentage value as an integer."""
        return int(self.value)

    @property
    def threshold(self) -> float:
        """Get the threshold as a decimal for calculations."""
        return self.percentage / 100.0


@dataclass(frozen=True)
class ReminderRecord:
    """Tracks which reminders have been sent for a task.

    Used to prevent duplicate reminders for the same milestone.

    Attributes:
        task_id: ID of the task this record tracks.
        cluster_id: ID of the Cluster to receive reminders.
        milestones_sent: Set of milestones already sent.
        created_at: When the tracking record was created.
        last_sent_at: Timestamp of last reminder sent.
    """

    task_id: UUID
    cluster_id: str
    milestones_sent: frozenset[ReminderMilestone] = field(default_factory=frozenset)
    created_at: datetime | None = None
    last_sent_at: datetime | None = None

    def with_milestone_sent(
        self,
        milestone: ReminderMilestone,
        sent_at: datetime,
    ) -> ReminderRecord:
        """Create new record with milestone marked as sent.

        Args:
            milestone: The milestone that was sent.
            sent_at: When the reminder was sent.

        Returns:
            New ReminderRecord with updated milestones_sent.
        """
        new_milestones = self.milestones_sent | frozenset({milestone})
        return ReminderRecord(
            task_id=self.task_id,
            cluster_id=self.cluster_id,
            milestones_sent=new_milestones,
            created_at=self.created_at,
            last_sent_at=sent_at,
        )

    def has_milestone_sent(self, milestone: ReminderMilestone) -> bool:
        """Check if a milestone reminder was already sent.

        Args:
            milestone: The milestone to check.

        Returns:
            True if reminder already sent for this milestone.
        """
        return milestone in self.milestones_sent


@dataclass(frozen=True)
class ReminderSendResult:
    """Result of attempting to send a single reminder.

    Attributes:
        task_id: ID of the task.
        milestone: The milestone this reminder was for.
        sent: Whether the reminder was actually sent.
        filter_accepted: Whether the Coercion Filter accepted the content.
        filter_decision_id: UUID of the filter decision for audit.
        blocked_reason: Reason if filter blocked/rejected.
        sent_at: Timestamp when sent (if successful).
    """

    task_id: UUID
    milestone: ReminderMilestone
    sent: bool
    filter_accepted: bool
    filter_decision_id: UUID | None = None
    blocked_reason: str | None = None
    sent_at: datetime | None = None


@dataclass(frozen=True)
class ReminderProcessingResult:
    """Result of processing all pending reminders.

    Contains lists of results for each milestone type processed.

    Attributes:
        halfway_results: Results for 50% TTL reminders.
        final_results: Results for 90% TTL reminders.
        skipped_actioned: Task IDs skipped because already actioned.
        skipped_duplicate: Task IDs skipped because milestone already sent.
        errors: List of (task_id, error_message) tuples for failures.
    """

    halfway_results: list[ReminderSendResult] = field(default_factory=list)
    final_results: list[ReminderSendResult] = field(default_factory=list)
    skipped_actioned: list[UUID] = field(default_factory=list)
    skipped_duplicate: list[UUID] = field(default_factory=list)
    errors: list[tuple[UUID, str]] = field(default_factory=list)

    @property
    def total_sent(self) -> int:
        """Total number of reminders successfully sent."""
        return sum(1 for r in self.halfway_results if r.sent) + sum(
            1 for r in self.final_results if r.sent
        )

    @property
    def total_blocked(self) -> int:
        """Total number of reminders blocked by filter."""
        return sum(1 for r in self.halfway_results if not r.filter_accepted) + sum(
            1 for r in self.final_results if not r.filter_accepted
        )

    @property
    def total_skipped(self) -> int:
        """Total number of reminders skipped."""
        return len(self.skipped_actioned) + len(self.skipped_duplicate)

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during processing."""
        return len(self.errors) > 0


@runtime_checkable
class ReminderTrackingPort(Protocol):
    """Port for tracking which reminders have been sent.

    This interface provides persistence for reminder tracking
    to prevent duplicate reminders for the same milestone.

    Per AC9: Duplicate reminders prevented for same milestone.
    """

    async def get_reminder_record(
        self,
        task_id: UUID,
    ) -> ReminderRecord | None:
        """Get the reminder tracking record for a task.

        Args:
            task_id: ID of the task.

        Returns:
            ReminderRecord if exists, None otherwise.
        """
        ...

    async def save_reminder_record(
        self,
        record: ReminderRecord,
    ) -> None:
        """Save or update a reminder tracking record.

        Args:
            record: The ReminderRecord to save.
        """
        ...

    async def has_milestone_sent(
        self,
        task_id: UUID,
        milestone: ReminderMilestone,
    ) -> bool:
        """Check if a milestone reminder was already sent.

        Convenience method that combines get + check.

        Args:
            task_id: ID of the task.
            milestone: The milestone to check.

        Returns:
            True if reminder already sent for this milestone.
        """
        ...

    async def mark_milestone_sent(
        self,
        task_id: UUID,
        cluster_id: str,
        milestone: ReminderMilestone,
        sent_at: datetime,
    ) -> None:
        """Mark a milestone as sent for a task.

        Creates or updates the tracking record.

        Args:
            task_id: ID of the task.
            cluster_id: ID of the Cluster.
            milestone: The milestone that was sent.
            sent_at: When the reminder was sent.
        """
        ...


@runtime_checkable
class TaskReminderPort(Protocol):
    """Port for sending neutral task reminders.

    This interface defines the contract for processing reminders
    at TTL milestones. All reminders MUST pass through Coercion Filter.

    Constitutional Guarantee:
    - All content passes through Coercion Filter (no bypass)
    - Reminders are informational, not pressuring
    - Duplicate prevention per milestone
    - Events emitted for each reminder

    Reminder Milestones:
    - 50% TTL: First reminder (informational)
    - 90% TTL: Final reminder (still neutral tone)

    Per FR11: Neutral reminders at TTL milestones.
    Per NFR-CONST-05: No path bypasses Coercion Filter.
    """

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
        ...

    async def send_milestone_reminder(
        self,
        task_id: UUID,
        milestone: ReminderMilestone,
    ) -> ReminderSendResult:
        """Send a reminder for a specific task and milestone.

        This method:
        1. Generates neutral reminder content
        2. Passes through Coercion Filter
        3. Sends to Cluster if accepted
        4. Emits event regardless of filter outcome
        5. Tracks milestone as sent if delivered

        Per AC3: Reminders MUST pass through Coercion Filter.
        Per AC8: Reminder uses FilteredContent type.

        Args:
            task_id: ID of the task.
            milestone: Which milestone reminder to send.

        Returns:
            ReminderSendResult with outcome details.

        Raises:
            TaskNotFoundError: If task does not exist.
        """
        ...

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
        ...
