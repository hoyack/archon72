"""Content verification stub implementation (Story 2.5, FR13).

In-memory stub for ContentVerificationPort for development and testing.
Follows DEV_MODE_WATERMARK pattern per RT-1/ADR-4.

Constitutional Constraints:
- FR13: Published hash must equal canonical hash
- AC3: Verification endpoint returns TRUE/FALSE with hash values
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern for dev stubs
"""

from __future__ import annotations

import hashlib
from uuid import UUID

import structlog

from src.application.ports.content_verification import (
    ContentVerificationResult,
)

logger = structlog.get_logger()


# DEV_MODE_WATERMARK per RT-1/ADR-4
# This constant indicates this is a development stub, not production code
DEV_MODE_WATERMARK: str = "DEV_STUB:ContentVerificationStub:v1"


class ContentVerificationStub:
    """In-memory stub for ContentVerificationPort (FR13, AC3).

    Development and testing implementation that stores content hashes
    in memory. Follows DEV_MODE_WATERMARK pattern.

    WARNING: This is a development stub. Not for production use.
    Production implementations should use the event store.

    Attributes:
        _hashes: In-memory dict mapping content_id to hash.

    Example:
        >>> stub = ContentVerificationStub()
        >>> await stub.register_content_hash(uuid4(), "a" * 64)
        >>> result = await stub.verify_content(content_id, content_bytes)
        >>> result.matches  # True or False
    """

    def __init__(self) -> None:
        """Initialize empty content hash store."""
        self._hashes: dict[UUID, str] = {}
        logger.debug(
            "content_verification_stub_initialized",
            watermark=DEV_MODE_WATERMARK,
        )

    async def register_content_hash(
        self,
        content_id: UUID,
        content_hash: str,
    ) -> None:
        """Register a content hash for a content ID.

        This is an additional method for the stub to allow
        setting up test data. Production implementations would
        read hashes from the event store.

        Args:
            content_id: UUID of the content.
            content_hash: SHA-256 hash of the content.
        """
        self._hashes[content_id] = content_hash
        logger.debug(
            "content_hash_registered",
            content_id=str(content_id),
            hash_prefix=content_hash[:8],
        )

    async def get_stored_hash(self, content_id: UUID) -> str | None:
        """Get the stored canonical hash for content.

        Args:
            content_id: The UUID of the content.

        Returns:
            The stored hash if found, None otherwise.
        """
        stored = self._hashes.get(content_id)
        logger.debug(
            "stored_hash_lookup",
            content_id=str(content_id),
            found=stored is not None,
        )
        return stored

    async def verify_content(
        self,
        content_id: UUID,
        content: bytes,
    ) -> ContentVerificationResult:
        """Verify content hash against stored canonical hash (AC3).

        Args:
            content_id: The UUID of the content.
            content: The content bytes to verify.

        Returns:
            ContentVerificationResult with matches flag and both hashes.
            If no stored hash exists, matches=False with empty stored_hash.
        """
        stored_hash = await self.get_stored_hash(content_id)
        computed_hash = hashlib.sha256(content).hexdigest()

        if stored_hash is None:
            logger.debug(
                "no_stored_hash_for_verification",
                content_id=str(content_id),
            )
            return ContentVerificationResult(
                matches=False,
                stored_hash="",
                computed_hash=computed_hash,
                content_id=content_id,
            )

        matches = stored_hash == computed_hash

        if matches:
            logger.debug(
                "content_verification_passed",
                content_id=str(content_id),
                hash_prefix=stored_hash[:8],
            )
        else:
            logger.warning(
                "content_verification_failed",
                content_id=str(content_id),
                stored_hash=stored_hash[:8] + "...",
                computed_hash=computed_hash[:8] + "...",
            )

        return ContentVerificationResult(
            matches=matches,
            stored_hash=stored_hash,
            computed_hash=computed_hash,
            content_id=content_id,
        )
