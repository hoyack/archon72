"""Content Verification Port interface (Story 2.5, FR13).

This module defines the application port for content verification,
enabling the No Silent Edits constraint to be enforced through
a pluggable adapter pattern.

Constitutional Constraints:
- FR13: Published hash must equal canonical hash
- AC3: Verification endpoint returns TRUE/FALSE with hash values
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, eq=True)
class ContentVerificationResult:
    """Result of content hash verification (FR13, AC3).

    This dataclass captures the result of verifying content hash
    against the stored canonical hash.

    Attributes:
        matches: True if published hash equals stored hash (AC3)
        stored_hash: The original hash from event store
        computed_hash: The hash computed from current content
        content_id: The UUID of the content being verified

    Example:
        >>> from uuid import uuid4
        >>> result = ContentVerificationResult(
        ...     matches=True,
        ...     stored_hash="a" * 64,
        ...     computed_hash="a" * 64,
        ...     content_id=uuid4(),
        ... )
        >>> result.matches
        True
    """

    matches: bool
    stored_hash: str
    computed_hash: str
    content_id: UUID


class ContentVerificationPort(Protocol):
    """Port interface for content verification (FR13).

    This protocol defines the contract for content verification adapters.
    Implementations must provide hash storage retrieval and content
    verification against stored hashes.

    Constitutional Constraints:
        - FR13: Published hash must equal canonical hash
        - AC3: verify_content returns TRUE/FALSE with hash values

    Example implementation:
        class ContentVerificationAdapter:
            async def get_stored_hash(self, content_id: UUID) -> Optional[str]:
                return await self.event_store.get_content_hash(content_id)

            async def verify_content(
                self, content_id: UUID, content: bytes
            ) -> ContentVerificationResult:
                stored = await self.get_stored_hash(content_id)
                computed = compute_hash(content)
                return ContentVerificationResult(
                    matches=(stored == computed),
                    stored_hash=stored or "",
                    computed_hash=computed,
                    content_id=content_id,
                )
    """

    async def get_stored_hash(self, content_id: UUID) -> str | None:
        """Get the stored canonical hash for content.

        Args:
            content_id: The UUID of the content.

        Returns:
            The stored hash if found, None otherwise.
        """
        ...

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
        """
        ...
