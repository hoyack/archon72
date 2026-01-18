"""Publish service (Story 2.5, FR13).

Application service for publishing content with FR13 (No Silent Edits)
enforcement. All publish operations verify content hash before execution.

Constitutional Constraints:
- FR13: Published hash must equal canonical hash
- AC1: Hash equality verified on publish
- AC2: Hash mismatch blocks publish with FR13ViolationError
- CT-11: Silent failure destroys legitimacy
- CT-13: Integrity outranks availability

Golden Rules:
- HALT FIRST: Check halt state before every operation
"""

from __future__ import annotations

from uuid import UUID

import structlog

from src.application.ports.content_verification import (
    ContentVerificationPort,
    ContentVerificationResult,
)
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.silent_edit import FR13ViolationError
from src.domain.errors.writer import SystemHaltedError

logger = structlog.get_logger()


class PublishService:
    """Application service for publishing content with FR13 enforcement.

    Coordinates publish operations with content verification to ensure
    the No Silent Edits constraint is enforced. Any attempt to publish
    content with a hash different from the stored hash is blocked.

    Constitutional Constraints:
        - FR13: Published hash must equal canonical hash
        - HALT FIRST: All operations check halt state first

    Example:
        >>> service = PublishService(halt_checker, verification_port)
        >>> await service.publish_content(content_id, content_bytes)  # Verifies first
        True
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        verification_port: ContentVerificationPort,
    ) -> None:
        """Initialize PublishService with dependencies.

        Args:
            halt_checker: HaltChecker for checking system halt state.
            verification_port: ContentVerificationPort for hash verification.
        """
        self._halt_checker = halt_checker
        self._verification_port = verification_port

    async def _check_halt(self) -> None:
        """Check halt state and raise if halted.

        Raises:
            SystemHaltedError: If system is halted.
        """
        if await self._halt_checker.is_halted():
            logger.warning("publish_blocked_system_halted")
            raise SystemHaltedError("System is halted - publish operations blocked")

    async def publish_content(
        self,
        content_id: UUID,
        content: bytes,
    ) -> bool:
        """Publish content after verifying hash integrity (AC1, AC2).

        HALT FIRST: Checks halt state before any operation.

        Args:
            content_id: UUID of the content to publish.
            content: Content bytes to publish.

        Returns:
            True if publish succeeds.

        Raises:
            SystemHaltedError: If system is halted.
            FR13ViolationError: If hash mismatch detected (AC2).
        """
        # HALT FIRST
        await self._check_halt()

        # Verify hash before publish (AC1)
        result = await self._verification_port.verify_content(content_id, content)

        if not result.matches:
            logger.warning(
                "silent_edit_blocked",
                content_id=str(content_id),
                stored_hash=result.stored_hash[:8] + "..."
                if result.stored_hash
                else "none",
                computed_hash=result.computed_hash[:8] + "...",
            )
            raise FR13ViolationError(
                f"FR13: Silent edit detected - hash mismatch "
                f"(content_id={content_id}, "
                f"stored={result.stored_hash[:8] if result.stored_hash else 'none'}..., "
                f"computed={result.computed_hash[:8]}...)"
            )

        logger.info(
            "content_published",
            content_id=str(content_id),
            hash_prefix=result.stored_hash[:8],
        )
        return True

    async def verify_content(
        self,
        content_id: UUID,
        content: bytes,
    ) -> ContentVerificationResult:
        """Verify content hash without publishing (AC3).

        HALT FIRST: Checks halt state before any operation.

        Args:
            content_id: UUID of the content to verify.
            content: Content bytes to verify.

        Returns:
            ContentVerificationResult with matches flag and both hashes.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST
        await self._check_halt()

        result = await self._verification_port.verify_content(content_id, content)

        logger.debug(
            "content_verified",
            content_id=str(content_id),
            matches=result.matches,
        )
        return result
