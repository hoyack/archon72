"""Dissent event for deliberation dissent recording (Story 2B.1, FR-11.8).

This module defines the DissentRecordedEvent dataclass for emitting when
a dissent is recorded in a 2-1 deliberation vote. The event is witnessed
in the hash chain for audit purposes.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - dissent is witnessed
- AT-6: Deliberation is collective judgment - minority voice preserved
- CT-14: Silence is expensive - even dissent terminates visibly
- NFR-10.4: 100% witness completeness
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


# Event type constant
DISSENT_RECORDED_EVENT_TYPE: str = "deliberation.dissent.recorded"

# Schema version for forward compatibility
DISSENT_RECORDED_SCHEMA_VERSION: int = 1


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class DissentRecordedEvent:
    """Event emitted when dissent is recorded (FR-11.8, CT-12).

    This event is witnessed in the hash chain for audit purposes.
    Note: Full rationale is NOT included - only hash reference for privacy.

    Constitutional Constraints:
    - CT-12: Witnessing creates accountability
    - AT-6: Minority voice preserved for collective judgment record
    - NFR-10.4: 100% witness completeness

    Attributes:
        event_id: UUIDv7 for this event.
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        dissent_archon_id: ID of dissenting archon.
        dissent_disposition: What they voted for (ACKNOWLEDGE, REFER, ESCALATE).
        rationale_hash: Blake3 hash of rationale (hex-encoded).
        majority_disposition: The winning outcome.
        recorded_at: Timestamp of recording.
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    petition_id: UUID
    dissent_archon_id: UUID
    dissent_disposition: str  # Serialized enum value
    rationale_hash: str  # Hex-encoded Blake3 hash
    majority_disposition: str  # Serialized enum value
    recorded_at: datetime = field(default_factory=_utc_now)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate event invariants."""
        self._validate_dispositions()
        self._validate_hash()

    def _validate_dispositions(self) -> None:
        """Validate dissent differs from majority.

        Raises:
            ValueError: If dispositions match.
        """
        if self.dissent_disposition == self.majority_disposition:
            raise ValueError(
                f"Dissent disposition ({self.dissent_disposition}) "
                f"cannot match majority disposition ({self.majority_disposition})"
            )

    def _validate_hash(self) -> None:
        """Validate rationale hash format.

        Raises:
            ValueError: If hash is not 64 hex characters (32 bytes).
        """
        if len(self.rationale_hash) != 64:
            raise ValueError(
                f"rationale_hash must be 64 hex characters (32 bytes Blake3), "
                f"got {len(self.rationale_hash)}"
            )
        # Validate it's valid hex
        try:
            bytes.fromhex(self.rationale_hash)
        except ValueError as e:
            raise ValueError(f"rationale_hash must be valid hex: {e}") from e

    @property
    def event_type(self) -> str:
        """Return the event type constant."""
        return DISSENT_RECORDED_EVENT_TYPE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_type": self.event_type,
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "dissent_archon_id": str(self.dissent_archon_id),
            "dissent_disposition": self.dissent_disposition,
            "rationale_hash": self.rationale_hash,
            "majority_disposition": self.majority_disposition,
            "recorded_at": self.recorded_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "schema_version": DISSENT_RECORDED_SCHEMA_VERSION,
        }
