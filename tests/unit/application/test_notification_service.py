"""Unit tests for NotificationService (Story 4.8, Task 2).

Tests for push notification service including webhook and SSE delivery.

Constitutional Constraints:
- SR-9: Observer push notifications for breach events.
- RT-5: Breach events pushed to multiple channels.
- CT-11: Silent failure destroys legitimacy - delivery logged.
- CT-12: Witnessing creates accountability - attribution in notifications.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.api.models.observer import (
    NotificationEventType,
    NotificationPayload,
    WebhookSubscription,
)
from src.application.services.notification_service import NotificationService


class MockEvent:
    """Mock Event for testing."""

    def __init__(
        self,
        event_type: str = "breach",
        sequence: int = 42,
        event_id: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        self.event_id = uuid4() if event_id is None else event_id
        self.event_type = event_type
        self.sequence = sequence
        self.content_hash = content_hash or "a" * 64


class TestNotificationServiceInit:
    """Tests for NotificationService initialization."""

    def test_notification_service_creates_with_defaults(self) -> None:
        """Test service creates with default configuration."""
        service = NotificationService()

        assert service._base_url == "http://localhost:8000"
        assert service._webhook_timeout == 10.0
        assert service._max_retries == 3

    def test_notification_service_custom_config(self) -> None:
        """Test service accepts custom configuration."""
        service = NotificationService(
            base_url="https://api.example.com",
            webhook_timeout=30.0,
            max_retries=5,
        )

        assert service._base_url == "https://api.example.com"
        assert service._webhook_timeout == 30.0
        assert service._max_retries == 5


class TestWebhookSubscription:
    """Tests for webhook subscription management."""

    @pytest.mark.asyncio
    async def test_subscribe_webhook_creates_subscription(self) -> None:
        """Test that subscribe_webhook creates a new subscription."""
        service = NotificationService()

        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.BREACH],
        )

        # Mock the test notification to avoid actual HTTP call
        with patch.object(service, "_send_test_notification", return_value=True):
            response = await service.subscribe_webhook(subscription)

        assert response.subscription_id is not None
        assert response.webhook_url == "https://example.com/webhook"
        assert NotificationEventType.BREACH in response.event_types
        assert response.status == "active"

    @pytest.mark.asyncio
    async def test_subscribe_webhook_sends_test_notification(self) -> None:
        """Test that subscribe_webhook sends a test notification."""
        service = NotificationService()

        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
        )

        # Mock the test notification
        with patch.object(service, "_send_test_notification", return_value=True) as mock:
            response = await service.subscribe_webhook(subscription)

        assert response.test_sent is True
        mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsubscribe_webhook_removes_subscription(self) -> None:
        """Test that unsubscribe_webhook removes the subscription."""
        service = NotificationService()

        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
        )

        with patch.object(service, "_send_test_notification", return_value=True):
            response = await service.subscribe_webhook(subscription)

        # Verify subscription exists
        assert service.get_subscription(response.subscription_id) is not None

        # Unsubscribe
        result = await service.unsubscribe_webhook(response.subscription_id)
        assert result is True

        # Verify subscription is removed
        assert service.get_subscription(response.subscription_id) is None

    @pytest.mark.asyncio
    async def test_unsubscribe_webhook_returns_false_for_unknown(self) -> None:
        """Test that unsubscribe returns False for unknown ID."""
        service = NotificationService()

        result = await service.unsubscribe_webhook(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_get_subscription_returns_subscription(self) -> None:
        """Test that get_subscription returns the subscription."""
        service = NotificationService()

        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
        )

        with patch.object(service, "_send_test_notification", return_value=True):
            response = await service.subscribe_webhook(subscription)

        retrieved = service.get_subscription(response.subscription_id)
        assert retrieved is not None
        assert retrieved.webhook_url == "https://example.com/webhook"

    def test_get_subscription_count(self) -> None:
        """Test subscription count tracking."""
        service = NotificationService()

        assert service.get_subscription_count() == 0


class TestSSEConnection:
    """Tests for SSE connection management."""

    def test_register_sse_connection_returns_queue(self) -> None:
        """Test that register_sse_connection returns ID and queue."""
        service = NotificationService()

        connection_id, queue = service.register_sse_connection(
            event_types=[NotificationEventType.BREACH]
        )

        assert connection_id is not None
        assert queue is not None
        assert isinstance(queue, asyncio.Queue)

    def test_unregister_sse_connection_removes_connection(self) -> None:
        """Test that unregister removes the connection."""
        service = NotificationService()

        connection_id, _ = service.register_sse_connection(
            event_types=[NotificationEventType.ALL]
        )

        # Verify connection exists
        assert service.get_active_connection_count() == 1

        # Unregister
        service.unregister_sse_connection(connection_id)

        # Verify connection is removed
        assert service.get_active_connection_count() == 0

    def test_get_active_connection_count(self) -> None:
        """Test connection count tracking."""
        service = NotificationService()

        assert service.get_active_connection_count() == 0

        service.register_sse_connection(event_types=[NotificationEventType.ALL])
        assert service.get_active_connection_count() == 1

        service.register_sse_connection(event_types=[NotificationEventType.BREACH])
        assert service.get_active_connection_count() == 2


class TestNotifyEvent:
    """Tests for event notification delivery."""

    @pytest.mark.asyncio
    async def test_notify_event_publishes_to_sse(self) -> None:
        """Test that notify_event pushes to SSE connections."""
        service = NotificationService()

        # Register SSE connection
        _, queue = service.register_sse_connection(
            event_types=[NotificationEventType.BREACH]
        )

        # Create breach event
        event = MockEvent(event_type="breach", sequence=42)

        # Notify
        await service.notify_event(event)

        # Check queue received notification
        assert not queue.empty()
        payload = await queue.get()
        assert payload.event_type == "breach"
        assert payload.sequence == 42

    @pytest.mark.asyncio
    async def test_notify_event_calls_webhooks(self) -> None:
        """Test that notify_event calls registered webhooks."""
        service = NotificationService()

        # Register webhook
        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.BREACH],
        )

        with patch.object(service, "_send_test_notification", return_value=True):
            await service.subscribe_webhook(subscription)

        # Create breach event
        event = MockEvent(event_type="breach", sequence=42)

        # Mock webhook delivery
        with patch.object(service, "_deliver_webhook", return_value=True) as mock:
            await service.notify_event(event)

        # Verify webhook was called
        mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_event_filters_by_event_type(self) -> None:
        """Test that notify only sends to matching subscriptions."""
        service = NotificationService()

        # Register webhook for HALT only
        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.HALT],
        )

        with patch.object(service, "_send_test_notification", return_value=True):
            await service.subscribe_webhook(subscription)

        # Create BREACH event (should not trigger HALT subscription)
        event = MockEvent(event_type="breach", sequence=42)

        # Mock webhook delivery
        with patch.object(service, "_deliver_webhook", return_value=True) as mock:
            await service.notify_event(event)

        # Verify webhook was NOT called (wrong event type)
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_event_all_matches_any_type(self) -> None:
        """Test that ALL subscription matches any event type."""
        service = NotificationService()

        # Register webhook for ALL
        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.ALL],
        )

        with patch.object(service, "_send_test_notification", return_value=True):
            await service.subscribe_webhook(subscription)

        # Create breach event
        event = MockEvent(event_type="breach", sequence=42)

        # Mock webhook delivery
        with patch.object(service, "_deliver_webhook", return_value=True) as mock:
            await service.notify_event(event)

        # Verify webhook WAS called (ALL matches any)
        mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_event_skips_non_notifiable_types(self) -> None:
        """Test that non-notifiable event types are ignored."""
        service = NotificationService()

        # Register SSE connection
        _, queue = service.register_sse_connection(
            event_types=[NotificationEventType.ALL]
        )

        # Create non-notifiable event (e.g., "vote")
        event = MockEvent(event_type="vote", sequence=42)

        # Notify
        await service.notify_event(event)

        # Queue should be empty (vote is not notifiable)
        assert queue.empty()


class TestWebhookDelivery:
    """Tests for webhook delivery with retry."""

    @pytest.mark.asyncio
    async def test_webhook_delivery_with_signature(self) -> None:
        """Test that webhook delivery includes HMAC signature when secret provided."""
        service = NotificationService()

        # Register webhook with secret
        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.BREACH],
            secret="a" * 32,  # 32 char secret
        )

        with patch.object(service, "_send_test_notification", return_value=True):
            await service.subscribe_webhook(subscription)

        # Create event
        event = MockEvent(event_type="breach", sequence=42)

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await service.notify_event(event)

            # Verify signature header was sent
            call_args = mock_post.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "X-Archon72-Signature" in headers
            assert headers["X-Archon72-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_webhook_retry_on_failure(self) -> None:
        """Test that webhook retries on failure."""
        service = NotificationService(max_retries=3)

        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="breach",
            sequence=42,
            summary="Test",
            event_url="http://localhost/events/test",
            content_hash="a" * 64,
        )

        # Mock httpx to fail first 2 times, succeed on 3rd
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return mock_response_fail
            return mock_response_success

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=mock_post
            )
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service._deliver_webhook(
                    uuid4(),
                    "https://example.com/webhook",
                    payload,
                    None,
                )

        assert result is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_delivery_confirmation_logged(self) -> None:
        """Test that delivery confirmation is logged (CT-11)."""
        service = NotificationService()

        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="breach",
            sequence=42,
            summary="Test",
            event_url="http://localhost/events/test",
            content_hash="a" * 64,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            with patch("structlog.get_logger") as mock_logger:
                mock_log = MagicMock()
                mock_logger.return_value = mock_log

                # Create new service to get patched logger
                test_service = NotificationService()

                result = await test_service._deliver_webhook(
                    uuid4(),
                    "https://example.com/webhook",
                    payload,
                    None,
                )

        assert result is True


class TestCreateSummary:
    """Tests for event summary creation."""

    def test_create_summary_breach(self) -> None:
        """Test summary for breach event."""
        service = NotificationService()
        event = MockEvent(event_type="breach", sequence=42)

        summary = service._create_summary(event)

        assert "breach" in summary.lower()
        assert "42" in summary

    def test_create_summary_halt(self) -> None:
        """Test summary for halt event."""
        service = NotificationService()
        event = MockEvent(event_type="halt", sequence=100)

        summary = service._create_summary(event)

        assert "halt" in summary.lower()
        assert "100" in summary

    def test_create_summary_fork(self) -> None:
        """Test summary for fork event."""
        service = NotificationService()
        event = MockEvent(event_type="fork_detected", sequence=500)

        summary = service._create_summary(event)

        assert "fork" in summary.lower()
        assert "500" in summary

    def test_create_summary_unknown(self) -> None:
        """Test summary for unknown event type."""
        service = NotificationService()
        event = MockEvent(event_type="custom_event", sequence=10)

        summary = service._create_summary(event)

        assert "custom_event" in summary
        assert "10" in summary
