"""Unit tests for ProceduralRecordGeneratorStub infrastructure (Story 2.8, FR141-FR142).

Tests the in-memory stub implementation of ProceduralRecordGeneratorPort.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.ports.procedural_record_generator import ProceduralRecordData
from src.infrastructure.stubs.procedural_record_generator_stub import (
    DEV_MODE_WATERMARK,
    ProceduralRecordGeneratorStub,
)


class TestDevModeWatermark:
    """Tests for DEV_MODE_WATERMARK constant."""

    def test_watermark_contains_stub_name(self) -> None:
        """Watermark should contain stub name."""
        assert "ProceduralRecordGeneratorStub" in DEV_MODE_WATERMARK

    def test_watermark_indicates_dev(self) -> None:
        """Watermark should indicate development mode."""
        assert "DEV" in DEV_MODE_WATERMARK


class TestProceduralRecordGeneratorStubInit:
    """Tests for ProceduralRecordGeneratorStub initialization."""

    def test_init_creates_empty_store(self) -> None:
        """Initialize should create empty record store."""
        stub = ProceduralRecordGeneratorStub()
        assert stub._records == {}

    def test_init_with_halt_checker(self) -> None:
        """Initialize should accept optional halt checker."""
        stub = ProceduralRecordGeneratorStub()
        assert stub._halt_checker is None


class TestProceduralRecordGeneratorStubGenerateRecord:
    """Tests for ProceduralRecordGeneratorStub.generate_record()."""

    @pytest.mark.asyncio
    async def test_generate_record_returns_procedural_record_data(self) -> None:
        """generate_record should return ProceduralRecordData."""
        stub = ProceduralRecordGeneratorStub()
        result = await stub.generate_record(deliberation_id=uuid4())

        assert isinstance(result, ProceduralRecordData)

    @pytest.mark.asyncio
    async def test_generate_record_generates_unique_ids(self) -> None:
        """Each record should have unique record_id."""
        stub = ProceduralRecordGeneratorStub()

        result1 = await stub.generate_record(deliberation_id=uuid4())
        result2 = await stub.generate_record(deliberation_id=uuid4())

        assert result1.record_id != result2.record_id

    @pytest.mark.asyncio
    async def test_generate_record_stores_record(self) -> None:
        """generate_record should store record for later retrieval."""
        stub = ProceduralRecordGeneratorStub()
        result = await stub.generate_record(deliberation_id=uuid4())

        retrieved = await stub.get_record(result.record_id)
        assert retrieved is not None
        assert retrieved.record_id == result.record_id

    @pytest.mark.asyncio
    async def test_generate_record_includes_hash(self) -> None:
        """Record should include 64-char hash."""
        stub = ProceduralRecordGeneratorStub()
        result = await stub.generate_record(deliberation_id=uuid4())

        assert len(result.record_hash) == 64

    @pytest.mark.asyncio
    async def test_generate_record_includes_signature(self) -> None:
        """Record should include signature."""
        stub = ProceduralRecordGeneratorStub()
        result = await stub.generate_record(deliberation_id=uuid4())

        assert result.signature != ""

    @pytest.mark.asyncio
    async def test_generate_record_preserves_deliberation_id(self) -> None:
        """Record should preserve deliberation_id."""
        stub = ProceduralRecordGeneratorStub()
        delib_id = uuid4()

        result = await stub.generate_record(deliberation_id=delib_id)

        assert result.deliberation_id == delib_id


class TestProceduralRecordGeneratorStubWithMockData:
    """Tests for ProceduralRecordGeneratorStub with mock data."""

    @pytest.mark.asyncio
    async def test_generate_record_with_mock_data(self) -> None:
        """generate_record should include mock data fields."""
        stub = ProceduralRecordGeneratorStub()

        # Register mock deliberation data
        delib_id = uuid4()
        stub.register_mock_deliberation_data(
            deliberation_id=delib_id,
            agenda_items=["Motion A", "Motion B"],
            participant_ids=["agent-1", "agent-2", "agent-3"],
            vote_summary={"aye": 45, "nay": 20, "abstain": 7},
            timeline_events=[
                {"timestamp": "2025-12-28T10:00:00Z", "event": "started"},
                {"timestamp": "2025-12-28T11:00:00Z", "event": "ended"},
            ],
            decisions=["Approved Motion A", "Rejected Motion B"],
        )

        result = await stub.generate_record(deliberation_id=delib_id)

        assert result.agenda_items == ["Motion A", "Motion B"]
        assert result.participant_ids == ["agent-1", "agent-2", "agent-3"]
        assert result.vote_summary == {"aye": 45, "nay": 20, "abstain": 7}
        assert len(result.timeline_events) == 2
        assert result.decisions == ["Approved Motion A", "Rejected Motion B"]


class TestProceduralRecordGeneratorStubGetRecord:
    """Tests for ProceduralRecordGeneratorStub.get_record()."""

    @pytest.mark.asyncio
    async def test_get_record_returns_stored(self) -> None:
        """get_record should return stored record."""
        stub = ProceduralRecordGeneratorStub()
        record = await stub.generate_record(deliberation_id=uuid4())

        retrieved = await stub.get_record(record.record_id)

        assert retrieved is not None
        assert retrieved == record

    @pytest.mark.asyncio
    async def test_get_record_returns_none_for_unknown(self) -> None:
        """get_record should return None for unknown record."""
        stub = ProceduralRecordGeneratorStub()

        retrieved = await stub.get_record(uuid4())

        assert retrieved is None


class TestProceduralRecordGeneratorStubVerifyRecord:
    """Tests for ProceduralRecordGeneratorStub.verify_record()."""

    @pytest.mark.asyncio
    async def test_verify_record_returns_true_for_known(self) -> None:
        """verify_record should return True for known record."""
        stub = ProceduralRecordGeneratorStub()
        record = await stub.generate_record(deliberation_id=uuid4())

        is_valid = await stub.verify_record(record.record_id)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_record_returns_false_for_unknown(self) -> None:
        """verify_record should return False for unknown record."""
        stub = ProceduralRecordGeneratorStub()

        is_valid = await stub.verify_record(uuid4())

        assert is_valid is False
