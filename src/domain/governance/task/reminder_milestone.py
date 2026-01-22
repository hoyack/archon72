"""Reminder milestone domain enum for task reminders."""

from __future__ import annotations

from enum import Enum


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


__all__ = ["ReminderMilestone"]
