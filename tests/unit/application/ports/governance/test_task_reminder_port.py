"""Unit tests for TaskReminderPort interface.

Story: consent-gov-2.6: Task Reminders

These tests verify the TaskReminderPort interface contract and
data structures are correctly defined.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.governance.task_reminder_port import (
    ReminderProcessingResult,
    ReminderRecord,
    ReminderSendResult,
)
from src.domain.governance.task.reminder_milestone import ReminderMilestone


class TestReminderMilestone:
    """Tests for ReminderMilestone enum."""

    def test_halfway_value_is_50(self) -> None:
        """HALFWAY milestone is 50%."""
        assert ReminderMilestone.HALFWAY.value == "50"

    def test_final_value_is_90(self) -> None:
        """FINAL milestone is 90%."""
        assert ReminderMilestone.FINAL.value == "90"

    def test_halfway_percentage(self) -> None:
        """HALFWAY percentage is 50."""
        assert ReminderMilestone.HALFWAY.percentage == 50

    def test_final_percentage(self) -> None:
        """FINAL percentage is 90."""
        assert ReminderMilestone.FINAL.percentage == 90

    def test_halfway_threshold(self) -> None:
        """HALFWAY threshold is 0.5."""
        assert ReminderMilestone.HALFWAY.threshold == 0.5

    def test_final_threshold(self) -> None:
        """FINAL threshold is 0.9."""
        assert ReminderMilestone.FINAL.threshold == 0.9


class TestReminderRecord:
    """Tests for ReminderRecord dataclass."""

    def test_create_empty_record(self) -> None:
        """Can create record with no milestones sent."""
        task_id = uuid4()
        record = ReminderRecord(
            task_id=task_id,
            cluster_id="cluster-1",
        )

        assert record.task_id == task_id
        assert record.cluster_id == "cluster-1"
        assert record.milestones_sent == frozenset()
        assert record.created_at is None
        assert record.last_sent_at is None

    def test_has_milestone_sent_empty(self) -> None:
        """Empty record has no milestones sent."""
        record = ReminderRecord(
            task_id=uuid4(),
            cluster_id="cluster-1",
        )

        assert not record.has_milestone_sent(ReminderMilestone.HALFWAY)
        assert not record.has_milestone_sent(ReminderMilestone.FINAL)

    def test_with_milestone_sent_returns_new_record(self) -> None:
        """Adding milestone returns new immutable record."""
        now = datetime.now(tz=timezone.utc)
        original = ReminderRecord(
            task_id=uuid4(),
            cluster_id="cluster-1",
        )

        updated = original.with_milestone_sent(ReminderMilestone.HALFWAY, now)

        # Original unchanged
        assert not original.has_milestone_sent(ReminderMilestone.HALFWAY)
        # New record has milestone
        assert updated.has_milestone_sent(ReminderMilestone.HALFWAY)
        assert updated.last_sent_at == now

    def test_with_multiple_milestones(self) -> None:
        """Can track multiple milestones."""
        now = datetime.now(tz=timezone.utc)
        later = now + timedelta(hours=12)

        record = ReminderRecord(
            task_id=uuid4(),
            cluster_id="cluster-1",
        )

        record = record.with_milestone_sent(ReminderMilestone.HALFWAY, now)
        record = record.with_milestone_sent(ReminderMilestone.FINAL, later)

        assert record.has_milestone_sent(ReminderMilestone.HALFWAY)
        assert record.has_milestone_sent(ReminderMilestone.FINAL)
        assert record.last_sent_at == later

    def test_record_is_frozen(self) -> None:
        """ReminderRecord is immutable."""
        record = ReminderRecord(
            task_id=uuid4(),
            cluster_id="cluster-1",
        )

        with pytest.raises(AttributeError):
            record.cluster_id = "other"  # type: ignore


class TestReminderSendResult:
    """Tests for ReminderSendResult dataclass."""

    def test_successful_send_result(self) -> None:
        """Can create successful send result."""
        now = datetime.now(tz=timezone.utc)
        task_id = uuid4()
        decision_id = uuid4()

        result = ReminderSendResult(
            task_id=task_id,
            milestone=ReminderMilestone.HALFWAY,
            sent=True,
            filter_accepted=True,
            filter_decision_id=decision_id,
            sent_at=now,
        )

        assert result.task_id == task_id
        assert result.milestone == ReminderMilestone.HALFWAY
        assert result.sent is True
        assert result.filter_accepted is True
        assert result.filter_decision_id == decision_id
        assert result.blocked_reason is None
        assert result.sent_at == now

    def test_blocked_send_result(self) -> None:
        """Can create blocked send result."""
        task_id = uuid4()
        decision_id = uuid4()

        result = ReminderSendResult(
            task_id=task_id,
            milestone=ReminderMilestone.FINAL,
            sent=False,
            filter_accepted=False,
            filter_decision_id=decision_id,
            blocked_reason="Coercive language detected",
        )

        assert result.sent is False
        assert result.filter_accepted is False
        assert result.blocked_reason == "Coercive language detected"
        assert result.sent_at is None


class TestReminderProcessingResult:
    """Tests for ReminderProcessingResult dataclass."""

    def test_empty_result(self) -> None:
        """Empty result has all zeros."""
        result = ReminderProcessingResult()

        assert result.total_sent == 0
        assert result.total_blocked == 0
        assert result.total_skipped == 0
        assert not result.has_errors

    def test_total_sent_counts_both_milestones(self) -> None:
        """Total sent counts reminders from both milestones."""
        result = ReminderProcessingResult(
            halfway_results=[
                ReminderSendResult(
                    task_id=uuid4(),
                    milestone=ReminderMilestone.HALFWAY,
                    sent=True,
                    filter_accepted=True,
                ),
                ReminderSendResult(
                    task_id=uuid4(),
                    milestone=ReminderMilestone.HALFWAY,
                    sent=True,
                    filter_accepted=True,
                ),
            ],
            final_results=[
                ReminderSendResult(
                    task_id=uuid4(),
                    milestone=ReminderMilestone.FINAL,
                    sent=True,
                    filter_accepted=True,
                ),
            ],
        )

        assert result.total_sent == 3

    def test_total_blocked_counts_filter_rejections(self) -> None:
        """Total blocked counts filter rejections."""
        result = ReminderProcessingResult(
            halfway_results=[
                ReminderSendResult(
                    task_id=uuid4(),
                    milestone=ReminderMilestone.HALFWAY,
                    sent=False,
                    filter_accepted=False,
                ),
            ],
            final_results=[
                ReminderSendResult(
                    task_id=uuid4(),
                    milestone=ReminderMilestone.FINAL,
                    sent=False,
                    filter_accepted=False,
                ),
            ],
        )

        assert result.total_blocked == 2

    def test_total_skipped_counts_actioned_and_duplicate(self) -> None:
        """Total skipped counts both reasons."""
        result = ReminderProcessingResult(
            skipped_actioned=[uuid4(), uuid4()],
            skipped_duplicate=[uuid4()],
        )

        assert result.total_skipped == 3

    def test_has_errors_true_when_errors_present(self) -> None:
        """has_errors is True when errors list non-empty."""
        result = ReminderProcessingResult(
            errors=[(uuid4(), "Some error")],
        )

        assert result.has_errors

    def test_result_is_frozen(self) -> None:
        """ReminderProcessingResult is immutable."""
        result = ReminderProcessingResult()

        with pytest.raises(AttributeError):
            result.errors = []  # type: ignore
