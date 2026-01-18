"""Violation event subscriber for legitimacy decay.

This module subscribes to constitutional violation events and triggers
the legitimacy decay service to process them.

Constitutional Compliance:
- AC1: Auto-transition downward based on violation events (FR29)
- AC8: Multiple violations accumulate (don't reset on transition)
"""

from typing import Any, Protocol

# Event pattern for violation events
VIOLATION_EVENT_PATTERN = "constitutional.violation.*"


class EventBusProtocol(Protocol):
    """Protocol for event bus subscription."""

    def subscribe(self, pattern: str, handler: Any) -> None:
        """Subscribe to events matching pattern."""
        ...


class DecayServiceProtocol(Protocol):
    """Protocol for decay service."""

    async def process_violation(
        self,
        violation_event_id: Any,
        violation_type: str,
    ) -> Any:
        """Process a violation event."""
        ...


class ViolationEventSubscriber:
    """Subscribes to violation events and triggers legitimacy decay.

    This subscriber listens for constitutional.violation.* events
    and forwards them to the decay service for processing.

    Attributes:
        _decay_service: Service for processing violations.
        _event_bus: Event bus for subscribing to events.
    """

    def __init__(
        self,
        decay_service: DecayServiceProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize the subscriber.

        Args:
            decay_service: Service for processing violations.
            event_bus: Event bus for subscribing to events.
        """
        self._decay_service = decay_service
        self._event_bus = event_bus

        # Subscribe to violation events
        self._event_bus.subscribe(VIOLATION_EVENT_PATTERN, self._handle_event)

    async def _handle_event(self, event: Any) -> None:
        """Handle a violation event.

        Extracts violation information from the event and triggers
        the decay service.

        Args:
            event: The violation event to process.
        """
        # Extract violation type from payload, default to "unknown"
        violation_type = event.payload.get("violation_type", "unknown")

        # Process the violation
        await self._decay_service.process_violation(
            event.event_id,
            violation_type,
        )
