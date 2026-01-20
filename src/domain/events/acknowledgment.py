"""Acknowledgment domain events (Story 3.2, FR-3.1).

This module defines events emitted when petitions are acknowledged.
These events are witnessed per CT-12 requirements.

Constitutional Constraints:
- FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
- CT-12: Every action that affects an Archon must be witnessed
- CT-14: Every claim terminates in visible, witnessed fate
- NFR-6.1: All fate transitions witnessed
- NFR-6.3: Rationale preservation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode

# =============================================================================
# Event Type Constants
# =============================================================================

# Event emitted when a petition is acknowledged
PETITION_ACKNOWLEDGED_EVENT_TYPE: str = "petition.fate.acknowledged"

# Schema version for forward/backward compatibility (D2 requirement)
ACKNOWLEDGMENT_EVENT_SCHEMA_VERSION: int = 1


@dataclass(frozen=True, eq=True)
class PetitionAcknowledgedEvent:
    """Event emitted when a petition receives ACKNOWLEDGED fate (FR-3.1).

    This event is witnessed in the event store and provides a complete
    audit trail for the acknowledgment decision per CT-12 requirements.

    Constitutional Constraints:
    - FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
    - CT-12: Every action that affects an Archon must be witnessed
    - CT-14: Every claim terminates in visible, witnessed fate
    - NFR-6.1: All fate transitions witnessed (event has actor, timestamp, reason)
    - NFR-6.3: Rationale preservation (REFUSED/NO_ACTION rationale stored)

    Attributes:
        event_id: UUIDv7 for this event.
        acknowledgment_id: UUID of the Acknowledgment record.
        petition_id: Petition that was acknowledged.
        reason_code: Enumerated reason for acknowledgment (FR-3.2).
        rationale: Explanation text (required for REFUSED/NO_ACTION_WARRANTED).
        reference_petition_id: For DUPLICATE, points to canonical petition.
        acknowledging_archon_ids: Archon IDs who voted ACKNOWLEDGE (min 2).
        acknowledged_at: When acknowledgment was executed.
        witness_hash: Blake3 hash for CT-12 witnessing.
        schema_version: Event schema version for compatibility (D2).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    acknowledgment_id: UUID
    petition_id: UUID
    reason_code: AcknowledgmentReasonCode
    acknowledging_archon_ids: tuple[int, ...]
    acknowledged_at: datetime
    witness_hash: str
    rationale: str | None = None
    reference_petition_id: UUID | None = None
    schema_version: int = field(default=ACKNOWLEDGMENT_EVENT_SCHEMA_VERSION)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_archon_count()
        self._validate_witness_hash()
        self._validate_schema_version()
        self._validate_rationale_for_reason()
        self._validate_reference_for_duplicate()

    def _validate_archon_count(self) -> None:
        """Validate at least 2 archons voted ACKNOWLEDGE."""
        if len(self.acknowledging_archon_ids) < 2:
            raise ValueError(
                f"acknowledging_archon_ids must contain at least 2 IDs, "
                f"got {len(self.acknowledging_archon_ids)}"
            )

    def _validate_witness_hash(self) -> None:
        """Validate witness_hash is present (CT-12 requirement)."""
        if not self.witness_hash or not self.witness_hash.strip():
            raise ValueError(
                "witness_hash is required for CT-12 witnessing compliance"
            )

    def _validate_schema_version(self) -> None:
        """Validate schema version is current."""
        if self.schema_version != ACKNOWLEDGMENT_EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {ACKNOWLEDGMENT_EVENT_SCHEMA_VERSION}, "
                f"got {self.schema_version}"
            )

    def _validate_rationale_for_reason(self) -> None:
        """Validate rationale present for codes that require it (FR-3.3)."""
        if AcknowledgmentReasonCode.requires_rationale(self.reason_code):
            if not self.rationale or not self.rationale.strip():
                raise ValueError(
                    f"rationale is required for reason code {self.reason_code.value} "
                    f"per FR-3.3"
                )

    def _validate_reference_for_duplicate(self) -> None:
        """Validate reference present for DUPLICATE reason (FR-3.4)."""
        if AcknowledgmentReasonCode.requires_reference(self.reason_code):
            if self.reference_petition_id is None:
                raise ValueError(
                    f"reference_petition_id is required for DUPLICATE reason "
                    f"per FR-3.4"
                )

    @property
    def is_unanimous(self) -> bool:
        """Return True if all 3 archons voted ACKNOWLEDGE."""
        return len(self.acknowledging_archon_ids) == 3

    @property
    def has_rationale(self) -> bool:
        """Return True if rationale was provided."""
        return bool(self.rationale)

    @property
    def is_duplicate_reference(self) -> bool:
        """Return True if this acknowledges a duplicate petition."""
        return self.reason_code == AcknowledgmentReasonCode.DUPLICATE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (D2 pattern).

        Uses explicit to_dict() per project-context.md, NOT asdict().

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_type": PETITION_ACKNOWLEDGED_EVENT_TYPE,
            "event_id": str(self.event_id),
            "acknowledgment_id": str(self.acknowledgment_id),
            "petition_id": str(self.petition_id),
            "reason_code": self.reason_code.value,
            "rationale": self.rationale,
            "reference_petition_id": (
                str(self.reference_petition_id)
                if self.reference_petition_id
                else None
            ),
            "acknowledging_archon_ids": list(self.acknowledging_archon_ids),
            "acknowledged_at": self.acknowledged_at.isoformat(),
            "witness_hash": self.witness_hash,
            "schema_version": self.schema_version,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_acknowledgment(
        cls,
        event_id: UUID,
        acknowledgment_id: UUID,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        acknowledging_archon_ids: tuple[int, ...],
        acknowledged_at: datetime,
        witness_hash: str,
        rationale: str | None = None,
        reference_petition_id: UUID | None = None,
    ) -> PetitionAcknowledgedEvent:
        """Factory method to create event from acknowledgment data.

        Args:
            event_id: UUID for this event
            acknowledgment_id: UUID of the Acknowledgment record
            petition_id: Petition being acknowledged
            reason_code: Reason for acknowledgment
            acknowledging_archon_ids: Archons who voted ACKNOWLEDGE
            acknowledged_at: Timestamp of acknowledgment
            witness_hash: Blake3 hash for witnessing
            rationale: Optional explanation text
            reference_petition_id: For DUPLICATE, the original petition

        Returns:
            Validated PetitionAcknowledgedEvent instance
        """
        return cls(
            event_id=event_id,
            acknowledgment_id=acknowledgment_id,
            petition_id=petition_id,
            reason_code=reason_code,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
            acknowledging_archon_ids=acknowledging_archon_ids,
            acknowledged_at=acknowledged_at,
            witness_hash=witness_hash,
        )
