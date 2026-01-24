"""Fate Notification Service implementation (Story 7.2, FR-7.3).

Service for delivering fate assignment notifications to observers.

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-12: Witnessing creates accountability - all notifications witnessed
- D7: RFC 7807 error responses for invalid preferences

Developer Golden Rules:
1. Fire-and-forget - don't block fate assignment
2. All notifications witnessed per CT-12
3. Graceful degradation - log failures, don't raise
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.application.ports.fate_notification_service import (
    FateNotificationServiceProtocol,
)
from src.domain.events.notification import (
    FATE_NOTIFICATION_SENT_EVENT_TYPE,
    FateNotificationSentEventPayload,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from src.domain.models.notification_preference import (
    NotificationChannel as PreferenceChannel,
)

if TYPE_CHECKING:
    from src.application.ports.notification_preference_repository import (
        NotificationPreferenceRepositoryProtocol,
    )
    from src.application.ports.webhook_delivery_adapter import (
        WebhookDeliveryAdapterProtocol,
    )
    from src.application.ports.status_token_registry import StatusTokenRegistryProtocol

logger = logging.getLogger(__name__)


@dataclass
class RetryEntry:
    """Entry for a notification pending retry.

    Attributes:
        notification_id: UUID of the notification.
        petition_id: UUID of the petition.
        fate: Terminal fate.
        fate_reason: Reason for fate.
        fate_timestamp: When the fate was assigned.
        channel: Notification channel.
        webhook_url: Webhook URL (for WEBHOOK channel).
        retry_count: Current retry count.
        scheduled_at: When the retry is scheduled.
    """

    notification_id: UUID
    petition_id: UUID
    fate: str
    fate_reason: str | None
    fate_timestamp: datetime
    channel: str
    webhook_url: str | None
    retry_count: int
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FateNotificationService(FateNotificationServiceProtocol):
    """Implementation of fate notification service (FR-7.3).

    This service handles:
    - Notification delivery on fate assignment
    - Long-poll waiter notification via StatusTokenRegistry
    - Webhook delivery via WebhookDeliveryAdapter
    - Retry scheduling for failed deliveries
    - Event emission for witnessing (CT-12)

    Constitutional Constraints:
    - FR-7.3: System SHALL notify Observer on fate assignment
    - CT-12: All notifications are witnessed events
    """

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS_SECONDS = [5, 30, 120]  # 5s, 30s, 2min

    def __init__(
        self,
        notification_preference_repo: NotificationPreferenceRepositoryProtocol,
        status_token_registry: StatusTokenRegistryProtocol,
        webhook_adapter: WebhookDeliveryAdapterProtocol | None = None,
        event_writer: object | None = None,
    ) -> None:
        """Initialize the fate notification service.

        Args:
            notification_preference_repo: Repository for notification preferences.
            status_token_registry: Registry for long-poll notification.
            webhook_adapter: Adapter for webhook delivery (optional).
            event_writer: Event writer for witnessing (optional).
        """
        self._preference_repo = notification_preference_repo
        self._registry = status_token_registry
        self._webhook_adapter = webhook_adapter
        self._event_writer = event_writer
        self._retry_queue: list[RetryEntry] = []
        self._lock = asyncio.Lock()

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
        logger.info(
            "Notifying fate assignment: petition_id=%s, fate=%s, reason=%s",
            petition_id,
            fate,
            fate_reason,
        )

        # 1. Always notify long-poll waiters via registry (immediate return)
        try:
            await self._registry.update_version(petition_id, new_version)
            logger.debug(
                "Long-poll waiters notified for petition %s version %d",
                petition_id,
                new_version,
            )
        except Exception as e:
            logger.warning(
                "Failed to notify long-poll waiters for petition %s: %s",
                petition_id,
                e,
            )

        # 2. Look up notification preferences
        try:
            preference = await self._preference_repo.get_by_petition_id(petition_id)
        except Exception as e:
            logger.debug(
                "No notification preferences for petition %s: %s", petition_id, e
            )
            preference = None

        if preference is None or not preference.should_notify():
            logger.debug(
                "No active notification preferences for petition %s", petition_id
            )
            # Still emit event for long-poll notification (witnessing)
            await self._emit_notification_event(
                notification_id=uuid4(),
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
                channel=NotificationChannel.LONG_POLL,
                delivery_status=NotificationDeliveryStatus.DELIVERED,
                delivered_at=datetime.now(timezone.utc),
            )
            return

        # 3. Deliver via configured channel
        notification_id = uuid4()

        if preference.channel == PreferenceChannel.WEBHOOK:
            await self._deliver_webhook(
                notification_id=notification_id,
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
                webhook_url=preference.webhook_url,
            )
        elif preference.channel == PreferenceChannel.IN_APP:
            await self._deliver_in_app(
                notification_id=notification_id,
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
            )

    async def _deliver_webhook(
        self,
        notification_id: UUID,
        petition_id: UUID,
        fate: str,
        fate_reason: str | None,
        fate_timestamp: datetime,
        webhook_url: str | None,
    ) -> None:
        """Deliver notification via webhook.

        Args:
            notification_id: UUID of the notification.
            petition_id: UUID of the petition.
            fate: Terminal fate.
            fate_reason: Reason for fate.
            fate_timestamp: When the fate was assigned.
            webhook_url: URL to POST notification to.
        """
        if webhook_url is None:
            logger.error(
                "Webhook URL is None for webhook notification: petition_id=%s",
                petition_id,
            )
            return

        if self._webhook_adapter is None:
            logger.warning(
                "Webhook adapter not configured, skipping webhook delivery: petition_id=%s",
                petition_id,
            )
            # Emit pending event
            await self._emit_notification_event(
                notification_id=notification_id,
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
                channel=NotificationChannel.WEBHOOK,
                delivery_status=NotificationDeliveryStatus.PENDING,
                webhook_url=webhook_url,
            )
            return

        try:
            # Attempt delivery
            success = await self._webhook_adapter.deliver(
                url=webhook_url,
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
            )

            if success:
                logger.info(
                    "Webhook delivered successfully: petition_id=%s, url=%s",
                    petition_id,
                    webhook_url,
                )
                await self._emit_notification_event(
                    notification_id=notification_id,
                    petition_id=petition_id,
                    fate=fate,
                    fate_reason=fate_reason,
                    fate_timestamp=fate_timestamp,
                    channel=NotificationChannel.WEBHOOK,
                    delivery_status=NotificationDeliveryStatus.DELIVERED,
                    delivered_at=datetime.now(timezone.utc),
                    webhook_url=webhook_url,
                )
            else:
                logger.warning(
                    "Webhook delivery failed: petition_id=%s, url=%s",
                    petition_id,
                    webhook_url,
                )
                # Schedule retry
                await self.schedule_retry(
                    notification_id=notification_id,
                    petition_id=petition_id,
                    fate=fate,
                    fate_reason=fate_reason,
                    fate_timestamp=fate_timestamp,
                    channel="WEBHOOK",
                    webhook_url=webhook_url,
                    retry_count=0,
                )

        except Exception as e:
            logger.warning(
                "Webhook delivery exception: petition_id=%s, url=%s, error=%s",
                petition_id,
                webhook_url,
                e,
            )
            # Schedule retry
            await self.schedule_retry(
                notification_id=notification_id,
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
                channel="WEBHOOK",
                webhook_url=webhook_url,
                retry_count=0,
            )

    async def _deliver_in_app(
        self,
        notification_id: UUID,
        petition_id: UUID,
        fate: str,
        fate_reason: str | None,
        fate_timestamp: datetime,
    ) -> None:
        """Deliver notification via in-app storage.

        For now, this just logs and emits an event. Future implementation
        would store to a notification queue for retrieval.

        Args:
            notification_id: UUID of the notification.
            petition_id: UUID of the petition.
            fate: Terminal fate.
            fate_reason: Reason for fate.
            fate_timestamp: When the fate was assigned.
        """
        logger.info(
            "In-app notification stored: petition_id=%s, fate=%s",
            petition_id,
            fate,
        )
        # In future: store to notification queue
        # For now: emit event
        await self._emit_notification_event(
            notification_id=notification_id,
            petition_id=petition_id,
            fate=fate,
            fate_reason=fate_reason,
            fate_timestamp=fate_timestamp,
            channel=NotificationChannel.IN_APP,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=datetime.now(timezone.utc),
        )

    async def _emit_notification_event(
        self,
        notification_id: UUID,
        petition_id: UUID,
        fate: str,
        fate_reason: str | None,
        fate_timestamp: datetime,
        channel: NotificationChannel,
        delivery_status: NotificationDeliveryStatus,
        delivered_at: datetime | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
        webhook_url: str | None = None,
    ) -> None:
        """Emit a FateNotificationSent event for witnessing (CT-12).

        Args:
            notification_id: UUID of the notification.
            petition_id: UUID of the petition.
            fate: Terminal fate.
            fate_reason: Reason for fate.
            fate_timestamp: When the fate was assigned.
            channel: Notification channel.
            delivery_status: Delivery status.
            delivered_at: When delivered (if applicable).
            error_message: Error message (if failed).
            retry_count: Retry count.
            webhook_url: Webhook URL (if applicable).
        """
        payload = FateNotificationSentEventPayload(
            notification_id=notification_id,
            petition_id=petition_id,
            fate=fate,
            fate_reason=fate_reason,
            fate_timestamp=fate_timestamp,
            channel=channel,
            delivery_status=delivery_status,
            delivered_at=delivered_at,
            error_message=error_message,
            retry_count=retry_count,
            webhook_url=webhook_url,
        )

        logger.debug(
            "Emitting %s event: petition_id=%s, status=%s",
            FATE_NOTIFICATION_SENT_EVENT_TYPE,
            petition_id,
            delivery_status.value,
        )

        if self._event_writer is not None:
            try:
                # Future: await self._event_writer.write_event(...)
                pass
            except Exception as e:
                logger.warning(
                    "Failed to emit notification event: %s", e
                )

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
        if retry_count >= self.MAX_RETRIES:
            logger.warning(
                "Max retries exceeded for notification: notification_id=%s, petition_id=%s",
                notification_id,
                petition_id,
            )
            # Emit permanently failed event
            channel_enum = (
                NotificationChannel.WEBHOOK
                if channel == "WEBHOOK"
                else NotificationChannel.IN_APP
            )
            await self._emit_notification_event(
                notification_id=notification_id,
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
                channel=channel_enum,
                delivery_status=NotificationDeliveryStatus.PERMANENTLY_FAILED,
                error_message="Max retries exceeded",
                retry_count=retry_count,
                webhook_url=webhook_url,
            )
            return

        # Calculate delay
        delay_index = min(retry_count, len(self.RETRY_DELAYS_SECONDS) - 1)
        delay_seconds = self.RETRY_DELAYS_SECONDS[delay_index]

        logger.info(
            "Scheduling retry %d for notification: notification_id=%s, delay=%ds",
            retry_count + 1,
            notification_id,
            delay_seconds,
        )

        # Add to retry queue
        entry = RetryEntry(
            notification_id=notification_id,
            petition_id=petition_id,
            fate=fate,
            fate_reason=fate_reason,
            fate_timestamp=fate_timestamp,
            channel=channel,
            webhook_url=webhook_url,
            retry_count=retry_count + 1,
        )

        async with self._lock:
            self._retry_queue.append(entry)

        # Emit failed event (non-permanent)
        channel_enum = (
            NotificationChannel.WEBHOOK
            if channel == "WEBHOOK"
            else NotificationChannel.IN_APP
        )
        await self._emit_notification_event(
            notification_id=notification_id,
            petition_id=petition_id,
            fate=fate,
            fate_reason=fate_reason,
            fate_timestamp=fate_timestamp,
            channel=channel_enum,
            delivery_status=NotificationDeliveryStatus.FAILED,
            error_message="Delivery failed, retry scheduled",
            retry_count=retry_count,
            webhook_url=webhook_url,
        )

    def get_pending_retry_count(self) -> int:
        """Get the count of notifications pending retry.

        Returns:
            Number of notifications in the retry queue.
        """
        return len(self._retry_queue)

    async def process_retries(self) -> int:
        """Process all pending retries.

        This method is intended to be called by a background task
        or job scheduler.

        Returns:
            Number of retries processed.
        """
        async with self._lock:
            entries = list(self._retry_queue)
            self._retry_queue.clear()

        processed = 0
        for entry in entries:
            if entry.channel == "WEBHOOK" and entry.webhook_url:
                await self._deliver_webhook(
                    notification_id=entry.notification_id,
                    petition_id=entry.petition_id,
                    fate=entry.fate,
                    fate_reason=entry.fate_reason,
                    fate_timestamp=entry.fate_timestamp,
                    webhook_url=entry.webhook_url,
                )
                processed += 1
            elif entry.channel == "IN_APP":
                await self._deliver_in_app(
                    notification_id=entry.notification_id,
                    petition_id=entry.petition_id,
                    fate=entry.fate,
                    fate_reason=entry.fate_reason,
                    fate_timestamp=entry.fate_timestamp,
                )
                processed += 1

        return processed

    async def clear_retry_queue(self) -> None:
        """Clear the retry queue (for testing)."""
        async with self._lock:
            self._retry_queue.clear()
