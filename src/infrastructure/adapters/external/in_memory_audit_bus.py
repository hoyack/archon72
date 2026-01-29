"""In-Memory Audit Event Bus implementation.

Simple in-memory implementation of the AuditEventBus port.
Stores events in a list for inspection in tests and simulation mode.

Admin PUBLISHES events. Witness SUBSCRIBES independently.
Admin does not call Witness directly (branch boundary).
"""

from __future__ import annotations

from structlog import get_logger

from src.application.ports.audit_event_bus import AuditEvent, AuditEventBus

logger = get_logger(__name__)


class InMemoryAuditEventBus(AuditEventBus):
    """In-memory audit event bus for tests and simulation.

    Stores published events in a list. In production, this would
    be replaced by a persistent bus implementation.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        logger.info("in_memory_audit_bus_initialized")

    async def publish(self, event: AuditEvent) -> None:
        """Publish event to in-memory store."""
        self._events.append(event)
        logger.info(
            "audit_event_published",
            event_type=event.event_type,
            program_id=event.program_id,
            severity=event.severity,
        )

    @property
    def events(self) -> list[AuditEvent]:
        """Access published events (read-only view)."""
        return list(self._events)

    def clear(self) -> None:
        """Clear all stored events."""
        self._events.clear()

    def count(self) -> int:
        """Return number of stored events."""
        return len(self._events)
