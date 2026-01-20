"""Transcript store stub implementation (Story 2B.5, AC-7).

This module provides an in-memory stub implementation of
TranscriptStoreProtocol for development and testing purposes.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - hash enables verification
- FR-11.7: Hash-referenced preservation requirement
- NFR-6.5: Audit trail completeness - transcripts retrievable by hash
- NFR-4.2: Hash guarantees immutability (append-only semantic)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, auto

import blake3

from src.application.ports.transcript_store import TranscriptStoreProtocol
from src.domain.models.transcript_reference import TranscriptReference


# Blake3 hash length in bytes
BLAKE3_HASH_LENGTH = 32


class TranscriptStoreOperation(Enum):
    """Operations that can be recorded on the stub (for testing)."""

    STORE = auto()
    RETRIEVE = auto()
    EXISTS = auto()
    VERIFY = auto()
    GET_REFERENCE = auto()


class TranscriptStoreStub(TranscriptStoreProtocol):
    """In-memory stub implementation of TranscriptStoreProtocol.

    This stub provides a simple implementation for development and testing
    that stores transcripts in memory, indexed by their Blake3 hash.

    NOT suitable for production use.

    Constitutional Compliance:
    - CT-12: Hash enables verification (simulated)
    - FR-11.7: Hash-referenced preservation (simulated)
    - NFR-6.5: Audit trail completeness (simulated)
    - NFR-4.2: Append-only semantic (enforced)

    Attributes:
        _transcripts: Dictionary mapping content hash (bytes) to transcript (str).
        _references: Dictionary mapping content hash (bytes) to TranscriptReference.
        _operations: List of operations for test verification.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._transcripts: dict[bytes, str] = {}
        self._references: dict[bytes, TranscriptReference] = {}
        self._operations: list[tuple[TranscriptStoreOperation, dict]] = []

    def _compute_hash(self, content: str) -> bytes:
        """Compute Blake3 hash of content.

        Args:
            content: The content to hash.

        Returns:
            32-byte Blake3 hash.
        """
        return blake3.blake3(content.encode("utf-8")).digest()

    async def store(self, transcript: str) -> TranscriptReference:
        """Store transcript and return content-addressed reference.

        Args:
            transcript: Full text transcript content to store.

        Returns:
            TranscriptReference with content hash and metadata.

        Raises:
            ValueError: If transcript is empty or None.
        """
        if not transcript:
            raise ValueError("Transcript cannot be empty")

        content_hash = self._compute_hash(transcript)

        self._operations.append(
            (
                TranscriptStoreOperation.STORE,
                {
                    "content_hash": content_hash.hex(),
                    "size": len(transcript.encode("utf-8")),
                },
            )
        )

        # Check if already exists (idempotent)
        if content_hash in self._references:
            return self._references[content_hash]

        # Store new transcript
        now = datetime.now(timezone.utc)
        content_size = len(transcript.encode("utf-8"))

        reference = TranscriptReference(
            content_hash=content_hash,
            content_size=content_size,
            stored_at=now,
            storage_path=None,
        )

        self._transcripts[content_hash] = transcript
        self._references[content_hash] = reference

        return reference

    async def retrieve(self, content_hash: bytes) -> str | None:
        """Retrieve transcript by content hash.

        Args:
            content_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            Raw transcript text if found, None otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        if len(content_hash) != BLAKE3_HASH_LENGTH:
            raise ValueError(
                f"content_hash must be {BLAKE3_HASH_LENGTH} bytes, "
                f"got {len(content_hash)}"
            )

        self._operations.append(
            (
                TranscriptStoreOperation.RETRIEVE,
                {"content_hash": content_hash.hex()},
            )
        )

        return self._transcripts.get(content_hash)

    async def exists(self, content_hash: bytes) -> bool:
        """Check if transcript exists by content hash.

        Args:
            content_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            True if transcript exists, False otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        if len(content_hash) != BLAKE3_HASH_LENGTH:
            raise ValueError(
                f"content_hash must be {BLAKE3_HASH_LENGTH} bytes, "
                f"got {len(content_hash)}"
            )

        self._operations.append(
            (
                TranscriptStoreOperation.EXISTS,
                {"content_hash": content_hash.hex()},
            )
        )

        return content_hash in self._transcripts

    async def verify(self, content_hash: bytes, transcript: str) -> bool:
        """Verify transcript integrity against stored hash.

        Args:
            content_hash: Expected Blake3 hash (32 bytes).
            transcript: Transcript content to verify.

        Returns:
            True if hash matches, False otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        if len(content_hash) != BLAKE3_HASH_LENGTH:
            raise ValueError(
                f"content_hash must be {BLAKE3_HASH_LENGTH} bytes, "
                f"got {len(content_hash)}"
            )

        self._operations.append(
            (
                TranscriptStoreOperation.VERIFY,
                {"content_hash": content_hash.hex()},
            )
        )

        computed_hash = self._compute_hash(transcript)
        return computed_hash == content_hash

    async def get_reference(self, content_hash: bytes) -> TranscriptReference | None:
        """Get TranscriptReference metadata without retrieving content.

        Args:
            content_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            TranscriptReference if found, None otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        if len(content_hash) != BLAKE3_HASH_LENGTH:
            raise ValueError(
                f"content_hash must be {BLAKE3_HASH_LENGTH} bytes, "
                f"got {len(content_hash)}"
            )

        self._operations.append(
            (
                TranscriptStoreOperation.GET_REFERENCE,
                {"content_hash": content_hash.hex()},
            )
        )

        return self._references.get(content_hash)

    # Test helper methods

    def clear(self) -> None:
        """Clear all stored transcripts and state (for testing)."""
        self._transcripts.clear()
        self._references.clear()
        self._operations.clear()

    def get_transcript_count(self) -> int:
        """Get total number of transcripts stored.

        Returns:
            Total count.
        """
        return len(self._transcripts)

    def get_operations(self) -> list[tuple[TranscriptStoreOperation, dict]]:
        """Get list of operations for test verification.

        Returns:
            List of (operation, args) tuples.
        """
        return self._operations.copy()

    def inject_transcript(
        self,
        transcript: str,
        reference: TranscriptReference | None = None,
    ) -> TranscriptReference:
        """Inject a transcript for testing.

        Args:
            transcript: The transcript content.
            reference: Optional reference (will be created if not provided).

        Returns:
            TranscriptReference for the injected transcript.
        """
        content_hash = self._compute_hash(transcript)

        if reference is None:
            reference = TranscriptReference(
                content_hash=content_hash,
                content_size=len(transcript.encode("utf-8")),
                stored_at=datetime.now(timezone.utc),
                storage_path=None,
            )

        self._transcripts[content_hash] = transcript
        self._references[content_hash] = reference

        return reference

    def get_all_hashes(self) -> list[bytes]:
        """Get all stored content hashes (for testing).

        Returns:
            List of content hashes.
        """
        return list(self._transcripts.keys())
