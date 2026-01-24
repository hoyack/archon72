"""Notification preference domain model for fate assignment notifications (Story 7.2, FR-7.3).

Value object representing Observer notification preferences for petition
fate assignment notifications. Supports webhook and in-app notification
channels with configurable preferences per petition.

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-12: All notifications are witnessed events
- D7: RFC 7807 error responses for invalid preferences

Developer Golden Rules:
1. Preferences are IMMUTABLE once created - frozen dataclass
2. Webhook URLs MUST be HTTPS (security requirement)
3. Preferences are stored per-petition (not per-user)
4. Invalid preferences return RFC 7807 errors
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import UUID

if TYPE_CHECKING:
    pass


class NotificationChannel(Enum):
    """Notification delivery channels (Story 7.2).

    Channels:
        WEBHOOK: HTTP POST to configured URL
        IN_APP: Store in notification queue for retrieval (future)
    """

    WEBHOOK = "WEBHOOK"
    IN_APP = "IN_APP"


class InvalidNotificationPreferenceError(ValueError):
    """Raised when notification preferences are invalid."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class InvalidWebhookUrlError(InvalidNotificationPreferenceError):
    """Raised when webhook URL is invalid or not HTTPS."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            message=f"Invalid webhook URL '{url}': {reason}",
            field="webhook_url",
        )
        self.url = url
        self.reason = reason


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _validate_webhook_url(url: str | None) -> None:
    """Validate webhook URL is HTTPS and well-formed.

    Args:
        url: The webhook URL to validate (None is allowed).

    Raises:
        InvalidWebhookUrlError: If URL is invalid or not HTTPS.
    """
    if url is None:
        return

    if not url.strip():
        raise InvalidWebhookUrlError(url, "URL cannot be empty")

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise InvalidWebhookUrlError(url, f"Malformed URL: {e}") from e

    if not parsed.scheme:
        raise InvalidWebhookUrlError(url, "URL must include scheme")

    if parsed.scheme.lower() != "https":
        raise InvalidWebhookUrlError(
            url, f"URL must use HTTPS (got {parsed.scheme})"
        )

    if not parsed.netloc:
        raise InvalidWebhookUrlError(url, "URL must include host")


@dataclass(frozen=True, eq=True)
class NotificationPreference:
    """Notification preferences for petition fate assignment (FR-7.3).

    Stores how an Observer wants to be notified when their petition
    receives a fate (ACKNOWLEDGED, REFERRED, ESCALATED, DEFERRED, or NO_RESPONSE).

    Constitutional Constraints:
    - FR-7.3: System SHALL notify Observer on fate assignment
    - CT-12: Frozen dataclass ensures immutability for witnessing

    Attributes:
        id: UUIDv7 unique identifier for this preference.
        petition_id: UUID of the petition these preferences apply to.
        channel: Notification channel (WEBHOOK, IN_APP).
        enabled: Whether notifications are enabled for this channel.
        webhook_url: URL for webhook delivery (HTTPS only, required for WEBHOOK channel).
        created_at: When preferences were created (UTC).

    Example:
        >>> pref = NotificationPreference.create_webhook(
        ...     petition_id=UUID("..."),
        ...     webhook_url="https://example.com/webhook",
        ... )
        >>> pref.channel
        <NotificationChannel.WEBHOOK: 'WEBHOOK'>
    """

    id: UUID
    petition_id: UUID
    channel: NotificationChannel
    enabled: bool = field(default=True)
    webhook_url: str | None = field(default=None)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate notification preference fields."""
        # Validate webhook URL if channel is WEBHOOK
        if self.channel == NotificationChannel.WEBHOOK:
            if self.webhook_url is None:
                raise InvalidNotificationPreferenceError(
                    "webhook_url is required for WEBHOOK channel",
                    field="webhook_url",
                )
            _validate_webhook_url(self.webhook_url)

        # Validate webhook_url format even if provided for non-webhook channel
        if self.webhook_url is not None:
            _validate_webhook_url(self.webhook_url)

    @classmethod
    def create_webhook(
        cls,
        preference_id: UUID,
        petition_id: UUID,
        webhook_url: str,
        enabled: bool = True,
    ) -> NotificationPreference:
        """Create a webhook notification preference.

        Args:
            preference_id: UUIDv7 for this preference.
            petition_id: UUID of the petition.
            webhook_url: HTTPS URL for webhook delivery.
            enabled: Whether notifications are enabled.

        Returns:
            New NotificationPreference for webhook channel.

        Raises:
            InvalidWebhookUrlError: If URL is invalid or not HTTPS.
        """
        return cls(
            id=preference_id,
            petition_id=petition_id,
            channel=NotificationChannel.WEBHOOK,
            enabled=enabled,
            webhook_url=webhook_url,
            created_at=_utc_now(),
        )

    @classmethod
    def create_in_app(
        cls,
        preference_id: UUID,
        petition_id: UUID,
        enabled: bool = True,
    ) -> NotificationPreference:
        """Create an in-app notification preference.

        Args:
            preference_id: UUIDv7 for this preference.
            petition_id: UUID of the petition.
            enabled: Whether notifications are enabled.

        Returns:
            New NotificationPreference for in-app channel.
        """
        return cls(
            id=preference_id,
            petition_id=petition_id,
            channel=NotificationChannel.IN_APP,
            enabled=enabled,
            webhook_url=None,
            created_at=_utc_now(),
        )

    def with_enabled(self, enabled: bool) -> NotificationPreference:
        """Create new preference with updated enabled flag.

        Since NotificationPreference is frozen, returns new instance.

        Args:
            enabled: New enabled state.

        Returns:
            New NotificationPreference with updated enabled flag.
        """
        return NotificationPreference(
            id=self.id,
            petition_id=self.petition_id,
            channel=self.channel,
            enabled=enabled,
            webhook_url=self.webhook_url,
            created_at=self.created_at,
        )

    def is_webhook(self) -> bool:
        """Check if this preference is for webhook delivery.

        Returns:
            True if channel is WEBHOOK, False otherwise.
        """
        return self.channel == NotificationChannel.WEBHOOK

    def is_in_app(self) -> bool:
        """Check if this preference is for in-app delivery.

        Returns:
            True if channel is IN_APP, False otherwise.
        """
        return self.channel == NotificationChannel.IN_APP

    def should_notify(self) -> bool:
        """Check if notification should be sent based on preferences.

        Returns:
            True if enabled and channel is configured, False otherwise.
        """
        if not self.enabled:
            return False

        if self.channel == NotificationChannel.WEBHOOK:
            return self.webhook_url is not None

        # IN_APP is always deliverable if enabled
        return True
