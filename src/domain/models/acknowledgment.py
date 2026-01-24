"""Acknowledgment domain model for petition fate execution.

This module defines the Acknowledgment aggregate root representing
the formal closure of a petition with the ACKNOWLEDGED fate.

Story: 3.2 - Acknowledgment Execution Service
FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
NFR-6.1: All fate transitions witnessed
CT-12: Every action that affects an Archon must be witnessed
CT-14: Every claim terminates in visible, witnessed fate
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.domain.models.acknowledgment_reason import (
    AcknowledgmentReasonCode,
    validate_acknowledgment_requirements,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


# Minimum archons required for acknowledgment (supermajority of 3)
MIN_ACKNOWLEDGING_ARCHONS = 2

# Schema version for serialization compatibility
ACKNOWLEDGMENT_SCHEMA_VERSION = "1.0.0"


class InsufficientArchonsError(ValueError):
    """Raised when fewer than MIN_ACKNOWLEDGING_ARCHONS vote to acknowledge."""

    def __init__(self, actual_count: int) -> None:
        self.actual_count = actual_count
        super().__init__(
            f"At least {MIN_ACKNOWLEDGING_ARCHONS} archons must vote ACKNOWLEDGE, "
            f"but only {actual_count} were provided. "
            f"This violates FR-11.5 supermajority consensus requirement."
        )


class AlreadyAcknowledgedError(ValueError):
    """Raised when attempting to acknowledge an already-acknowledged petition."""

    def __init__(self, petition_id: UUID, existing_acknowledgment_id: UUID) -> None:
        self.petition_id = petition_id
        self.existing_acknowledgment_id = existing_acknowledgment_id
        super().__init__(
            f"Petition {petition_id} has already been acknowledged "
            f"(acknowledgment_id: {existing_acknowledgment_id}). "
            f"Per NFR-3.2, fate assignment is atomic and single."
        )


@dataclass(frozen=True)
class Acknowledgment:
    """Acknowledgment record for a petition (FR-3.1).

    Represents the formal closure of a petition with ACKNOWLEDGED fate.
    Created when Three Fates deliberation reaches consensus on ACKNOWLEDGE disposition.

    This is an immutable aggregate root that captures all details needed
    for auditing and witnessing per CT-12 requirements.

    Attributes:
        id: Unique identifier for this acknowledgment
        petition_id: Reference to the acknowledged petition
        reason_code: Enumerated reason for acknowledgment (FR-3.2)
        rationale: Explanation text (required for REFUSED, NO_ACTION_WARRANTED per FR-3.3)
        reference_petition_id: For DUPLICATE, points to the canonical petition (FR-3.4)
        acknowledging_archon_ids: Archon IDs who voted ACKNOWLEDGE (min 2 for supermajority)
        acknowledged_by_king_id: King UUID for King acknowledgments (Story 6.5, FR-5.8)
        acknowledged_at: UTC timestamp of acknowledgment
        witness_hash: Blake3 hash for CT-12 witnessing compliance

    Example:
        >>> ack = Acknowledgment.create(
        ...     petition_id=petition.id,
        ...     reason_code=AcknowledgmentReasonCode.NOTED,
        ...     acknowledging_archon_ids=(15, 42, 67),
        ...     witness_hash="blake3:abc123...",
        ... )
        >>> assert len(ack.acknowledging_archon_ids) >= 2
    """

    id: UUID
    petition_id: UUID
    reason_code: AcknowledgmentReasonCode
    rationale: str | None
    reference_petition_id: UUID | None
    acknowledging_archon_ids: tuple[int, ...]
    acknowledged_by_king_id: UUID | None
    acknowledged_at: datetime
    witness_hash: str

    def __post_init__(self) -> None:
        """Validate all invariants after initialization."""
        # Validate rationale and reference requirements (from Story 3.1)
        validate_acknowledgment_requirements(
            self.reason_code,
            self.rationale,
            self.reference_petition_id,
        )

        # Validate minimum archon count (FR-11.5 supermajority)
        # KNIGHT_REFERRAL is exempt - it comes from Knight's recommendation (Story 4.4)
        # King acknowledgments are exempt - King acts alone (Story 6.5, FR-5.8)
        is_king_acknowledgment = self.acknowledged_by_king_id is not None
        if (
            self.reason_code != AcknowledgmentReasonCode.KNIGHT_REFERRAL
            and not is_king_acknowledgment
        ):
            if len(self.acknowledging_archon_ids) < MIN_ACKNOWLEDGING_ARCHONS:
                raise InsufficientArchonsError(len(self.acknowledging_archon_ids))

        # Validate witness hash is present (CT-12)
        if not self.witness_hash or not self.witness_hash.strip():
            raise ValueError("witness_hash is required for CT-12 compliance")

    @classmethod
    def create(
        cls,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        acknowledging_archon_ids: Sequence[int],
        witness_hash: str,
        rationale: str | None = None,
        reference_petition_id: UUID | None = None,
        acknowledged_by_king_id: UUID | None = None,
        acknowledged_at: datetime | None = None,
        id: UUID | None = None,
    ) -> Acknowledgment:
        """Factory method to create an Acknowledgment with validation.

        Args:
            petition_id: The petition being acknowledged
            reason_code: Reason for acknowledgment from enum
            acknowledging_archon_ids: IDs of archons who voted ACKNOWLEDGE
            witness_hash: Blake3 hash for witnessing
            rationale: Required for REFUSED/NO_ACTION_WARRANTED
            reference_petition_id: Required for DUPLICATE
            acknowledged_by_king_id: King UUID for King acknowledgments (Story 6.5)
            acknowledged_at: Timestamp (defaults to now)
            id: Optional UUID (generated if not provided)

        Returns:
            A validated Acknowledgment instance

        Raises:
            InsufficientArchonsError: Fewer than 2 archons
            RationaleRequiredError: Missing rationale for REFUSED/NO_ACTION_WARRANTED
            ReferenceRequiredError: Missing reference for DUPLICATE
            ValueError: Other validation failures
        """
        return cls(
            id=id or uuid4(),
            petition_id=petition_id,
            reason_code=reason_code,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
            acknowledging_archon_ids=tuple(acknowledging_archon_ids),
            acknowledged_by_king_id=acknowledged_by_king_id,
            acknowledged_at=acknowledged_at or datetime.now(timezone.utc),
            witness_hash=witness_hash,
        )

    @property
    def archon_count(self) -> int:
        """Return the number of archons who voted to acknowledge."""
        return len(self.acknowledging_archon_ids)

    @property
    def is_unanimous(self) -> bool:
        """Return True if all 3 archons voted ACKNOWLEDGE."""
        return self.archon_count == 3

    @property
    def has_rationale(self) -> bool:
        """Return True if rationale text was provided."""
        return bool(self.rationale)

    @property
    def is_duplicate_reference(self) -> bool:
        """Return True if this acknowledges a duplicate petition."""
        return self.reason_code == AcknowledgmentReasonCode.DUPLICATE

    def to_dict(self) -> dict:
        """Serialize to dictionary for persistence or API response."""
        return {
            "id": str(self.id),
            "petition_id": str(self.petition_id),
            "reason_code": self.reason_code.value,
            "rationale": self.rationale,
            "reference_petition_id": (
                str(self.reference_petition_id) if self.reference_petition_id else None
            ),
            "acknowledging_archon_ids": list(self.acknowledging_archon_ids),
            "acknowledged_by_king_id": (
                str(self.acknowledged_by_king_id)
                if self.acknowledged_by_king_id
                else None
            ),
            "acknowledged_at": self.acknowledged_at.isoformat(),
            "witness_hash": self.witness_hash,
            "schema_version": ACKNOWLEDGMENT_SCHEMA_VERSION,
        }
