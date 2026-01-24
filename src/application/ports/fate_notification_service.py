"""Fate Notification Service port (Story 7.2, FR-7.3).

Protocol defining the interface for fate notification delivery.

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-12: Witnessing creates accountability - all notifications witnessed
- D7: RFC 7807 error responses for invalid preferences

Developer Golden Rules:
1. Protocol-based DI - all implementations through ports
2. Fire-and-forget delivery - don't block fate assignment
3. All notifications witnessed per CT-12
"""

from abc import abstractmethod
from datetime import datetime
from typing import Protocol
from uuid import UUID


class FateNotificationServiceProtocol(Protocol):
    """Protocol for fate notification service operations (FR-7.3).

    This service handles:
    - Notification delivery on fate assignment
    - Long-poll waiter notification
    - Witnessed event emission

    Constitutional Constraints:
    - FR-7.3: System SHALL notify Observer on fate assignment
    - CT-12: All notifications are witnessed events
    """

    @abstractmethod
    async def notify_fate_assigned(
        self,
        petition_id: UUID,
        fate: str,
        fate_reason: str | None,
        fate_timestamp: datetime,
        new_version: int,
    ) -> None:
        """Notify observers that a petition has been fated.

        This method triggers:
        1. Long-poll waiter notification via StatusTokenRegistry
        2. Webhook delivery (if configured)
        3. In-app notification storage (if configured)
        4. Event emission for witnessing (CT-12)

        Delivery failures are logged but DO NOT raise exceptions.
        This is fire-and-forget to avoid blocking fate assignment.

        Args:
            petition_id: UUID of the fated petition.
            fate: Terminal fate (ACKNOWLEDGED, REFERRED, ESCALATED, DEFERRED, NO_RESPONSE).
            fate_reason: Reason for fate (for ACKNOWLEDGED).
            fate_timestamp: When the fate was assigned.
            new_version: New state version for long-poll notification.
        """
        ...

    @abstractmethod
    async def schedule_retry(
        self,
        notification_id: UUID,
        petition_id: UUID,
        fate: str,
        fate_reason: str | None,
        fate_timestamp: datetime,
        channel: str,
        webhook_url: str | None,
        retry_count: int,
    ) -> None:
        """Schedule a retry for a failed notification.

        This is called when a notification delivery fails and
        should be retried according to the retry policy.

        Args:
            notification_id: UUID of the notification to retry.
            petition_id: UUID of the petition.
            fate: Terminal fate.
            fate_reason: Reason for fate.
            fate_timestamp: When the fate was assigned.
            channel: Notification channel (WEBHOOK, IN_APP).
            webhook_url: Webhook URL for WEBHOOK channel.
            retry_count: Current retry count (for backoff calculation).
        """
        ...

    @abstractmethod
    def get_pending_retry_count(self) -> int:
        """Get the count of notifications pending retry.

        Returns:
            Number of notifications in the retry queue.
        """
        ...
