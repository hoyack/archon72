"""Phase witness event for deliberation witnessing (Story 2A.7, FR-11.7).

This module defines the PhaseWitnessEvent dataclass for recording phase-level
witness events during deliberation. Per Ruling-1, witnessing occurs at phase
boundaries (not per-utterance) to avoid witness volume explosion while
maintaining 100% auditability.

Constitutional Constraints:
- CT-12: Every action must be witnessed
- CT-14: Every claim terminates in witnessed fate
- FR-11.7: Hash-referenced ledger witnessing at phase boundaries
- NFR-10.4: 100% witness completeness
- Ruling-1: Phase-level batching (not per-utterance)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import blake3

from src.domain.models.deliberation_session import DeliberationPhase

# Event type constant
PHASE_WITNESS_EVENT_TYPE: str = "deliberation.phase.witnessed"

# Blake3 hash size in bytes
BLAKE3_HASH_SIZE: int = 32


@dataclass(frozen=True, eq=True)
class PhaseWitnessEvent:
    """Witness event for a deliberation phase (Story 2A.7, FR-11.7).

    Emitted at phase boundaries to witness all utterances without
    per-utterance event explosion. The transcript is stored as a
    content-addressed artifact referenced by hash.

    Constitutional Constraints:
    - CT-12: Every action must be witnessed
    - CT-14: Every claim terminates in witnessed fate
    - FR-11.7: Hash-referenced ledger witnessing at phase boundaries
    - NFR-10.4: 100% witness completeness
    - Ruling-1: Phase-level batching

    Attributes:
        event_id: UUIDv7 for this witness event.
        session_id: UUID of the deliberation session.
        phase: The phase being witnessed.
        transcript_hash: Blake3 hash of full transcript (32 bytes).
        participating_archons: Tuple of 3 archon UUIDs.
        start_timestamp: When phase started (UTC).
        end_timestamp: When phase completed (UTC).
        phase_metadata: Phase-specific metadata dict.
        previous_witness_hash: Hash of previous phase's witness (None for ASSESS).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    phase: DeliberationPhase
    transcript_hash: bytes
    participating_archons: tuple[UUID, UUID, UUID]
    start_timestamp: datetime
    end_timestamp: datetime
    phase_metadata: dict[str, Any] = field(default_factory=dict)
    previous_witness_hash: bytes | None = field(default=None)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate witness event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_transcript_hash()
        self._validate_archon_count()
        self._validate_timestamps()
        self._validate_phase_chain()

    def _validate_transcript_hash(self) -> None:
        """Validate transcript hash is 32 bytes (Blake3)."""
        if len(self.transcript_hash) != BLAKE3_HASH_SIZE:
            raise ValueError(
                f"transcript_hash must be {BLAKE3_HASH_SIZE} bytes (Blake3), "
                f"got {len(self.transcript_hash)}"
            )

    def _validate_archon_count(self) -> None:
        """Validate exactly 3 archons participated."""
        if len(self.participating_archons) != 3:
            raise ValueError(
                f"participating_archons must contain exactly 3 UUIDs, "
                f"got {len(self.participating_archons)}"
            )

    def _validate_timestamps(self) -> None:
        """Validate end is after start."""
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("end_timestamp must be >= start_timestamp")

    def _validate_phase_chain(self) -> None:
        """Validate phase chain constraints.

        ASSESS should not have previous hash; others should.
        """
        if self.phase == DeliberationPhase.ASSESS:
            if self.previous_witness_hash is not None:
                raise ValueError(
                    "ASSESS phase should not have previous_witness_hash"
                )
        else:
            if self.previous_witness_hash is None:
                raise ValueError(
                    f"{self.phase.value} phase must have previous_witness_hash"
                )
            if len(self.previous_witness_hash) != BLAKE3_HASH_SIZE:
                raise ValueError(
                    f"previous_witness_hash must be {BLAKE3_HASH_SIZE} bytes (Blake3), "
                    f"got {len(self.previous_witness_hash)}"
                )

    @property
    def transcript_hash_hex(self) -> str:
        """Return transcript hash as hex string."""
        return self.transcript_hash.hex()

    @property
    def previous_witness_hash_hex(self) -> str | None:
        """Return previous witness hash as hex string."""
        if self.previous_witness_hash is None:
            return None
        return self.previous_witness_hash.hex()

    @property
    def event_hash(self) -> bytes:
        """Compute hash of this witness event for chaining.

        Used as previous_witness_hash for the next phase's event.
        Creates a verifiable chain of witness events.

        Returns:
            32-byte Blake3 hash of this event.
        """
        # Deterministic content for hashing
        content = (
            f"{self.event_id}:"
            f"{self.session_id}:"
            f"{self.phase.value}:"
            f"{self.transcript_hash.hex()}:"
            f"{self.end_timestamp.isoformat()}"
        )
        return blake3.blake3(content.encode("utf-8")).digest()

    @property
    def event_hash_hex(self) -> str:
        """Return event hash as hex string."""
        return self.event_hash.hex()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "phase": self.phase.value,
            "transcript_hash": self.transcript_hash_hex,
            "participating_archons": [str(a) for a in self.participating_archons],
            "start_timestamp": self.start_timestamp.isoformat(),
            "end_timestamp": self.end_timestamp.isoformat(),
            "phase_metadata": self.phase_metadata,
            "previous_witness_hash": self.previous_witness_hash_hex,
            "created_at": self.created_at.isoformat(),
            "event_hash": self.event_hash_hex,
        }
