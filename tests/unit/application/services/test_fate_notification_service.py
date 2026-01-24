"""Unit tests for FateNotificationService (Story 7.2, FR-7.3).

Tests:
- Notification delivery via registry (long-poll)
- Webhook delivery with adapter
- In-app notification storage
- Retry scheduling and processing
- Event emission for witnessing (CT-12)
- Graceful degradation on failures
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.application.services.fate_notification_service import (
    FateNotificationService,
    RetryEntry,
)
from src.domain.models.notification_preference import (
    NotificationPreference,
)


class MockNotificationPreferenceRepository:
    """Mock repository for notification preferences."""

    def __init__(self) -> None:
        self._preferences: dict = {}
        self._should_raise = False

    async def get_by_petition_id(self, petition_id):
        if self._should_raise:
            raise Exception("Repository error")
        return self._preferences.get(petition_id)

    def set_preference(self, petition_id, preference):
        self._preferences[petition_id] = preference

    def set_should_raise(self, should_raise: bool):
        self._should_raise = should_raise


class MockStatusTokenRegistry:
    """Mock registry for status token operations."""

    def __init__(self) -> None:
        self.update_version_called = False
        self.update_version_args = None
        self._should_raise = False

    async def update_version(self, petition_id, new_version):
        if self._should_raise:
            raise Exception("Registry error")
        self.update_version_called = True
        self.update_version_args = (petition_id, new_version)

    def set_should_raise(self, should_raise: bool):
        self._should_raise = should_raise


class MockWebhookDeliveryAdapter:
    """Mock adapter for webhook delivery."""

    def __init__(self) -> None:
        self.deliver_called = False
        self.deliver_args = None
        self._should_succeed = True
        self._should_raise = False

    async def deliver(self, url, petition_id, fate, fate_reason, fate_timestamp):
        if self._should_raise:
            raise Exception("Webhook delivery error")
        self.deliver_called = True
        self.deliver_args = {
            "url": url,
            "petition_id": petition_id,
            "fate": fate,
            "fate_reason": fate_reason,
            "fate_timestamp": fate_timestamp,
        }
        return self._should_succeed

    def set_should_succeed(self, should_succeed: bool):
        self._should_succeed = should_succeed

    def set_should_raise(self, should_raise: bool):
        self._should_raise = should_raise


class TestFateNotificationServiceCreation:
    """Tests for FateNotificationService initialization."""

    def test_create_service_with_required_dependencies(self) -> None:
        """Create service with required dependencies."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        assert service._preference_repo is repo
        assert service._registry is registry
        assert service._webhook_adapter is None

    def test_create_service_with_all_dependencies(self) -> None:
        """Create service with all optional dependencies."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()
        webhook_adapter = MockWebhookDeliveryAdapter()
        event_writer = MagicMock()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
            event_writer=event_writer,
        )

        assert service._webhook_adapter is webhook_adapter
        assert service._event_writer is event_writer


class TestNotifyFateAssignedLongPoll:
    """Tests for long-poll notification via registry."""

    @pytest.mark.asyncio
    async def test_notify_updates_registry_version(self) -> None:
        """Long-poll notification updates registry version."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="ALREADY_RESOLVED",
            fate_timestamp=now,
            new_version=5,
        )

        assert registry.update_version_called
        assert registry.update_version_args == (petition_id, 5)

    @pytest.mark.asyncio
    async def test_notify_continues_on_registry_error(self) -> None:
        """Notification continues even if registry update fails."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()
        registry.set_should_raise(True)

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        # Should not raise
        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            new_version=1,
        )


class TestNotifyFateAssignedWebhook:
    """Tests for webhook notification delivery."""

    @pytest.mark.asyncio
    async def test_webhook_delivery_success(self) -> None:
        """Successful webhook delivery."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()
        webhook_adapter = MockWebhookDeliveryAdapter()

        # Set up webhook preference
        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
        )
        repo.set_preference(petition_id, pref)

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
        )

        now = datetime.now(timezone.utc)

        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="OUT_OF_SCOPE",
            fate_timestamp=now,
            new_version=3,
        )

        assert webhook_adapter.deliver_called
        assert webhook_adapter.deliver_args["url"] == "https://example.com/hook"
        assert webhook_adapter.deliver_args["petition_id"] == petition_id
        assert webhook_adapter.deliver_args["fate"] == "ACKNOWLEDGED"
        assert webhook_adapter.deliver_args["fate_reason"] == "OUT_OF_SCOPE"

    @pytest.mark.asyncio
    async def test_webhook_delivery_failure_schedules_retry(self) -> None:
        """Failed webhook delivery schedules retry."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()
        webhook_adapter = MockWebhookDeliveryAdapter()
        webhook_adapter.set_should_succeed(False)

        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
        )
        repo.set_preference(petition_id, pref)

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
        )

        now = datetime.now(timezone.utc)

        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
            new_version=2,
        )

        # Should have scheduled a retry
        assert service.get_pending_retry_count() == 1

    @pytest.mark.asyncio
    async def test_webhook_delivery_exception_schedules_retry(self) -> None:
        """Webhook delivery exception schedules retry."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()
        webhook_adapter = MockWebhookDeliveryAdapter()
        webhook_adapter.set_should_raise(True)

        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
        )
        repo.set_preference(petition_id, pref)

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
        )

        now = datetime.now(timezone.utc)

        # Should not raise - graceful degradation
        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            new_version=1,
        )

        assert service.get_pending_retry_count() == 1

    @pytest.mark.asyncio
    async def test_webhook_without_adapter_skips_delivery(self) -> None:
        """Webhook delivery skipped when adapter not configured."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
        )
        repo.set_preference(petition_id, pref)

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
            # No webhook adapter
        )

        now = datetime.now(timezone.utc)

        # Should not raise - just skip
        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="DUPLICATE",
            fate_timestamp=now,
            new_version=4,
        )

        # No retries scheduled (no adapter to retry with)
        assert service.get_pending_retry_count() == 0


class TestNotifyFateAssignedInApp:
    """Tests for in-app notification delivery."""

    @pytest.mark.asyncio
    async def test_in_app_notification_delivered(self) -> None:
        """In-app notification is delivered successfully."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        petition_id = uuid4()
        pref = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=petition_id,
        )
        repo.set_preference(petition_id, pref)

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        now = datetime.now(timezone.utc)

        # Should not raise
        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
            new_version=2,
        )


class TestNoPreferences:
    """Tests for notifications without preferences."""

    @pytest.mark.asyncio
    async def test_notify_without_preferences_still_updates_registry(self) -> None:
        """Notification updates registry even without preferences."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            new_version=1,
        )

        # Registry should still be updated
        assert registry.update_version_called

    @pytest.mark.asyncio
    async def test_notify_with_disabled_preferences_skips_delivery(self) -> None:
        """Disabled preferences skip channel delivery."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()
        webhook_adapter = MockWebhookDeliveryAdapter()

        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
            enabled=False,  # Disabled
        )
        repo.set_preference(petition_id, pref)

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
        )

        now = datetime.now(timezone.utc)

        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="OUT_OF_SCOPE",
            fate_timestamp=now,
            new_version=5,
        )

        # Webhook adapter should NOT be called
        assert not webhook_adapter.deliver_called

    @pytest.mark.asyncio
    async def test_notify_with_repo_error_still_updates_registry(self) -> None:
        """Repository error doesn't prevent registry update."""
        repo = MockNotificationPreferenceRepository()
        repo.set_should_raise(True)
        registry = MockStatusTokenRegistry()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await service.notify_fate_assigned(
            petition_id=petition_id,
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
            new_version=3,
        )

        # Registry should still be updated
        assert registry.update_version_called


class TestRetryScheduling:
    """Tests for retry scheduling."""

    @pytest.mark.asyncio
    async def test_schedule_retry_adds_to_queue(self) -> None:
        """schedule_retry adds entry to queue."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        notification_id = uuid4()
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await service.schedule_retry(
            notification_id=notification_id,
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="DUPLICATE",
            fate_timestamp=now,
            channel="WEBHOOK",
            webhook_url="https://example.com/hook",
            retry_count=0,
        )

        assert service.get_pending_retry_count() == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_does_not_queue(self) -> None:
        """Max retries exceeded doesn't add to queue."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        notification_id = uuid4()
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await service.schedule_retry(
            notification_id=notification_id,
            petition_id=petition_id,
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
            channel="WEBHOOK",
            webhook_url="https://example.com/hook",
            retry_count=3,  # At max
        )

        assert service.get_pending_retry_count() == 0

    @pytest.mark.asyncio
    async def test_process_retries_clears_queue(self) -> None:
        """process_retries processes and clears queue."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()
        webhook_adapter = MockWebhookDeliveryAdapter()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
        )

        notification_id = uuid4()
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        # Schedule a retry
        await service.schedule_retry(
            notification_id=notification_id,
            petition_id=petition_id,
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
            channel="WEBHOOK",
            webhook_url="https://example.com/hook",
            retry_count=0,
        )

        assert service.get_pending_retry_count() == 1

        # Process retries
        processed = await service.process_retries()

        assert processed == 1
        assert service.get_pending_retry_count() == 0
        assert webhook_adapter.deliver_called

    @pytest.mark.asyncio
    async def test_clear_retry_queue(self) -> None:
        """clear_retry_queue empties the queue."""
        repo = MockNotificationPreferenceRepository()
        registry = MockStatusTokenRegistry()

        service = FateNotificationService(
            notification_preference_repo=repo,
            status_token_registry=registry,
        )

        # Schedule some retries
        now = datetime.now(timezone.utc)
        for i in range(3):
            await service.schedule_retry(
                notification_id=uuid4(),
                petition_id=uuid4(),
                fate="ACKNOWLEDGED",
                fate_reason=None,
                fate_timestamp=now,
                channel="WEBHOOK",
                webhook_url="https://example.com/hook",
                retry_count=0,
            )

        assert service.get_pending_retry_count() == 3

        await service.clear_retry_queue()

        assert service.get_pending_retry_count() == 0


class TestRetryEntry:
    """Tests for RetryEntry dataclass."""

    def test_create_retry_entry(self) -> None:
        """Create RetryEntry with all fields."""
        notification_id = uuid4()
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        entry = RetryEntry(
            notification_id=notification_id,
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="DUPLICATE",
            fate_timestamp=now,
            channel="WEBHOOK",
            webhook_url="https://example.com/hook",
            retry_count=1,
        )

        assert entry.notification_id == notification_id
        assert entry.petition_id == petition_id
        assert entry.fate == "ACKNOWLEDGED"
        assert entry.fate_reason == "DUPLICATE"
        assert entry.fate_timestamp == now
        assert entry.channel == "WEBHOOK"
        assert entry.webhook_url == "https://example.com/hook"
        assert entry.retry_count == 1
        assert entry.scheduled_at is not None

    def test_retry_entry_default_scheduled_at(self) -> None:
        """RetryEntry has default scheduled_at timestamp."""
        before = datetime.now(timezone.utc)
        entry = RetryEntry(
            notification_id=uuid4(),
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
            channel="WEBHOOK",
            webhook_url="https://example.com/hook",
            retry_count=0,
        )
        after = datetime.now(timezone.utc)

        assert before <= entry.scheduled_at <= after


class TestServiceConstants:
    """Tests for service constants."""

    def test_max_retries_constant(self) -> None:
        """MAX_RETRIES constant is defined."""
        assert FateNotificationService.MAX_RETRIES == 3

    def test_retry_delays_constant(self) -> None:
        """RETRY_DELAYS_SECONDS constant is defined."""
        assert FateNotificationService.RETRY_DELAYS_SECONDS == [5, 30, 120]
