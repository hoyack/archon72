"""Silent Edit Enforcer domain service (Story 2.5, FR13).

This domain service enforces the No Silent Edits constraint (FR13) which requires
that published hash always equals the canonical hash stored in the event store.
Any attempt to publish content with a different hash is blocked.

Constitutional Constraints:
- FR13: Published hash must equal canonical hash
- CT-11: Silent failure destroys legitimacy → Violations raise errors
- CT-13: Integrity outranks availability → Block publish on mismatch

AC1: Hash Equality on Publish
AC2: Silent Edit Detection and Block
"""

from __future__ import annotations

from uuid import UUID

import structlog

from src.domain.errors.silent_edit import FR13ViolationError

logger = structlog.get_logger()


class SilentEditEnforcer:
    """Domain service enforcing the No Silent Edits constraint (FR13).

    This service tracks content hashes and verifies that published content
    matches the originally recorded content. Any hash mismatch indicates
    a potential silent edit and is blocked.

    The enforcer maintains an in-memory registry of content hashes.
    Production usage combines this with event store verification.

    Constitutional Constraints:
        - FR13: Published hash must equal canonical hash
        - AC1: Hash equality verified on publish
        - AC2: Hash mismatch raises FR13ViolationError

    Example:
        >>> from uuid import uuid4
        >>> enforcer = SilentEditEnforcer()
        >>> content_id = uuid4()
        >>> enforcer.register_hash(content_id, "a" * 64)
        >>> enforcer.verify_hash(content_id, "a" * 64)  # True
        True
        >>> enforcer.verify_hash(content_id, "b" * 64)  # Raises FR13ViolationError
    """

    def __init__(self) -> None:
        """Initialize the enforcer with empty hash registry."""
        # Map of content_id -> content_hash
        self._hashes: dict[UUID, str] = {}

    def register_hash(self, content_id: UUID, content_hash: str) -> None:
        """Register a content hash for a content ID.

        Call this when content is first stored in the event store.

        Args:
            content_id: The UUID of the content.
            content_hash: The SHA-256 hash of the content.
        """
        self._hashes[content_id] = content_hash
        logger.debug(
            "content_hash_registered",
            content_id=str(content_id),
            hash_prefix=content_hash[:8],
        )

    def get_stored_hash(self, content_id: UUID) -> str | None:
        """Get the stored hash for a content ID.

        Args:
            content_id: The UUID of the content.

        Returns:
            The stored hash if found, None otherwise.
        """
        return self._hashes.get(content_id)

    def verify_hash(self, content_id: UUID, computed_hash: str) -> bool:
        """Verify computed hash matches stored hash.

        Args:
            content_id: The UUID of the content.
            computed_hash: The hash computed from current content.

        Returns:
            True if hashes match or no stored hash exists.

        Raises:
            FR13ViolationError: If hashes don't match (silent edit detected).
        """
        stored_hash = self.get_stored_hash(content_id)

        if stored_hash is None:
            # No hash stored - cannot verify, allow operation
            logger.debug(
                "no_stored_hash_for_verification",
                content_id=str(content_id),
            )
            return True

        if stored_hash != computed_hash:
            logger.warning(
                "silent_edit_detected",
                content_id=str(content_id),
                stored_hash=stored_hash[:8] + "...",
                computed_hash=computed_hash[:8] + "...",
            )
            self.block_silent_edit(content_id, stored_hash, computed_hash)

        logger.debug(
            "hash_verification_passed",
            content_id=str(content_id),
            hash_prefix=stored_hash[:8],
        )
        return True

    def verify_before_publish(self, content_id: UUID, computed_hash: str) -> bool:
        """Verify hash before allowing publish operation (AC1).

        This is the primary method for FR13 enforcement. Call this before
        any publish operation to external systems.

        Args:
            content_id: The UUID of the content to publish.
            computed_hash: The hash computed from the content being published.

        Returns:
            True if verification passes.

        Raises:
            FR13ViolationError: If hash mismatch detected (AC2).
        """
        return self.verify_hash(content_id, computed_hash)

    def block_silent_edit(
        self,
        content_id: UUID,
        stored_hash: str,
        computed_hash: str,
    ) -> None:
        """Explicitly block a silent edit attempt by raising FR13ViolationError.

        Args:
            content_id: The UUID of the content.
            stored_hash: The originally stored hash.
            computed_hash: The hash of the modified content.

        Raises:
            FR13ViolationError: Always raised with detailed message.
        """
        raise FR13ViolationError(
            f"FR13: Silent edit detected - hash mismatch "
            f"(content_id={content_id}, "
            f"stored={stored_hash[:8]}..., "
            f"computed={computed_hash[:8]}...)"
        )
