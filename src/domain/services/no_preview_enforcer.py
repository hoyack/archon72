"""No Preview Enforcer domain service (Story 2.1, FR9).

This domain service enforces the No Preview constraint (FR9) which requires
that all agent outputs are recorded to the event store before any human
can view them.

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- CT-11: Silent failure destroys legitimacy → Violations raise errors
- CT-12: Witnessing creates accountability → All outputs must be witnessed
- CT-13: Integrity outranks availability → Deny access rather than serve modified content

AC3: Pre-Commit Access Denial
AC4: No Preview Code Path
"""

from __future__ import annotations

from uuid import UUID

from src.domain.errors.no_preview import FR9ViolationError
from src.domain.errors.silent_edit import FR13ViolationError


class NoPreviewEnforcer:
    """Domain service enforcing the No Preview constraint (FR9).

    This service tracks which outputs have been committed to the event store
    and prevents access to uncommitted outputs. It also verifies content
    hash integrity when outputs are retrieved.

    The enforcer maintains an in-memory registry of committed outputs.
    Production usage should be combined with event store verification.

    Constitutional Constraints:
        - FR9: Outputs must be recorded before viewing
        - AC3: Uncommitted outputs denied with FR9 error
        - AC4: No code path allows preview before commit

    Example:
        >>> from uuid import uuid4
        >>> enforcer = NoPreviewEnforcer()
        >>> output_id = uuid4()
        >>> enforcer.is_committed(output_id)  # False - not yet committed
        False
        >>> enforcer.mark_committed(output_id, content_hash="a" * 64)
        >>> enforcer.is_committed(output_id)  # True - now committed
        True
        >>> enforcer.enforce_no_preview(output_id)  # Passes silently
    """

    def __init__(self) -> None:
        """Initialize the enforcer with empty registries."""
        # Map of output_id -> committed status
        self._committed: set[UUID] = set()
        # Map of output_id -> content_hash (optional)
        self._hashes: dict[UUID, str] = {}

    def mark_committed(
        self,
        output_id: UUID,
        content_hash: str | None = None,
    ) -> None:
        """Mark an output as committed to the event store.

        Call this after successfully writing the DeliberationOutputEvent
        to the event store.

        Args:
            output_id: The UUID of the committed output.
            content_hash: Optional SHA-256 hash of the output content.
        """
        self._committed.add(output_id)
        if content_hash is not None:
            self._hashes[output_id] = content_hash

    def is_committed(self, output_id: UUID) -> bool:
        """Check if an output has been committed.

        Args:
            output_id: The UUID of the output to check.

        Returns:
            True if the output has been marked as committed, False otherwise.
        """
        return output_id in self._committed

    def verify_committed(self, output_id: UUID) -> bool:
        """Verify an output is committed, raising FR9ViolationError if not.

        Args:
            output_id: The UUID of the output to verify.

        Returns:
            True if the output is committed.

        Raises:
            FR9ViolationError: If the output has not been committed.
        """
        if not self.is_committed(output_id):
            raise FR9ViolationError(
                f"FR9: Output must be recorded before viewing (output_id={output_id})"
            )
        return True

    def enforce_no_preview(self, output_id: UUID) -> None:
        """Enforce the No Preview constraint for an output.

        This is the primary enforcement method. Call this before returning
        any output content to ensure FR9 compliance.

        Args:
            output_id: The UUID of the output to enforce.

        Raises:
            FR9ViolationError: If the output has not been committed.
        """
        self.verify_committed(output_id)

    def get_content_hash(self, output_id: UUID) -> str | None:
        """Get the stored content hash for an output.

        Args:
            output_id: The UUID of the output.

        Returns:
            The content hash if stored, None otherwise.
        """
        return self._hashes.get(output_id)

    def verify_hash(self, output_id: UUID, content_hash: str) -> bool:
        """Verify content hash matches stored hash (for viewing operations).

        Use this for FR9 (No Preview) enforcement when content is accessed
        for viewing. For publish operations, use verify_hash_for_publish.

        Args:
            output_id: The UUID of the output.
            content_hash: The hash to verify against stored hash.

        Returns:
            True if hashes match.

        Raises:
            FR9ViolationError: If hashes don't match (potential tampering).
        """
        stored_hash = self.get_content_hash(output_id)
        if stored_hash is None:
            # No hash stored - cannot verify
            return True

        if stored_hash != content_hash:
            raise FR9ViolationError(
                f"FR9: Content hash mismatch - potential tampering detected "
                f"(output_id={output_id}, expected={stored_hash[:8]}..., "
                f"got={content_hash[:8]}...)"
            )
        return True

    def verify_hash_for_publish(self, output_id: UUID, content_hash: str) -> bool:
        """Verify content hash for publish operations (FR13).

        Use this for FR13 (No Silent Edits) enforcement when content is
        being published to external systems.

        Args:
            output_id: The UUID of the output.
            content_hash: The hash to verify against stored hash.

        Returns:
            True if hashes match or no stored hash exists.

        Raises:
            FR13ViolationError: If hashes don't match (silent edit detected).
        """
        stored_hash = self.get_content_hash(output_id)
        if stored_hash is None:
            # No hash stored - cannot verify
            return True

        if stored_hash != content_hash:
            raise FR13ViolationError(
                f"FR13: Silent edit detected - hash mismatch "
                f"(output_id={output_id}, "
                f"stored={stored_hash[:8]}..., "
                f"computed={content_hash[:8]}...)"
            )
        return True
