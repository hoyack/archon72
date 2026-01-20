"""Unit tests for TranscriptReference domain model (Story 2B.5, AC-9).

Tests the TranscriptReference value object:
- Validation of content hash (32 bytes Blake3)
- Serialization/deserialization
- Immutability (frozen dataclass)

Constitutional Constraints:
- CT-12: Enables witness verification through hash referencing
- FR-11.7: Hash-referenced preservation requirement
- NFR-6.5: Supports audit trail reconstruction
- NFR-4.2: Hash guarantees immutability (append-only)
"""

from __future__ import annotations

from datetime import datetime, timezone

import blake3
import pytest

from src.domain.models.transcript_reference import (
    BLAKE3_HASH_LENGTH,
    TranscriptReference,
)


def _create_valid_hash() -> bytes:
    """Create a valid 32-byte Blake3 hash for testing."""
    return blake3.blake3(b"test content").digest()


class TestTranscriptReferenceCreation:
    """Tests for TranscriptReference creation and validation."""

    def test_create_with_valid_hash(self) -> None:
        """Test creating TranscriptReference with valid hash."""
        valid_hash = _create_valid_hash()

        ref = TranscriptReference(
            content_hash=valid_hash,
            content_size=100,
        )

        assert ref.content_hash == valid_hash
        assert ref.content_size == 100
        assert ref.stored_at is not None
        assert ref.storage_path is None

    def test_create_with_all_fields(self) -> None:
        """Test creating TranscriptReference with all fields."""
        valid_hash = _create_valid_hash()
        stored_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        ref = TranscriptReference(
            content_hash=valid_hash,
            content_size=500,
            stored_at=stored_at,
            storage_path="/path/to/transcript.txt",
        )

        assert ref.content_hash == valid_hash
        assert ref.content_size == 500
        assert ref.stored_at == stored_at
        assert ref.storage_path == "/path/to/transcript.txt"

    def test_invalid_hash_length_short_raises(self) -> None:
        """Test creating with short hash raises ValueError."""
        short_hash = b"too_short"

        with pytest.raises(
            ValueError, match=f"content_hash must be {BLAKE3_HASH_LENGTH} bytes"
        ):
            TranscriptReference(
                content_hash=short_hash,
                content_size=100,
            )

    def test_invalid_hash_length_long_raises(self) -> None:
        """Test creating with long hash raises ValueError."""
        long_hash = b"x" * 64

        with pytest.raises(
            ValueError, match=f"content_hash must be {BLAKE3_HASH_LENGTH} bytes"
        ):
            TranscriptReference(
                content_hash=long_hash,
                content_size=100,
            )

    def test_negative_content_size_raises(self) -> None:
        """Test creating with negative content_size raises ValueError."""
        valid_hash = _create_valid_hash()

        with pytest.raises(ValueError, match="content_size must be >= 0"):
            TranscriptReference(
                content_hash=valid_hash,
                content_size=-1,
            )

    def test_zero_content_size_is_valid(self) -> None:
        """Test creating with zero content_size is valid (empty file edge case)."""
        valid_hash = _create_valid_hash()

        ref = TranscriptReference(
            content_hash=valid_hash,
            content_size=0,
        )

        assert ref.content_size == 0


class TestTranscriptReferenceImmutability:
    """Tests for TranscriptReference immutability (frozen dataclass)."""

    def test_cannot_modify_content_hash(self) -> None:
        """Test content_hash is immutable."""
        valid_hash = _create_valid_hash()
        ref = TranscriptReference(content_hash=valid_hash, content_size=100)

        with pytest.raises(AttributeError):
            ref.content_hash = blake3.blake3(b"new").digest()  # type: ignore[misc]

    def test_cannot_modify_content_size(self) -> None:
        """Test content_size is immutable."""
        valid_hash = _create_valid_hash()
        ref = TranscriptReference(content_hash=valid_hash, content_size=100)

        with pytest.raises(AttributeError):
            ref.content_size = 200  # type: ignore[misc]


class TestTranscriptReferenceEquality:
    """Tests for TranscriptReference equality."""

    def test_equal_references_are_equal(self) -> None:
        """Test two references with same content_hash are equal."""
        valid_hash = _create_valid_hash()
        stored_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        ref1 = TranscriptReference(
            content_hash=valid_hash,
            content_size=100,
            stored_at=stored_at,
        )
        ref2 = TranscriptReference(
            content_hash=valid_hash,
            content_size=100,
            stored_at=stored_at,
        )

        assert ref1 == ref2

    def test_different_hashes_are_not_equal(self) -> None:
        """Test references with different hashes are not equal."""
        hash1 = blake3.blake3(b"content1").digest()
        hash2 = blake3.blake3(b"content2").digest()

        ref1 = TranscriptReference(content_hash=hash1, content_size=100)
        ref2 = TranscriptReference(content_hash=hash2, content_size=100)

        assert ref1 != ref2

    def test_references_are_hashable(self) -> None:
        """Test TranscriptReference can be used in sets."""
        valid_hash = _create_valid_hash()
        stored_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        ref1 = TranscriptReference(
            content_hash=valid_hash,
            content_size=100,
            stored_at=stored_at,
        )
        ref2 = TranscriptReference(
            content_hash=valid_hash,
            content_size=100,
            stored_at=stored_at,
        )

        ref_set = {ref1, ref2}
        assert len(ref_set) == 1


class TestTranscriptReferenceProperties:
    """Tests for TranscriptReference properties."""

    def test_content_hash_hex_property(self) -> None:
        """Test content_hash_hex returns hex string."""
        valid_hash = _create_valid_hash()
        ref = TranscriptReference(content_hash=valid_hash, content_size=100)

        hex_str = ref.content_hash_hex

        assert isinstance(hex_str, str)
        assert len(hex_str) == 64  # 32 bytes = 64 hex chars
        assert bytes.fromhex(hex_str) == valid_hash


class TestTranscriptReferenceSerialization:
    """Tests for TranscriptReference serialization."""

    def test_to_dict(self) -> None:
        """Test to_dict produces correct dictionary."""
        valid_hash = _create_valid_hash()
        stored_at = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

        ref = TranscriptReference(
            content_hash=valid_hash,
            content_size=256,
            stored_at=stored_at,
            storage_path="/path/to/file",
        )

        result = ref.to_dict()

        assert result["content_hash"] == valid_hash.hex()
        assert result["content_size"] == 256
        assert result["stored_at"] == stored_at.isoformat()
        assert result["storage_path"] == "/path/to/file"
        assert result["schema_version"] == 1

    def test_from_dict(self) -> None:
        """Test from_dict creates correct TranscriptReference."""
        valid_hash = _create_valid_hash()
        stored_at = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

        data = {
            "content_hash": valid_hash.hex(),
            "content_size": 256,
            "stored_at": stored_at.isoformat(),
            "storage_path": "/path/to/file",
        }

        ref = TranscriptReference.from_dict(data)

        assert ref.content_hash == valid_hash
        assert ref.content_size == 256
        assert ref.stored_at == stored_at
        assert ref.storage_path == "/path/to/file"

    def test_from_dict_missing_content_hash_raises(self) -> None:
        """Test from_dict raises ValueError if content_hash missing."""
        data = {"content_size": 100}

        with pytest.raises(ValueError, match="content_hash is required"):
            TranscriptReference.from_dict(data)

    def test_from_dict_with_defaults(self) -> None:
        """Test from_dict uses defaults for optional fields."""
        valid_hash = _create_valid_hash()

        data = {"content_hash": valid_hash.hex()}

        ref = TranscriptReference.from_dict(data)

        assert ref.content_hash == valid_hash
        assert ref.content_size == 0  # Default
        assert ref.storage_path is None  # Default
        assert ref.stored_at is not None  # Auto-generated

    def test_roundtrip_serialization(self) -> None:
        """Test to_dict and from_dict roundtrip."""
        valid_hash = _create_valid_hash()
        stored_at = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

        original = TranscriptReference(
            content_hash=valid_hash,
            content_size=1024,
            stored_at=stored_at,
            storage_path="/archive/transcripts/abc123",
        )

        serialized = original.to_dict()
        restored = TranscriptReference.from_dict(serialized)

        assert restored.content_hash == original.content_hash
        assert restored.content_size == original.content_size
        assert restored.stored_at == original.stored_at
        assert restored.storage_path == original.storage_path


class TestBLAKE3HashLengthConstant:
    """Tests for BLAKE3_HASH_LENGTH constant."""

    def test_blake3_hash_length_is_32(self) -> None:
        """Test BLAKE3_HASH_LENGTH is 32 bytes."""
        assert BLAKE3_HASH_LENGTH == 32

    def test_blake3_produces_32_byte_hash(self) -> None:
        """Test blake3 library actually produces 32-byte hash."""
        test_hash = blake3.blake3(b"test").digest()
        assert len(test_hash) == BLAKE3_HASH_LENGTH
