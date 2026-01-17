"""MessageType enum for filter message classification.

This module defines the MessageType enum in the domain layer to avoid
circular imports between the application and domain layers.

All participant-facing messages must specify their type for appropriate
filtering rules.
"""

from __future__ import annotations

from enum import Enum


class MessageType(str, Enum):
    """Types of messages that can be filtered.

    All participant-facing messages must specify their type
    for appropriate filtering rules.

    Values:
        TASK_ACTIVATION: Task activation request from Earl to Cluster
        REMINDER: Reminder message about pending tasks
        NOTIFICATION: General notification to participant
        SYSTEM_MESSAGE: System-generated message
    """

    TASK_ACTIVATION = "task_activation"
    REMINDER = "reminder"
    NOTIFICATION = "notification"
    SYSTEM_MESSAGE = "system_message"

    @property
    def description(self) -> str:
        """Human-readable description of this message type."""
        descriptions = {
            MessageType.TASK_ACTIVATION: "Task activation request from Earl to Cluster",
            MessageType.REMINDER: "Reminder message about pending tasks",
            MessageType.NOTIFICATION: "General notification to participant",
            MessageType.SYSTEM_MESSAGE: "System-generated message",
        }
        return descriptions[self]
