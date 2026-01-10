"""Unit tests for WitnessedHaltWriterStub (Story 3.9, Task 5).

Tests the stub implementation for testing halt event writing.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.witnessed_halt_writer import WitnessedHaltWriter
from src.domain.events.constitutional_crisis import (
    CONSTITUTIONAL_CRISIS_EVENT_TYPE,
    ConstitutionalCrisisPayload,
    CrisisType,
)
from src.infrastructure.stubs.witnessed_halt_writer_stub import WitnessedHaltWriterStub


class TestWitnessedHaltWriterStubProtocol:
    """Tests for protocol compliance."""

    def test_stub_implements_protocol(self) -> None:
        """Should implement WitnessedHaltWriter protocol."""
        stub = WitnessedHaltWriterStub()
        assert isinstance(stub, WitnessedHaltWriter)


class TestWitnessedHaltWriterStubWrite:
    """Tests for write_halt_event method."""

    @pytest.fixture
    def stub(self) -> WitnessedHaltWriterStub:
        return WitnessedHaltWriterStub()

    @pytest.fixture
    def sample_crisis_payload(self) -> ConstitutionalCrisisPayload:
        return ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test fork detection",
            triggering_event_ids=(uuid4(), uuid4()),
            detecting_service_id="test-service",
        )

    @pytest.mark.asyncio
    async def test_write_returns_event_on_success(
        self,
        stub: WitnessedHaltWriterStub,
        sample_crisis_payload: ConstitutionalCrisisPayload,
    ) -> None:
        """Should return Event on successful write."""
        result = await stub.write_halt_event(sample_crisis_payload)

        assert result is not None
        assert result.event_type == CONSTITUTIONAL_CRISIS_EVENT_TYPE
        assert result.witness_id is not None
        assert result.witness_signature is not None

    @pytest.mark.asyncio
    async def test_write_returns_none_when_configured_to_fail(
        self,
        stub: WitnessedHaltWriterStub,
        sample_crisis_payload: ConstitutionalCrisisPayload,
    ) -> None:
        """Should return None when configured to fail."""
        stub.set_fail_next()
        result = await stub.write_halt_event(sample_crisis_payload)

        assert result is None

    @pytest.mark.asyncio
    async def test_fail_next_only_affects_next_call(
        self,
        stub: WitnessedHaltWriterStub,
        sample_crisis_payload: ConstitutionalCrisisPayload,
    ) -> None:
        """set_fail_next should only affect the next call."""
        stub.set_fail_next()

        # First call fails
        result1 = await stub.write_halt_event(sample_crisis_payload)
        assert result1 is None

        # Second call succeeds
        result2 = await stub.write_halt_event(sample_crisis_payload)
        assert result2 is not None


class TestWitnessedHaltWriterStubHistory:
    """Tests for written events history."""

    @pytest.fixture
    def stub(self) -> WitnessedHaltWriterStub:
        return WitnessedHaltWriterStub()

    @pytest.mark.asyncio
    async def test_get_written_events_returns_history(
        self, stub: WitnessedHaltWriterStub
    ) -> None:
        """Should track all successfully written events."""
        payload1 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Fork 1",
            triggering_event_ids=(uuid4(),),
            detecting_service_id="test",
        )
        payload2 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.SEQUENCE_GAP_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Gap",
            triggering_event_ids=(uuid4(),),
            detecting_service_id="test",
        )

        await stub.write_halt_event(payload1)
        await stub.write_halt_event(payload2)

        history = stub.get_written_events()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_failed_writes_not_in_history(
        self, stub: WitnessedHaltWriterStub
    ) -> None:
        """Failed writes should not appear in history."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test",
            triggering_event_ids=(uuid4(),),
            detecting_service_id="test",
        )

        stub.set_fail_next()
        await stub.write_halt_event(payload)

        history = stub.get_written_events()
        assert len(history) == 0


class TestWitnessedHaltWriterStubReset:
    """Tests for reset method."""

    @pytest.fixture
    def stub(self) -> WitnessedHaltWriterStub:
        return WitnessedHaltWriterStub()

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, stub: WitnessedHaltWriterStub) -> None:
        """Should clear all state on reset."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test",
            triggering_event_ids=(uuid4(),),
            detecting_service_id="test",
        )

        await stub.write_halt_event(payload)
        stub.set_fail_next()

        stub.reset()

        # History should be cleared
        assert len(stub.get_written_events()) == 0

        # Should no longer fail
        result = await stub.write_halt_event(payload)
        assert result is not None


class TestWitnessedHaltWriterStubEventFields:
    """Tests for generated event fields."""

    @pytest.fixture
    def stub(self) -> WitnessedHaltWriterStub:
        return WitnessedHaltWriterStub()

    @pytest.mark.asyncio
    async def test_event_has_witness_fields(
        self, stub: WitnessedHaltWriterStub
    ) -> None:
        """Written event should have witness_id and witness_signature (CT-12)."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test",
            triggering_event_ids=(uuid4(),),
            detecting_service_id="test",
        )

        event = await stub.write_halt_event(payload)

        assert event is not None
        assert event.witness_id is not None
        assert len(event.witness_id) > 0
        assert event.witness_signature is not None
        assert len(event.witness_signature) > 0

    @pytest.mark.asyncio
    async def test_event_has_sequence_number(
        self, stub: WitnessedHaltWriterStub
    ) -> None:
        """Written event should have sequence number assigned."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test",
            triggering_event_ids=(uuid4(),),
            detecting_service_id="test",
        )

        event = await stub.write_halt_event(payload)

        assert event is not None
        assert event.sequence is not None
        assert event.sequence > 0
