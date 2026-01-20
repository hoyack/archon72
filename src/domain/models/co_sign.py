"""Co-sign domain models (Story 5.1, FR-6.2, NFR-3.5).

This module defines the domain model for petition co-signing:
- CoSign: Represents a Seeker's support signature on a petition

Constitutional Constraints:
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-6.4: Co-signer attribution - full signer list queryable
- CT-12: Witnessing creates accountability

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating co-signs (writes)
2. WITNESS EVERYTHING - All co-sign events require attribution
3. FAIL LOUD - Never silently swallow constraint violations
4. UNIQUE CONSTRAINT - Database enforces, code validates
"""

from __future__ import annotations

import blake3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


# Note: No CoSignStatus enum needed for M1 - all co-signs are valid on creation.
# Future extension point: May add PENDING, VERIFIED, REVOKED if withdrawal supported.


@dataclass(frozen=True, eq=True)
class CoSign:
    """A Seeker's co-signature on a petition (FR-6.2, NFR-3.5).

    Represents a unique support relationship between a Seeker and a Petition.
    The (petition_id, signer_id) pair is guaranteed unique by database constraint.

    Constitutional Constraints:
    - FR-6.2: Unique (petition_id, signer_id)
    - NFR-3.5: 0 duplicate signatures
    - NFR-6.4: Full signer list queryable
    - CT-12: Content hash for witness integrity

    Attributes:
        cosign_id: Unique identifier for this co-signature (UUIDv7).
        petition_id: Reference to the petition being co-signed.
        signer_id: UUID of the Seeker adding their support.
        signed_at: When the co-signature was recorded (UTC timezone-aware).
        content_hash: BLAKE3 hash for witness integrity (32 bytes).
        identity_verified: Whether signer identity was verified (Story 5.3).
        witness_event_id: Reference to witness event (set after witnessing).
    """

    # Required fields
    cosign_id: UUID
    petition_id: UUID
    signer_id: UUID
    signed_at: datetime
    content_hash: bytes

    # Optional fields
    identity_verified: bool = field(default=False)
    witness_event_id: Optional[UUID] = field(default=None)

    def __post_init__(self) -> None:
        """Validate co-sign fields after initialization.

        Raises:
            ValueError: If any field validation fails.
        """
        # Validate signed_at is timezone-aware
        if self.signed_at.tzinfo is None:
            raise ValueError("signed_at must be timezone-aware (UTC)")

        # Validate content_hash is 32 bytes (BLAKE3)
        if len(self.content_hash) != 32:
            raise ValueError(
                f"content_hash must be 32 bytes (BLAKE3), got {len(self.content_hash)}"
            )

    def signable_content(self) -> bytes:
        """Return canonical bytes for hashing/signing.

        Includes all immutable fields that define this co-sign.
        Used for witness integrity verification (CT-12).

        Returns:
            Canonical bytes representation of the co-sign.
        """
        # Canonical format: petition_id|signer_id|signed_at_iso
        return (
            f"{self.petition_id}|{self.signer_id}|{self.signed_at.isoformat()}"
        ).encode("utf-8")

    @staticmethod
    def compute_content_hash(
        petition_id: UUID, signer_id: UUID, signed_at: datetime
    ) -> bytes:
        """Compute BLAKE3 hash for co-sign content.

        Used before creating a CoSign to generate the content_hash.

        Args:
            petition_id: The petition being co-signed.
            signer_id: The Seeker adding their support.
            signed_at: When the co-signature is being recorded.

        Returns:
            32-byte BLAKE3 hash of the canonical content.
        """
        content = f"{petition_id}|{signer_id}|{signed_at.isoformat()}".encode("utf-8")
        return blake3.blake3(content).digest()

    def verify_content_hash(self) -> bool:
        """Verify that content_hash matches computed hash.

        Used to detect tampering or corruption of co-sign data.

        Returns:
            True if content_hash is valid, False otherwise.
        """
        expected = self.compute_content_hash(
            self.petition_id, self.signer_id, self.signed_at
        )
        return self.content_hash == expected

    def to_dict(self) -> dict:
        """Serialize to dictionary for events (D2 compliant).

        WARNING: Never use asdict() - it breaks UUID/datetime serialization.

        Returns:
            Dictionary representation suitable for event payloads.
        """
        return {
            "cosign_id": str(self.cosign_id),
            "petition_id": str(self.petition_id),
            "signer_id": str(self.signer_id),
            "signed_at": self.signed_at.isoformat(),
            "identity_verified": self.identity_verified,
            "content_hash": self.content_hash.hex(),
            "witness_event_id": (
                str(self.witness_event_id) if self.witness_event_id else None
            ),
            "schema_version": 1,  # D2: Required for all event payloads
        }

    @classmethod
    def from_dict(cls, data: dict) -> CoSign:
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation of a CoSign.

        Returns:
            CoSign instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If field values are invalid.
        """
        return cls(
            cosign_id=UUID(data["cosign_id"]),
            petition_id=UUID(data["petition_id"]),
            signer_id=UUID(data["signer_id"]),
            signed_at=datetime.fromisoformat(data["signed_at"]),
            identity_verified=data.get("identity_verified", False),
            content_hash=bytes.fromhex(data["content_hash"]),
            witness_event_id=(
                UUID(data["witness_event_id"]) if data.get("witness_event_id") else None
            ),
        )
