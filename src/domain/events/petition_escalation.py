"""Petition escalation event payloads (Story 5.6, FR-5.1, FR-5.3).

This module defines event payloads for petition auto-escalation when
co-signer thresholds are reached in the Three Fates system.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- CT-12: All outputs through witnessing pipeline
- CT-14: Silence must be expensive - auto-escalation ensures petitions get King attention

Developer Golden Rules:
1. WITNESS EVERYTHING - All escalation events must be witnessed (CT-12)
2. USE to_dict() - Never use asdict() for event serialization (D2)
3. INCLUDE schema_version - All event payloads require schema_version (D2)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

# Event type constant for petition escalation triggered
PETITION_ESCALATION_TRIGGERED_EVENT_TYPE: str = "petition.escalation.triggered"

# Schema version for D2 compliance
PETITION_ESCALATION_SCHEMA_VERSION: int = 1


@dataclass(frozen=True, eq=True)
class PetitionEscalationTriggeredEvent:
    """Event payload for petition auto-escalation (Story 5.6, FR-5.1, FR-5.3).

    A PetitionEscalationTriggeredEvent is created when a petition's co-signer
    count reaches its escalation threshold (CESSATION=100, GRIEVANCE=50).

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-5.1: System SHALL ESCALATE petition when threshold reached
    - FR-5.3: Event SHALL include co_signer_count at time of trigger
    - CT-12: Witnessing creates accountability - must be witnessed
    - CT-14: Silence must be expensive - ensures King attention

    Attributes:
        escalation_id: Unique identifier for this escalation event.
        petition_id: The petition being escalated.
        trigger_type: Type of trigger (e.g., "CO_SIGNER_THRESHOLD").
        co_signer_count: Co-signer count at time of trigger.
        threshold: The threshold that was reached (100 for CESSATION, 50 for GRIEVANCE).
        triggered_at: When the escalation was triggered (UTC).
        triggered_by: UUID of the signer who triggered threshold, or None for system.
        petition_type: Type of petition (CESSATION, GRIEVANCE, etc.).
        escalation_source: Source of escalation (e.g., "CO_SIGNER_THRESHOLD").
        realm_id: The realm for King queue routing.
        schema_version: Schema version for D2 compliance.
    """

    escalation_id: UUID
    petition_id: UUID
    trigger_type: str
    co_signer_count: int
    threshold: int
    triggered_at: datetime
    triggered_by: UUID | None = None
    petition_type: str | None = None
    escalation_source: str = "CO_SIGNER_THRESHOLD"
    realm_id: str = "default"
    schema_version: int = PETITION_ESCALATION_SCHEMA_VERSION

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
            "co_signer_count": self.co_signer_count,
            "escalation_id": str(self.escalation_id),
            "escalation_source": self.escalation_source,
            "petition_id": str(self.petition_id),
            "petition_type": self.petition_type,
            "realm_id": self.realm_id,
            "schema_version": self.schema_version,
            "threshold": self.threshold,
            "trigger_type": self.trigger_type,
            "triggered_at": self.triggered_at.isoformat(),
            "triggered_by": str(self.triggered_by) if self.triggered_by else None,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage (D2 compliance).

        IMPORTANT: Use this method, NOT asdict(), for event serialization.
        asdict() doesn't handle UUID and datetime serialization correctly.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "escalation_id": str(self.escalation_id),
            "petition_id": str(self.petition_id),
            "trigger_type": self.trigger_type,
            "co_signer_count": self.co_signer_count,
            "threshold": self.threshold,
            "triggered_at": self.triggered_at.isoformat(),
            "triggered_by": str(self.triggered_by) if self.triggered_by else None,
            "petition_type": self.petition_type,
            "escalation_source": self.escalation_source,
            "realm_id": self.realm_id,
            "schema_version": self.schema_version,
        }
