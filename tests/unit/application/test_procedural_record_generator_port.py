"""Unit tests for ProceduralRecordGeneratorPort interface (Story 2.8, FR141-FR142).

Tests the port interface and ProceduralRecordData dataclass.
"""

from __future__ import annotations

from types import MappingProxyType
from uuid import UUID, uuid4

import pytest

from src.application.ports.procedural_record_generator import (
    ProceduralRecordData,
    ProceduralRecordGeneratorPort,
)


class TestProceduralRecordData:
    """Tests for ProceduralRecordData dataclass."""

    def test_create_valid_record_data(self) -> None:
        """Should create valid ProceduralRecordData with all fields."""
        record_id = uuid4()
        deliberation_id = uuid4()

        data = ProceduralRecordData(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=("Motion A", "Motion B"),
            participant_ids=("agent-1", "agent-2"),
            vote_summary=MappingProxyType({"aye": 45, "nay": 20}),
            timeline_events=(
                MappingProxyType({"timestamp": "2025-12-28T10:00:00Z", "event": "started"}),
            ),
            decisions=("Approved Motion A",),
            record_hash="a" * 64,
            signature="sig123",
        )

        assert data.record_id == record_id
        assert data.deliberation_id == deliberation_id
        assert data.agenda_items == ("Motion A", "Motion B")
        assert data.participant_ids == ("agent-1", "agent-2")
        assert dict(data.vote_summary) == {"aye": 45, "nay": 20}
        assert len(data.timeline_events) == 1
        assert data.decisions == ("Approved Motion A",)
        assert data.record_hash == "a" * 64
        assert data.signature == "sig123"

    def test_record_data_is_frozen(self) -> None:
        """ProceduralRecordData should be immutable (frozen dataclass)."""
        data = ProceduralRecordData(
            record_id=uuid4(),
            deliberation_id=uuid4(),
            agenda_items=(),
            participant_ids=(),
            vote_summary=MappingProxyType({}),
            timeline_events=(),
            decisions=(),
            record_hash="b" * 64,
            signature="sig456",
        )

        with pytest.raises(AttributeError):
            data.record_hash = "c" * 64  # type: ignore[misc]

    def test_empty_collections_allowed(self) -> None:
        """Should allow empty collections."""
        data = ProceduralRecordData(
            record_id=uuid4(),
            deliberation_id=uuid4(),
            agenda_items=(),
            participant_ids=(),
            vote_summary=MappingProxyType({}),
            timeline_events=(),
            decisions=(),
            record_hash="d" * 64,
            signature="sig789",
        )

        assert data.agenda_items == ()
        assert data.participant_ids == ()
        assert dict(data.vote_summary) == {}
        assert data.timeline_events == ()
        assert data.decisions == ()


class TestProceduralRecordGeneratorPortProtocol:
    """Tests for ProceduralRecordGeneratorPort protocol definition."""

    def test_protocol_has_generate_record_method(self) -> None:
        """Protocol should define generate_record method."""
        assert hasattr(ProceduralRecordGeneratorPort, "generate_record")

    def test_protocol_has_get_record_method(self) -> None:
        """Protocol should define get_record method."""
        assert hasattr(ProceduralRecordGeneratorPort, "get_record")

    def test_protocol_has_verify_record_method(self) -> None:
        """Protocol should define verify_record method."""
        assert hasattr(ProceduralRecordGeneratorPort, "verify_record")


class MockProceduralRecordGenerator:
    """Mock implementation of ProceduralRecordGeneratorPort for testing."""

    def __init__(self) -> None:
        self._records: dict[UUID, ProceduralRecordData] = {}

    async def generate_record(
        self,
        deliberation_id: UUID,
    ) -> ProceduralRecordData:
        """Mock record generation."""
        record_id = uuid4()
        data = ProceduralRecordData(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=("Mock Agenda Item",),
            participant_ids=("mock-agent-1",),
            vote_summary=MappingProxyType({"aye": 10}),
            timeline_events=(),
            decisions=("Mock Decision",),
            record_hash="e" * 64,
            signature="mock_signature",
        )
        self._records[record_id] = data
        return data

    async def get_record(
        self,
        record_id: UUID,
    ) -> ProceduralRecordData | None:
        """Mock get record."""
        return self._records.get(record_id)

    async def verify_record(
        self,
        record_id: UUID,
    ) -> bool:
        """Mock verification."""
        return record_id in self._records


class TestMockProceduralRecordGenerator:
    """Tests that mock implements the protocol correctly."""

    @pytest.mark.asyncio
    async def test_generate_record_returns_procedural_record_data(self) -> None:
        """generate_record should return ProceduralRecordData."""
        generator = MockProceduralRecordGenerator()
        result = await generator.generate_record(deliberation_id=uuid4())

        assert isinstance(result, ProceduralRecordData)
        assert result.agenda_items == ("Mock Agenda Item",)

    @pytest.mark.asyncio
    async def test_get_record_returns_stored_record(self) -> None:
        """get_record should return stored record."""
        generator = MockProceduralRecordGenerator()
        generated = await generator.generate_record(deliberation_id=uuid4())

        retrieved = await generator.get_record(record_id=generated.record_id)

        assert retrieved is not None
        assert retrieved.record_id == generated.record_id

    @pytest.mark.asyncio
    async def test_get_record_returns_none_for_unknown(self) -> None:
        """get_record should return None for unknown record."""
        generator = MockProceduralRecordGenerator()

        retrieved = await generator.get_record(record_id=uuid4())

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_verify_record_returns_true_for_known_record(self) -> None:
        """verify_record should return True for known record."""
        generator = MockProceduralRecordGenerator()
        generated = await generator.generate_record(deliberation_id=uuid4())

        is_valid = await generator.verify_record(record_id=generated.record_id)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_record_returns_false_for_unknown(self) -> None:
        """verify_record should return False for unknown record."""
        generator = MockProceduralRecordGenerator()

        is_valid = await generator.verify_record(record_id=uuid4())

        assert is_valid is False
