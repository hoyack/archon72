"""Escalation protocol (Story 6.2, FR31).

This module defines the protocol for escalation operations including
escalating breaches to Conclave agenda and acknowledging breaches.

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events must be witnessed
"""

from __future__ import annotations

from typing import Any, Optional, Protocol
from uuid import UUID

from src.domain.events.escalation import (
    BreachAcknowledgedEventPayload,
    EscalationEventPayload,
    ResponseChoice,
)
from src.domain.models.pending_escalation import PendingEscalation


class EscalationProtocol(Protocol):
    """Protocol for escalation operations (FR31).

    Constitutional Constraints:
    - FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
    - CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
    - CT-12: Witnessing creates accountability -> All events MUST be witnessed
    """

    async def escalate_breach(self, breach_id: UUID) -> EscalationEventPayload:
        """Escalate a breach to the Conclave agenda (FR31).

        Constitutional Constraint (FR31):
        Unacknowledged breaches after 7 days SHALL escalate.

        CRITICAL: Must check halt state before operation (CT-11).
        CRITICAL: Event MUST be witnessed (CT-12).

        Args:
            breach_id: UUID of the breach to escalate.

        Returns:
            The created EscalationEventPayload.

        Raises:
            BreachNotFoundError: If breach does not exist.
            BreachAlreadyEscalatedError: If breach was already escalated.
            SystemHaltedError: If system is in halted state.
        """
        ...

    async def acknowledge_breach(
        self,
        breach_id: UUID,
        acknowledged_by: str,
        response_choice: ResponseChoice,
    ) -> BreachAcknowledgedEventPayload:
        """Acknowledge a breach, stopping escalation timer (FR31).

        Constitutional Constraint (FR31):
        Acknowledgment stops the 7-day escalation timer.

        CRITICAL: Must check halt state before operation (CT-11).
        CRITICAL: Event MUST be witnessed (CT-12).

        Args:
            breach_id: UUID of the breach to acknowledge.
            acknowledged_by: Attribution of who is acknowledging.
            response_choice: The type of response taken.

        Returns:
            The created BreachAcknowledgedEventPayload.

        Raises:
            BreachNotFoundError: If breach does not exist.
            BreachAlreadyAcknowledgedError: If breach was already acknowledged.
            InvalidAcknowledgmentError: If acknowledgment details are invalid.
            SystemHaltedError: If system is in halted state.
        """
        ...

    async def get_pending_escalations(self) -> list[PendingEscalation]:
        """Get all breaches approaching 7-day escalation deadline (FR31).

        Constitutional Constraint (FR31):
        Query pending escalations to see breaches approaching deadline
        and time remaining.

        CRITICAL: Must check halt state before operation (CT-11).

        Returns:
            List of PendingEscalation sorted by urgency (least time remaining first).

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        ...

    async def is_breach_acknowledged(self, breach_id: UUID) -> bool:
        """Check if a breach has been acknowledged (FR31).

        Args:
            breach_id: UUID of the breach to check.

        Returns:
            True if breach has been acknowledged, False otherwise.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        ...

    async def is_breach_escalated(self, breach_id: UUID) -> bool:
        """Check if a breach has been escalated (FR31).

        Args:
            breach_id: UUID of the breach to check.

        Returns:
            True if breach has been escalated, False otherwise.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        ...

    async def get_breach_status(self, breach_id: UUID) -> Optional[dict[str, Any]]:
        """Get the escalation/acknowledgment status of a breach (FR31).

        Args:
            breach_id: UUID of the breach to check.

        Returns:
            Dict with keys: is_acknowledged, is_escalated,
            acknowledgment_details, escalation_details.
            None if breach not found.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        ...
