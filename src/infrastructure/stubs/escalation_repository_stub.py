"""Escalation Repository Stub (Story 6.2, FR31).

This module provides an in-memory stub implementation of EscalationRepositoryProtocol
for testing and development purposes.

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
"""

from __future__ import annotations

from uuid import UUID

from src.application.ports.escalation_repository import EscalationRepositoryProtocol
from src.domain.errors.escalation import (
    BreachAlreadyAcknowledgedError,
    BreachAlreadyEscalatedError,
)
from src.domain.events.escalation import (
    BreachAcknowledgedEventPayload,
    EscalationEventPayload,
)


class EscalationRepositoryStub(EscalationRepositoryProtocol):
    """In-memory stub for escalation repository (FR31).

    This stub provides an in-memory implementation of EscalationRepositoryProtocol
    for testing purposes. It stores escalations and acknowledgments in dictionaries
    keyed by breach_id.

    Constitutional Constraint (FR31):
    Repository supports tracking escalation and acknowledgment state for
    breach events.
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        # Map breach_id -> EscalationEventPayload
        self._escalations: dict[UUID, EscalationEventPayload] = {}
        # Map breach_id -> BreachAcknowledgedEventPayload
        self._acknowledgments: dict[UUID, BreachAcknowledgedEventPayload] = {}

    def clear(self) -> None:
        """Clear all stored data for test cleanup."""
        self._escalations.clear()
        self._acknowledgments.clear()

    async def save_escalation(self, escalation: EscalationEventPayload) -> None:
        """Save an escalation event.

        Args:
            escalation: The escalation event payload to persist.

        Raises:
            BreachAlreadyEscalatedError: If escalation already exists for breach.
        """
        if escalation.breach_id in self._escalations:
            raise BreachAlreadyEscalatedError(escalation.breach_id)

        self._escalations[escalation.breach_id] = escalation

    async def save_acknowledgment(
        self, acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Save an acknowledgment event.

        Args:
            acknowledgment: The acknowledgment event payload to persist.

        Raises:
            BreachAlreadyAcknowledgedError: If acknowledgment already exists for breach.
        """
        if acknowledgment.breach_id in self._acknowledgments:
            raise BreachAlreadyAcknowledgedError(acknowledgment.breach_id)

        self._acknowledgments[acknowledgment.breach_id] = acknowledgment

    async def get_acknowledgment_for_breach(
        self, breach_id: UUID
    ) -> BreachAcknowledgedEventPayload | None:
        """Get the acknowledgment for a specific breach.

        Args:
            breach_id: UUID of the breach.

        Returns:
            The acknowledgment event payload, or None if not acknowledged.
        """
        return self._acknowledgments.get(breach_id)

    async def get_escalation_for_breach(
        self, breach_id: UUID
    ) -> EscalationEventPayload | None:
        """Get the escalation for a specific breach.

        Args:
            breach_id: UUID of the breach.

        Returns:
            The escalation event payload, or None if not escalated.
        """
        return self._escalations.get(breach_id)

    async def list_escalations(self) -> list[EscalationEventPayload]:
        """List all escalation events.

        Returns:
            List of all escalation event payloads.
        """
        return list(self._escalations.values())

    async def list_acknowledgments(self) -> list[BreachAcknowledgedEventPayload]:
        """List all acknowledgment events.

        Returns:
            List of all acknowledgment event payloads.
        """
        return list(self._acknowledgments.values())
