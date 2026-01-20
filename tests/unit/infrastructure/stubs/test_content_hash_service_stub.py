"""Unit tests for ContentHashServiceStub (Story 0.5, AC3).

Tests verify the stub implementation provides:
- Deterministic fake hashes
- Operation tracking for assertions
- Configurable hash overrides

Constitutional Constraints:
- HP-2: Content hashing for duplicate detection (testing)
- HC-5: Sybil amplification defense testing
"""

import pytest

from src.infrastructure.stubs.content_hash_service_stub import (
    ContentHashServiceStub,
)


class TestContentHashServiceStub:
    """Tests for ContentHashServiceStub implementation."""

    @pytest.fixture
    def stub(self) -> ContentHashServiceStub:
        """Create a ContentHashServiceStub instance."""
        return ContentHashServiceStub()

    # Basic functionality

    def test_hash_content_returns_32_bytes(self, stub: ContentHashServiceStub) -> None:
        """Verify hash_content returns exactly 32 bytes."""
        result = stub.hash_content(b"test content")
        assert len(result) == 32
        assert isinstance(result, bytes)

    def test_hash_text_returns_32_bytes(self, stub: ContentHashServiceStub) -> None:
        """Verify hash_text returns exactly 32 bytes."""
        result = stub.hash_text("test content")
        assert len(result) == 32
        assert isinstance(result, bytes)

    def test_hash_is_deterministic(self, stub: ContentHashServiceStub) -> None:
        """Verify same input produces same hash (determinism)."""
        content = b"test content"
        hash1 = stub.hash_content(content)
        hash2 = stub.hash_content(content)
        assert hash1 == hash2

    def test_different_content_different_hash(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify different inputs produce different hashes."""
        hash1 = stub.hash_content(b"content one")
        hash2 = stub.hash_content(b"content two")
        assert hash1 != hash2

    # Verify hash functionality

    def test_verify_hash_returns_true_for_match(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify verify_hash returns True for matching content."""
        content = b"test content"
        expected = stub.hash_content(content)
        assert stub.verify_hash(content, expected) is True

    def test_verify_hash_returns_false_for_mismatch(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify verify_hash returns False for non-matching content."""
        hash1 = stub.hash_content(b"content one")
        assert stub.verify_hash(b"content two", hash1) is False

    def test_verify_hash_raises_for_invalid_length(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify verify_hash raises ValueError for invalid hash length."""
        with pytest.raises(ValueError, match="32 bytes"):
            stub.verify_hash(b"content", b"too short")

    # Operation tracking

    def test_tracks_hash_content_operations(self, stub: ContentHashServiceStub) -> None:
        """Verify hash_content operations are tracked."""
        stub.hash_content(b"content one")
        stub.hash_content(b"content two")

        operations = stub.get_operations()
        assert len(operations) == 2
        assert operations[0].method == "hash_content"
        assert operations[0].content == b"content one"
        assert operations[1].content == b"content two"

    def test_tracks_hash_text_operations(self, stub: ContentHashServiceStub) -> None:
        """Verify hash_text operations are tracked."""
        stub.hash_text("text one")
        stub.hash_text("text two")

        operations = stub.get_hash_text_calls()
        assert len(operations) == 2
        assert operations[0].method == "hash_text"
        assert operations[0].content == b"text one"

    def test_tracks_verify_operations(self, stub: ContentHashServiceStub) -> None:
        """Verify verify_hash operations are tracked."""
        content = b"test"
        hash_result = stub.hash_content(content)
        stub.verify_hash(content, hash_result)

        verify_calls = stub.get_verify_calls()
        assert len(verify_calls) == 1
        content_arg, expected_arg, result_arg = verify_calls[0]
        assert content_arg == content
        assert expected_arg == hash_result
        assert result_arg is True

    def test_operation_count(self, stub: ContentHashServiceStub) -> None:
        """Verify operation count is correct."""
        assert stub.get_operation_count() == 0

        stub.hash_content(b"one")
        assert stub.get_operation_count() == 1

        stub.hash_text("two")
        assert stub.get_operation_count() == 2

        stub.hash_content(b"three")
        assert stub.get_operation_count() == 3

    def test_was_content_hashed(self, stub: ContentHashServiceStub) -> None:
        """Verify was_content_hashed helper works."""
        stub.hash_content(b"tracked content")

        assert stub.was_content_hashed(b"tracked content") is True
        assert stub.was_content_hashed(b"not tracked") is False

    def test_was_text_hashed(self, stub: ContentHashServiceStub) -> None:
        """Verify was_text_hashed helper works."""
        stub.hash_text("tracked text")

        assert stub.was_text_hashed("tracked text") is True
        assert stub.was_text_hashed("not tracked") is False

    def test_get_last_hash(self, stub: ContentHashServiceStub) -> None:
        """Verify get_last_hash returns most recent hash."""
        assert stub.get_last_hash() is None  # No operations yet

        hash1 = stub.hash_content(b"first")
        assert stub.get_last_hash() == hash1

        hash2 = stub.hash_text("second")
        assert stub.get_last_hash() == hash2

    # Hash override functionality

    def test_set_override_changes_hash_result(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify set_override changes the returned hash."""
        content = b"test content"
        custom_hash = b"x" * 32

        stub.set_override(content, custom_hash)
        result = stub.hash_content(content)

        assert result == custom_hash

    def test_set_text_override_changes_hash_result(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify set_text_override changes the returned hash."""
        text = "test text"
        custom_hash = b"y" * 32

        stub.set_text_override(text, custom_hash)
        result = stub.hash_text(text)

        assert result == custom_hash

    def test_override_requires_32_byte_hash(self, stub: ContentHashServiceStub) -> None:
        """Verify set_override raises for invalid hash length."""
        with pytest.raises(ValueError, match="32 bytes"):
            stub.set_override(b"content", b"too short")

    def test_override_does_not_affect_other_content(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify override only affects specified content."""
        content1 = b"content one"
        content2 = b"content two"
        custom_hash = b"z" * 32

        stub.set_override(content1, custom_hash)

        assert stub.hash_content(content1) == custom_hash
        assert stub.hash_content(content2) != custom_hash

    # Clear functionality

    def test_clear_removes_operations(self, stub: ContentHashServiceStub) -> None:
        """Verify clear removes all tracked operations."""
        stub.hash_content(b"content")
        stub.hash_text("text")
        assert stub.get_operation_count() > 0

        stub.clear()

        assert stub.get_operation_count() == 0
        assert len(stub.get_operations()) == 0

    def test_clear_removes_overrides(self, stub: ContentHashServiceStub) -> None:
        """Verify clear removes hash overrides."""
        content = b"test"
        custom_hash = b"a" * 32

        stub.set_override(content, custom_hash)
        assert stub.hash_content(content) == custom_hash

        stub.clear()

        # After clear, should use default (SHA-256) hash, not custom
        result = stub.hash_content(content)
        assert result != custom_hash

    def test_clear_removes_verify_calls(self, stub: ContentHashServiceStub) -> None:
        """Verify clear removes verify operation tracking."""
        stub.verify_hash(b"content", b"x" * 32)
        assert len(stub.get_verify_calls()) == 1

        stub.clear()

        assert len(stub.get_verify_calls()) == 0

    # HashOperation dataclass

    def test_hash_operation_has_timestamp(self, stub: ContentHashServiceStub) -> None:
        """Verify HashOperation includes timestamp."""
        stub.hash_content(b"content")
        operation = stub.get_operations()[0]

        assert operation.timestamp is not None
        assert hasattr(operation, "timestamp")

    def test_hash_operation_is_frozen(self, stub: ContentHashServiceStub) -> None:
        """Verify HashOperation is immutable (frozen dataclass)."""
        stub.hash_content(b"content")
        operation = stub.get_operations()[0]

        with pytest.raises(Exception):  # FrozenInstanceError
            operation.content = b"modified"  # type: ignore

    # Edge cases

    def test_hash_empty_content(self, stub: ContentHashServiceStub) -> None:
        """Verify empty content can be hashed."""
        result = stub.hash_content(b"")
        assert len(result) == 32

    def test_hash_empty_text(self, stub: ContentHashServiceStub) -> None:
        """Verify empty string can be hashed."""
        result = stub.hash_text("")
        assert len(result) == 32

    def test_hash_unicode_text(self, stub: ContentHashServiceStub) -> None:
        """Verify Unicode text is properly hashed."""
        result = stub.hash_text("Hello, 世界! 🌍")
        assert len(result) == 32

    def test_hash_large_content(self, stub: ContentHashServiceStub) -> None:
        """Verify large content can be hashed."""
        large_content = b"x" * 10_000
        result = stub.hash_content(large_content)
        assert len(result) == 32

    # Protocol compliance

    def test_stub_has_hash_size_constant(self, stub: ContentHashServiceStub) -> None:
        """Verify stub has HASH_SIZE constant matching protocol."""
        assert stub.HASH_SIZE == 32

    def test_text_hash_equals_content_hash_for_utf8(
        self, stub: ContentHashServiceStub
    ) -> None:
        """Verify hash_text and hash_content produce same result for UTF-8."""
        text = "test content"
        text_hash = stub.hash_text(text)
        content_hash = stub.hash_content(text.encode("utf-8"))
        assert text_hash == content_hash
