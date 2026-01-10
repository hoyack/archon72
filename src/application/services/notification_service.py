"""Notification service for push notifications (Story 4.8, Task 2).

Service for managing and delivering push notifications to external observers.
Supports both webhook callbacks and Server-Sent Events (SSE) streams.

Constitutional Constraints:
- SR-9: Observer push notifications for breach events.
- RT-5: Breach events pushed to multiple channels (webhook + SSE).
- CT-11: Silent failure destroys legitimacy - delivery confirmation logged.
- CT-12: Witnessing creates accountability - attribution in notifications.
"""

import asyncio
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import httpx
import structlog

from src.application.dtos.observer import (
    NotificationEventType,
    NotificationPayload,
    WebhookSubscription,
    WebhookSubscriptionResponse,
)
from src.application.ports.notification_publisher import NotificationPublisherPort
from src.domain.events.event import Event

log = structlog.get_logger()


class NotificationService(NotificationPublisherPort):
    """Service for push notification delivery (SR-9).

    Per RT-5: Breach events pushed to multiple channels.
    Per CT-11: Delivery confirmation logged.
    Per CT-12: Attribution in all notifications.

    This service manages:
    - Webhook subscriptions (registration, delivery, retry)
    - SSE connections (registration, event streaming)
    - Event notification distribution to all channels
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        webhook_timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize notification service.

        Args:
            base_url: Base URL for event permalinks.
            webhook_timeout: Timeout for webhook delivery in seconds.
            max_retries: Maximum retry attempts for failed webhooks.
        """
        self._base_url = base_url
        self._webhook_timeout = webhook_timeout
        self._max_retries = max_retries

        # In-memory storage for subscriptions and connections
        # In production, these would be persisted to database
        self._subscriptions: dict[UUID, tuple[WebhookSubscriptionResponse, Optional[str]]] = {}
        self._sse_connections: dict[UUID, asyncio.Queue[NotificationPayload]] = {}

        # Map event types to notification types
        self._event_type_map: dict[str, NotificationEventType] = {
            "breach": NotificationEventType.BREACH,
            "halt": NotificationEventType.HALT,
            "fork_detected": NotificationEventType.FORK,
            "constitutional_crisis": NotificationEventType.CONSTITUTIONAL_CRISIS,
        }

    async def subscribe_webhook(
        self,
        subscription: WebhookSubscription,
    ) -> WebhookSubscriptionResponse:
        """Register a webhook subscription.

        Per SR-9: Register webhook for breach event notifications.
        Per RT-5: Breach events will be pushed to this webhook.

        Args:
            subscription: Webhook subscription details.

        Returns:
            Subscription response with ID and status.
        """
        subscription_id = uuid4()
        response = WebhookSubscriptionResponse(
            subscription_id=subscription_id,
            webhook_url=str(subscription.webhook_url),
            event_types=subscription.event_types,
            created_at=datetime.now(timezone.utc),
            status="active",
            test_sent=False,
        )

        # Store subscription with secret (secret not in response)
        self._subscriptions[subscription_id] = (response, subscription.secret)

        # Send test notification to verify webhook URL
        test_sent = await self._send_test_notification(
            subscription_id,
            str(subscription.webhook_url),
            subscription.secret,
        )
        response.test_sent = test_sent

        log.info(
            "webhook_subscribed",
            subscription_id=str(subscription_id),
            webhook_url=str(subscription.webhook_url),
            event_types=[et.value for et in subscription.event_types],
            test_sent=test_sent,
        )

        return response

    async def unsubscribe_webhook(self, subscription_id: UUID) -> bool:
        """Remove a webhook subscription.

        Args:
            subscription_id: ID of subscription to remove.

        Returns:
            True if subscription was found and removed.
        """
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            log.info("webhook_unsubscribed", subscription_id=str(subscription_id))
            return True
        return False

    def get_subscription(self, subscription_id: UUID) -> Optional[WebhookSubscriptionResponse]:
        """Get a subscription by ID.

        Args:
            subscription_id: ID of subscription to retrieve.

        Returns:
            Subscription response if found, None otherwise.
        """
        if subscription_id in self._subscriptions:
            return self._subscriptions[subscription_id][0]
        return None

    def register_sse_connection(
        self,
        event_types: list[NotificationEventType],
    ) -> tuple[UUID, "asyncio.Queue[NotificationPayload]"]:
        """Register a new SSE connection.

        Per SR-9: SSE for real-time breach event streaming.

        Args:
            event_types: Event types to receive.

        Returns:
            Tuple of (connection_id, event_queue).
        """
        connection_id = uuid4()
        queue: asyncio.Queue[NotificationPayload] = asyncio.Queue()
        self._sse_connections[connection_id] = queue

        log.info(
            "sse_connection_registered",
            connection_id=str(connection_id),
            event_types=[et.value for et in event_types],
        )

        return connection_id, queue

    def unregister_sse_connection(self, connection_id: UUID) -> None:
        """Remove an SSE connection.

        Args:
            connection_id: ID of connection to remove.
        """
        if connection_id in self._sse_connections:
            del self._sse_connections[connection_id]
            log.info("sse_connection_closed", connection_id=str(connection_id))

    def get_active_connection_count(self) -> int:
        """Get count of active SSE connections.

        Returns:
            Number of active SSE connections.
        """
        return len(self._sse_connections)

    def get_subscription_count(self) -> int:
        """Get count of webhook subscriptions.

        Returns:
            Number of active webhook subscriptions.
        """
        return len(self._subscriptions)

    async def notify_event(self, event: Event) -> None:
        """Publish notification for an event.

        Per RT-5: Pushes to ALL registered channels.
        Per CT-11: Log delivery confirmation for each channel.

        Args:
            event: The event to notify about.
        """
        # Determine notification type
        event_type_str = event.event_type.lower()
        notification_type = self._event_type_map.get(event_type_str)

        if notification_type is None:
            # Not a notifiable event type - silently ignore
            return

        # Create notification payload with attribution (CT-12)
        payload = NotificationPayload(
            notification_id=uuid4(),
            event_id=event.event_id,
            event_type=event_type_str,
            sequence=event.sequence,
            summary=self._create_summary(event),
            event_url=f"{self._base_url}/v1/observer/events/{event.event_id}",
            timestamp=datetime.now(timezone.utc),
            content_hash=event.content_hash,
        )

        # Push to all SSE connections
        sse_count = await self._push_to_sse_connections(payload, notification_type)

        # Push to all webhooks
        webhook_count = await self._push_to_webhooks(payload, notification_type)

        # Log delivery confirmation (CT-11)
        log.info(
            "notification_published",
            event_id=str(event.event_id),
            event_type=event_type_str,
            sequence=event.sequence,
            sse_connections=sse_count,
            webhook_subscriptions=webhook_count,
        )

    async def _push_to_sse_connections(
        self,
        payload: NotificationPayload,
        notification_type: NotificationEventType,
    ) -> int:
        """Push notification to all matching SSE connections.

        Args:
            payload: Notification payload to push.
            notification_type: Type of notification.

        Returns:
            Number of connections notified.
        """
        count = 0
        for connection_id, queue in list(self._sse_connections.items()):
            try:
                await queue.put(payload)
                count += 1
            except Exception as e:
                log.warning(
                    "sse_push_failed",
                    connection_id=str(connection_id),
                    error=str(e),
                )
        return count

    async def _push_to_webhooks(
        self,
        payload: NotificationPayload,
        notification_type: NotificationEventType,
    ) -> int:
        """Push notification to all matching webhooks with retry.

        Per CT-11: Log delivery confirmation for each webhook.

        Args:
            payload: Notification payload to push.
            notification_type: Type of notification.

        Returns:
            Number of webhooks successfully notified.
        """
        count = 0
        tasks = []

        for sub_id, (subscription, secret) in list(self._subscriptions.items()):
            # Check if subscription matches event type
            if (
                NotificationEventType.ALL in subscription.event_types
                or notification_type in subscription.event_types
            ):
                tasks.append(
                    self._deliver_webhook(sub_id, subscription.webhook_url, payload, secret)
                )

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            count = sum(1 for r in results if r is True)
        return count

    async def _deliver_webhook(
        self,
        subscription_id: UUID,
        webhook_url: str,
        payload: NotificationPayload,
        secret: Optional[str] = None,
    ) -> bool:
        """Deliver notification to a webhook with retry.

        Per CT-11: Log delivery confirmation.

        Args:
            subscription_id: ID of the subscription.
            webhook_url: URL to deliver to.
            payload: Notification payload.
            secret: Optional HMAC secret for signature.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        payload_json = payload.model_dump_json()
        headers = {"Content-Type": "application/json"}

        # Add HMAC signature if secret provided
        if secret:
            signature = hmac.new(
                secret.encode(),
                payload_json.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Archon72-Signature"] = f"sha256={signature}"

        async with httpx.AsyncClient() as client:
            for attempt in range(self._max_retries):
                try:
                    response = await client.post(
                        webhook_url,
                        content=payload_json,
                        headers=headers,
                        timeout=self._webhook_timeout,
                    )

                    if response.status_code < 300:
                        # Delivery confirmed (CT-11)
                        log.info(
                            "webhook_delivered",
                            subscription_id=str(subscription_id),
                            notification_id=str(payload.notification_id),
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        return True

                    log.warning(
                        "webhook_delivery_failed",
                        subscription_id=str(subscription_id),
                        status_code=response.status_code,
                        attempt=attempt + 1,
                    )

                except Exception as e:
                    log.warning(
                        "webhook_delivery_error",
                        subscription_id=str(subscription_id),
                        error=str(e),
                        attempt=attempt + 1,
                    )

                # Exponential backoff before retry
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        # All retries exhausted (CT-11: log failure)
        log.error(
            "webhook_delivery_exhausted",
            subscription_id=str(subscription_id),
            notification_id=str(payload.notification_id),
            max_retries=self._max_retries,
        )
        return False

    async def _send_test_notification(
        self,
        subscription_id: UUID,
        webhook_url: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Send test notification to verify webhook URL.

        Args:
            subscription_id: ID of the subscription.
            webhook_url: URL to test.
            secret: Optional HMAC secret.

        Returns:
            True if test notification was delivered successfully.
        """
        test_payload = NotificationPayload(
            notification_id=uuid4(),
            event_id=uuid4(),
            event_type="test",
            sequence=0,  # Test notifications use sequence 0
            summary="Test notification to verify webhook subscription",
            event_url=f"{self._base_url}/v1/observer/events/test",
            timestamp=datetime.now(timezone.utc),
            content_hash="0" * 64,  # Placeholder hash for test
        )

        return await self._deliver_webhook(
            subscription_id, webhook_url, test_payload, secret
        )

    def _create_summary(self, event: Event) -> str:
        """Create human-readable summary of event.

        Args:
            event: Event to summarize.

        Returns:
            Human-readable summary string.
        """
        summaries = {
            "breach": f"Constitutional breach detected at sequence {event.sequence}",
            "halt": f"System halt triggered at sequence {event.sequence}",
            "fork_detected": f"Fork detected at sequence {event.sequence}",
            "constitutional_crisis": f"Constitutional crisis declared at sequence {event.sequence}",
        }
        return summaries.get(
            event.event_type.lower(),
            f"Event {event.event_type} at sequence {event.sequence}",
        )
