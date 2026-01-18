"""Unit tests for ViolationEventSubscriber.

Tests the event subscription layer that triggers legitimacy decay
when violation events are received (AC8).
"""

from collections.abc import Callable
from uuid import uuid4

import pytest

from src.application.services.governance.violation_event_subscriber import (
    VIOLATION_EVENT_PATTERN,
    ViolationEventSubscriber,
)
from src.domain.governance.legitimacy.violation_severity import ViolationSeverity


class FakeEvent:
    """Fake event for testing."""

    def __init__(
        self,
        event_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        self.event_id = uuid4() if not event_id else uuid4()
        self.event_type = event_type
        self.payload = payload


class FakeEventBus:
    """Fake event bus for testing subscriptions."""

    def __init__(self) -> None:
        self.subscriptions: dict[str, list[Callable]] = {}

    def subscribe(
        self,
        pattern: str,
        handler: Callable,
    ) -> None:
        """Subscribe to events matching pattern."""
        if pattern not in self.subscriptions:
            self.subscriptions[pattern] = []
        self.subscriptions[pattern].append(handler)

    async def emit(self, event: FakeEvent) -> None:
        """Emit an event to matching subscribers."""
        for pattern, handlers in self.subscriptions.items():
            if self._pattern_matches(pattern, event.event_type):
                for handler in handlers:
                    await handler(event)

    def _pattern_matches(self, pattern: str, event_type: str) -> bool:
        """Check if pattern matches event type."""
        # Simple wildcard matching
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return event_type.startswith(prefix)
        return pattern == event_type


class FakeDecayService:
    """Fake decay service for testing."""

    def __init__(self) -> None:
        self.violations_processed: list[tuple] = []

    async def process_violation(
        self,
        violation_event_id,
        violation_type: str,
    ):
        """Record the violation for testing."""
        self.violations_processed.append((violation_event_id, violation_type))
        # Return a dummy result
        from src.application.ports.governance.legitimacy_decay_port import DecayResult

        return DecayResult(
            transition_occurred=True,
            new_state=None,
            violation_event_id=violation_event_id,
            severity=ViolationSeverity.MINOR,
            bands_dropped=1,
        )


class TestViolationEventSubscriber:
    """Tests for ViolationEventSubscriber."""

    def test_subscribes_to_violation_pattern(self) -> None:
        """Subscriber subscribes to constitutional.violation.* events."""
        event_bus = FakeEventBus()
        decay_service = FakeDecayService()

        ViolationEventSubscriber(decay_service, event_bus)

        assert VIOLATION_EVENT_PATTERN in event_bus.subscriptions
        assert len(event_bus.subscriptions[VIOLATION_EVENT_PATTERN]) == 1

    @pytest.mark.asyncio
    async def test_handles_violation_event(self) -> None:
        """Handler triggers decay service for violation events."""
        event_bus = FakeEventBus()
        decay_service = FakeDecayService()

        ViolationEventSubscriber(decay_service, event_bus)

        # Emit a violation event
        event = FakeEvent(
            event_id=str(uuid4()),
            event_type="constitutional.violation.coercion_blocked",
            payload={
                "violation_type": "coercion.filter_blocked",
                "description": "Coercion detected and blocked",
            },
        )
        await event_bus.emit(event)

        # Verify decay service was called
        assert len(decay_service.violations_processed) == 1
        _, violation_type = decay_service.violations_processed[0]
        assert violation_type == "coercion.filter_blocked"

    @pytest.mark.asyncio
    async def test_extracts_violation_type_from_payload(self) -> None:
        """Extracts violation_type from event payload."""
        event_bus = FakeEventBus()
        decay_service = FakeDecayService()

        ViolationEventSubscriber(decay_service, event_bus)

        event = FakeEvent(
            event_id=str(uuid4()),
            event_type="constitutional.violation.chain_gap",
            payload={
                "violation_type": "chain.discontinuity",
            },
        )
        await event_bus.emit(event)

        _, violation_type = decay_service.violations_processed[0]
        assert violation_type == "chain.discontinuity"

    @pytest.mark.asyncio
    async def test_uses_unknown_for_missing_violation_type(self) -> None:
        """Uses 'unknown' if violation_type not in payload."""
        event_bus = FakeEventBus()
        decay_service = FakeDecayService()

        ViolationEventSubscriber(decay_service, event_bus)

        event = FakeEvent(
            event_id=str(uuid4()),
            event_type="constitutional.violation.generic",
            payload={
                "description": "Something bad happened",
            },
        )
        await event_bus.emit(event)

        _, violation_type = decay_service.violations_processed[0]
        assert violation_type == "unknown"

    @pytest.mark.asyncio
    async def test_ignores_non_violation_events(self) -> None:
        """Does not process events that don't match pattern."""
        event_bus = FakeEventBus()
        decay_service = FakeDecayService()

        ViolationEventSubscriber(decay_service, event_bus)

        event = FakeEvent(
            event_id=str(uuid4()),
            event_type="constitutional.task.created",
            payload={},
        )
        await event_bus.emit(event)

        assert len(decay_service.violations_processed) == 0
