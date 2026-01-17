"""Unit tests for ReminderTemplate domain model.

Story: consent-gov-2.6: Task Reminders

These tests verify:
- Templates contain no banned coercive words
- Templates format correctly with placeholders
- Pre-defined templates are neutral
"""

from uuid import uuid4

import pytest

from src.application.ports.governance.task_reminder_port import ReminderMilestone
from src.domain.governance.task.reminder_template import (
    BANNED_WORDS,
    FINAL_TEMPLATE,
    HALFWAY_TEMPLATE,
    ReminderTemplate,
    get_template_for_milestone,
    validate_custom_template,
)


class TestReminderTemplateValidation:
    """Tests for template validation (banned words)."""

    def test_template_with_banned_word_urgent_raises(self) -> None:
        """Template with 'urgent' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ReminderTemplate(
                milestone=ReminderMilestone.HALFWAY,
                subject="Urgent: Task Update",
                body_template="This is an update.",
            )

        assert "urgent" in str(exc_info.value).lower()
        assert "NFR-UX-01" in str(exc_info.value)

    def test_template_with_banned_word_deadline_raises(self) -> None:
        """Template with 'deadline' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ReminderTemplate(
                milestone=ReminderMilestone.HALFWAY,
                subject="Task Update",
                body_template="The deadline is approaching.",
            )

        assert "deadline" in str(exc_info.value).lower()

    def test_template_with_banned_phrase_you_must_raises(self) -> None:
        """Template with 'you must' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ReminderTemplate(
                milestone=ReminderMilestone.HALFWAY,
                subject="Task Update",
                body_template="You must respond.",
            )

        assert "you must" in str(exc_info.value).lower()

    def test_template_with_banned_phrase_action_required_raises(self) -> None:
        """Template with 'action required' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ReminderTemplate(
                milestone=ReminderMilestone.HALFWAY,
                subject="Action Required",
                body_template="This is an update.",
            )

        assert "action required" in str(exc_info.value).lower()

    def test_template_with_banned_phrase_last_chance_raises(self) -> None:
        """Template with 'last chance' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ReminderTemplate(
                milestone=ReminderMilestone.FINAL,
                subject="Task Update",
                body_template="This is your last chance to respond.",
            )

        assert "last chance" in str(exc_info.value).lower()

    def test_template_with_banned_word_consequences_raises(self) -> None:
        """Template with 'consequences' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ReminderTemplate(
                milestone=ReminderMilestone.HALFWAY,
                subject="Task Update",
                body_template="There may be consequences.",
            )

        assert "consequences" in str(exc_info.value).lower()

    def test_valid_neutral_template_allowed(self) -> None:
        """Neutral template with no banned words is allowed."""
        template = ReminderTemplate(
            milestone=ReminderMilestone.HALFWAY,
            subject="Task Status Update",
            body_template="Time remaining: {ttl_remaining_hours} hours. "
            "You may respond at your convenience.",
        )

        assert template.milestone == ReminderMilestone.HALFWAY


class TestReminderTemplateFormat:
    """Tests for template formatting."""

    def test_format_replaces_task_id(self) -> None:
        """Format replaces task_id placeholder."""
        template = ReminderTemplate(
            milestone=ReminderMilestone.HALFWAY,
            subject="Update",
            body_template="Task: {task_id}",
        )

        task_id = str(uuid4())
        result = template.format(task_id=task_id, ttl_remaining_hours=36)

        assert task_id in result

    def test_format_replaces_ttl_remaining(self) -> None:
        """Format replaces ttl_remaining_hours placeholder."""
        template = ReminderTemplate(
            milestone=ReminderMilestone.HALFWAY,
            subject="Update",
            body_template="Time remaining: {ttl_remaining_hours} hours",
        )

        result = template.format(task_id="123", ttl_remaining_hours=36)

        assert "36 hours" in result

    def test_format_replaces_cluster_id_when_provided(self) -> None:
        """Format replaces cluster_id when provided."""
        template = ReminderTemplate(
            milestone=ReminderMilestone.HALFWAY,
            subject="Update",
            body_template="Cluster: {cluster_id}",
        )

        result = template.format(
            task_id="123",
            ttl_remaining_hours=36,
            cluster_id="cluster-abc",
        )

        assert "cluster-abc" in result

    def test_format_subject_replaces_task_id(self) -> None:
        """Format subject replaces task_id."""
        template = ReminderTemplate(
            milestone=ReminderMilestone.HALFWAY,
            subject="Update for {task_id}",
            body_template="Body",
        )

        result = template.format_subject(task_id="task-123")

        assert "task-123" in result


class TestPreDefinedTemplates:
    """Tests for pre-defined HALFWAY and FINAL templates."""

    def test_halfway_template_is_neutral(self) -> None:
        """HALFWAY_TEMPLATE contains no banned words."""
        # If it exists without error, it passed validation
        assert HALFWAY_TEMPLATE.milestone == ReminderMilestone.HALFWAY

    def test_final_template_is_neutral(self) -> None:
        """FINAL_TEMPLATE contains no banned words."""
        assert FINAL_TEMPLATE.milestone == ReminderMilestone.FINAL

    def test_halfway_template_contains_no_banned_words(self) -> None:
        """Double-check HALFWAY template content."""
        text = (HALFWAY_TEMPLATE.subject + " " + HALFWAY_TEMPLATE.body_template).lower()

        for banned in BANNED_WORDS:
            assert banned.lower() not in text, f"Found banned word: {banned}"

    def test_final_template_contains_no_banned_words(self) -> None:
        """Double-check FINAL template content."""
        text = (FINAL_TEMPLATE.subject + " " + FINAL_TEMPLATE.body_template).lower()

        for banned in BANNED_WORDS:
            assert banned.lower() not in text, f"Found banned word: {banned}"

    def test_halfway_template_mentions_no_action_required(self) -> None:
        """HALFWAY template indicates no action is obligatory."""
        text = HALFWAY_TEMPLATE.body_template.lower()
        assert "no action is obligatory" in text or "you may respond" in text

    def test_final_template_mentions_no_penalty(self) -> None:
        """FINAL template indicates no penalty for non-response."""
        text = FINAL_TEMPLATE.body_template.lower()
        assert "no penalty" in text or "carries no penalty" in text

    def test_halfway_template_formats_correctly(self) -> None:
        """HALFWAY template formats with all placeholders."""
        result = HALFWAY_TEMPLATE.format(
            task_id="abc-123",
            ttl_remaining_hours=36,
        )

        assert "abc-123" in result
        assert "36 hours" in result

    def test_final_template_formats_correctly(self) -> None:
        """FINAL template formats with all placeholders."""
        result = FINAL_TEMPLATE.format(
            task_id="xyz-789",
            ttl_remaining_hours=7,
        )

        assert "xyz-789" in result
        assert "7 hours" in result


class TestGetTemplateForMilestone:
    """Tests for get_template_for_milestone function."""

    def test_get_halfway_template(self) -> None:
        """Returns HALFWAY template for HALFWAY milestone."""
        template = get_template_for_milestone(ReminderMilestone.HALFWAY)

        assert template is HALFWAY_TEMPLATE

    def test_get_final_template(self) -> None:
        """Returns FINAL template for FINAL milestone."""
        template = get_template_for_milestone(ReminderMilestone.FINAL)

        assert template is FINAL_TEMPLATE


class TestValidateCustomTemplate:
    """Tests for validate_custom_template function."""

    def test_valid_text_returns_empty_list(self) -> None:
        """Valid text returns empty list."""
        result = validate_custom_template(
            "This is a neutral update. Time remaining: 36 hours."
        )

        assert result == []

    def test_text_with_urgent_returns_urgent(self) -> None:
        """Text with 'urgent' returns it in list."""
        result = validate_custom_template("This is urgent!")

        assert "urgent" in result

    def test_text_with_multiple_banned_returns_all(self) -> None:
        """Text with multiple banned words returns all."""
        result = validate_custom_template(
            "Urgent deadline! You must respond immediately."
        )

        assert "urgent" in result
        assert "deadline" in result
        assert "you must" in result
        assert "immediately" in result

    def test_case_insensitive_detection(self) -> None:
        """Detection is case insensitive."""
        result = validate_custom_template("URGENT! DEADLINE!")

        assert len(result) >= 2
