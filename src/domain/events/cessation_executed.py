"""Cessation executed event payload (Story 7.3, FR40, NFR40).

This module defines the terminal event that marks system cessation.
Once a CESSATION_EXECUTED event is written, NO further events may be appended.

Constitutional Constraints:
- FR40: No cessation_reversal event type in schema
- NFR40: Cessation reversal is architecturally prohibited
- CT-11: Silent failure destroys legitimacy -> All cessation events must be logged
- CT-12: Witnessing creates accountability -> Must be witnessed
- CT-13: Integrity outranks availability -> System terminates permanently

Developer Golden Rules:
1. TERMINAL EVENT - is_terminal is ALWAYS True (immutable)
2. WITNESS EVERYTHING - Cessation execution must be witnessed
3. FAIL LOUD - Post-cessation writes must raise SchemaIrreversibilityError
4. NO REVERSAL - This event type has no undo/revert/rollback equivalent

NFR40 COMPLIANCE:
=================
By architectural design, this is a TERMINAL event. The schema intentionally
contains NO event type that can reverse, undo, or cancel this event.
Import-time validation ensures no such types can be added.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

# Event type constant - TERMINAL marker
CESSATION_EXECUTED_EVENT_TYPE: str = "cessation.executed"


@dataclass(frozen=True, eq=True)
class CessationExecutedEventPayload:
    """Payload for cessation execution event (FR40, NFR40).

    A CessationExecutedEventPayload is created when the system enters
    permanent cessation. This is a TERMINAL event - no further events
    may be written after this point.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR40: No cessation_reversal event type exists
    - NFR40: Cessation reversal is architecturally prohibited
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: Integrity outranks availability -> Permanent termination

    TERMINAL SEMANTICS:
    The is_terminal field is ALWAYS True. This is enforced by:
    1. The dataclass constructor (default=True)
    2. The frozen=True constraint (immutable)
    3. Post-construction validation in create() method

    Attributes:
        cessation_id: Unique identifier for this cessation event.
        execution_timestamp: When cessation was executed (UTC).
        is_terminal: ALWAYS True - marks this as the final event.
        final_sequence_number: Last valid sequence number before cessation.
        final_hash: SHA-256 hash of the last event before cessation.
        reason: Human-readable reason for cessation (from agenda).
        triggering_event_id: Reference to the agenda placement event that
            triggered this cessation (FR37, FR38, or FR39 trigger).
    """

    cessation_id: UUID
    execution_timestamp: datetime
    is_terminal: bool  # ALWAYS True - no setter, frozen dataclass
    final_sequence_number: int
    final_hash: str
    reason: str
    triggering_event_id: UUID

    def __post_init__(self) -> None:
        """Validate terminal semantics (NFR40).

        Constitutional Constraint:
        The is_terminal field MUST be True. Any attempt to create
        a non-terminal cessation event is a constitutional violation.
        """
        if not self.is_terminal:
            # This should never happen due to frozen=True and create() factory
            # But we validate anyway for defense-in-depth
            raise ValueError(
                "NFR40: CessationExecutedEventPayload.is_terminal must be True. "
                "Cessation is architecturally irreversible."
            )

    @classmethod
    def create(
        cls,
        cessation_id: UUID,
        execution_timestamp: datetime,
        final_sequence_number: int,
        final_hash: str,
        reason: str,
        triggering_event_id: UUID,
    ) -> CessationExecutedEventPayload:
        """Factory method to create a cessation event (recommended).

        This factory method enforces is_terminal=True and provides
        a clean API without exposing the terminal field.

        Args:
            cessation_id: Unique identifier for this cessation.
            execution_timestamp: When cessation occurred (UTC).
            final_sequence_number: Last valid sequence number.
            final_hash: SHA-256 hash of the last event.
            reason: Human-readable cessation reason.
            triggering_event_id: Reference to triggering agenda event.

        Returns:
            CessationExecutedEventPayload with is_terminal=True.
        """
        return cls(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            is_terminal=True,  # ALWAYS True - NFR40
            final_sequence_number=final_sequence_number,
            final_hash=final_hash,
            reason=reason,
            triggering_event_id=triggering_event_id,
        )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        The is_terminal field is INCLUDED in the signature to
        cryptographically bind the terminal semantics.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "cessation_id": str(self.cessation_id),
            "execution_timestamp": self.execution_timestamp.isoformat(),
            "final_hash": self.final_hash,
            "final_sequence_number": self.final_sequence_number,
            "is_terminal": self.is_terminal,  # Included for binding
            "reason": self.reason,
            "triggering_event_id": str(self.triggering_event_id),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().

        Note (FR43 AC2):
            The dict includes both canonical field names AND API-friendly aliases:
            - reason -> also exposed as trigger_reason
            - triggering_event_id -> also exposed as trigger_source
            - final_sequence_number -> also exposed as final_sequence
        """
        return {
            "cessation_id": str(self.cessation_id),
            "execution_timestamp": self.execution_timestamp.isoformat(),
            "is_terminal": self.is_terminal,
            "final_sequence_number": self.final_sequence_number,
            "final_sequence": self.final_sequence_number,  # FR43 AC2 alias
            "final_hash": self.final_hash,
            "reason": self.reason,
            "trigger_reason": self.reason,  # FR43 AC2 alias
            "triggering_event_id": str(self.triggering_event_id),
            "trigger_source": str(self.triggering_event_id),  # FR43 AC2 alias
        }

    @property
    def trigger_reason(self) -> str:
        """Human-readable reason for cessation (FR43 AC2 alias for reason)."""
        return self.reason

    @property
    def trigger_source(self) -> UUID:
        """Reference to triggering event (FR43 AC2 alias for triggering_event_id)."""
        return self.triggering_event_id

    @property
    def final_sequence(self) -> int:
        """Final sequence number (FR43 AC2 alias for final_sequence_number)."""
        return self.final_sequence_number
