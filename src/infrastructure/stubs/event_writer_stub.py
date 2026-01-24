"""Stub EventWriterService for testing (CT-12 witnessed event emission)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class EventWriterStub:
    """Simple in-memory event writer stub.

    Stores events written via write_event() for assertions in tests.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def write_event(
        self,
        *,
        event_type: str,
        event_payload: dict[str, Any],
        agent_id: str | None = None,
        local_timestamp: datetime | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Record an event in memory.

        Args:
            event_type: Event type classification.
            event_payload: Event payload dictionary.
            agent_id: Optional agent identifier.
            local_timestamp: Optional timestamp for the event.
            **kwargs: Ignored extra fields for compatibility.

        Returns:
            The stored event dict.
        """
        event = {
            "event_type": event_type,
            "event_payload": event_payload,
            "agent_id": agent_id,
            "local_timestamp": (local_timestamp or datetime.now(timezone.utc)),
        }
        self.events.append(event)
        return event

    def clear(self) -> None:
        """Clear all recorded events."""
        self.events.clear()


__all__ = ["EventWriterStub"]
