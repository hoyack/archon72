"""Notification publisher port for push notifications (Story 4.8, Task 5).

Port interface for publishing event notifications to external observers.

Constitutional Constraints:
- SR-9: Observer push notifications for breach events.
- RT-5: Breach events pushed to multiple channels.
- CT-11: Silent failure destroys legitimacy - delivery must be logged.
- CT-12: Witnessing creates accountability - notification events have attribution.
"""

from typing import Protocol

from src.domain.events.event import Event


class NotificationPublisherPort(Protocol):
    """Port for publishing event notifications (SR-9).

    Per RT-5: Breach events pushed to multiple channels.
    Per CT-11: Delivery confirmation must be logged.

    Implementations should push notifications to all registered
    channels (SSE connections and webhook subscriptions).
    """

    async def notify_event(self, event: Event) -> None:
        """Publish notification for an event.

        Called when a notifiable event (breach, halt, fork) occurs.
        Per RT-5: Must push to ALL registered channels.

        Args:
            event: The event to notify about.

        Note:
            - Non-notifiable event types should be silently ignored
            - Delivery failures should be logged but not raised
            - Per CT-11: All delivery attempts must be logged
        """
        ...
