"""Deliberation cancelled event (Story 5.6, AC4).

This module defines the DeliberationCancelledEvent for recording when a
deliberation session is cancelled, typically due to auto-escalation when
co-signer thresholds are reached.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- CT-12: All outputs through witnessing pipeline
- CT-14: Silence must be expensive - ensures King attention via auto-escalation

Developer Golden Rules:
1. WITNESS EVERYTHING - Cancellation events must be witnessed (CT-12)
2. USE to_dict() - Never use asdict() for event serialization (D2)
3. INCLUDE schema_version - All event payloads require schema_version (D2)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


# Event type constant
DELIBERATION_CANCELLED_EVENT_TYPE: str = "deliberation.session.cancelled"

# Schema version for D2 compliance
DELIBERATION_CANCELLED_SCHEMA_VERSION: int = 1


class CancelReason(Enum):
    """Reason for deliberation cancellation.

    Values:
        AUTO_ESCALATED: Cancelled because petition auto-escalated due to
                        co-signer threshold being reached (FR-5.1).
        TIMEOUT: Cancelled due to deliberation timeout expiry.
        MANUAL: Cancelled manually by system administrator.
        PETITION_WITHDRAWN: Cancelled because the petition was withdrawn.
    """

    AUTO_ESCALATED = "AUTO_ESCALATED"
    TIMEOUT = "TIMEOUT"
    MANUAL = "MANUAL"
    PETITION_WITHDRAWN = "PETITION_WITHDRAWN"


@dataclass(frozen=True, eq=True)
class DeliberationCancelledEvent:
    """Event emitted when a deliberation session is cancelled (Story 5.6, AC4).

    A DeliberationCancelledEvent is created when a deliberation session
    is cancelled before reaching completion. The primary use case is
    auto-escalation due to co-signer thresholds (FR-5.1).

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-5.1: System SHALL ESCALATE petition when threshold reached
    - CT-12: Witnessing creates accountability - must be witnessed
    - CT-14: Silence must be expensive - ensures proper termination

    Attributes:
        event_id: Unique identifier for this cancellation event.
        session_id: The deliberation session being cancelled.
        petition_id: The petition that was being deliberated.
        cancel_reason: Why the deliberation was cancelled.
        cancelled_at: When the cancellation occurred (UTC).
        cancelled_by: Actor who triggered cancellation, or None for system.
        transcript_preserved: Whether the session transcript was preserved.
        participating_archons: Tuple of archon UUIDs notified of cancellation.
        escalation_id: If AUTO_ESCALATED, the escalation event ID.
        schema_version: Schema version for D2 compliance.
    """

    event_id: UUID
    session_id: UUID
    petition_id: UUID
    cancel_reason: CancelReason
    cancelled_at: datetime
    cancelled_by: UUID | None = None
    transcript_preserved: bool = True
    participating_archons: tuple[UUID, ...] = field(default_factory=tuple)
    escalation_id: UUID | None = None
    schema_version: int = DELIBERATION_CANCELLED_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_schema_version()
        self._validate_escalation_consistency()

    def _validate_schema_version(self) -> None:
        """Validate schema version is current."""
        if self.schema_version != DELIBERATION_CANCELLED_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {DELIBERATION_CANCELLED_SCHEMA_VERSION}, "
                f"got {self.schema_version}"
            )

    def _validate_escalation_consistency(self) -> None:
        """Validate escalation_id is present only for AUTO_ESCALATED."""
        if self.cancel_reason == CancelReason.AUTO_ESCALATED:
            if self.escalation_id is None:
                raise ValueError(
                    "escalation_id is required when cancel_reason is AUTO_ESCALATED"
                )

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
            "cancel_reason": self.cancel_reason.value,
            "cancelled_at": self.cancelled_at.isoformat(),
            "cancelled_by": str(self.cancelled_by) if self.cancelled_by else None,
            "escalation_id": str(self.escalation_id) if self.escalation_id else None,
            "event_id": str(self.event_id),
            "participating_archons": [str(a) for a in self.participating_archons],
            "petition_id": str(self.petition_id),
            "schema_version": self.schema_version,
            "session_id": str(self.session_id),
            "transcript_preserved": self.transcript_preserved,
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
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "cancel_reason": self.cancel_reason.value,
            "cancelled_at": self.cancelled_at.isoformat(),
            "cancelled_by": str(self.cancelled_by) if self.cancelled_by else None,
            "transcript_preserved": self.transcript_preserved,
            "participating_archons": [str(a) for a in self.participating_archons],
            "escalation_id": str(self.escalation_id) if self.escalation_id else None,
            "schema_version": self.schema_version,
        }
