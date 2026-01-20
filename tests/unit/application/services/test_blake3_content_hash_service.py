"""Unit tests for Blake3ContentHashService (Story 0.5, AC2, AC6).

Tests verify the BLAKE3 content hashing implementation for:
- Hash consistency (same input -> same output)
- Hash determinism across multiple calls
- Hash length (32 bytes)
- Different inputs produce different hashes
- Empty content handling
- Unicode content handling
- Integration with PetitionSubmission model

Constitutional Constraints:
- HP-2: Content hashing for duplicate detection
- HC-5: Sybil amplification defense via content hash
- CT-12: Witness integrity
"""

from uuid import uuid4

import pytest

from src.application.services.content_hash_service import Blake3ContentHashService
from src.domain.models.petition_submission import (
    PetitionSubmission,
    PetitionType,
)


class TestBlake3ContentHashService:
    """Tests for Blake3ContentHashService implementation."""

    @pytest.fixture
    def service(self) -> Blake3ContentHashService:
        """Create a Blake3ContentHashService instance."""
        return Blake3ContentHashService()

    # AC2: Hash length tests

    def test_hash_content_returns_32_bytes(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify hash_content returns exactly 32 bytes."""
        result = service.hash_content(b"test content")
        assert len(result) == 32
        assert isinstance(result, bytes)

    def test_hash_text_returns_32_bytes(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify hash_text returns exactly 32 bytes."""
        result = service.hash_text("test content")
        assert len(result) == 32
        assert isinstance(result, bytes)

    # AC6: Hash consistency tests

    def test_hash_content_is_consistent(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify same input always produces same output (determinism)."""
        content = b"identical content"
        hash1 = service.hash_content(content)
        hash2 = service.hash_content(content)
        assert hash1 == hash2

    def test_hash_text_is_consistent(self, service: Blake3ContentHashService) -> None:
        """Verify same text always produces same hash (determinism)."""
        text = "identical text content"
        hash1 = service.hash_text(text)
        hash2 = service.hash_text(text)
        assert hash1 == hash2

    def test_hash_consistency_across_instances(self) -> None:
        """Verify same input produces same hash across service instances."""
        service1 = Blake3ContentHashService()
        service2 = Blake3ContentHashService()
        content = b"test content for multiple instances"
        assert service1.hash_content(content) == service2.hash_content(content)

    # AC6: Collision resistance tests

    def test_different_content_produces_different_hashes(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify different inputs produce different hashes."""
        hash1 = service.hash_content(b"content one")
        hash2 = service.hash_content(b"content two")
        assert hash1 != hash2

    def test_different_text_produces_different_hashes(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify different text produces different hashes."""
        hash1 = service.hash_text("petition about taxes")
        hash2 = service.hash_text("petition about education")
        assert hash1 != hash2

    def test_similar_content_produces_different_hashes(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify even slightly different content produces different hashes."""
        hash1 = service.hash_text("test")
        hash2 = service.hash_text("Test")  # Capital T
        hash3 = service.hash_text("test ")  # Trailing space
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    # AC6: Empty content handling

    def test_hash_empty_content(self, service: Blake3ContentHashService) -> None:
        """Verify empty bytes can be hashed."""
        result = service.hash_content(b"")
        assert len(result) == 32
        # Empty content should produce a consistent hash
        assert result == service.hash_content(b"")

    def test_hash_empty_text(self, service: Blake3ContentHashService) -> None:
        """Verify empty string can be hashed."""
        result = service.hash_text("")
        assert len(result) == 32
        # Empty string hash should match empty bytes hash
        assert result == service.hash_content(b"")

    # AC6: Unicode content handling

    def test_hash_unicode_text(self, service: Blake3ContentHashService) -> None:
        """Verify Unicode text is properly hashed."""
        result = service.hash_text("Hello, 世界! 🌍")
        assert len(result) == 32

    def test_unicode_consistency(self, service: Blake3ContentHashService) -> None:
        """Verify Unicode text produces consistent hashes."""
        text = "Привет мир! 你好世界! مرحبا بالعالم!"
        hash1 = service.hash_text(text)
        hash2 = service.hash_text(text)
        assert hash1 == hash2

    def test_text_and_content_produce_same_hash(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify hash_text and hash_content produce same result for UTF-8."""
        text = "test content"
        text_hash = service.hash_text(text)
        content_hash = service.hash_content(text.encode("utf-8"))
        assert text_hash == content_hash

    # AC2: Verify hash tests

    def test_verify_hash_returns_true_for_matching_content(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify verify_hash returns True for matching content."""
        content = b"test content"
        expected_hash = service.hash_content(content)
        assert service.verify_hash(content, expected_hash) is True

    def test_verify_hash_returns_false_for_non_matching_content(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify verify_hash returns False for non-matching content."""
        content1 = b"content one"
        content2 = b"content two"
        hash1 = service.hash_content(content1)
        assert service.verify_hash(content2, hash1) is False

    def test_verify_hash_raises_for_invalid_hash_length(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify verify_hash raises ValueError for invalid hash length."""
        content = b"test content"
        with pytest.raises(ValueError, match="32 bytes"):
            service.verify_hash(content, b"too short")

    def test_verify_hash_raises_for_too_long_hash(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify verify_hash raises ValueError for too long hash."""
        content = b"test content"
        with pytest.raises(ValueError, match="32 bytes"):
            service.verify_hash(content, b"x" * 64)

    # AC4: Integration with PetitionSubmission

    def test_hash_petition_canonical_content(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify petition canonical_content_bytes produces hashable content."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="This is a test petition about governance.",
        )

        content_bytes = petition.canonical_content_bytes()
        hash_result = service.hash_content(content_bytes)

        assert len(hash_result) == 32
        assert isinstance(hash_result, bytes)

    def test_petition_with_content_hash_integration(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify service integrates with PetitionSubmission.with_content_hash."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Petition requesting budget review.",
        )

        # Hash the content
        content_hash = service.hash_content(petition.canonical_content_bytes())

        # Create new petition with hash
        hashed_petition = petition.with_content_hash(content_hash)

        # Verify the hash was set correctly
        assert hashed_petition.content_hash == content_hash
        assert len(hashed_petition.content_hash) == 32

    def test_identical_petition_text_produces_identical_hash(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify duplicate petition detection works (HC-5)."""
        petition1 = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Identical petition content for duplicate detection.",
        )
        petition2 = PetitionSubmission(
            id=uuid4(),  # Different ID
            type=PetitionType.CESSATION,  # Different type
            text="Identical petition content for duplicate detection.",  # Same text
        )

        hash1 = service.hash_content(petition1.canonical_content_bytes())
        hash2 = service.hash_content(petition2.canonical_content_bytes())

        # Hashes should be identical because text is identical
        assert hash1 == hash2

    def test_hash_petition_content_convenience_method(
        self, service: Blake3ContentHashService
    ) -> None:
        """Verify hash_petition_content convenience method works."""
        petition_text = "This petition requests constitutional review."
        result = service.hash_petition_content(petition_text)

        assert len(result) == 32
        # Should be same as hash_text
        assert result == service.hash_text(petition_text)

    # Service attributes

    def test_hash_size_constant(self, service: Blake3ContentHashService) -> None:
        """Verify HASH_SIZE constant is 32."""
        assert service.HASH_SIZE == 32

    def test_service_has_logging_mixin(self, service: Blake3ContentHashService) -> None:
        """Verify service has logging mixin attributes."""
        assert hasattr(service, "_log")

    # Large content handling

    def test_hash_large_content(self, service: Blake3ContentHashService) -> None:
        """Verify large content can be hashed."""
        # Create 10KB of content
        large_content = b"x" * 10_000
        result = service.hash_content(large_content)
        assert len(result) == 32

    def test_hash_max_petition_content(self, service: Blake3ContentHashService) -> None:
        """Verify maximum petition content (10,000 chars) can be hashed."""
        max_text = "a" * 10_000  # Maximum petition length
        result = service.hash_text(max_text)
        assert len(result) == 32
