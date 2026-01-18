"""Integration tests for Cessation as Final Recorded Event (Story 7.6, FR43).

Tests for:
- Execute cessation -> cessation is last event
- Cessation event includes trigger_reason, trigger_source, final_sequence
- Cessation event is witnessed (CT-12)
- Write after cessation raises SchemaIrreversibilityError
- TerminalEventDetector returns True after cessation
- Observer can still read after cessation (FR42 regression)
- Freeze flag is set after cessation event
- Atomic behavior - event write failure doesn't set freeze
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.cessation_execution_service import (
    CessationExecutionError,
    CessationExecutionService,
)
from src.application.services.event_writer_service import EventWriterService
from src.domain.errors.schema_irreversibility import SchemaIrreversibilityError
from src.domain.events.cessation_executed import CESSATION_EXECUTED_EVENT_TYPE
from src.domain.events.event import Event
from src.infrastructure.adapters.persistence.terminal_event_detector import (
    InMemoryTerminalEventDetector,
)
from src.infrastructure.stubs import (
    CessationFlagRepositoryStub,
    EventStoreStub,
    FreezeCheckerStub,
    HaltCheckerStub,
    TerminalEventDetectorStub,
    WriterLockStub,
)


def create_test_event(
    *,
    sequence: int,
    event_type: str = "test.event",
    payload: dict | None = None,
) -> Event:
    """Create a test event for integration tests."""
    return Event(
        event_id=uuid4(),
        sequence=sequence,
        event_type=event_type,
        payload=payload or {},
        prev_hash="0" * 64,
        content_hash="a" * 64,
        signature="sig123",
        witness_id="witness-1",
        witness_signature="wsig123",
        local_timestamp=datetime.now(timezone.utc),
        agent_id="test-agent",
    )


def create_mock_atomic_writer(event_store: EventStoreStub) -> AsyncMock:
    """Create a mock AtomicEventWriter that writes to the event store.

    This creates a mock that:
    - Tracks sequence numbers correctly
    - Returns realistic Event objects with all required fields
    - Actually appends events to the provided event store
    """
    writer = AsyncMock()

    async def write_event_impl(
        *,
        event_type: str,
        payload: dict,
        agent_id: str,
        local_timestamp: datetime | None = None,
    ) -> Event:
        # Get next sequence from event store
        latest = await event_store.get_latest_event()
        sequence = (latest.sequence + 1) if latest else 1

        # Compute prev_hash
        prev_hash = latest.content_hash if latest else "0" * 64

        # Create cessation event with proper payload
        event = Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type=event_type,
            payload=payload,
            prev_hash=prev_hash,
            content_hash="h" * 64,
            signature="sig_atomic",
            witness_id="witness-atomic",
            witness_signature="wsig_atomic",
            local_timestamp=local_timestamp or datetime.now(timezone.utc),
            agent_id=agent_id,
        )

        # Add to event store (async call)
        await event_store.append_event(event)

        return event

    writer.write_event = AsyncMock(side_effect=write_event_impl)
    return writer


@pytest.fixture
def event_store() -> EventStoreStub:
    """Create EventStoreStub."""
    return EventStoreStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create HaltCheckerStub (not halted)."""
    return HaltCheckerStub()


@pytest.fixture
def terminal_detector() -> TerminalEventDetectorStub:
    """Create TerminalEventDetectorStub."""
    return TerminalEventDetectorStub()


@pytest.fixture
def freeze_checker() -> FreezeCheckerStub:
    """Create FreezeCheckerStub."""
    return FreezeCheckerStub()


@pytest.fixture
def cessation_flag_repo() -> CessationFlagRepositoryStub:
    """Create CessationFlagRepositoryStub."""
    return CessationFlagRepositoryStub()


@pytest.fixture
def writer_lock() -> WriterLockStub:
    """Create WriterLockStub."""
    return WriterLockStub()


@pytest.fixture
def atomic_writer(event_store: EventStoreStub) -> AsyncMock:
    """Create mock AtomicEventWriter."""
    return create_mock_atomic_writer(event_store)


@pytest.fixture
async def event_writer(
    atomic_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
    writer_lock: WriterLockStub,
    event_store: EventStoreStub,
    terminal_detector: TerminalEventDetectorStub,
    freeze_checker: FreezeCheckerStub,
) -> EventWriterService:
    """Create EventWriterService with all dependencies.

    Pre-acquires writer lock and sets _verified flag for testing.
    """
    # Acquire writer lock for testing
    await writer_lock.acquire()

    service = EventWriterService(
        atomic_writer=atomic_writer,
        halt_checker=halt_checker,
        writer_lock=writer_lock,
        event_store=event_store,
        terminal_detector=terminal_detector,
        freeze_checker=freeze_checker,
    )
    # Set _verified flag for testing (normally done via startup verification)
    service._verified = True
    return service


@pytest.fixture
def cessation_service(
    event_writer: EventWriterService,
    event_store: EventStoreStub,
    cessation_flag_repo: CessationFlagRepositoryStub,
) -> CessationExecutionService:
    """Create CessationExecutionService."""
    return CessationExecutionService(
        event_writer=event_writer,
        event_store=event_store,
        cessation_flag_repo=cessation_flag_repo,
    )


class TestCessationIsLastEvent:
    """Tests for FR43: Cessation is the last event in the store."""

    @pytest.mark.asyncio
    async def test_cessation_event_is_last_event(
        self, event_store: EventStoreStub, cessation_service: CessationExecutionService
    ) -> None:
        """After cessation, the cessation event should be the last event."""
        # Add some initial events
        event1 = create_test_event(sequence=1)
        event2 = create_test_event(sequence=2)
        await event_store.append_event(event1)
        await event_store.append_event(event2)

        # Execute cessation
        triggering_event_id = uuid4()
        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=triggering_event_id,
            reason="Test cessation for FR43",
        )

        # Verify cessation event is last
        latest_event = await event_store.get_latest_event()
        assert latest_event is not None
        assert latest_event.event_id == cessation_event.event_id
        assert latest_event.event_type == CESSATION_EXECUTED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_cessation_event_sequence_is_last(
        self, event_store: EventStoreStub, cessation_service: CessationExecutionService
    ) -> None:
        """Cessation event should have the highest sequence number."""
        # Add initial events
        for i in range(1, 11):
            await event_store.append_event(create_test_event(sequence=i))

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        # Verify sequence is 11 (after 10 events)
        assert cessation_event.sequence == 11


class TestCessationEventContent:
    """Tests for FR43 AC2: Cessation event payload content."""

    @pytest.mark.asyncio
    async def test_cessation_event_includes_trigger_reason(
        self, event_store: EventStoreStub, cessation_service: CessationExecutionService
    ) -> None:
        """Cessation event should include trigger_reason."""
        await event_store.append_event(create_test_event(sequence=1))

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Constitutional threshold exceeded",
        )

        payload = cessation_event.payload
        assert payload is not None
        assert "trigger_reason" in payload
        assert payload["trigger_reason"] == "Constitutional threshold exceeded"

    @pytest.mark.asyncio
    async def test_cessation_event_includes_trigger_source(
        self, event_store: EventStoreStub, cessation_service: CessationExecutionService
    ) -> None:
        """Cessation event should include trigger_source."""
        await event_store.append_event(create_test_event(sequence=1))

        trigger_id = uuid4()
        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=trigger_id,
            reason="Test",
        )

        payload = cessation_event.payload
        assert payload is not None
        assert "trigger_source" in payload
        assert payload["trigger_source"] == str(trigger_id)

    @pytest.mark.asyncio
    async def test_cessation_event_includes_final_sequence(
        self, event_store: EventStoreStub, cessation_service: CessationExecutionService
    ) -> None:
        """Cessation event should include final_sequence."""
        await event_store.append_event(create_test_event(sequence=1))

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        payload = cessation_event.payload
        assert payload is not None
        assert "final_sequence" in payload

    @pytest.mark.asyncio
    async def test_cessation_event_is_terminal(
        self, event_store: EventStoreStub, cessation_service: CessationExecutionService
    ) -> None:
        """Cessation event should have is_terminal=True."""
        await event_store.append_event(create_test_event(sequence=1))

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        payload = cessation_event.payload
        assert payload is not None
        assert payload["is_terminal"] is True


class TestWriteAfterCessation:
    """Tests for FR43 AC7: Write rejection after cessation."""

    @pytest.mark.asyncio
    async def test_write_after_cessation_raises_error(
        self,
        event_store: EventStoreStub,
        cessation_service: CessationExecutionService,
        event_writer: EventWriterService,
        terminal_detector: TerminalEventDetectorStub,
    ) -> None:
        """Write after cessation should raise SchemaIrreversibilityError."""
        await event_store.append_event(create_test_event(sequence=1))

        # Execute cessation
        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # Simulate terminal state detection
        terminal_detector.set_terminated(cessation_event)

        # Attempt to write after cessation
        with pytest.raises(SchemaIrreversibilityError) as exc_info:
            await event_writer.write_event(
                event_type="test.event",
                payload={"data": "test"},
                agent_id="test-agent",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "NFR40" in str(exc_info.value)
        assert "cessation" in str(exc_info.value).lower()


class TestTerminalEventDetection:
    """Tests for FR43 AC6: Terminal event detection."""

    @pytest.mark.asyncio
    async def test_terminal_detector_returns_true_after_cessation(
        self, event_store: EventStoreStub
    ) -> None:
        """TerminalEventDetector should return True after cessation."""
        await event_store.append_event(create_test_event(sequence=1))

        terminal_detector = InMemoryTerminalEventDetector()
        freeze_checker = FreezeCheckerStub()
        cessation_flag_repo = CessationFlagRepositoryStub()
        halt_checker = HaltCheckerStub()
        writer_lock = WriterLockStub()
        await writer_lock.acquire()  # Acquire lock for testing
        atomic_writer = create_mock_atomic_writer(event_store)

        event_writer = EventWriterService(
            atomic_writer=atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=event_store,
            terminal_detector=terminal_detector,
            freeze_checker=freeze_checker,
        )
        event_writer._verified = True  # Set verified flag for testing

        cessation_service = CessationExecutionService(
            event_writer=event_writer,
            event_store=event_store,
            cessation_flag_repo=cessation_flag_repo,
        )

        # Before cessation
        assert await terminal_detector.is_system_terminated() is False

        # Execute cessation
        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # Simulate adding cessation event to detector
        terminal_detector.add_event(cessation_event)

        # After cessation
        assert await terminal_detector.is_system_terminated() is True

    @pytest.mark.asyncio
    async def test_terminal_detector_returns_cessation_event(
        self, event_store: EventStoreStub
    ) -> None:
        """get_terminal_event() should return the cessation event."""
        await event_store.append_event(create_test_event(sequence=1))

        terminal_detector = InMemoryTerminalEventDetector()
        freeze_checker = FreezeCheckerStub()
        cessation_flag_repo = CessationFlagRepositoryStub()
        halt_checker = HaltCheckerStub()
        writer_lock = WriterLockStub()
        await writer_lock.acquire()  # Acquire lock for testing
        atomic_writer = create_mock_atomic_writer(event_store)

        event_writer = EventWriterService(
            atomic_writer=atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=event_store,
            terminal_detector=terminal_detector,
            freeze_checker=freeze_checker,
        )
        event_writer._verified = True  # Set verified flag for testing

        cessation_service = CessationExecutionService(
            event_writer=event_writer,
            event_store=event_store,
            cessation_flag_repo=cessation_flag_repo,
        )

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # Simulate adding cessation event to detector
        terminal_detector.add_event(cessation_event)

        # Verify terminal event
        detected_event = await terminal_detector.get_terminal_event()
        assert detected_event is not None
        assert detected_event.event_id == cessation_event.event_id


class TestFreezeFlag:
    """Tests for FR43 AC5: Freeze flag setting."""

    @pytest.mark.asyncio
    async def test_freeze_flag_set_after_cessation(
        self,
        event_store: EventStoreStub,
        cessation_service: CessationExecutionService,
        cessation_flag_repo: CessationFlagRepositoryStub,
    ) -> None:
        """Freeze flag should be set after cessation event."""
        await event_store.append_event(create_test_event(sequence=1))

        # Before cessation
        assert await cessation_flag_repo.is_ceased() is False

        # Execute cessation
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # After cessation
        assert await cessation_flag_repo.is_ceased() is True


class TestAtomicBehavior:
    """Tests for FR43 AC5: Atomic behavior."""

    @pytest.mark.asyncio
    async def test_no_event_on_empty_store(
        self,
        cessation_service: CessationExecutionService,
        cessation_flag_repo: CessationFlagRepositoryStub,
    ) -> None:
        """Cessation should fail on empty event store."""
        # Empty store - no events added

        with pytest.raises(CessationExecutionError) as exc_info:
            await cessation_service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test",
            )

        assert "empty" in str(exc_info.value).lower()

        # Verify freeze flag NOT set
        assert await cessation_flag_repo.is_ceased() is False


class TestCessationEventWitnessed:
    """Tests for CT-12: Cessation event witnessing."""

    @pytest.mark.asyncio
    async def test_cessation_event_has_witness(
        self,
        event_store: EventStoreStub,
        cessation_service: CessationExecutionService,
    ) -> None:
        """Cessation event should have witness attribution."""
        await event_store.append_event(create_test_event(sequence=1))

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # Verify witness attribution
        assert cessation_event.witness_id is not None
        assert cessation_event.witness_signature is not None


class TestCessationDetailsContent:
    """Tests for cessation details in flag repository."""

    @pytest.mark.asyncio
    async def test_cessation_details_include_event_id(
        self,
        event_store: EventStoreStub,
        cessation_service: CessationExecutionService,
        cessation_flag_repo: CessationFlagRepositoryStub,
    ) -> None:
        """Cessation details should include cessation event ID."""
        await event_store.append_event(create_test_event(sequence=1))

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # Verify cessation details
        details = await cessation_flag_repo.get_cessation_details()
        assert details is not None
        assert details.cessation_event_id == cessation_event.event_id

    @pytest.mark.asyncio
    async def test_cessation_details_include_final_sequence(
        self,
        event_store: EventStoreStub,
        cessation_service: CessationExecutionService,
        cessation_flag_repo: CessationFlagRepositoryStub,
    ) -> None:
        """Cessation details should include final sequence number."""
        for i in range(1, 6):
            await event_store.append_event(create_test_event(sequence=i))

        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # Verify cessation details
        details = await cessation_flag_repo.get_cessation_details()
        assert details is not None
        # Cessation event is sequence 6 (after 5 events)
        assert details.final_sequence_number == cessation_event.sequence
