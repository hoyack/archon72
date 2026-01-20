"""PostgreSQL Transcript Store adapter (Story 2B.5, AC-8).

This module provides the production PostgreSQL implementation of
TranscriptStoreProtocol for content-addressed transcript storage.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - hash enables verification
- FR-11.7: Hash-referenced preservation requirement
- NFR-6.5: Audit trail completeness - transcripts retrievable by hash
- NFR-4.2: Hash guarantees immutability (append-only semantic)
- NFR-10.4: Witness completeness - 100% utterances witnessed

Architecture:
- Content-addressed storage (primary key is Blake3 hash)
- Append-only semantic enforced by database trigger
- Idempotent store operation (upsert on conflict do nothing)
- Efficient retrieval by content hash (primary key lookup)

Database Table: transcript_contents (migration 020)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import blake3
from sqlalchemy import text
from structlog import get_logger

from src.application.ports.transcript_store import TranscriptStoreProtocol
from src.domain.models.transcript_reference import TranscriptReference

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = get_logger()


# Blake3 hash length in bytes
BLAKE3_HASH_LENGTH = 32


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class PostgresTranscriptStore(TranscriptStoreProtocol):
    """PostgreSQL implementation of TranscriptStoreProtocol (Story 2B.5, AC-8).

    Uses the transcript_contents table created by
    migration 020_create_transcript_contents.sql.

    Constitutional Compliance:
    - CT-12: Hash enables witness verification
    - FR-11.7: Hash-referenced preservation
    - NFR-6.5: Audit trail completeness
    - NFR-4.2: Append-only semantic (enforced by DB trigger)

    Query Patterns:
    - store: INSERT ON CONFLICT DO NOTHING (idempotent)
    - retrieve: SELECT content WHERE content_hash = $1
    - exists: SELECT 1 WHERE content_hash = $1
    - verify: Compute hash and compare
    - get_reference: SELECT metadata WHERE content_hash = $1

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the PostgreSQL transcript store.

        Args:
            session_factory: SQLAlchemy async session factory for DB access.
        """
        self._session_factory = session_factory

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

        Uses INSERT ON CONFLICT DO NOTHING for idempotent storage.
        If content already exists, retrieves existing reference.

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
        content_size = len(transcript.encode("utf-8"))

        log = logger.bind(
            content_hash=content_hash.hex(),
            content_size=content_size,
        )

        async with self._session_factory() as session:
            async with session.begin():
                # Idempotent insert - if exists, do nothing
                now = _utc_now()
                await session.execute(
                    text("""
                        INSERT INTO transcript_contents (
                            content_hash, content, content_size, stored_at
                        )
                        VALUES (
                            :content_hash, :content, :content_size, :stored_at
                        )
                        ON CONFLICT (content_hash) DO NOTHING
                    """),
                    {
                        "content_hash": content_hash,
                        "content": transcript,
                        "content_size": content_size,
                        "stored_at": now,
                    },
                )

                # Retrieve the stored reference (might be existing)
                result = await session.execute(
                    text("""
                        SELECT content_size, stored_at, storage_path
                        FROM transcript_contents
                        WHERE content_hash = :content_hash
                    """),
                    {"content_hash": content_hash},
                )
                row = result.fetchone()

                if row is None:
                    # Should not happen, but handle gracefully
                    log.error("transcript_store_failed", message="Insert succeeded but select failed")
                    raise RuntimeError("Transcript storage failed - consistency error")

                stored_size, stored_at, storage_path = row

        log.debug(
            "transcript_stored",
            stored_at=stored_at.isoformat() if stored_at else None,
        )

        return TranscriptReference(
            content_hash=content_hash,
            content_size=stored_size,
            stored_at=stored_at if stored_at else now,
            storage_path=storage_path,
        )

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

        log = logger.bind(content_hash=content_hash.hex())

        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT content
                    FROM transcript_contents
                    WHERE content_hash = :content_hash
                """),
                {"content_hash": content_hash},
            )
            row = result.fetchone()

        if row is None:
            log.debug("transcript_not_found")
            return None

        log.debug("transcript_retrieved")
        return row[0]

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

        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT 1
                    FROM transcript_contents
                    WHERE content_hash = :content_hash
                """),
                {"content_hash": content_hash},
            )
            row = result.fetchone()

        return row is not None

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

        log = logger.bind(content_hash=content_hash.hex())

        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT content_size, stored_at, storage_path
                    FROM transcript_contents
                    WHERE content_hash = :content_hash
                """),
                {"content_hash": content_hash},
            )
            row = result.fetchone()

        if row is None:
            log.debug("transcript_reference_not_found")
            return None

        content_size, stored_at, storage_path = row

        log.debug("transcript_reference_retrieved")
        return TranscriptReference(
            content_hash=content_hash,
            content_size=content_size,
            stored_at=stored_at,
            storage_path=storage_path,
        )
