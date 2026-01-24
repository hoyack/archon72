"""Webhook Delivery Adapter stub (Story 7.2, Task 7).

In-memory stub implementation for webhook delivery during development.
Provides configurable success/failure behavior for testing.

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-12: Witnessing creates accountability - all deliveries logged

Developer Golden Rules:
1. Configurable success/failure for testing
2. Track delivery attempts for verification
3. Thread-safe operations
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.webhook_delivery_adapter import (
    WebhookDeliveryAdapterProtocol,
)

logger = logging.getLogger(__name__)


@dataclass
class DeliveryAttempt:
    """Record of a delivery attempt.

    Attributes:
        url: URL the delivery was attempted to.
        petition_id: UUID of the petition.
        fate: Terminal fate.
        fate_reason: Reason for fate.
        fate_timestamp: When the fate was assigned.
        attempted_at: When the delivery was attempted.
        success: Whether delivery succeeded.
    """

    url: str
    petition_id: UUID
    fate: str
    fate_reason: str | None
    fate_timestamp: datetime
    attempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = False


class WebhookDeliveryAdapterStub(WebhookDeliveryAdapterProtocol):
    """In-memory stub implementation of webhook delivery adapter.

    This stub provides configurable behavior for testing:
    - Default success/failure response
    - Per-URL success/failure configuration
    - Callback support for custom behavior
    - Delivery attempt tracking

    Attributes:
        _timeout_seconds: Configured timeout.
        _default_success: Default success response.
        _url_responses: Per-URL success/failure configuration.
        _delivery_callback: Optional callback for custom behavior.
        _attempts: List of delivery attempts.
        _lock: Async lock for thread-safety.
    """

    DEFAULT_TIMEOUT_SECONDS = 10.0

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        default_success: bool = True,
    ) -> None:
        """Initialize the webhook delivery adapter stub.

        Args:
            timeout_seconds: Timeout for webhook delivery.
            default_success: Default success response.
        """
        self._timeout_seconds = timeout_seconds
        self._default_success = default_success
        self._url_responses: dict[str, bool] = {}
        self._delivery_callback: Callable[..., bool] | None = None
        self._attempts: list[DeliveryAttempt] = []
        self._lock = asyncio.Lock()

    async def deliver(
        self,
        url: str,
        petition_id: UUID,
        fate: str,
        fate_reason: str | None,
        fate_timestamp: datetime,
    ) -> bool:
        """Deliver a fate notification to a webhook URL.

        Simulates HTTP POST to the configured URL. Behavior is
        determined by configuration (default, per-URL, or callback).

        Args:
            url: HTTPS URL to POST to.
            petition_id: UUID of the fated petition.
            fate: Terminal fate (ACKNOWLEDGED, REFERRED, ESCALATED, DEFERRED, NO_RESPONSE).
            fate_reason: Reason for fate (for ACKNOWLEDGED).
            fate_timestamp: When the fate was assigned.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        logger.debug(
            "Webhook delivery attempt: url=%s, petition_id=%s, fate=%s",
            url,
            petition_id,
            fate,
        )

        # Determine success based on configuration
        success: bool
        if self._delivery_callback is not None:
            success = self._delivery_callback(
                url=url,
                petition_id=petition_id,
                fate=fate,
                fate_reason=fate_reason,
                fate_timestamp=fate_timestamp,
            )
        elif url in self._url_responses:
            success = self._url_responses[url]
        else:
            success = self._default_success

        # Record attempt
        attempt = DeliveryAttempt(
            url=url,
            petition_id=petition_id,
            fate=fate,
            fate_reason=fate_reason,
            fate_timestamp=fate_timestamp,
            success=success,
        )

        async with self._lock:
            self._attempts.append(attempt)

        logger.info(
            "Webhook delivery %s: url=%s, petition_id=%s",
            "succeeded" if success else "failed",
            url,
            petition_id,
        )

        return success

    def get_timeout_seconds(self) -> float:
        """Get the configured timeout for webhook delivery.

        Returns:
            Timeout in seconds for HTTP requests.
        """
        return self._timeout_seconds

    def get_delivery_count(self) -> int:
        """Get the total number of delivery attempts.

        Returns:
            Total delivery attempts.
        """
        return len(self._attempts)

    # Configuration methods for testing

    def set_default_success(self, success: bool) -> None:
        """Set the default success response.

        Args:
            success: Whether deliveries should succeed by default.
        """
        self._default_success = success

    def set_url_response(self, url: str, success: bool) -> None:
        """Set success response for a specific URL.

        Args:
            url: URL to configure.
            success: Whether deliveries to this URL should succeed.
        """
        self._url_responses[url] = success

    def clear_url_responses(self) -> None:
        """Clear all per-URL response configurations."""
        self._url_responses.clear()

    def set_delivery_callback(self, callback: Callable[..., bool] | None) -> None:
        """Set a custom delivery callback.

        The callback receives keyword arguments: url, petition_id,
        fate, fate_reason, fate_timestamp. Return True for success.

        Args:
            callback: Callback function, or None to clear.
        """
        self._delivery_callback = callback

    def get_attempts(self) -> list[DeliveryAttempt]:
        """Get all delivery attempts.

        Returns:
            List of delivery attempts.
        """
        return list(self._attempts)

    def get_successful_attempts(self) -> list[DeliveryAttempt]:
        """Get successful delivery attempts.

        Returns:
            List of successful delivery attempts.
        """
        return [a for a in self._attempts if a.success]

    def get_failed_attempts(self) -> list[DeliveryAttempt]:
        """Get failed delivery attempts.

        Returns:
            List of failed delivery attempts.
        """
        return [a for a in self._attempts if not a.success]

    def get_attempts_for_petition(self, petition_id: UUID) -> list[DeliveryAttempt]:
        """Get delivery attempts for a specific petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            List of delivery attempts for the petition.
        """
        return [a for a in self._attempts if a.petition_id == petition_id]

    async def clear_attempts(self) -> None:
        """Clear all recorded delivery attempts."""
        async with self._lock:
            self._attempts.clear()

    def reset(self) -> None:
        """Reset stub to default state."""
        self._default_success = True
        self._url_responses.clear()
        self._delivery_callback = None
        self._attempts.clear()


# Singleton instance for the stub
_adapter_instance: WebhookDeliveryAdapterStub | None = None
_adapter_lock: asyncio.Lock | None = None


def _get_adapter_lock() -> asyncio.Lock:
    """Get or create the adapter lock for the current event loop.

    Returns:
        The asyncio.Lock for adapter access.
    """
    global _adapter_lock
    if _adapter_lock is None:
        _adapter_lock = asyncio.Lock()
    return _adapter_lock


async def get_webhook_delivery_adapter() -> WebhookDeliveryAdapterStub:
    """Get the singleton adapter instance.

    Returns:
        The WebhookDeliveryAdapterStub singleton.
    """
    global _adapter_instance
    if _adapter_instance is None:
        async with _get_adapter_lock():
            if _adapter_instance is None:
                _adapter_instance = WebhookDeliveryAdapterStub()
    return _adapter_instance


def reset_webhook_delivery_adapter() -> None:
    """Reset the singleton adapter (for testing).

    Also resets the lock to ensure clean state across different
    event loops in test scenarios.
    """
    global _adapter_instance, _adapter_lock
    if _adapter_instance is not None:
        _adapter_instance.reset()
    _adapter_instance = None
    _adapter_lock = None
