"""Notification event payloads for fate assignment notifications (Story 7.2).

This module defines event payloads for notification operations:
- FateNotificationSentEventPayload: When a fate notification is sent to an Observer

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-12: Witnessing creates accountability → All events MUST be witnessed
- CT-13: No writes during halt → Event emission blocked during system halt

Developer Golden Rules:
1. WITNESS EVERYTHING - All notification events require attribution
2. NOTIFICATION FAILURE != HALT - Notification failures don't block fate assignment
3. FIRE-AND-FORGET - Notifications are best-effort with retry
4. READS DURING HALT - Notification queries work during halt (CT-13)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

# Event type constant for fate notification sent (Story 7.2, FR-7.3)
FATE_NOTIFICATION_SENT_EVENT_TYPE: str = "petition.notification.fate_sent"

# Schema version for notification events (deterministic replay)
NOTIFICATION_EVENT_SCHEMA_VERSION: str = "1.0.0"


class NotificationDeliveryStatus(str, Enum):
    """Status of a notification delivery attempt (Story 7.2).

    Delivery states:
    - PENDING: Notification queued, not yet delivered
    - DELIVERED: Successfully delivered to recipient
    - FAILED: Delivery attempt failed (will retry)
    - PERMANENTLY_FAILED: All retry attempts exhausted
    """

    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    PERMANENTLY_FAILED = "PERMANENTLY_FAILED"


class NotificationChannel(str, Enum):
    """Notification delivery channels (Story 7.2).

    Channels:
        WEBHOOK: HTTP POST to configured URL
        IN_APP: Store in notification queue for retrieval
        LONG_POLL: Immediate return to waiting long-poll connection
    """

    WEBHOOK = "WEBHOOK"
    IN_APP = "IN_APP"
    LONG_POLL = "LONG_POLL"


@dataclass(frozen=True, eq=True)
class FateNotificationSentEventPayload:
    """Payload for fate notification sent events (Story 7.2, FR-7.3).

    A FateNotificationSentEventPayload is created when a fate assignment
    notification is delivered (or attempted) to an Observer. This event
    tracks the notification delivery status for audit and retry purposes.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-7.3: System SHALL notify Observer on fate assignment
    - CT-12: Witnessing creates accountability → All events witnessed
    - AC4: Notification failures are logged but don't block fate assignment

    IMPORTANT: Unlike fate events, notification events use graceful degradation.
    Notification failure does NOT roll back fate assignment.

    Attributes:
        notification_id: Unique identifier for this notification attempt.
        petition_id: UUID of the petition that received a fate.
        fate: Terminal fate state (ACKNOWLEDGED, REFERRED, ESCALATED).
        fate_reason: Reason for fate assignment (for ACKNOWLEDGED).
        fate_timestamp: When the fate was assigned (UTC).
        channel: Notification delivery channel used.
        delivery_status: Current status of the delivery attempt.
        delivered_at: When delivery was confirmed (None if not yet delivered).
        error_message: Error message if delivery failed (None if successful).
        retry_count: Number of retry attempts made.
        webhook_url: Target URL for WEBHOOK channel (None for other channels).
    """

    notification_id: UUID
    petition_id: UUID
    fate: str
    fate_reason: str | None
    fate_timestamp: datetime
    channel: NotificationChannel
    delivery_status: NotificationDeliveryStatus
    delivered_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0
    webhook_url: str | None = None

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "channel": self.channel.value,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "delivery_status": self.delivery_status.value,
            "error_message": self.error_message,
            "fate": self.fate,
            "fate_reason": self.fate_reason,
            "fate_timestamp": self.fate_timestamp.isoformat(),
            "notification_id": str(self.notification_id),
            "petition_id": str(self.petition_id),
            "retry_count": self.retry_count,
            "webhook_url": self.webhook_url,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "notification_id": str(self.notification_id),
            "petition_id": str(self.petition_id),
            "fate": self.fate,
            "fate_reason": self.fate_reason,
            "fate_timestamp": self.fate_timestamp.isoformat(),
            "channel": self.channel.value,
            "delivery_status": self.delivery_status.value,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "webhook_url": self.webhook_url,
            "schema_version": NOTIFICATION_EVENT_SCHEMA_VERSION,
        }

    def with_delivered(self, delivered_at: datetime) -> "FateNotificationSentEventPayload":
        """Create new event with DELIVERED status.

        Since FateNotificationSentEventPayload is frozen, returns new instance.

        Args:
            delivered_at: When delivery was confirmed.

        Returns:
            New payload with DELIVERED status.
        """
        return FateNotificationSentEventPayload(
            notification_id=self.notification_id,
            petition_id=self.petition_id,
            fate=self.fate,
            fate_reason=self.fate_reason,
            fate_timestamp=self.fate_timestamp,
            channel=self.channel,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=delivered_at,
            error_message=None,
            retry_count=self.retry_count,
            webhook_url=self.webhook_url,
        )

    def with_failed(
        self, error_message: str, permanent: bool = False
    ) -> "FateNotificationSentEventPayload":
        """Create new event with FAILED or PERMANENTLY_FAILED status.

        Since FateNotificationSentEventPayload is frozen, returns new instance.

        Args:
            error_message: Description of the failure.
            permanent: If True, use PERMANENTLY_FAILED status.

        Returns:
            New payload with failure status and incremented retry count.
        """
        return FateNotificationSentEventPayload(
            notification_id=self.notification_id,
            petition_id=self.petition_id,
            fate=self.fate,
            fate_reason=self.fate_reason,
            fate_timestamp=self.fate_timestamp,
            channel=self.channel,
            delivery_status=(
                NotificationDeliveryStatus.PERMANENTLY_FAILED
                if permanent
                else NotificationDeliveryStatus.FAILED
            ),
            delivered_at=None,
            error_message=error_message,
            retry_count=self.retry_count + 1,
            webhook_url=self.webhook_url,
        )

    def is_terminal(self) -> bool:
        """Check if this notification is in a terminal state.

        Returns:
            True if DELIVERED or PERMANENTLY_FAILED, False otherwise.
        """
        return self.delivery_status in (
            NotificationDeliveryStatus.DELIVERED,
            NotificationDeliveryStatus.PERMANENTLY_FAILED,
        )

    def should_retry(self, max_retries: int = 3) -> bool:
        """Check if this notification should be retried.

        Args:
            max_retries: Maximum number of retry attempts allowed.

        Returns:
            True if status is FAILED and retry count is below max.
        """
        return (
            self.delivery_status == NotificationDeliveryStatus.FAILED
            and self.retry_count < max_retries
        )
