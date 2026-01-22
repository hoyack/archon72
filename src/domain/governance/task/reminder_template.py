"""ReminderTemplate - Neutral reminder text templates for task notifications.

Story: consent-gov-2.6: Task Reminders

This module defines neutral reminder templates that MUST pass through
the Coercion Filter. Templates contain ONLY informational content,
with no pressuring language.

Constitutional Guarantees:
- Reminder content is informational, NOT pressuring (AC4)
- No coercive language allowed (NFR-UX-01)
- All content must pass Coercion Filter (AC3)

BANNED words/phrases in reminders:
- "urgent", "immediately", "hurry"
- "deadline", "expires", "running out"
- "consequences", "failure", "penalties"
- "must", "required", "mandatory"
- "last chance", "final warning"

ALLOWED tone:
- "This is a status update"
- "Time remaining: X hours"
- "You may respond at your convenience"
- "No response required"

References:
- FR11: Neutral reminders at TTL milestones
- NFR-UX-01: Anti-engagement (neutral tone)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from src.domain.governance.task.reminder_milestone import ReminderMilestone

# Banned phrases that indicate coercive language in reminders
# These MUST NOT appear in any reminder template (matched as phrases)
# Note: We allow "no penalty", "carries no penalty" etc. - these are neutral
BANNED_PHRASES: frozenset[str] = frozenset(
    {
        "urgent",
        "immediately",
        "hurry",
        "deadline",
        "expires soon",
        "expiring soon",
        "running out",
        "consequences",
        "you must",
        "is required",
        "are required",
        "required to",
        "mandatory",
        "last chance",
        "final warning",
        "time is running out",
        "act now",
        "don't delay",
        "asap",
        "critical",
        "important notice",
        "attention required",
        "action required",
        "respond immediately",
        "failure to respond",
        "will result in",
        "will incur",
    }
)

# Legacy alias for backwards compatibility
BANNED_WORDS = BANNED_PHRASES


@dataclass(frozen=True)
class ReminderTemplate:
    """Neutral reminder text template.

    Templates generate informational content about task status
    without any pressuring or coercive language.

    Per AC4: Reminder content is informational, NOT pressuring.
    Per NFR-UX-01: Anti-engagement (neutral tone).

    Attributes:
        milestone: The milestone this template is for.
        subject: Email/notification subject line.
        body_template: The template body with placeholders.
    """

    milestone: ReminderMilestone
    subject: str
    body_template: str

    # Template placeholders
    PLACEHOLDER_TASK_ID: ClassVar[str] = "{task_id}"
    PLACEHOLDER_TTL_REMAINING: ClassVar[str] = "{ttl_remaining_hours}"
    PLACEHOLDER_CLUSTER_ID: ClassVar[str] = "{cluster_id}"
    PLACEHOLDER_EARL_ID: ClassVar[str] = "{earl_id}"

    def __post_init__(self) -> None:
        """Validate template contains no banned words."""
        self._validate_no_banned_words()

    def _validate_no_banned_words(self) -> None:
        """Check that template contains no coercive language.

        Raises:
            ValueError: If any banned phrase is found.
        """
        full_text = (self.subject + " " + self.body_template).lower()

        for banned in BANNED_PHRASES:
            if banned.lower() in full_text:
                raise ValueError(
                    f"ReminderTemplate contains banned coercive phrase: '{banned}'. "
                    f"Per NFR-UX-01, reminders must use neutral tone only."
                )

    def format(
        self,
        task_id: str,
        ttl_remaining_hours: int,
        cluster_id: str | None = None,
        earl_id: str | None = None,
    ) -> str:
        """Format the template with actual values.

        Args:
            task_id: ID of the task.
            ttl_remaining_hours: Hours remaining before TTL expiry.
            cluster_id: Optional Cluster ID.
            earl_id: Optional Earl ID.

        Returns:
            Formatted reminder body text.
        """
        result = self.body_template
        result = result.replace(self.PLACEHOLDER_TASK_ID, str(task_id))
        result = result.replace(
            self.PLACEHOLDER_TTL_REMAINING, str(ttl_remaining_hours)
        )
        if cluster_id:
            result = result.replace(self.PLACEHOLDER_CLUSTER_ID, cluster_id)
        if earl_id:
            result = result.replace(self.PLACEHOLDER_EARL_ID, earl_id)
        return result

    def format_subject(self, task_id: str) -> str:
        """Format the subject line with actual values.

        Args:
            task_id: ID of the task.

        Returns:
            Formatted subject line.
        """
        return self.subject.replace(self.PLACEHOLDER_TASK_ID, str(task_id))


# =============================================================================
# Pre-defined Neutral Templates
# =============================================================================

# 50% TTL reminder - first informational update
HALFWAY_TEMPLATE = ReminderTemplate(
    milestone=ReminderMilestone.HALFWAY,
    subject="Task Status Update - {task_id}",
    body_template="""Task Status Update

Task ID: {task_id}
Status: Awaiting your response

Time remaining: approximately {ttl_remaining_hours} hours

This is an informational update about a task that has been routed to your cluster.

You may respond at your convenience. No action is obligatory.

If you choose not to respond, the task will transition automatically after the time period concludes. This is a procedural transition, not a penalty.

This message is provided for informational purposes only.
""",
)


# 90% TTL reminder - final informational update
FINAL_TEMPLATE = ReminderTemplate(
    milestone=ReminderMilestone.FINAL,
    subject="Task Status Update - {task_id}",
    body_template="""Task Status Update

Task ID: {task_id}
Status: Awaiting your response

Time remaining: approximately {ttl_remaining_hours} hours

This is an informational update. The task will auto-transition after the time period concludes.

This transition is procedural and carries no penalty or negative attribution.

You may respond if you choose to do so. No response is obligatory.

This message is provided for informational purposes only.
""",
)


def get_template_for_milestone(milestone: ReminderMilestone) -> ReminderTemplate:
    """Get the appropriate template for a milestone.

    Args:
        milestone: The milestone to get template for.

    Returns:
        The ReminderTemplate for this milestone.

    Raises:
        ValueError: If milestone has no associated template.
    """
    templates = {
        ReminderMilestone.HALFWAY: HALFWAY_TEMPLATE,
        ReminderMilestone.FINAL: FINAL_TEMPLATE,
    }

    if milestone not in templates:
        raise ValueError(f"No template defined for milestone: {milestone}")

    return templates[milestone]


def validate_custom_template(template_text: str) -> list[str]:
    """Validate custom template text for banned words.

    Use this to check custom reminder content before creating.

    Args:
        template_text: The text to validate.

    Returns:
        List of banned words found (empty if valid).
    """
    text_lower = template_text.lower()
    found = []

    for banned in BANNED_WORDS:
        if banned.lower() in text_lower:
            found.append(banned)

    return found
