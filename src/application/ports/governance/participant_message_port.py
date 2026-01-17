"""ParticipantMessagePort - Interface for participant-facing messages.

Story: consent-gov-2.2: Task Activation Request

This port defines the contract for sending messages to participants
(Clusters) via async protocol.

Constitutional Guarantees:
- Only accepts FilteredContent (not raw strings) - FR21
- Type system prevents bypass of Coercion Filter
- All messages use async protocol - NFR-INT-01

References:
- [Source: governance-architecture.md#Routing Architecture (Locked)]
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.governance.task.task_activation_request import FilteredContent


class MessageDeliveryError(Exception):
    """Raised when message delivery fails."""

    def __init__(
        self,
        participant_id: str,
        message_type: str,
        reason: str,
    ):
        self.participant_id = participant_id
        self.message_type = message_type
        self.reason = reason
        super().__init__(
            f"Failed to deliver {message_type} to {participant_id}: {reason}"
        )


@runtime_checkable
class ParticipantMessagePort(Protocol):
    """Port for sending messages to participants.

    All participant-facing messages go through this port.

    Constitutional Guarantee:
    - Only accepts FilteredContent (not raw strings)
    - Type system prevents bypass of Coercion Filter
    - Uses async protocol (email) per NFR-INT-01

    Message Types:
    - task_activation: Task activation request
    - task_reminder: Reminder for pending task
    - task_acknowledgment: Acknowledgment of submitted result
    """

    async def send_to_participant(
        self,
        participant_id: str,
        content: FilteredContent,
        message_type: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Send filtered content to participant via async protocol.

        Per NFR-INT-01, all Earl→Cluster communication uses async
        protocol (email). This method sends the filtered content
        to the participant.

        Constitutional Guarantee:
        - Content parameter MUST be FilteredContent, not raw strings
        - This is enforced by the type system

        Args:
            participant_id: ID of the participant (Cluster ID).
            content: FilteredContent that has passed through Coercion Filter.
            message_type: Type of message being sent.
            metadata: Additional metadata (e.g., task_id, earl_id).

        Returns:
            True if message was queued for delivery.

        Raises:
            MessageDeliveryError: If delivery fails.

        Note:
            The actual delivery may be asynchronous (email).
            This method returns after the message is queued.
        """
        ...

    async def get_delivery_status(
        self,
        message_id: str,
    ) -> str | None:
        """Get delivery status for a sent message.

        Args:
            message_id: ID of the message to check.

        Returns:
            Status string if found, None if not found.
            Possible values: "queued", "sent", "delivered", "failed"
        """
        ...
