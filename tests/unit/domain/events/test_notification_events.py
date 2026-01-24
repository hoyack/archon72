"""Unit tests for notification event payloads (Story 7.2).

Tests:
- FateNotificationSentEventPayload creation and fields
- Signable content for witnessing (CT-12)
- to_dict serialization
- State transition helpers (with_delivered, with_failed)
- Status checking (is_terminal, should_retry)
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.events.notification import (
    FATE_NOTIFICATION_SENT_EVENT_TYPE,
    NOTIFICATION_EVENT_SCHEMA_VERSION,
    FateNotificationSentEventPayload,
    NotificationChannel,
    NotificationDeliveryStatus,
)


class TestNotificationDeliveryStatus:
    """Tests for NotificationDeliveryStatus enum."""

    def test_all_statuses_defined(self) -> None:
        """All expected statuses are defined."""
        statuses = {s.value for s in NotificationDeliveryStatus}
        assert statuses == {"PENDING", "DELIVERED", "FAILED", "PERMANENTLY_FAILED"}


class TestNotificationChannel:
    """Tests for NotificationChannel enum."""

    def test_all_channels_defined(self) -> None:
        """All expected channels are defined."""
        channels = {c.value for c in NotificationChannel}
        assert channels == {"WEBHOOK", "IN_APP", "LONG_POLL"}


class TestFateNotificationSentEventPayloadCreation:
    """Tests for FateNotificationSentEventPayload creation."""

    def test_create_webhook_notification_pending(self) -> None:
        """Create pending webhook notification."""
        now = datetime.now(timezone.utc)
        notification_id = uuid4()
        petition_id = uuid4()

        payload = FateNotificationSentEventPayload(
            notification_id=notification_id,
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="ALREADY_RESOLVED",
            fate_timestamp=now,
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.PENDING,
            webhook_url="https://example.com/hook",
        )

        assert payload.notification_id == notification_id
        assert payload.petition_id == petition_id
        assert payload.fate == "ACKNOWLEDGED"
        assert payload.fate_reason == "ALREADY_RESOLVED"
        assert payload.channel == NotificationChannel.WEBHOOK
        assert payload.delivery_status == NotificationDeliveryStatus.PENDING
        assert payload.webhook_url == "https://example.com/hook"
        assert payload.delivered_at is None
        assert payload.error_message is None
        assert payload.retry_count == 0

    def test_create_long_poll_notification_delivered(self) -> None:
        """Create delivered long-poll notification."""
        now = datetime.now(timezone.utc)

        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            channel=NotificationChannel.LONG_POLL,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=now,
        )

        assert payload.channel == NotificationChannel.LONG_POLL
        assert payload.delivery_status == NotificationDeliveryStatus.DELIVERED
        assert payload.delivered_at == now

    def test_create_failed_notification(self) -> None:
        """Create failed notification with error."""
        now = datetime.now(timezone.utc)

        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.FAILED,
            error_message="Connection timeout",
            retry_count=1,
            webhook_url="https://example.com/hook",
        )

        assert payload.delivery_status == NotificationDeliveryStatus.FAILED
        assert payload.error_message == "Connection timeout"
        assert payload.retry_count == 1


class TestFateNotificationSentEventPayloadSignableContent:
    """Tests for signable_content method (CT-12)."""

    def test_signable_content_is_deterministic(self) -> None:
        """Signable content is deterministic (same payload = same bytes)."""
        now = datetime.now(timezone.utc)
        notification_id = uuid4()
        petition_id = uuid4()

        payload = FateNotificationSentEventPayload(
            notification_id=notification_id,
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="OUT_OF_SCOPE",
            fate_timestamp=now,
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.PENDING,
            webhook_url="https://example.com/hook",
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2

    def test_signable_content_is_json(self) -> None:
        """Signable content is valid JSON."""
        now = datetime.now(timezone.utc)

        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            channel=NotificationChannel.LONG_POLL,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=now,
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert "petition_id" in parsed
        assert "fate" in parsed
        assert parsed["fate"] == "ESCALATED"

    def test_signable_content_has_sorted_keys(self) -> None:
        """Signable content has sorted keys for determinism."""
        now = datetime.now(timezone.utc)

        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
            channel=NotificationChannel.IN_APP,
            delivery_status=NotificationDeliveryStatus.PENDING,
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())

        assert keys == sorted(keys)


class TestFateNotificationSentEventPayloadToDict:
    """Tests for to_dict serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all required fields."""
        now = datetime.now(timezone.utc)
        notification_id = uuid4()
        petition_id = uuid4()

        payload = FateNotificationSentEventPayload(
            notification_id=notification_id,
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="DUPLICATE",
            fate_timestamp=now,
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=now,
            webhook_url="https://example.com/hook",
        )

        data = payload.to_dict()

        assert data["notification_id"] == str(notification_id)
        assert data["petition_id"] == str(petition_id)
        assert data["fate"] == "ACKNOWLEDGED"
        assert data["fate_reason"] == "DUPLICATE"
        assert data["channel"] == "WEBHOOK"
        assert data["delivery_status"] == "DELIVERED"
        assert data["webhook_url"] == "https://example.com/hook"
        assert data["schema_version"] == NOTIFICATION_EVENT_SCHEMA_VERSION

    def test_to_dict_handles_none_values(self) -> None:
        """to_dict properly handles None values."""
        now = datetime.now(timezone.utc)

        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            channel=NotificationChannel.LONG_POLL,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=now,
        )

        data = payload.to_dict()

        assert data["fate_reason"] is None
        assert data["error_message"] is None
        assert data["webhook_url"] is None


class TestFateNotificationSentEventPayloadStateTransitions:
    """Tests for state transition helper methods."""

    def test_with_delivered_creates_delivered_status(self) -> None:
        """with_delivered creates new payload with DELIVERED status."""
        now = datetime.now(timezone.utc)

        original = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason="OUT_OF_SCOPE",
            fate_timestamp=now,
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.PENDING,
            webhook_url="https://example.com/hook",
        )

        delivered_at = datetime.now(timezone.utc)
        delivered = original.with_delivered(delivered_at)

        assert delivered.delivery_status == NotificationDeliveryStatus.DELIVERED
        assert delivered.delivered_at == delivered_at
        assert delivered.error_message is None
        # Original unchanged
        assert original.delivery_status == NotificationDeliveryStatus.PENDING

    def test_with_failed_creates_failed_status(self) -> None:
        """with_failed creates new payload with FAILED status."""
        now = datetime.now(timezone.utc)

        original = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.PENDING,
            retry_count=0,
            webhook_url="https://example.com/hook",
        )

        failed = original.with_failed("Connection timeout")

        assert failed.delivery_status == NotificationDeliveryStatus.FAILED
        assert failed.error_message == "Connection timeout"
        assert failed.retry_count == 1  # Incremented

    def test_with_failed_permanent_creates_permanently_failed_status(self) -> None:
        """with_failed(permanent=True) creates PERMANENTLY_FAILED status."""
        now = datetime.now(timezone.utc)

        original = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.FAILED,
            retry_count=2,
            webhook_url="https://example.com/hook",
        )

        permanently_failed = original.with_failed("Max retries exceeded", permanent=True)

        assert permanently_failed.delivery_status == NotificationDeliveryStatus.PERMANENTLY_FAILED
        assert permanently_failed.retry_count == 3


class TestFateNotificationSentEventPayloadStatusChecks:
    """Tests for status checking methods."""

    def test_is_terminal_true_for_delivered(self) -> None:
        """is_terminal returns True for DELIVERED status."""
        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=datetime.now(timezone.utc),
            webhook_url="https://example.com/hook",
        )

        assert payload.is_terminal() is True

    def test_is_terminal_true_for_permanently_failed(self) -> None:
        """is_terminal returns True for PERMANENTLY_FAILED status."""
        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.PERMANENTLY_FAILED,
            error_message="Max retries exceeded",
            webhook_url="https://example.com/hook",
        )

        assert payload.is_terminal() is True

    def test_is_terminal_false_for_pending(self) -> None:
        """is_terminal returns False for PENDING status."""
        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.PENDING,
            webhook_url="https://example.com/hook",
        )

        assert payload.is_terminal() is False

    def test_should_retry_true_for_failed_under_max(self) -> None:
        """should_retry returns True for FAILED with retries under max."""
        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.FAILED,
            retry_count=2,
            webhook_url="https://example.com/hook",
        )

        assert payload.should_retry(max_retries=3) is True

    def test_should_retry_false_for_failed_at_max(self) -> None:
        """should_retry returns False for FAILED at max retries."""
        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.FAILED,
            retry_count=3,
            webhook_url="https://example.com/hook",
        )

        assert payload.should_retry(max_retries=3) is False

    def test_should_retry_false_for_delivered(self) -> None:
        """should_retry returns False for DELIVERED status."""
        payload = FateNotificationSentEventPayload(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
            channel=NotificationChannel.WEBHOOK,
            delivery_status=NotificationDeliveryStatus.DELIVERED,
            delivered_at=datetime.now(timezone.utc),
            webhook_url="https://example.com/hook",
        )

        assert payload.should_retry() is False


class TestEventTypeConstant:
    """Tests for event type constant."""

    def test_event_type_defined(self) -> None:
        """Event type constant is properly defined."""
        assert FATE_NOTIFICATION_SENT_EVENT_TYPE == "petition.notification.fate_sent"
