"""Unit tests for WebhookDeliveryAdapterStub (Story 7.2, Task 7).

Tests:
- Default success/failure behavior
- Per-URL response configuration
- Custom callback behavior
- Delivery attempt tracking
- Singleton management
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.infrastructure.stubs.webhook_delivery_adapter_stub import (
    DeliveryAttempt,
    WebhookDeliveryAdapterStub,
    get_webhook_delivery_adapter,
    reset_webhook_delivery_adapter,
)


class TestWebhookDeliveryAdapterStubCreation:
    """Tests for WebhookDeliveryAdapterStub initialization."""

    def test_create_with_defaults(self) -> None:
        """Create adapter with default configuration."""
        adapter = WebhookDeliveryAdapterStub()

        assert adapter.get_timeout_seconds() == 10.0
        assert adapter.get_delivery_count() == 0
        assert adapter._default_success is True

    def test_create_with_custom_timeout(self) -> None:
        """Create adapter with custom timeout."""
        adapter = WebhookDeliveryAdapterStub(timeout_seconds=5.0)

        assert adapter.get_timeout_seconds() == 5.0

    def test_create_with_default_failure(self) -> None:
        """Create adapter that fails by default."""
        adapter = WebhookDeliveryAdapterStub(default_success=False)

        assert adapter._default_success is False


class TestWebhookDeliverySuccess:
    """Tests for successful webhook delivery."""

    @pytest.mark.asyncio
    async def test_deliver_success_default(self) -> None:
        """Delivery succeeds with default configuration."""
        adapter = WebhookDeliveryAdapterStub()
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        success = await adapter.deliver(
            url="https://example.com/hook",
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="OUT_OF_SCOPE",
            fate_timestamp=now,
        )

        assert success is True
        assert adapter.get_delivery_count() == 1

    @pytest.mark.asyncio
    async def test_deliver_records_attempt(self) -> None:
        """Delivery records attempt details."""
        adapter = WebhookDeliveryAdapterStub()
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await adapter.deliver(
            url="https://example.com/hook",
            petition_id=petition_id,
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
        )

        attempts = adapter.get_attempts()
        assert len(attempts) == 1
        assert attempts[0].url == "https://example.com/hook"
        assert attempts[0].petition_id == petition_id
        assert attempts[0].fate == "REFERRED"
        assert attempts[0].fate_reason is None
        assert attempts[0].success is True


class TestWebhookDeliveryFailure:
    """Tests for failed webhook delivery."""

    @pytest.mark.asyncio
    async def test_deliver_failure_default(self) -> None:
        """Delivery fails with default failure configuration."""
        adapter = WebhookDeliveryAdapterStub(default_success=False)
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        success = await adapter.deliver(
            url="https://example.com/hook",
            petition_id=petition_id,
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
        )

        assert success is False
        assert adapter.get_delivery_count() == 1

    @pytest.mark.asyncio
    async def test_deliver_failure_records_attempt(self) -> None:
        """Failed delivery records attempt with success=False."""
        adapter = WebhookDeliveryAdapterStub(default_success=False)
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await adapter.deliver(
            url="https://example.com/hook",
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="DUPLICATE",
            fate_timestamp=now,
        )

        attempts = adapter.get_failed_attempts()
        assert len(attempts) == 1
        assert attempts[0].success is False


class TestPerUrlConfiguration:
    """Tests for per-URL response configuration."""

    @pytest.mark.asyncio
    async def test_url_specific_success(self) -> None:
        """Specific URL configured for success."""
        adapter = WebhookDeliveryAdapterStub(default_success=False)
        adapter.set_url_response("https://good.example.com/hook", True)
        now = datetime.now(timezone.utc)

        # Good URL succeeds
        success1 = await adapter.deliver(
            url="https://good.example.com/hook",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )

        # Other URL fails (default)
        success2 = await adapter.deliver(
            url="https://bad.example.com/hook",
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
        )

        assert success1 is True
        assert success2 is False

    @pytest.mark.asyncio
    async def test_url_specific_failure(self) -> None:
        """Specific URL configured for failure."""
        adapter = WebhookDeliveryAdapterStub(default_success=True)
        adapter.set_url_response("https://bad.example.com/hook", False)
        now = datetime.now(timezone.utc)

        # Bad URL fails
        success1 = await adapter.deliver(
            url="https://bad.example.com/hook",
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
        )

        # Other URL succeeds (default)
        success2 = await adapter.deliver(
            url="https://good.example.com/hook",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason="OUT_OF_SCOPE",
            fate_timestamp=now,
        )

        assert success1 is False
        assert success2 is True

    @pytest.mark.asyncio
    async def test_clear_url_responses(self) -> None:
        """Clear per-URL configuration."""
        adapter = WebhookDeliveryAdapterStub(default_success=True)
        adapter.set_url_response("https://example.com/hook", False)
        adapter.clear_url_responses()
        now = datetime.now(timezone.utc)

        # Should use default now
        success = await adapter.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
        )

        assert success is True


class TestDeliveryCallback:
    """Tests for custom delivery callback."""

    @pytest.mark.asyncio
    async def test_callback_determines_success(self) -> None:
        """Custom callback determines success."""
        adapter = WebhookDeliveryAdapterStub(default_success=False)

        # Callback returns True for ACKNOWLEDGED fate
        def callback(**kwargs) -> bool:
            return kwargs["fate"] == "ACKNOWLEDGED"

        adapter.set_delivery_callback(callback)
        now = datetime.now(timezone.utc)

        success1 = await adapter.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )

        success2 = await adapter.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
        )

        assert success1 is True
        assert success2 is False

    @pytest.mark.asyncio
    async def test_callback_overrides_url_config(self) -> None:
        """Callback takes precedence over URL configuration."""
        adapter = WebhookDeliveryAdapterStub()
        adapter.set_url_response("https://example.com/hook", True)
        adapter.set_delivery_callback(lambda **kwargs: False)
        now = datetime.now(timezone.utc)

        success = await adapter.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
        )

        # Callback returns False, overriding URL config
        assert success is False

    @pytest.mark.asyncio
    async def test_clear_callback(self) -> None:
        """Clear delivery callback."""
        adapter = WebhookDeliveryAdapterStub(default_success=True)
        adapter.set_delivery_callback(lambda **kwargs: False)
        adapter.set_delivery_callback(None)
        now = datetime.now(timezone.utc)

        # Should use default now
        success = await adapter.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )

        assert success is True


class TestAttemptTracking:
    """Tests for delivery attempt tracking."""

    @pytest.mark.asyncio
    async def test_get_successful_attempts(self) -> None:
        """Get only successful attempts."""
        adapter = WebhookDeliveryAdapterStub()
        adapter.set_url_response("https://fail.example.com", False)
        now = datetime.now(timezone.utc)

        await adapter.deliver(
            url="https://success.example.com",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )
        await adapter.deliver(
            url="https://fail.example.com",
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
        )

        successful = adapter.get_successful_attempts()
        assert len(successful) == 1
        assert successful[0].url == "https://success.example.com"

    @pytest.mark.asyncio
    async def test_get_failed_attempts(self) -> None:
        """Get only failed attempts."""
        adapter = WebhookDeliveryAdapterStub()
        adapter.set_url_response("https://fail.example.com", False)
        now = datetime.now(timezone.utc)

        await adapter.deliver(
            url="https://success.example.com",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )
        await adapter.deliver(
            url="https://fail.example.com",
            petition_id=uuid4(),
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
        )

        failed = adapter.get_failed_attempts()
        assert len(failed) == 1
        assert failed[0].url == "https://fail.example.com"

    @pytest.mark.asyncio
    async def test_get_attempts_for_petition(self) -> None:
        """Get attempts for a specific petition."""
        adapter = WebhookDeliveryAdapterStub()
        petition_id = uuid4()
        other_petition_id = uuid4()
        now = datetime.now(timezone.utc)

        await adapter.deliver(
            url="https://example.com/hook",
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )
        await adapter.deliver(
            url="https://example.com/hook",
            petition_id=other_petition_id,
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=now,
        )
        await adapter.deliver(
            url="https://example.com/hook",
            petition_id=petition_id,
            fate="ESCALATED",
            fate_reason=None,
            fate_timestamp=now,
        )

        petition_attempts = adapter.get_attempts_for_petition(petition_id)
        assert len(petition_attempts) == 2

    @pytest.mark.asyncio
    async def test_clear_attempts(self) -> None:
        """Clear all recorded attempts."""
        adapter = WebhookDeliveryAdapterStub()
        now = datetime.now(timezone.utc)

        await adapter.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )

        assert adapter.get_delivery_count() == 1

        await adapter.clear_attempts()

        assert adapter.get_delivery_count() == 0


class TestAdapterReset:
    """Tests for adapter reset."""

    @pytest.mark.asyncio
    async def test_reset_clears_all_state(self) -> None:
        """Reset clears all configuration and attempts."""
        adapter = WebhookDeliveryAdapterStub(default_success=False)
        adapter.set_url_response("https://example.com/hook", True)
        adapter.set_delivery_callback(lambda **kwargs: True)
        now = datetime.now(timezone.utc)

        await adapter.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=now,
        )

        adapter.reset()

        assert adapter._default_success is True
        assert len(adapter._url_responses) == 0
        assert adapter._delivery_callback is None
        assert adapter.get_delivery_count() == 0


class TestDeliveryAttempt:
    """Tests for DeliveryAttempt dataclass."""

    def test_create_attempt(self) -> None:
        """Create DeliveryAttempt with all fields."""
        petition_id = uuid4()
        now = datetime.now(timezone.utc)

        attempt = DeliveryAttempt(
            url="https://example.com/hook",
            petition_id=petition_id,
            fate="ACKNOWLEDGED",
            fate_reason="DUPLICATE",
            fate_timestamp=now,
            success=True,
        )

        assert attempt.url == "https://example.com/hook"
        assert attempt.petition_id == petition_id
        assert attempt.fate == "ACKNOWLEDGED"
        assert attempt.fate_reason == "DUPLICATE"
        assert attempt.fate_timestamp == now
        assert attempt.success is True
        assert attempt.attempted_at is not None

    def test_attempt_default_success_false(self) -> None:
        """DeliveryAttempt defaults success to False."""
        attempt = DeliveryAttempt(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="REFERRED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
        )

        assert attempt.success is False


class TestSingleton:
    """Tests for singleton management."""

    @pytest.mark.asyncio
    async def test_get_singleton_returns_same_instance(self) -> None:
        """get_webhook_delivery_adapter returns same instance."""
        reset_webhook_delivery_adapter()

        adapter1 = await get_webhook_delivery_adapter()
        adapter2 = await get_webhook_delivery_adapter()

        assert adapter1 is adapter2

    @pytest.mark.asyncio
    async def test_reset_clears_singleton(self) -> None:
        """reset_webhook_delivery_adapter clears singleton."""
        adapter1 = await get_webhook_delivery_adapter()
        await adapter1.deliver(
            url="https://example.com/hook",
            petition_id=uuid4(),
            fate="ACKNOWLEDGED",
            fate_reason=None,
            fate_timestamp=datetime.now(timezone.utc),
        )

        reset_webhook_delivery_adapter()

        adapter2 = await get_webhook_delivery_adapter()

        # New instance with no attempts
        assert adapter2 is not adapter1
        assert adapter2.get_delivery_count() == 0
