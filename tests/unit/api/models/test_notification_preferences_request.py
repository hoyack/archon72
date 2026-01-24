"""Unit tests for NotificationPreferencesRequest API model (Story 7.2).

Tests:
- Valid webhook preferences with HTTPS URL
- Valid in-app preferences
- Webhook channel requires webhook_url
- Non-HTTPS webhook URL rejected
- Empty/whitespace webhook URL rejected
- Invalid URL format rejected
"""

import pytest
from pydantic import ValidationError

from src.api.models.petition_submission import (
    NotificationChannelEnum,
    NotificationPreferencesRequest,
    SubmitPetitionSubmissionRequest,
    PetitionTypeEnum,
)


class TestNotificationChannelEnum:
    """Tests for NotificationChannelEnum."""

    def test_webhook_channel_value(self) -> None:
        """WEBHOOK channel has correct value."""
        assert NotificationChannelEnum.WEBHOOK.value == "WEBHOOK"

    def test_in_app_channel_value(self) -> None:
        """IN_APP channel has correct value."""
        assert NotificationChannelEnum.IN_APP.value == "IN_APP"


class TestNotificationPreferencesRequestValid:
    """Tests for valid notification preferences."""

    def test_valid_webhook_preference(self) -> None:
        """Valid webhook preference with HTTPS URL succeeds."""
        pref = NotificationPreferencesRequest(
            channel=NotificationChannelEnum.WEBHOOK,
            webhook_url="https://example.com/webhook",
        )

        assert pref.channel == NotificationChannelEnum.WEBHOOK
        assert pref.webhook_url == "https://example.com/webhook"
        assert pref.enabled is True

    def test_valid_webhook_preference_disabled(self) -> None:
        """Valid webhook preference can be disabled."""
        pref = NotificationPreferencesRequest(
            channel=NotificationChannelEnum.WEBHOOK,
            webhook_url="https://example.com/hook",
            enabled=False,
        )

        assert pref.enabled is False

    def test_valid_in_app_preference(self) -> None:
        """Valid in-app preference succeeds."""
        pref = NotificationPreferencesRequest(
            channel=NotificationChannelEnum.IN_APP,
        )

        assert pref.channel == NotificationChannelEnum.IN_APP
        assert pref.webhook_url is None
        assert pref.enabled is True

    def test_valid_webhook_with_port(self) -> None:
        """Webhook URL with port succeeds."""
        pref = NotificationPreferencesRequest(
            channel=NotificationChannelEnum.WEBHOOK,
            webhook_url="https://example.com:8443/webhook",
        )

        assert ":8443" in pref.webhook_url

    def test_valid_webhook_with_path(self) -> None:
        """Webhook URL with complex path succeeds."""
        pref = NotificationPreferencesRequest(
            channel=NotificationChannelEnum.WEBHOOK,
            webhook_url="https://api.example.com/v1/webhooks/petition",
        )

        assert "/v1/webhooks" in pref.webhook_url


class TestNotificationPreferencesRequestInvalid:
    """Tests for invalid notification preferences."""

    def test_webhook_without_url_rejected(self) -> None:
        """Webhook channel without URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
            )

        errors = exc_info.value.errors()
        assert any("webhook_url is required" in str(e) for e in errors)

    def test_webhook_with_empty_url_rejected(self) -> None:
        """Webhook channel with empty URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
                webhook_url="",
            )

        errors = exc_info.value.errors()
        # Empty string is falsy, so it triggers "webhook_url is required" error
        assert any("webhook_url is required" in str(e) for e in errors)

    def test_webhook_with_whitespace_url_rejected(self) -> None:
        """Webhook channel with whitespace URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
                webhook_url="   ",
            )

        errors = exc_info.value.errors()
        assert any("cannot be empty" in str(e) for e in errors)

    def test_webhook_with_http_url_rejected(self) -> None:
        """Webhook channel with HTTP (non-HTTPS) URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
                webhook_url="http://example.com/webhook",
            )

        errors = exc_info.value.errors()
        assert any("HTTPS" in str(e) for e in errors)

    def test_webhook_with_ftp_url_rejected(self) -> None:
        """Webhook channel with FTP URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
                webhook_url="ftp://example.com/file",
            )

        errors = exc_info.value.errors()
        assert any("HTTPS" in str(e) for e in errors)

    def test_webhook_with_invalid_url_rejected(self) -> None:
        """Webhook channel with invalid URL format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
                webhook_url="not-a-valid-url",
            )

        errors = exc_info.value.errors()
        # Either "HTTPS" error or "host" error depending on parsing
        assert len(errors) > 0


class TestSubmitPetitionRequestWithNotificationPreferences:
    """Tests for petition submission request with notification preferences."""

    def test_request_without_notification_preferences(self) -> None:
        """Request without notification preferences succeeds."""
        request = SubmitPetitionSubmissionRequest(
            type=PetitionTypeEnum.GENERAL,
            text="This is a test petition.",
        )

        assert request.notification_preferences is None

    def test_request_with_webhook_notification_preferences(self) -> None:
        """Request with webhook notification preferences succeeds."""
        request = SubmitPetitionSubmissionRequest(
            type=PetitionTypeEnum.GENERAL,
            text="This is a test petition.",
            notification_preferences=NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
                webhook_url="https://example.com/webhook",
            ),
        )

        assert request.notification_preferences is not None
        assert request.notification_preferences.channel == NotificationChannelEnum.WEBHOOK
        assert request.notification_preferences.webhook_url == "https://example.com/webhook"

    def test_request_with_in_app_notification_preferences(self) -> None:
        """Request with in-app notification preferences succeeds."""
        request = SubmitPetitionSubmissionRequest(
            type=PetitionTypeEnum.GENERAL,
            text="This is a test petition.",
            notification_preferences=NotificationPreferencesRequest(
                channel=NotificationChannelEnum.IN_APP,
            ),
        )

        assert request.notification_preferences is not None
        assert request.notification_preferences.channel == NotificationChannelEnum.IN_APP

    def test_request_with_invalid_webhook_url_rejected(self) -> None:
        """Request with invalid webhook URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SubmitPetitionSubmissionRequest(
                type=PetitionTypeEnum.GENERAL,
                text="This is a test petition.",
                notification_preferences=NotificationPreferencesRequest(
                    channel=NotificationChannelEnum.WEBHOOK,
                    webhook_url="http://insecure.com/webhook",
                ),
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_request_serialization_with_notification_preferences(self) -> None:
        """Request with notification preferences serializes correctly."""
        request = SubmitPetitionSubmissionRequest(
            type=PetitionTypeEnum.CESSATION,
            text="Cessation petition text.",
            notification_preferences=NotificationPreferencesRequest(
                channel=NotificationChannelEnum.WEBHOOK,
                webhook_url="https://example.com/hook",
                enabled=False,
            ),
        )

        data = request.model_dump()

        assert data["notification_preferences"]["channel"] == "WEBHOOK"
        assert data["notification_preferences"]["webhook_url"] == "https://example.com/hook"
        assert data["notification_preferences"]["enabled"] is False
