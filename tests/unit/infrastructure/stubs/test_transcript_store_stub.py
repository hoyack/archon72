"""Unit tests for TranscriptStoreStub (Story 2B.5, AC-9).

Tests the in-memory stub implementation of TranscriptStoreProtocol:
- Content-addressed storage by Blake3 hash
- Append-only semantics (idempotent store)
- Retrieval and verification
- Test helper methods

Constitutional Constraints:
- CT-12: Witnessing creates accountability - hash enables verification
- FR-11.7: Hash-referenced preservation requirement
- NFR-6.5: Audit trail completeness - transcripts retrievable by hash
- NFR-4.2: Hash guarantees immutability (append-only semantic)
"""

from __future__ import annotations

import blake3
import pytest

from src.domain.models.transcript_reference import BLAKE3_HASH_LENGTH
from src.infrastructure.stubs.transcript_store_stub import (
    TranscriptStoreOperation,
    TranscriptStoreStub,
)


class TestTranscriptStoreStubStore:
    """Tests for store method."""

    @pytest.mark.asyncio
    async def test_store_returns_transcript_reference(self) -> None:
        """Test store returns TranscriptReference with correct fields."""
        stub = TranscriptStoreStub()
        transcript = "Test transcript content"

        ref = await stub.store(transcript)

        assert ref.content_hash is not None
        assert len(ref.content_hash) == BLAKE3_HASH_LENGTH
        assert ref.content_size == len(transcript.encode("utf-8"))
        assert ref.stored_at is not None
        assert ref.storage_path is None  # Stub doesn't use storage path

    @pytest.mark.asyncio
    async def test_store_computes_correct_blake3_hash(self) -> None:
        """Test store computes correct Blake3 hash of content."""
        stub = TranscriptStoreStub()
        transcript = "Unique transcript content for hashing"

        ref = await stub.store(transcript)

        expected_hash = blake3.blake3(transcript.encode("utf-8")).digest()
        assert ref.content_hash == expected_hash

    @pytest.mark.asyncio
    async def test_store_is_idempotent(self) -> None:
        """Test storing same content twice returns same reference."""
        stub = TranscriptStoreStub()
        transcript = "Same content stored twice"

        ref1 = await stub.store(transcript)
        ref2 = await stub.store(transcript)

        assert ref1.content_hash == ref2.content_hash
        assert stub.get_transcript_count() == 1  # Only one stored

    @pytest.mark.asyncio
    async def test_store_empty_transcript_raises_value_error(self) -> None:
        """Test storing empty transcript raises ValueError."""
        stub = TranscriptStoreStub()

        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            await stub.store("")

    @pytest.mark.asyncio
    async def test_store_none_transcript_raises_value_error(self) -> None:
        """Test storing None transcript raises ValueError."""
        stub = TranscriptStoreStub()

        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            await stub.store(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_store_records_operation(self) -> None:
        """Test store records operation for test verification."""
        stub = TranscriptStoreStub()
        transcript = "Operation tracking test"

        await stub.store(transcript)

        ops = stub.get_operations()
        assert len(ops) == 1
        assert ops[0][0] == TranscriptStoreOperation.STORE
        assert "content_hash" in ops[0][1]
        assert "size" in ops[0][1]


class TestTranscriptStoreStubRetrieve:
    """Tests for retrieve method."""

    @pytest.mark.asyncio
    async def test_retrieve_returns_stored_transcript(self) -> None:
        """Test retrieve returns original transcript content."""
        stub = TranscriptStoreStub()
        transcript = "Retrievable transcript content"

        ref = await stub.store(transcript)
        retrieved = await stub.retrieve(ref.content_hash)

        assert retrieved == transcript

    @pytest.mark.asyncio
    async def test_retrieve_unknown_hash_returns_none(self) -> None:
        """Test retrieve with unknown hash returns None."""
        stub = TranscriptStoreStub()
        unknown_hash = blake3.blake3(b"nonexistent").digest()

        result = await stub.retrieve(unknown_hash)

        assert result is None

    @pytest.mark.asyncio
    async def test_retrieve_invalid_hash_length_raises(self) -> None:
        """Test retrieve with invalid hash length raises ValueError."""
        stub = TranscriptStoreStub()
        invalid_hash = b"too_short"

        with pytest.raises(ValueError, match="content_hash must be 32 bytes"):
            await stub.retrieve(invalid_hash)

    @pytest.mark.asyncio
    async def test_retrieve_records_operation(self) -> None:
        """Test retrieve records operation for test verification."""
        stub = TranscriptStoreStub()
        transcript = "Retrieve tracking test"

        ref = await stub.store(transcript)
        await stub.retrieve(ref.content_hash)

        ops = stub.get_operations()
        assert len(ops) == 2
        assert ops[1][0] == TranscriptStoreOperation.RETRIEVE


class TestTranscriptStoreStubExists:
    """Tests for exists method."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_stored(self) -> None:
        """Test exists returns True for stored transcript."""
        stub = TranscriptStoreStub()
        transcript = "Existing transcript"

        ref = await stub.store(transcript)
        result = await stub.exists(ref.content_hash)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_unknown(self) -> None:
        """Test exists returns False for unknown hash."""
        stub = TranscriptStoreStub()
        unknown_hash = blake3.blake3(b"unknown").digest()

        result = await stub.exists(unknown_hash)

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_invalid_hash_length_raises(self) -> None:
        """Test exists with invalid hash length raises ValueError."""
        stub = TranscriptStoreStub()

        with pytest.raises(ValueError, match="content_hash must be 32 bytes"):
            await stub.exists(b"short")

    @pytest.mark.asyncio
    async def test_exists_records_operation(self) -> None:
        """Test exists records operation for test verification."""
        stub = TranscriptStoreStub()
        test_hash = blake3.blake3(b"test").digest()

        await stub.exists(test_hash)

        ops = stub.get_operations()
        assert ops[0][0] == TranscriptStoreOperation.EXISTS


class TestTranscriptStoreStubVerify:
    """Tests for verify method."""

    @pytest.mark.asyncio
    async def test_verify_returns_true_for_matching_content(self) -> None:
        """Test verify returns True when content matches hash."""
        stub = TranscriptStoreStub()
        transcript = "Verifiable content"

        ref = await stub.store(transcript)
        result = await stub.verify(ref.content_hash, transcript)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_returns_false_for_mismatched_content(self) -> None:
        """Test verify returns False when content doesn't match hash."""
        stub = TranscriptStoreStub()
        transcript = "Original content"

        ref = await stub.store(transcript)
        result = await stub.verify(ref.content_hash, "Different content")

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_invalid_hash_length_raises(self) -> None:
        """Test verify with invalid hash length raises ValueError."""
        stub = TranscriptStoreStub()

        with pytest.raises(ValueError, match="content_hash must be 32 bytes"):
            await stub.verify(b"invalid", "some content")

    @pytest.mark.asyncio
    async def test_verify_records_operation(self) -> None:
        """Test verify records operation for test verification."""
        stub = TranscriptStoreStub()
        test_hash = blake3.blake3(b"test").digest()

        await stub.verify(test_hash, "test")

        ops = stub.get_operations()
        assert ops[0][0] == TranscriptStoreOperation.VERIFY


class TestTranscriptStoreStubGetReference:
    """Tests for get_reference method."""

    @pytest.mark.asyncio
    async def test_get_reference_returns_reference_for_stored(self) -> None:
        """Test get_reference returns TranscriptReference for stored content."""
        stub = TranscriptStoreStub()
        transcript = "Reference test content"

        stored_ref = await stub.store(transcript)
        retrieved_ref = await stub.get_reference(stored_ref.content_hash)

        assert retrieved_ref is not None
        assert retrieved_ref.content_hash == stored_ref.content_hash
        assert retrieved_ref.content_size == stored_ref.content_size

    @pytest.mark.asyncio
    async def test_get_reference_returns_none_for_unknown(self) -> None:
        """Test get_reference returns None for unknown hash."""
        stub = TranscriptStoreStub()
        unknown_hash = blake3.blake3(b"unknown").digest()

        result = await stub.get_reference(unknown_hash)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_reference_invalid_hash_length_raises(self) -> None:
        """Test get_reference with invalid hash length raises ValueError."""
        stub = TranscriptStoreStub()

        with pytest.raises(ValueError, match="content_hash must be 32 bytes"):
            await stub.get_reference(b"bad")

    @pytest.mark.asyncio
    async def test_get_reference_records_operation(self) -> None:
        """Test get_reference records operation for test verification."""
        stub = TranscriptStoreStub()
        test_hash = blake3.blake3(b"test").digest()

        await stub.get_reference(test_hash)

        ops = stub.get_operations()
        assert ops[0][0] == TranscriptStoreOperation.GET_REFERENCE


class TestTranscriptStoreStubHelpers:
    """Tests for helper methods."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_state(self) -> None:
        """Test clear removes all transcripts, references, and operations."""
        stub = TranscriptStoreStub()

        await stub.store("Transcript 1")
        await stub.store("Transcript 2")

        stub.clear()

        assert stub.get_transcript_count() == 0
        assert stub.get_operations() == []

    @pytest.mark.asyncio
    async def test_get_transcript_count(self) -> None:
        """Test get_transcript_count returns correct count."""
        stub = TranscriptStoreStub()

        assert stub.get_transcript_count() == 0

        await stub.store("First")
        assert stub.get_transcript_count() == 1

        await stub.store("Second")
        assert stub.get_transcript_count() == 2

        # Duplicate doesn't increase count
        await stub.store("First")
        assert stub.get_transcript_count() == 2

    @pytest.mark.asyncio
    async def test_inject_transcript(self) -> None:
        """Test inject_transcript adds transcript without normal store flow."""
        stub = TranscriptStoreStub()
        transcript = "Injected transcript"

        ref = stub.inject_transcript(transcript)

        # Should be retrievable
        retrieved = await stub.retrieve(ref.content_hash)
        assert retrieved == transcript

        ops = stub.get_operations()
        assert len(ops) == 1
        assert ops[0][0] == TranscriptStoreOperation.RETRIEVE

    @pytest.mark.asyncio
    async def test_get_all_hashes(self) -> None:
        """Test get_all_hashes returns all stored hashes."""
        stub = TranscriptStoreStub()

        ref1 = await stub.store("First transcript")
        ref2 = await stub.store("Second transcript")

        hashes = stub.get_all_hashes()

        assert len(hashes) == 2
        assert ref1.content_hash in hashes
        assert ref2.content_hash in hashes


class TestTranscriptStoreStubUnicode:
    """Tests for unicode content handling."""

    @pytest.mark.asyncio
    async def test_unicode_content_stored_correctly(self) -> None:
        """Test unicode content is stored and retrieved correctly."""
        stub = TranscriptStoreStub()
        unicode_transcript = "测试内容 🎯 Тест контент 🔥 テスト内容 ✅"

        ref = await stub.store(unicode_transcript)
        retrieved = await stub.retrieve(ref.content_hash)

        assert retrieved == unicode_transcript

    @pytest.mark.asyncio
    async def test_unicode_content_size_is_bytes(self) -> None:
        """Test content_size is byte length, not character count."""
        stub = TranscriptStoreStub()
        # Each Chinese character is 3 bytes in UTF-8
        unicode_transcript = "中文"

        ref = await stub.store(unicode_transcript)

        assert ref.content_size == len(unicode_transcript.encode("utf-8"))
        assert ref.content_size == 6  # 2 chars * 3 bytes each
