"""Unit tests for PublishService application service (Story 2.5, FR13).

Tests the application service that coordinates publish operations
with content verification to enforce the No Silent Edits constraint.

Constitutional Constraints Verified:
- FR13: Published hash must equal canonical hash
- AC1: Hash equality verified on publish
- AC2: Hash mismatch blocks publish with FR13ViolationError
- Golden Rules: HALT FIRST
"""

import hashlib
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.content_verification import ContentVerificationResult
from src.application.services.publish_service import PublishService
from src.domain.errors.silent_edit import FR13ViolationError
from src.domain.errors.writer import SystemHaltedError


class TestPublishService:
    """Test suite for PublishService."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock HaltChecker that returns not halted."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_verification_port(self) -> AsyncMock:
        """Create mock ContentVerificationPort."""
        port = AsyncMock()
        return port

    @pytest.fixture
    def service(
        self,
        mock_halt_checker: AsyncMock,
        mock_verification_port: AsyncMock,
    ) -> PublishService:
        """Create PublishService with mock dependencies."""
        return PublishService(
            halt_checker=mock_halt_checker,
            verification_port=mock_verification_port,
        )

    @pytest.mark.asyncio
    async def test_publish_checks_halt_first(
        self,
        service: PublishService,
        mock_halt_checker: AsyncMock,
        mock_verification_port: AsyncMock,
    ) -> None:
        """HALT FIRST: publish_content checks halt state first."""
        mock_halt_checker.is_halted = AsyncMock(return_value=True)

        with pytest.raises(SystemHaltedError):
            await service.publish_content(uuid4(), b"content")

        mock_halt_checker.is_halted.assert_called_once()
        # Verification port should NOT be called when halted
        mock_verification_port.verify_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_with_matching_hash_succeeds(
        self,
        service: PublishService,
        mock_verification_port: AsyncMock,
    ) -> None:
        """Publish succeeds when hash matches (AC1)."""
        content_id = uuid4()
        content = b"test content"
        content_hash = hashlib.sha256(content).hexdigest()

        mock_verification_port.verify_content = AsyncMock(
            return_value=ContentVerificationResult(
                matches=True,
                stored_hash=content_hash,
                computed_hash=content_hash,
                content_id=content_id,
            )
        )

        result = await service.publish_content(content_id, content)

        assert result is True
        mock_verification_port.verify_content.assert_called_once_with(
            content_id, content
        )

    @pytest.mark.asyncio
    async def test_publish_with_mismatched_hash_raises_fr13(
        self,
        service: PublishService,
        mock_verification_port: AsyncMock,
    ) -> None:
        """Publish raises FR13ViolationError on hash mismatch (AC2)."""
        content_id = uuid4()
        content = b"modified content"
        stored_hash = "a" * 64
        computed_hash = hashlib.sha256(content).hexdigest()

        mock_verification_port.verify_content = AsyncMock(
            return_value=ContentVerificationResult(
                matches=False,
                stored_hash=stored_hash,
                computed_hash=computed_hash,
                content_id=content_id,
            )
        )

        with pytest.raises(FR13ViolationError) as exc_info:
            await service.publish_content(content_id, content)

        assert "FR13" in str(exc_info.value)
        assert "Silent edit detected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_includes_hash_mismatch_in_error(
        self,
        service: PublishService,
        mock_verification_port: AsyncMock,
    ) -> None:
        """FR13ViolationError includes hash mismatch info (AC2)."""
        content_id = uuid4()
        content = b"tampered content"
        stored_hash = "1" * 64
        computed_hash = "2" * 64

        mock_verification_port.verify_content = AsyncMock(
            return_value=ContentVerificationResult(
                matches=False,
                stored_hash=stored_hash,
                computed_hash=computed_hash,
                content_id=content_id,
            )
        )

        with pytest.raises(FR13ViolationError) as exc_info:
            await service.publish_content(content_id, content)

        error_msg = str(exc_info.value)
        assert "hash mismatch" in error_msg

    @pytest.mark.asyncio
    async def test_verify_content_returns_result(
        self,
        service: PublishService,
        mock_verification_port: AsyncMock,
    ) -> None:
        """verify_content returns verification result (AC3)."""
        content_id = uuid4()
        content = b"content to verify"
        content_hash = hashlib.sha256(content).hexdigest()

        expected_result = ContentVerificationResult(
            matches=True,
            stored_hash=content_hash,
            computed_hash=content_hash,
            content_id=content_id,
        )
        mock_verification_port.verify_content = AsyncMock(return_value=expected_result)

        result = await service.verify_content(content_id, content)

        assert result == expected_result
        assert result.matches is True
        assert result.stored_hash == content_hash

    @pytest.mark.asyncio
    async def test_verify_content_checks_halt_first(
        self,
        service: PublishService,
        mock_halt_checker: AsyncMock,
        mock_verification_port: AsyncMock,
    ) -> None:
        """verify_content checks halt state first."""
        mock_halt_checker.is_halted = AsyncMock(return_value=True)

        with pytest.raises(SystemHaltedError):
            await service.verify_content(uuid4(), b"content")

        mock_halt_checker.is_halted.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_unknown_content_raises_fr13(
        self,
        service: PublishService,
        mock_verification_port: AsyncMock,
    ) -> None:
        """Publishing unknown content (no stored hash) raises FR13."""
        content_id = uuid4()
        content = b"unknown content"
        computed_hash = hashlib.sha256(content).hexdigest()

        # Stub returns no stored hash
        mock_verification_port.verify_content = AsyncMock(
            return_value=ContentVerificationResult(
                matches=False,
                stored_hash="",  # No stored hash
                computed_hash=computed_hash,
                content_id=content_id,
            )
        )

        with pytest.raises(FR13ViolationError):
            await service.publish_content(content_id, content)
