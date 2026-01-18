"""Unit tests for NotificationPublisherPort (Story 4.8, Task 5).

Tests verifying the port interface and protocol compliance.

Constitutional Constraints:
- SR-9: Observer push notifications for breach events.
- RT-5: Breach events pushed to multiple channels.
"""

from typing import Protocol
from uuid import uuid4

import pytest

from src.application.ports.notification_publisher import NotificationPublisherPort


class MockEvent:
    """Mock Event for testing."""

    def __init__(self) -> None:
        self.event_id = uuid4()
        self.event_type = "breach"
        self.sequence = 42
        self.content_hash = "a" * 64


class TestNotificationPublisherPort:
    """Tests for NotificationPublisherPort interface."""

    def test_port_is_protocol(self) -> None:
        """Test that NotificationPublisherPort is a Protocol."""
        assert issubclass(NotificationPublisherPort, Protocol)

    def test_port_notify_event_signature(self) -> None:
        """Test that port has notify_event method with correct signature."""
        # Check that notify_event is defined
        assert hasattr(NotificationPublisherPort, "notify_event")

        # Get the method
        method = NotificationPublisherPort.notify_event

        # Check it takes event parameter
        import inspect

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have self and event
        assert "self" in params
        assert "event" in params

    def test_notification_service_implements_port(self) -> None:
        """Test that NotificationService implements NotificationPublisherPort."""
        from src.application.services.notification_service import NotificationService

        # Create instance
        service = NotificationService()

        # Check it has the required method
        assert hasattr(service, "notify_event")
        assert callable(service.notify_event)

    @pytest.mark.asyncio
    async def test_port_can_be_called(self) -> None:
        """Test that port method can be called on implementation."""
        from src.application.services.notification_service import NotificationService

        service = NotificationService()
        event = MockEvent()

        # Should not raise
        await service.notify_event(event)
