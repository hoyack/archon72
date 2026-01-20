"""Dissent record domain model (Story 2B.1, FR-11.8).

This module defines the DissentRecord aggregate for capturing minority
opinions in 2-1 deliberation votes. Dissent is preserved for audit
and governance review purposes.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - dissent must be witnessed
- AT-6: Deliberation is collective judgment - minority voice matters
- CT-14: Silence is expensive - even dissent terminates visibly
- NFR-6.5: Audit trail completeness - complete reconstruction possible
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-10.4: Witness completeness - 100% utterances witnessed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationOutcome

if TYPE_CHECKING:
    pass


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


# Blake3 hash length in bytes
BLAKE3_HASH_LENGTH = 32


@dataclass(frozen=True, eq=True)
class DissentRecord:
    """Record of dissenting opinion in a 2-1 deliberation vote (FR-11.8).

    Captures the minority archon's vote and reasoning when consensus
    is achieved by supermajority (2-1) rather than unanimously (3-0).

    Constitutional Constraints:
    - CT-12: Witnessing creates accountability
    - AT-6: Minority voice preserved for collective judgment record
    - NFR-6.5: Enables complete audit trail reconstruction

    Attributes:
        dissent_id: UUIDv7 unique identifier.
        session_id: FK to deliberation session.
        petition_id: FK to petition being deliberated.
        dissent_archon_id: UUID of the dissenting archon.
        dissent_disposition: What the dissenter voted for.
        dissent_rationale: The dissenter's reasoning text.
        rationale_hash: Blake3 hash of rationale for integrity (32 bytes).
        majority_disposition: The winning outcome.
        recorded_at: When dissent was recorded (UTC).
    """

    dissent_id: UUID
    session_id: UUID
    petition_id: UUID
    dissent_archon_id: UUID
    dissent_disposition: DeliberationOutcome
    dissent_rationale: str
    rationale_hash: bytes  # 32-byte Blake3 hash
    majority_disposition: DeliberationOutcome
    recorded_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate dissent record invariants."""
        self._validate_rationale_hash()
        self._validate_dispositions()

    def _validate_rationale_hash(self) -> None:
        """Validate rationale hash is correct length (Blake3 = 32 bytes).

        Raises:
            ValueError: If rationale_hash is not 32 bytes.
        """
        if len(self.rationale_hash) != BLAKE3_HASH_LENGTH:
            raise ValueError(
                f"rationale_hash must be {BLAKE3_HASH_LENGTH} bytes (Blake3), "
                f"got {len(self.rationale_hash)} bytes"
            )

    def _validate_dispositions(self) -> None:
        """Validate dissent disposition differs from majority.

        Raises:
            ValueError: If dissent matches majority (not actually a dissent).
        """
        if self.dissent_disposition == self.majority_disposition:
            raise ValueError(
                f"Dissent disposition ({self.dissent_disposition.value}) "
                f"cannot match majority disposition ({self.majority_disposition.value})"
            )

    def verify_rationale_integrity(self, rationale: str) -> bool:
        """Verify rationale integrity by recomputing hash.

        Args:
            rationale: The rationale text to verify.

        Returns:
            True if hash matches, False otherwise.
        """
        import blake3

        computed_hash = blake3.blake3(rationale.encode()).digest()
        return computed_hash == self.rationale_hash

    @property
    def rationale_hash_hex(self) -> str:
        """Get rationale hash as hex string for serialization.

        Returns:
            Hex-encoded rationale hash string.
        """
        return self.rationale_hash.hex()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for storage/events.
        """
        return {
            "dissent_id": str(self.dissent_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "dissent_archon_id": str(self.dissent_archon_id),
            "dissent_disposition": self.dissent_disposition.value,
            "dissent_rationale": self.dissent_rationale,
            "rationale_hash": self.rationale_hash_hex,
            "majority_disposition": self.majority_disposition.value,
            "recorded_at": self.recorded_at.isoformat(),
            "schema_version": 1,
        }
