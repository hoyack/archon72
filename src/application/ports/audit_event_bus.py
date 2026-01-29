"""Port definition for Audit Event Bus.

Admin PUBLISHES events. Witness SUBSCRIBES independently.

Admin does not call Witness directly (branch boundary).
Admin does not require Witness acknowledgment (cannot compel Judicial).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditEvent:
    """An audit event published by the Administrative branch."""

    event_type: str
    timestamp: str  # ISO8601
    source: str = "administrative"
    program_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # "info" | "warning" | "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "source": self.source,
            "program_id": self.program_id,
            "payload": self.payload,
            "severity": self.severity,
        }


class AuditEventBus(ABC):
    """Port for publishing audit events.

    Admin publishes events to this bus. Witness subscribes
    independently - Admin's responsibility ends at publishing.
    Whether Witness observes is not Admin's problem or authority.
    """

    @abstractmethod
    async def publish(self, event: AuditEvent) -> None:
        """Publish event to bus. Fire-and-forget from Admin's perspective.

        Args:
            event: The audit event to publish.
        """
        ...


# Events Admin publishes that Witness may observe:
CRITICAL_AUDIT_EVENTS = [
    "administrative.blocker.escalated",
    "administrative.program.halted",
    "administrative.task.unusual_transition",
    "administrative.capacity.attestation_breach",
]
