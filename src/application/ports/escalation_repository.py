"""Escalation repository protocol (Story 6.2, FR31).

This module defines the protocol for persisting and retrieving
escalation and acknowledgment events.

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> All operations must be logged
"""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from src.domain.events.escalation import (
    BreachAcknowledgedEventPayload,
    EscalationEventPayload,
)


class EscalationRepositoryProtocol(Protocol):
    """Protocol for escalation repository operations (FR31).

    Provides persistence for escalation and acknowledgment events.

    Constitutional Constraint (FR31):
    Repository supports tracking escalation and acknowledgment state.
    """

    async def save_escalation(self, escalation: EscalationEventPayload) -> None:
        """Save an escalation event.

        Args:
            escalation: The escalation event payload to persist.

        Raises:
            BreachAlreadyEscalatedError: If escalation already exists for breach.
        """
        ...

    async def save_acknowledgment(
        self, acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Save an acknowledgment event.

        Args:
            acknowledgment: The acknowledgment event payload to persist.

        Raises:
            BreachAlreadyAcknowledgedError: If acknowledgment already exists for breach.
        """
        ...

    async def get_acknowledgment_for_breach(
        self, breach_id: UUID
    ) -> Optional[BreachAcknowledgedEventPayload]:
        """Get the acknowledgment for a specific breach.

        Args:
            breach_id: UUID of the breach.

        Returns:
            The acknowledgment event payload, or None if not acknowledged.
        """
        ...

    async def get_escalation_for_breach(
        self, breach_id: UUID
    ) -> Optional[EscalationEventPayload]:
        """Get the escalation for a specific breach.

        Args:
            breach_id: UUID of the breach.

        Returns:
            The escalation event payload, or None if not escalated.
        """
        ...

    async def list_escalations(self) -> list[EscalationEventPayload]:
        """List all escalation events.

        Returns:
            List of all escalation event payloads.
        """
        ...

    async def list_acknowledgments(self) -> list[BreachAcknowledgedEventPayload]:
        """List all acknowledgment events.

        Returns:
            List of all acknowledgment event payloads.
        """
        ...
