"""Transcript reference domain model (Story 2B.5, FR-11.7).

This module defines the TranscriptReference value object that provides
a compact reference to a transcript stored in the content-addressed
store. The hash can be used to retrieve and verify the original content.

Constitutional Constraints:
- CT-12: Enables witness verification through hash referencing
- FR-11.7: Hash-referenced preservation requirement
- NFR-6.5: Supports audit trail reconstruction
- NFR-4.2: Hash guarantees immutability (append-only)
- NFR-10.4: Witness completeness - 100% utterances witnessed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


# Blake3 hash length in bytes (32 bytes = 256 bits)
BLAKE3_HASH_LENGTH = 32


@dataclass(frozen=True, eq=True)
class TranscriptReference:
    """Reference to a content-addressed transcript (Story 2B.5, FR-11.7).

    Provides a compact reference to a transcript stored in the content-
    addressed store. The hash can be used to retrieve and verify the
    original content.

    Constitutional Constraints:
    - CT-12: Enables witness verification
    - NFR-6.5: Supports audit trail reconstruction
    - NFR-4.2: Hash guarantees immutability

    Attributes:
        content_hash: 32-byte Blake3 hash of transcript content.
        content_size: Size of content in bytes.
        stored_at: When the transcript was stored (UTC).
        storage_path: Optional path for filesystem-backed stores.
    """

    content_hash: bytes
    content_size: int
    stored_at: datetime = field(default_factory=_utc_now)
    storage_path: str | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate transcript reference invariants."""
        if len(self.content_hash) != BLAKE3_HASH_LENGTH:
            raise ValueError(
                f"content_hash must be {BLAKE3_HASH_LENGTH} bytes (Blake3), "
                f"got {len(self.content_hash)}"
            )
        if self.content_size < 0:
            raise ValueError(f"content_size must be >= 0, got {self.content_size}")

    @property
    def content_hash_hex(self) -> str:
        """Return content hash as hex string for serialization.

        Returns:
            Hex-encoded content hash string (64 characters).
        """
        return self.content_hash.hex()

    def to_dict(self) -> dict:
        """Serialize for storage/transmission.

        Follows D2 schema versioning requirement.

        Returns:
            Dictionary representation suitable for storage/events.
        """
        return {
            "content_hash": self.content_hash_hex,
            "content_size": self.content_size,
            "stored_at": self.stored_at.isoformat(),
            "storage_path": self.storage_path,
            "schema_version": 1,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TranscriptReference:
        """Create TranscriptReference from dictionary.

        Args:
            data: Dictionary with content_hash (hex), content_size, stored_at, storage_path.

        Returns:
            TranscriptReference instance.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        content_hash_hex = data.get("content_hash")
        if not content_hash_hex:
            raise ValueError("content_hash is required")

        content_hash = bytes.fromhex(content_hash_hex)
        content_size = data.get("content_size", 0)
        storage_path = data.get("storage_path")

        stored_at_str = data.get("stored_at")
        if stored_at_str:
            stored_at = datetime.fromisoformat(stored_at_str)
        else:
            stored_at = _utc_now()

        return cls(
            content_hash=content_hash,
            content_size=content_size,
            stored_at=stored_at,
            storage_path=storage_path,
        )
