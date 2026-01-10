"""Integration tests for EventWriterService (Story 1.6, AC1-5).

Tests the single canonical writer service with full infrastructure integration.

NOTE ON TEST STRATEGY:
    These tests use mock AtomicEventWriter and EventStorePort to isolate
    EventWriterService behavior. They test the service's orchestration logic
    (halt checks, lock verification, startup verification) without requiring
    actual database or Redis connections.

    For true end-to-end integration tests with real infrastructure, see
    tests that use real Supabase connections (when available).

Constitutional Constraints Tested:
- ADR-1: Single canonical writer, DB enforces chain integrity
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- GAP-CHAOS-001: Writer self-verification before accepting writes

Acceptance Criteria Tested:
- AC1: Writer Service Architecture (delegates to DB)
- AC2: Successful Event Submission (logs with event_id, sequence)
- AC3: Failed Event Submission (logs rejection, raises exception)
- AC4: Single-Writer Constraint (lock verification)
- AC5: Writer Self-Verification (head hash check on startup)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.event_writer_service import EventWriterService
from src.domain.errors.writer import (
    SystemHaltedError,
    WriterLockNotHeldError,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.writer_lock_stub import WriterLockStub


@pytest.fixture
def mock_atomic_writer() -> AsyncMock:
    """Create a mock AtomicEventWriter that simulates successful writes."""
    writer = AsyncMock()

    def create_mock_event(*args, **kwargs) -> MagicMock:
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.sequence = 1
        mock_event.content_hash = "c" * 64
        mock_event.event_type = kwargs.get("event_type", "test.event")
        mock_event.local_timestamp = kwargs.get("local_timestamp", datetime.now(timezone.utc))
        mock_event.authority_timestamp = datetime.now(timezone.utc)
        return mock_event

    writer.write_event = AsyncMock(side_effect=create_mock_event)
    return writer


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create a mock EventStorePort."""
    store = AsyncMock()
    store.get_latest_event = AsyncMock(return_value=None)
    store.append_event = AsyncMock()
    return store


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a HaltCheckerStub (not halted by default)."""
    return HaltCheckerStub()


@pytest.fixture
def writer_lock() -> WriterLockStub:
    """Create a WriterLockStub."""
    return WriterLockStub()


@pytest.fixture
def event_writer_service(
    mock_atomic_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
    writer_lock: WriterLockStub,
    mock_event_store: AsyncMock,
) -> EventWriterService:
    """Create an EventWriterService with mock/stub dependencies."""
    return EventWriterService(
        atomic_writer=mock_atomic_writer,
        halt_checker=halt_checker,
        writer_lock=writer_lock,
        event_store=mock_event_store,
    )


class TestSuccessfulEventSubmission:
    """Integration tests for successful event submission (AC2)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_successful_event_submission_returns_event_with_sequence(
        self,
        event_writer_service: EventWriterService,
        writer_lock: WriterLockStub,
    ) -> None:
        """Test that successful submission returns event with sequence (AC2)."""
        await writer_lock.acquire()
        await event_writer_service.verify_startup()

        event = await event_writer_service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event is not None
        assert event.sequence >= 1
        assert event.event_id is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_successful_event_submission_updates_head_hash(
        self,
        event_writer_service: EventWriterService,
        writer_lock: WriterLockStub,
    ) -> None:
        """Test that successful submission updates cached head hash."""
        await writer_lock.acquire()
        await event_writer_service.verify_startup()

        assert event_writer_service.last_known_head_hash is None

        event = await event_writer_service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event_writer_service.last_known_head_hash == event.content_hash

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_events_can_be_written_sequentially(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
        writer_lock: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that multiple events can be written in sequence."""
        sequence_counter = [0]

        def create_sequential_event(*args, **kwargs) -> MagicMock:
            sequence_counter[0] += 1
            mock_event = MagicMock()
            mock_event.event_id = uuid4()
            mock_event.sequence = sequence_counter[0]
            mock_event.content_hash = f"{sequence_counter[0]:064d}"
            mock_event.event_type = kwargs.get("event_type", "test.event")
            mock_event.local_timestamp = datetime.now(timezone.utc)
            mock_event.authority_timestamp = datetime.now(timezone.utc)
            return mock_event

        mock_atomic_writer.write_event = AsyncMock(side_effect=create_sequential_event)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=mock_event_store,
        )

        await writer_lock.acquire()
        await service.verify_startup()

        event1 = await service.write_event(
            event_type="test.event.1",
            payload={"count": 1},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        event2 = await service.write_event(
            event_type="test.event.2",
            payload={"count": 2},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event1.sequence == 1
        assert event2.sequence == 2


class TestFailedEventSubmission:
    """Integration tests for failed event submission (AC3)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_db_rejection_propagates_exception(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
        writer_lock: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that DB rejection raises appropriate exception (AC3)."""
        mock_atomic_writer.write_event = AsyncMock(
            side_effect=Exception("DB rejection: Invalid hash chain")
        )

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=mock_event_store,
        )

        await writer_lock.acquire()
        await service.verify_startup()

        with pytest.raises(Exception) as exc_info:
            await service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "DB rejection" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_failed_submission_does_not_update_head_hash(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
        writer_lock: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that failed submission leaves head hash unchanged (AC3)."""
        # First write succeeds
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.sequence = 1
        mock_event.content_hash = "d" * 64
        mock_event.local_timestamp = datetime.now(timezone.utc)
        mock_event.authority_timestamp = datetime.now(timezone.utc)

        call_count = [0]

        def write_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_event
            raise Exception("DB rejection")

        mock_atomic_writer.write_event = AsyncMock(side_effect=write_side_effect)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=mock_event_store,
        )

        await writer_lock.acquire()
        await service.verify_startup()

        # First write succeeds
        await service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        original_hash = service.last_known_head_hash

        # Second write fails
        with pytest.raises(Exception):
            await service.write_event(
                event_type="test.event",
                payload={"key": "value2"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        # Head hash should be unchanged
        assert service.last_known_head_hash == original_hash


class TestHaltCheckBehavior:
    """Integration tests for halt check behavior (CT-11)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_halt_check_blocks_writes(
        self,
        event_writer_service: EventWriterService,
        halt_checker: HaltCheckerStub,
        writer_lock: WriterLockStub,
    ) -> None:
        """Test that halt check blocks writes with SystemHaltedError."""
        await writer_lock.acquire()
        await event_writer_service.verify_startup()

        # Set system as halted
        halt_checker.set_halted(True, "Integrity breach detected")

        with pytest.raises(SystemHaltedError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_halt_can_be_cleared_and_writes_resume(
        self,
        event_writer_service: EventWriterService,
        halt_checker: HaltCheckerStub,
        writer_lock: WriterLockStub,
    ) -> None:
        """Test that writes resume after halt is cleared.

        CONSTITUTIONAL NOTE:
        This test uses HaltCheckerStub which allows programmatic halt clearing.
        In PRODUCTION, per ADR-3 and CT-11:
        - Halt is sticky (stays halted until ceremony)
        - 48-hour recovery waiting period required
        - Clearing halt requires witnessed ceremony, NOT automatic clearing

        This test validates the stub behavior for development, not production
        halt recovery semantics which will be tested in Epic 3.
        """
        await writer_lock.acquire()
        await event_writer_service.verify_startup()

        # Set and clear halt (STUB BEHAVIOR - not production semantics)
        halt_checker.set_halted(True, "Test halt")

        with pytest.raises(SystemHaltedError):
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        # Clear halt
        halt_checker.set_halted(False)

        # Write should succeed now
        event = await event_writer_service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event is not None


class TestStartupVerification:
    """Integration tests for startup verification (AC5, GAP-CHAOS-001)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_startup_verification_succeeds_on_empty_store(
        self,
        event_writer_service: EventWriterService,
        writer_lock: WriterLockStub,
    ) -> None:
        """Test that startup verification succeeds on empty store (AC5)."""
        await writer_lock.acquire()
        await event_writer_service.verify_startup()

        assert event_writer_service.is_verified is True
        assert event_writer_service.last_known_head_hash is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_startup_verification_loads_head_hash(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
        writer_lock: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that startup verification loads head hash from DB (AC5)."""
        # Set up existing event in store
        mock_event = MagicMock()
        mock_event.sequence = 42
        mock_event.content_hash = "e" * 64
        mock_event_store.get_latest_event = AsyncMock(return_value=mock_event)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=mock_event_store,
        )

        await writer_lock.acquire()
        await service.verify_startup()

        assert service.is_verified is True
        assert service.last_known_head_hash == "e" * 64


class TestSingleWriterLockBehavior:
    """Integration tests for single-writer lock behavior (ADR-1, AC4)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_write_fails_without_lock(
        self,
        event_writer_service: EventWriterService,
    ) -> None:
        """Test that writes fail without acquiring lock (ADR-1)."""
        # Force set verified without going through verify_startup
        event_writer_service._verified = True

        with pytest.raises(WriterLockNotHeldError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "ADR-1" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_write_fails_when_lock_lost(
        self,
        event_writer_service: EventWriterService,
        writer_lock: WriterLockStub,
    ) -> None:
        """Test that writes fail when lock is lost (ADR-1)."""
        await writer_lock.acquire()
        await event_writer_service.verify_startup()

        # Simulate lock loss
        writer_lock.set_lock_lost(True)

        with pytest.raises(WriterLockNotHeldError):
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )
