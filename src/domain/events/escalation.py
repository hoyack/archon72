"""Escalation event payloads (Story 6.2, FR31).

This module defines event payloads for breach escalation and acknowledgment:
- EscalationEventPayload: When a breach escalates to Conclave agenda after 7 days
- BreachAcknowledgedEventPayload: When a breach is acknowledged, stopping escalation
- ResponseChoice: Acknowledgment response options

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> All escalations must be logged
- CT-12: Witnessing creates accountability -> All escalation events MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating escalation events
2. WITNESS EVERYTHING - All escalation events must be witnessed
3. FAIL LOUD - Never silently swallow escalation detection
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from src.domain.events.breach import BreachType

# Event type constants for escalation
ESCALATION_EVENT_TYPE: str = "breach.escalated"
BREACH_ACKNOWLEDGED_EVENT_TYPE: str = "breach.acknowledged"


class ResponseChoice(str, Enum):
    """Acknowledgment response choices for breaches (FR31).

    Acknowledgment requires attributed response choice, not template confirmation.
    This ensures accountability for how breaches are handled.

    Constitutional Constraint (FR31):
    Each acknowledgment must specify the response type taken for the breach.
    """

    CORRECTIVE = "corrective"
    """Taking corrective action to address the breach."""

    DISMISS = "dismiss"
    """Dismissing as false positive after investigation."""

    DEFER = "defer"
    """Deferring to future Conclave session for full review."""

    ACCEPT = "accept"
    """Accepting breach as known limitation with documented rationale."""


@dataclass(frozen=True, eq=True)
class EscalationEventPayload:
    """Payload for breach escalation to Conclave agenda (FR31).

    An EscalationEventPayload is created when a breach remains unacknowledged
    for 7 days and must be escalated to the Conclave agenda.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: Integrity outranks availability

    Attributes:
        escalation_id: Unique identifier for this escalation event.
        breach_id: Reference to the original breach being escalated.
        breach_type: Category of the original breach (from BreachEventPayload).
        escalation_timestamp: When the escalation was triggered (UTC).
        days_since_breach: Number of days since breach was declared.
        agenda_placement_reason: Reason for agenda placement (e.g., "7-day unacknowledged breach per FR31").
    """

    escalation_id: UUID
    breach_id: UUID
    breach_type: BreachType
    escalation_timestamp: datetime
    days_since_breach: int
    agenda_placement_reason: str

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "agenda_placement_reason": self.agenda_placement_reason,
            "breach_id": str(self.breach_id),
            "breach_type": self.breach_type.value,
            "days_since_breach": self.days_since_breach,
            "escalation_id": str(self.escalation_id),
            "escalation_timestamp": self.escalation_timestamp.isoformat(),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "escalation_id": str(self.escalation_id),
            "breach_id": str(self.breach_id),
            "breach_type": self.breach_type.value,
            "escalation_timestamp": self.escalation_timestamp.isoformat(),
            "days_since_breach": self.days_since_breach,
            "agenda_placement_reason": self.agenda_placement_reason,
        }


@dataclass(frozen=True, eq=True)
class BreachAcknowledgedEventPayload:
    """Payload for breach acknowledgment events (FR31).

    A BreachAcknowledgedEventPayload is created when a breach is acknowledged,
    stopping the 7-day escalation timer.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR31: Acknowledgment stops the 7-day escalation timer
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        acknowledgment_id: Unique identifier for this acknowledgment event.
        breach_id: Reference to the breach being acknowledged.
        acknowledged_by: Attribution of who acknowledged the breach.
        acknowledgment_timestamp: When the acknowledgment occurred (UTC).
        response_choice: The type of response taken (CORRECTIVE, DISMISS, DEFER, ACCEPT).
    """

    acknowledgment_id: UUID
    breach_id: UUID
    acknowledged_by: str
    acknowledgment_timestamp: datetime
    response_choice: ResponseChoice

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "acknowledged_by": self.acknowledged_by,
            "acknowledgment_id": str(self.acknowledgment_id),
            "acknowledgment_timestamp": self.acknowledgment_timestamp.isoformat(),
            "breach_id": str(self.breach_id),
            "response_choice": self.response_choice.value,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "acknowledgment_id": str(self.acknowledgment_id),
            "breach_id": str(self.breach_id),
            "acknowledged_by": self.acknowledged_by,
            "acknowledgment_timestamp": self.acknowledgment_timestamp.isoformat(),
            "response_choice": self.response_choice.value,
        }
