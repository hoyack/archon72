"""Key generation ceremony event payloads (FR69, ADR-4).

This module defines event payloads for key generation ceremony lifecycle events.
These events create the constitutional audit trail for Keeper key generation.

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- CT-11: Silent failure destroys legitimacy -> Events MUST be logged
- CT-12: Witnessing creates accountability -> Events MUST be witnessed

Event Types:
- KeyGenerationCeremonyStartedPayload: Ceremony initiated
- KeyGenerationCeremonyWitnessedPayload: Witness added signature
- KeyGenerationCeremonyCompletedPayload: Ceremony completed, key registered
- KeyGenerationCeremonyFailedPayload: Ceremony failed or timed out
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

# Event type constants
KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE: str = "ceremony.key_generation.started"
KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE: str = "ceremony.key_generation.witnessed"
KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE: str = "ceremony.key_generation.completed"
KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE: str = "ceremony.key_generation.failed"


@dataclass(frozen=True, eq=True)
class KeyGenerationCeremonyStartedPayload:
    """Payload for ceremony started events - immutable.

    Created when a key generation ceremony is initiated.
    This event MUST be witnessed and recorded before the ceremony proceeds.

    Constitutional Constraints:
    - FR69: Keeper keys require witnessed ceremony
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        ceremony_id: UUID of the ceremony.
        keeper_id: ID of Keeper receiving the new key.
        ceremony_type: Type of ceremony (new_keeper_key or key_rotation).
        initiator_id: Who started the ceremony (e.g., "KEEPER:admin").
        old_key_id: HSM key ID being rotated (None for new keys).
        started_at: When the ceremony started (UTC).
    """

    # UUID of the ceremony
    ceremony_id: UUID

    # Keeper receiving the key
    keeper_id: str

    # Type of ceremony (NEW_KEEPER_KEY or KEY_ROTATION)
    ceremony_type: str  # Serialized enum value

    # Who initiated the ceremony
    initiator_id: str

    # Old key being rotated (None for new keys)
    old_key_id: str | None

    # When ceremony started
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE,
                "ceremony_id": str(self.ceremony_id),
                "keeper_id": self.keeper_id,
                "ceremony_type": self.ceremony_type,
                "initiator_id": self.initiator_id,
                "old_key_id": self.old_key_id,
                "started_at": self.started_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "ceremony_id": str(self.ceremony_id),
            "keeper_id": self.keeper_id,
            "ceremony_type": self.ceremony_type,
            "initiator_id": self.initiator_id,
            "old_key_id": self.old_key_id,
            "started_at": self.started_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class KeyGenerationCeremonyWitnessedPayload:
    """Payload for ceremony witnessed events - immutable.

    Created when a witness adds their signature to a ceremony.
    Each witness attestation is recorded as a separate event.

    Constitutional Constraints:
    - FR69: Keeper keys require witnessed ceremony
    - CT-12: Witnessing creates accountability

    Attributes:
        ceremony_id: UUID of the ceremony.
        keeper_id: ID of Keeper receiving the new key.
        witness_id: ID of the witness (e.g., "KEEPER:alice").
        witness_type: Type of witness (keeper, system, external).
        witness_count: Total witnesses after this attestation.
        witnessed_at: When the witness signed (UTC).
    """

    # UUID of the ceremony
    ceremony_id: UUID

    # Keeper receiving the key
    keeper_id: str

    # Witness who signed
    witness_id: str

    # Type of witness
    witness_type: str  # Serialized enum value

    # Total witnesses after this attestation
    witness_count: int

    # When witness signed
    witnessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE,
                "ceremony_id": str(self.ceremony_id),
                "keeper_id": self.keeper_id,
                "witness_id": self.witness_id,
                "witness_type": self.witness_type,
                "witness_count": self.witness_count,
                "witnessed_at": self.witnessed_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "ceremony_id": str(self.ceremony_id),
            "keeper_id": self.keeper_id,
            "witness_id": self.witness_id,
            "witness_type": self.witness_type,
            "witness_count": self.witness_count,
            "witnessed_at": self.witnessed_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class KeyGenerationCeremonyCompletedPayload:
    """Payload for ceremony completed events - immutable.

    Created when a key generation ceremony completes successfully.
    This event records the new key registration and any transition period.

    Constitutional Constraints:
    - FR69: Keeper keys require witnessed ceremony
    - ADR-4: Key rotation includes 30-day transition period
    - CT-11: Events MUST be logged before taking effect
    - CT-12: Witnessing creates accountability

    Attributes:
        ceremony_id: UUID of the ceremony.
        keeper_id: ID of Keeper receiving the new key.
        ceremony_type: Type of ceremony (new_keeper_key or key_rotation).
        new_key_id: HSM key ID of the new key.
        old_key_id: HSM key ID of the old key (for rotations).
        transition_end_at: When transition period ends (for rotations).
        witness_ids: IDs of all witnesses who signed.
        completed_at: When the ceremony completed (UTC).
    """

    # UUID of the ceremony
    ceremony_id: UUID

    # Keeper receiving the key
    keeper_id: str

    # Type of ceremony
    ceremony_type: str  # Serialized enum value

    # New key HSM ID
    new_key_id: str

    # Old key HSM ID (for rotations)
    old_key_id: str | None

    # When transition ends (ADR-4: 30 days)
    transition_end_at: datetime | None

    # All witnesses who signed
    witness_ids: tuple[str, ...]

    # When ceremony completed
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability."""
        if isinstance(self.witness_ids, list):
            object.__setattr__(self, "witness_ids", tuple(self.witness_ids))

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE,
                "ceremony_id": str(self.ceremony_id),
                "keeper_id": self.keeper_id,
                "ceremony_type": self.ceremony_type,
                "new_key_id": self.new_key_id,
                "old_key_id": self.old_key_id,
                "transition_end_at": (
                    self.transition_end_at.isoformat()
                    if self.transition_end_at
                    else None
                ),
                "witness_ids": list(self.witness_ids),
                "completed_at": self.completed_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "ceremony_id": str(self.ceremony_id),
            "keeper_id": self.keeper_id,
            "ceremony_type": self.ceremony_type,
            "new_key_id": self.new_key_id,
            "old_key_id": self.old_key_id,
            "transition_end_at": (
                self.transition_end_at.isoformat() if self.transition_end_at else None
            ),
            "witness_ids": list(self.witness_ids),
            "completed_at": self.completed_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class KeyGenerationCeremonyFailedPayload:
    """Payload for ceremony failed events - immutable.

    Created when a key generation ceremony fails or times out.
    This event provides audit trail for failed ceremony attempts.

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy -> Failures MUST be logged
    - VAL-2: Ceremony timeout enforcement

    Attributes:
        ceremony_id: UUID of the ceremony.
        keeper_id: ID of Keeper who would have received the key.
        ceremony_type: Type of ceremony that failed.
        failure_reason: Why the ceremony failed.
        witness_count: How many witnesses had signed before failure.
        failed_at: When the ceremony failed (UTC).
    """

    # UUID of the ceremony
    ceremony_id: UUID

    # Keeper who would have received the key
    keeper_id: str

    # Type of ceremony that failed
    ceremony_type: str  # Serialized enum value

    # Why the ceremony failed
    failure_reason: str

    # How many witnesses had signed
    witness_count: int

    # When ceremony failed
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE,
                "ceremony_id": str(self.ceremony_id),
                "keeper_id": self.keeper_id,
                "ceremony_type": self.ceremony_type,
                "failure_reason": self.failure_reason,
                "witness_count": self.witness_count,
                "failed_at": self.failed_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "ceremony_id": str(self.ceremony_id),
            "keeper_id": self.keeper_id,
            "ceremony_type": self.ceremony_type,
            "failure_reason": self.failure_reason,
            "witness_count": self.witness_count,
            "failed_at": self.failed_at.isoformat(),
        }
