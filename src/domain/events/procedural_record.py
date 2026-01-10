"""Procedural record event types (Story 2.8, FR141-FR142).

This module defines the ProceduralRecordPayload and event type constant
for recording procedural records of deliberations. Procedural records
capture the full audit trail of a deliberation: agenda, participants,
votes, timeline, and decisions.

Constitutional Constraints:
- FR141: Procedural records SHALL be generated for each deliberation
- FR142: Records SHALL include agenda, participants, votes, timeline, decisions
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID

# Event type constant following lowercase.dot.notation convention
PROCEDURAL_RECORD_EVENT_TYPE: str = "deliberation.record.procedural"


@dataclass(frozen=True, eq=True)
class ProceduralRecordPayload:
    """Payload for procedural record events (FR141-FR142).

    Records the complete procedural record of a deliberation. The record
    captures all aspects of the deliberation for audit and verification
    purposes.

    Attributes:
        record_id: Unique identifier for this procedural record (UUID).
        deliberation_id: ID of the deliberation this record documents (UUID).
        agenda_items: Immutable tuple of agenda item descriptions.
        participant_ids: Immutable tuple of participant agent IDs.
        vote_summary: Immutable mapping of vote counts (e.g., {"aye": 45, "nay": 20}).
        timeline_events: Immutable tuple of timestamped events during deliberation.
        decisions: Immutable tuple of decisions made.
        record_hash: SHA-256 hash of record content (64 hex chars).
        created_at: When record was created.

    Constitutional Constraints:
        - FR141: Complete record of deliberation
        - FR142: All required fields captured
        - CT-12: Record is witnessed and stored before disclosure

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> from types import MappingProxyType
        >>> payload = ProceduralRecordPayload(
        ...     record_id=uuid4(),
        ...     deliberation_id=uuid4(),
        ...     agenda_items=("Motion A", "Motion B"),
        ...     participant_ids=("agent-1", "agent-2"),
        ...     vote_summary=MappingProxyType({"aye": 45, "nay": 20}),
        ...     timeline_events=(),
        ...     decisions=("Approved Motion A",),
        ...     record_hash="a" * 64,
        ...     created_at=datetime.now(timezone.utc),
        ... )
    """

    record_id: UUID
    deliberation_id: UUID
    agenda_items: tuple[str, ...]
    participant_ids: tuple[str, ...]
    vote_summary: MappingProxyType[str, int]
    timeline_events: tuple[MappingProxyType[str, Any], ...]
    decisions: tuple[str, ...]
    record_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate payload fields.

        Raises:
            TypeError: If record_id or deliberation_id is not a UUID,
                       or if collections are wrong types.
            ValueError: If record_hash fails validation.
        """
        self._validate_record_id()
        self._validate_deliberation_id()
        self._validate_record_hash()
        self._validate_agenda_items()
        self._validate_participant_ids()

    def _validate_record_id(self) -> None:
        """Validate record_id is a UUID."""
        if not isinstance(self.record_id, UUID):
            raise TypeError(
                f"record_id must be UUID, got {type(self.record_id).__name__}"
            )

    def _validate_deliberation_id(self) -> None:
        """Validate deliberation_id is a UUID."""
        if not isinstance(self.deliberation_id, UUID):
            raise TypeError(
                f"deliberation_id must be UUID, got {type(self.deliberation_id).__name__}"
            )

    def _validate_record_hash(self) -> None:
        """Validate record_hash is 64 character hex string (SHA-256)."""
        if not isinstance(self.record_hash, str) or len(self.record_hash) != 64:
            length = len(self.record_hash) if isinstance(self.record_hash, str) else "N/A"
            raise ValueError(
                f"record_hash must be 64 character hex string (SHA-256), got length {length}"
            )

    def _validate_agenda_items(self) -> None:
        """Validate agenda_items is a tuple."""
        if not isinstance(self.agenda_items, tuple):
            raise TypeError(
                f"agenda_items must be tuple, got {type(self.agenda_items).__name__}"
            )

    def _validate_participant_ids(self) -> None:
        """Validate participant_ids is a tuple."""
        if not isinstance(self.participant_ids, tuple):
            raise TypeError(
                f"participant_ids must be tuple, got {type(self.participant_ids).__name__}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for event payload field.

        Returns:
            Dictionary with values suitable for JSON serialization.
        """
        return {
            "record_id": str(self.record_id),
            "deliberation_id": str(self.deliberation_id),
            "agenda_items": list(self.agenda_items),
            "participant_ids": list(self.participant_ids),
            "vote_summary": dict(self.vote_summary),
            "timeline_events": [dict(e) for e in self.timeline_events],
            "decisions": list(self.decisions),
            "record_hash": self.record_hash,
            "created_at": self.created_at.isoformat(),
        }
