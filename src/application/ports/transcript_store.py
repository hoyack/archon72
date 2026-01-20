"""Transcript store protocol (Story 2B.5, FR-11.7).

This module defines the protocol for content-addressed transcript
storage. Transcripts are stored by their Blake3 hash for immutability
and efficient deduplication.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - hash enables verification
- FR-11.7: Hash-referenced preservation requirement
- NFR-6.5: Audit trail completeness - transcripts retrievable by hash
- NFR-4.2: Hash guarantees immutability (append-only semantic)
- NFR-10.4: Witness completeness - 100% utterances witnessed
"""

from __future__ import annotations

from typing import Protocol

from src.domain.models.transcript_reference import TranscriptReference


class TranscriptStoreProtocol(Protocol):
    """Protocol for content-addressed transcript storage (Story 2B.5, FR-11.7).

    Implementations store transcripts indexed by their Blake3 hash,
    enabling efficient deduplication and integrity verification.

    Constitutional Constraints:
    - CT-12: Hash enables witness verification
    - FR-11.7: Hash-referenced preservation
    - NFR-6.5: Supports audit trail reconstruction
    - NFR-4.2: Append-only semantic (never overwrite)
    """

    async def store(self, transcript: str) -> TranscriptReference:
        """Store transcript and return content-addressed reference.

        Computes Blake3 hash of transcript content and stores it.
        If content with same hash already exists, returns existing
        reference (idempotent).

        Constitutional Constraint: Never overwrites existing content
        (append-only semantic per NFR-4.2).

        Args:
            transcript: Full text transcript content to store.

        Returns:
            TranscriptReference with content hash and metadata.

        Raises:
            ValueError: If transcript is empty or None.
            StorageError: If storage operation fails.
        """
        ...

    async def retrieve(self, content_hash: bytes) -> str | None:
        """Retrieve transcript by content hash.

        Used for audit trail reconstruction per NFR-6.5.

        Args:
            content_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            Raw transcript text if found, None otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        ...

    async def exists(self, content_hash: bytes) -> bool:
        """Check if transcript exists by content hash.

        Useful for verification without retrieving full content.

        Args:
            content_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            True if transcript exists, False otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        ...

    async def verify(self, content_hash: bytes, transcript: str) -> bool:
        """Verify transcript integrity against stored hash.

        Recomputes hash of provided transcript and compares to
        stored hash. Used for integrity verification.

        Args:
            content_hash: Expected Blake3 hash (32 bytes).
            transcript: Transcript content to verify.

        Returns:
            True if hash matches, False otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        ...

    async def get_reference(self, content_hash: bytes) -> TranscriptReference | None:
        """Get TranscriptReference metadata without retrieving content.

        Useful for checking metadata (size, storage time) without
        loading full transcript.

        Args:
            content_hash: Blake3 hash of the transcript (32 bytes).

        Returns:
            TranscriptReference if found, None otherwise.

        Raises:
            ValueError: If content_hash is not 32 bytes.
        """
        ...
