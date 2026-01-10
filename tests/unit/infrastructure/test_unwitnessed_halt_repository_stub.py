"""Unit tests for UnwitnessedHaltRepositoryStub (Story 3.9, Task 3).

Tests the in-memory stub implementation for testing.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.unwitnessed_halt_repository import UnwitnessedHaltRepository
from src.domain.events.constitutional_crisis import (
    ConstitutionalCrisisPayload,
    CrisisType,
)
from src.domain.models.unwitnessed_halt import UnwitnessedHaltRecord
from src.infrastructure.stubs.unwitnessed_halt_repository_stub import (
    UnwitnessedHaltRepositoryStub,
)


class TestUnwitnessedHaltRepositoryStubProtocol:
    """Tests for protocol compliance."""

    def test_stub_implements_protocol(self) -> None:
        """Should implement UnwitnessedHaltRepository protocol."""
        stub = UnwitnessedHaltRepositoryStub()
        assert isinstance(stub, UnwitnessedHaltRepository)


class TestUnwitnessedHaltRepositoryStubSave:
    """Tests for save method."""

    @pytest.fixture
    def stub(self) -> UnwitnessedHaltRepositoryStub:
        return UnwitnessedHaltRepositoryStub()

    @pytest.fixture
    def sample_record(self) -> UnwitnessedHaltRecord:
        return UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Test fork",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test-service",
            ),
            failure_reason="DB unavailable",
            fallback_timestamp=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_save_stores_record(
        self, stub: UnwitnessedHaltRepositoryStub, sample_record: UnwitnessedHaltRecord
    ) -> None:
        """Should store record in memory."""
        await stub.save(sample_record)

        retrieved = await stub.get_by_id(sample_record.halt_id)
        assert retrieved == sample_record

    @pytest.mark.asyncio
    async def test_save_multiple_records(
        self, stub: UnwitnessedHaltRepositoryStub
    ) -> None:
        """Should store multiple records."""
        records = [
            UnwitnessedHaltRecord(
                halt_id=uuid4(),
                crisis_payload=ConstitutionalCrisisPayload(
                    crisis_type=CrisisType.FORK_DETECTED,
                    detection_timestamp=datetime.now(timezone.utc),
                    detection_details=f"Fork {i}",
                    triggering_event_ids=(uuid4(),),
                    detecting_service_id="test",
                ),
                failure_reason=f"Failure {i}",
                fallback_timestamp=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]

        for record in records:
            await stub.save(record)

        all_records = await stub.get_all()
        assert len(all_records) == 3


class TestUnwitnessedHaltRepositoryStubGetAll:
    """Tests for get_all method."""

    @pytest.fixture
    def stub(self) -> UnwitnessedHaltRepositoryStub:
        return UnwitnessedHaltRepositoryStub()

    @pytest.mark.asyncio
    async def test_get_all_returns_all_records(
        self, stub: UnwitnessedHaltRepositoryStub
    ) -> None:
        """Should return all saved records."""
        record1 = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Fork 1",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Failure 1",
            fallback_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        record2 = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.SEQUENCE_GAP_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Gap",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Failure 2",
            fallback_timestamp=datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        )

        await stub.save(record1)
        await stub.save(record2)

        all_records = await stub.get_all()
        assert len(all_records) == 2
        assert record1 in all_records
        assert record2 in all_records

    @pytest.mark.asyncio
    async def test_get_all_returns_empty_when_none(
        self, stub: UnwitnessedHaltRepositoryStub
    ) -> None:
        """Should return empty list when no records."""
        result = await stub.get_all()
        assert result == []


class TestUnwitnessedHaltRepositoryStubGetById:
    """Tests for get_by_id method."""

    @pytest.fixture
    def stub(self) -> UnwitnessedHaltRepositoryStub:
        return UnwitnessedHaltRepositoryStub()

    @pytest.mark.asyncio
    async def test_get_by_id_returns_record(
        self, stub: UnwitnessedHaltRepositoryStub
    ) -> None:
        """Should return record when found."""
        halt_id = uuid4()
        record = UnwitnessedHaltRecord(
            halt_id=halt_id,
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Test",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Test failure",
            fallback_timestamp=datetime.now(timezone.utc),
        )

        await stub.save(record)
        retrieved = await stub.get_by_id(halt_id)

        assert retrieved == record

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(
        self, stub: UnwitnessedHaltRepositoryStub
    ) -> None:
        """Should return None when record not found."""
        result = await stub.get_by_id(uuid4())
        assert result is None


class TestUnwitnessedHaltRepositoryStubReset:
    """Tests for reset method."""

    @pytest.fixture
    def stub(self) -> UnwitnessedHaltRepositoryStub:
        return UnwitnessedHaltRepositoryStub()

    @pytest.mark.asyncio
    async def test_reset_clears_records(
        self, stub: UnwitnessedHaltRepositoryStub
    ) -> None:
        """Should clear all records on reset."""
        record = UnwitnessedHaltRecord(
            halt_id=uuid4(),
            crisis_payload=ConstitutionalCrisisPayload(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_timestamp=datetime.now(timezone.utc),
                detection_details="Test",
                triggering_event_ids=(uuid4(),),
                detecting_service_id="test",
            ),
            failure_reason="Test",
            fallback_timestamp=datetime.now(timezone.utc),
        )

        await stub.save(record)
        assert len(await stub.get_all()) == 1

        stub.reset()
        assert len(await stub.get_all()) == 0
