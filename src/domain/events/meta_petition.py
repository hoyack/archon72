"""META petition event payloads (Story 8.5, FR-10.4).

This module defines the event payloads for META petition lifecycle:
- MetaPetitionReceivedEventPayload: When META petition is routed to High Archon
- MetaPetitionResolvedEventPayload: When High Archon resolves META petition

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> All events must be logged
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
- CT-13: No writes during halt -> Event emission blocked during system halt
- FR-10.4: META petitions route to High Archon [P2]

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating META events (writes)
2. WITNESS EVERYTHING - All META petition events require attribution
3. FAIL LOUD - Never silently swallow signature errors
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.meta_petition import MetaDisposition

# Event type constants for META petition events
META_PETITION_RECEIVED_EVENT_TYPE: str = "meta_petition.received"
META_PETITION_RESOLVED_EVENT_TYPE: str = "meta_petition.resolved"

# Current schema version for META petition events (D2 compliance)
META_PETITION_EVENT_SCHEMA_VERSION: str = "1.0.0"


@dataclass(frozen=True, eq=True)
class MetaPetitionReceivedEventPayload:
    """Payload for META petition received events (Story 8.5, AC2, AC6).

    A MetaPetitionReceivedEventPayload is created when a META petition
    is received and routed to the High Archon queue, bypassing normal
    Three Fates deliberation.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-10.4: META petitions route to High Archon
    - AC2: META petitions bypass deliberation
    - AC6: Events are witnessed with Blake3 hash
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        petition_id: UUID of the META petition.
        submitter_id: UUID of the petition submitter.
        petition_text_preview: First 500 chars of petition text.
        received_at: When the petition was received (UTC).
        routing_reason: Why this petition was routed to High Archon.
                        Typically "EXPLICIT_META_TYPE".

    Usage:
        event = MetaPetitionReceivedEventPayload(
            petition_id=petition.id,
            submitter_id=petition.submitter_id,
            petition_text_preview=petition.text[:500],
            received_at=datetime.now(timezone.utc),
            routing_reason="EXPLICIT_META_TYPE",
        )
    """

    petition_id: UUID
    submitter_id: UUID
    petition_text_preview: str
    received_at: datetime
    routing_reason: str

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
            "petition_id": str(self.petition_id),
            "petition_text_preview": self.petition_text_preview,
            "received_at": self.received_at.isoformat(),
            "routing_reason": self.routing_reason,
            "submitter_id": str(self.submitter_id),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.
        FR-10.4: Immutable routing record for META petitions.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "submitter_id": str(self.submitter_id),
            "petition_text_preview": self.petition_text_preview,
            "received_at": self.received_at.isoformat(),
            "routing_reason": self.routing_reason,
            "schema_version": META_PETITION_EVENT_SCHEMA_VERSION,
        }


@dataclass(frozen=True, eq=True)
class MetaPetitionResolvedEventPayload:
    """Payload for META petition resolved events (Story 8.5, AC4, AC6).

    A MetaPetitionResolvedEventPayload is created when a High Archon
    resolves a META petition with a disposition.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-10.4: META petitions route to High Archon
    - AC4: Three disposition options (ACKNOWLEDGE, CREATE_ACTION, FORWARD)
    - AC6: Events are witnessed with Blake3 hash
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: High Archon explicit consent for handling

    Attributes:
        petition_id: UUID of the resolved META petition.
        disposition: High Archon's disposition (ACKNOWLEDGE, CREATE_ACTION, FORWARD).
        rationale: Required explanation from High Archon.
        high_archon_id: UUID of the High Archon who resolved.
        resolved_at: When the resolution occurred (UTC).
        forward_target: Target governance body if disposition is FORWARD.
                        Required if disposition == FORWARD, None otherwise.

    Usage:
        event = MetaPetitionResolvedEventPayload(
            petition_id=petition.id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Acknowledged the system feedback concern",
            high_archon_id=high_archon.id,
            resolved_at=datetime.now(timezone.utc),
            forward_target=None,
        )
    """

    petition_id: UUID
    disposition: MetaDisposition
    rationale: str
    high_archon_id: UUID
    resolved_at: datetime
    forward_target: str | None

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
            "disposition": self.disposition.value,
            "forward_target": self.forward_target,
            "high_archon_id": str(self.high_archon_id),
            "petition_id": str(self.petition_id),
            "rationale": self.rationale,
            "resolved_at": self.resolved_at.isoformat(),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.
        AC4: Immutable resolution record with disposition.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "disposition": self.disposition.value,
            "rationale": self.rationale,
            "high_archon_id": str(self.high_archon_id),
            "resolved_at": self.resolved_at.isoformat(),
            "forward_target": self.forward_target,
            "schema_version": META_PETITION_EVENT_SCHEMA_VERSION,
        }
