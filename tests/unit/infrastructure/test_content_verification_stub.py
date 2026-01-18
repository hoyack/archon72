"""Unit tests for ContentVerificationStub infrastructure (Story 2.5, FR13).

Tests the in-memory stub implementation of ContentVerificationPort
for development and testing purposes.

Constitutional Constraints Verified:
- FR13: Published hash must equal canonical hash
- AC3: Verification endpoint returns TRUE/FALSE with hash values
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern followed
"""

import hashlib
from uuid import uuid4

import pytest

from src.application.ports.content_verification import ContentVerificationResult
from src.infrastructure.stubs.content_verification_stub import (
    DEV_MODE_WATERMARK,
    ContentVerificationStub,
)


class TestContentVerificationStub:
    """Test suite for ContentVerificationStub."""

    @pytest.fixture
    def stub(self) -> ContentVerificationStub:
        """Create a fresh ContentVerificationStub instance."""
        return ContentVerificationStub()

    def test_dev_mode_watermark_exists(self) -> None:
        """DEV_MODE_WATERMARK follows RT-1/ADR-4 pattern."""
        assert DEV_MODE_WATERMARK is not None
        assert "DEV_STUB" in DEV_MODE_WATERMARK
        assert "ContentVerificationStub" in DEV_MODE_WATERMARK

    @pytest.mark.asyncio
    async def test_register_and_get_stored_hash(
        self, stub: ContentVerificationStub
    ) -> None:
        """Can register and retrieve content hash."""
        content_id = uuid4()
        content_hash = "a" * 64

        await stub.register_content_hash(content_id, content_hash)
        stored = await stub.get_stored_hash(content_id)

        assert stored == content_hash

    @pytest.mark.asyncio
    async def test_get_stored_hash_returns_none_for_unknown(
        self, stub: ContentVerificationStub
    ) -> None:
        """Returns None for unknown content ID."""
        unknown_id = uuid4()
        stored = await stub.get_stored_hash(unknown_id)
        assert stored is None

    @pytest.mark.asyncio
    async def test_verify_content_with_matching_hash(
        self, stub: ContentVerificationStub
    ) -> None:
        """verify_content returns matches=True for matching hash (AC3)."""
        content_id = uuid4()
        content = b"test content for verification"
        content_hash = hashlib.sha256(content).hexdigest()

        await stub.register_content_hash(content_id, content_hash)
        result = await stub.verify_content(content_id, content)

        assert isinstance(result, ContentVerificationResult)
        assert result.matches is True
        assert result.stored_hash == content_hash
        assert result.computed_hash == content_hash
        assert result.content_id == content_id

    @pytest.mark.asyncio
    async def test_verify_content_with_mismatched_hash(
        self, stub: ContentVerificationStub
    ) -> None:
        """verify_content returns matches=False for mismatched hash (AC3)."""
        content_id = uuid4()
        stored_hash = "a" * 64
        different_content = b"modified content"

        await stub.register_content_hash(content_id, stored_hash)
        result = await stub.verify_content(content_id, different_content)

        assert result.matches is False
        assert result.stored_hash == stored_hash
        assert result.computed_hash != stored_hash

    @pytest.mark.asyncio
    async def test_verify_content_includes_hash_values(
        self, stub: ContentVerificationStub
    ) -> None:
        """verify_content result includes both hash values (AC3)."""
        content_id = uuid4()
        content = b"content to verify"
        stored_hash = "b" * 64

        await stub.register_content_hash(content_id, stored_hash)
        result = await stub.verify_content(content_id, content)

        assert result.stored_hash == stored_hash
        assert len(result.computed_hash) == 64  # SHA-256 hex length

    @pytest.mark.asyncio
    async def test_verify_unknown_content(self, stub: ContentVerificationStub) -> None:
        """verify_content handles unknown content ID gracefully."""
        unknown_id = uuid4()
        content = b"some content"

        result = await stub.verify_content(unknown_id, content)

        # For unknown content, stored_hash is empty and matches is False
        assert result.matches is False
        assert result.stored_hash == ""
        assert result.content_id == unknown_id

    @pytest.mark.asyncio
    async def test_multiple_content_ids_tracked_independently(
        self, stub: ContentVerificationStub
    ) -> None:
        """Multiple content IDs tracked independently."""
        content_id_1 = uuid4()
        content_id_2 = uuid4()
        hash_1 = "1" * 64
        hash_2 = "2" * 64

        await stub.register_content_hash(content_id_1, hash_1)
        await stub.register_content_hash(content_id_2, hash_2)

        assert await stub.get_stored_hash(content_id_1) == hash_1
        assert await stub.get_stored_hash(content_id_2) == hash_2
