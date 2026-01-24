"""Unit tests for NotificationPreference domain model (Story 7.2).

Tests:
- NotificationPreference creation and factory methods
- Webhook URL validation (HTTPS required)
- Channel-specific validation
- Immutability and equality
- Helper methods (is_webhook, is_in_app, should_notify)
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.notification_preference import (
    InvalidNotificationPreferenceError,
    InvalidWebhookUrlError,
    NotificationChannel,
    NotificationPreference,
)


class TestNotificationChannel:
    """Tests for NotificationChannel enum."""

    def test_webhook_channel_value(self) -> None:
        """WEBHOOK channel has correct value."""
        assert NotificationChannel.WEBHOOK.value == "WEBHOOK"

    def test_in_app_channel_value(self) -> None:
        """IN_APP channel has correct value."""
        assert NotificationChannel.IN_APP.value == "IN_APP"

    def test_all_channels_defined(self) -> None:
        """All expected channels are defined."""
        channels = {c.value for c in NotificationChannel}
        assert channels == {"WEBHOOK", "IN_APP"}


class TestNotificationPreferenceCreation:
    """Tests for NotificationPreference creation and validation."""

    def test_create_webhook_preference_success(self) -> None:
        """Create webhook preference with valid HTTPS URL succeeds."""
        pref_id = uuid4()
        petition_id = uuid4()
        webhook_url = "https://example.com/webhook"

        pref = NotificationPreference.create_webhook(
            preference_id=pref_id,
            petition_id=petition_id,
            webhook_url=webhook_url,
        )

        assert pref.id == pref_id
        assert pref.petition_id == petition_id
        assert pref.channel == NotificationChannel.WEBHOOK
        assert pref.webhook_url == webhook_url
        assert pref.enabled is True

    def test_create_webhook_preference_disabled(self) -> None:
        """Create disabled webhook preference."""
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/hook",
            enabled=False,
        )

        assert pref.enabled is False

    def test_create_in_app_preference_success(self) -> None:
        """Create in-app preference succeeds."""
        pref_id = uuid4()
        petition_id = uuid4()

        pref = NotificationPreference.create_in_app(
            preference_id=pref_id,
            petition_id=petition_id,
        )

        assert pref.id == pref_id
        assert pref.petition_id == petition_id
        assert pref.channel == NotificationChannel.IN_APP
        assert pref.webhook_url is None
        assert pref.enabled is True

    def test_create_in_app_preference_disabled(self) -> None:
        """Create disabled in-app preference."""
        pref = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=uuid4(),
            enabled=False,
        )

        assert pref.enabled is False

    def test_created_at_is_set(self) -> None:
        """created_at is automatically set to current UTC time."""
        before = datetime.now(timezone.utc)
        pref = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=uuid4(),
        )
        after = datetime.now(timezone.utc)

        assert before <= pref.created_at <= after


class TestWebhookUrlValidation:
    """Tests for webhook URL validation."""

    def test_https_url_valid(self) -> None:
        """HTTPS URLs are valid."""
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/webhook",
        )
        assert pref.webhook_url == "https://example.com/webhook"

    def test_https_url_with_port_valid(self) -> None:
        """HTTPS URLs with port are valid."""
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com:8443/webhook",
        )
        assert pref.webhook_url == "https://example.com:8443/webhook"

    def test_https_url_with_path_valid(self) -> None:
        """HTTPS URLs with complex paths are valid."""
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://api.example.com/v1/webhooks/petition",
        )
        assert "v1/webhooks" in pref.webhook_url

    def test_http_url_rejected(self) -> None:
        """HTTP (non-HTTPS) URLs are rejected."""
        with pytest.raises(InvalidWebhookUrlError) as exc_info:
            NotificationPreference.create_webhook(
                preference_id=uuid4(),
                petition_id=uuid4(),
                webhook_url="http://example.com/webhook",
            )

        assert "must use HTTPS" in str(exc_info.value)
        assert exc_info.value.url == "http://example.com/webhook"

    def test_empty_url_rejected(self) -> None:
        """Empty URLs are rejected."""
        with pytest.raises(InvalidWebhookUrlError) as exc_info:
            NotificationPreference.create_webhook(
                preference_id=uuid4(),
                petition_id=uuid4(),
                webhook_url="",
            )

        assert "cannot be empty" in str(exc_info.value)

    def test_whitespace_url_rejected(self) -> None:
        """Whitespace-only URLs are rejected."""
        with pytest.raises(InvalidWebhookUrlError) as exc_info:
            NotificationPreference.create_webhook(
                preference_id=uuid4(),
                petition_id=uuid4(),
                webhook_url="   ",
            )

        assert "cannot be empty" in str(exc_info.value)

    def test_url_without_scheme_rejected(self) -> None:
        """URLs without scheme are rejected."""
        with pytest.raises(InvalidWebhookUrlError) as exc_info:
            NotificationPreference.create_webhook(
                preference_id=uuid4(),
                petition_id=uuid4(),
                webhook_url="example.com/webhook",
            )

        assert "must include scheme" in str(exc_info.value)

    def test_url_without_host_rejected(self) -> None:
        """URLs without host are rejected."""
        with pytest.raises(InvalidWebhookUrlError) as exc_info:
            NotificationPreference.create_webhook(
                preference_id=uuid4(),
                petition_id=uuid4(),
                webhook_url="https:///webhook",
            )

        assert "must include host" in str(exc_info.value)

    def test_ftp_url_rejected(self) -> None:
        """Non-HTTP URLs (ftp, etc.) are rejected."""
        with pytest.raises(InvalidWebhookUrlError) as exc_info:
            NotificationPreference.create_webhook(
                preference_id=uuid4(),
                petition_id=uuid4(),
                webhook_url="ftp://example.com/file",
            )

        assert "must use HTTPS" in str(exc_info.value)

    def test_webhook_channel_requires_url(self) -> None:
        """WEBHOOK channel requires webhook_url."""
        with pytest.raises(InvalidNotificationPreferenceError) as exc_info:
            NotificationPreference(
                id=uuid4(),
                petition_id=uuid4(),
                channel=NotificationChannel.WEBHOOK,
                webhook_url=None,
            )

        assert "webhook_url is required" in str(exc_info.value)
        assert exc_info.value.field == "webhook_url"


class TestNotificationPreferenceImmutability:
    """Tests for frozen dataclass immutability."""

    def test_preference_is_frozen(self) -> None:
        """NotificationPreference is immutable (frozen)."""
        pref = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=uuid4(),
        )

        with pytest.raises(AttributeError):
            pref.enabled = False  # type: ignore

    def test_with_enabled_returns_new_instance(self) -> None:
        """with_enabled returns a new instance."""
        original = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/hook",
            enabled=True,
        )

        updated = original.with_enabled(False)

        assert original.enabled is True
        assert updated.enabled is False
        assert original.id == updated.id
        assert original is not updated

    def test_equality_based_on_fields(self) -> None:
        """Equality is based on field values."""
        pref_id = uuid4()
        petition_id = uuid4()
        created = datetime.now(timezone.utc)

        pref1 = NotificationPreference(
            id=pref_id,
            petition_id=petition_id,
            channel=NotificationChannel.IN_APP,
            enabled=True,
            created_at=created,
        )
        pref2 = NotificationPreference(
            id=pref_id,
            petition_id=petition_id,
            channel=NotificationChannel.IN_APP,
            enabled=True,
            created_at=created,
        )

        assert pref1 == pref2


class TestNotificationPreferenceHelpers:
    """Tests for helper methods."""

    def test_is_webhook_true_for_webhook_channel(self) -> None:
        """is_webhook returns True for WEBHOOK channel."""
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/hook",
        )
        assert pref.is_webhook() is True
        assert pref.is_in_app() is False

    def test_is_in_app_true_for_in_app_channel(self) -> None:
        """is_in_app returns True for IN_APP channel."""
        pref = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=uuid4(),
        )
        assert pref.is_in_app() is True
        assert pref.is_webhook() is False

    def test_should_notify_true_when_enabled_and_configured(self) -> None:
        """should_notify returns True when enabled and properly configured."""
        webhook_pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/hook",
            enabled=True,
        )
        assert webhook_pref.should_notify() is True

        in_app_pref = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=uuid4(),
            enabled=True,
        )
        assert in_app_pref.should_notify() is True

    def test_should_notify_false_when_disabled(self) -> None:
        """should_notify returns False when disabled."""
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/hook",
            enabled=False,
        )
        assert pref.should_notify() is False


class TestInvalidNotificationPreferenceError:
    """Tests for error classes."""

    def test_error_has_message_and_field(self) -> None:
        """Error includes message and field."""
        error = InvalidNotificationPreferenceError(
            "Test error message",
            field="test_field",
        )
        assert error.message == "Test error message"
        assert error.field == "test_field"
        assert str(error) == "Test error message"

    def test_webhook_error_has_url_and_reason(self) -> None:
        """InvalidWebhookUrlError includes URL and reason."""
        error = InvalidWebhookUrlError(
            url="http://bad.url",
            reason="must use HTTPS",
        )
        assert error.url == "http://bad.url"
        assert error.reason == "must use HTTPS"
        assert "http://bad.url" in str(error)
        assert "must use HTTPS" in str(error)
