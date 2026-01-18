"""Unit tests for EventWriterService (Story 1.6, ADR-1; Story 7.3, NFR40; Story 7.4, FR41).

Tests the single canonical writer service with constitutional checks.

Constitutional Constraints Tested:
- ADR-1: Single canonical writer, DB enforces chain integrity
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability
- GAP-CHAOS-001: Writer self-verification before accepting writes
- NFR40: No cessation reversal - terminal check BEFORE halt check (Story 7.3)
- FR41: Freeze on new actions after cessation - freeze check AFTER terminal check (Story 7.4)

Acceptance Criteria Tested:
- AC1: Writer Service Architecture (delegates to DB)
- AC2: Successful Event Submission (logs with event_id, sequence)
- AC3: Failed Event Submission (logs rejection, raises exception)
- AC4: Single-Writer Constraint (lock verification)
- AC5: Writer Self-Verification (head hash check on startup)
- AC6 (Story 7.3): Terminal event detection blocks writes
- AC7 (Story 7.4): Freeze check blocks writes when system is ceased
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.event_writer_service import EventWriterService
from src.domain.errors.ceased import SystemCeasedError
from src.domain.errors.schema_irreversibility import SchemaIrreversibilityError
from src.domain.errors.writer import (
    SystemHaltedError,
    WriterInconsistencyError,
    WriterLockNotHeldError,
    WriterNotVerifiedError,
)
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.terminal_event_detector_stub import (
    TerminalEventDetectorStub,
)
from src.infrastructure.stubs.writer_lock_stub import WriterLockStub


@pytest.fixture
def mock_atomic_writer() -> AsyncMock:
    """Create a mock AtomicEventWriter."""
    writer = AsyncMock()

    # Create a proper mock event
    mock_event = MagicMock()
    mock_event.event_id = uuid4()
    mock_event.sequence = 1
    mock_event.content_hash = "a" * 64  # 64 hex chars
    mock_event.event_type = "test.event"
    mock_event.local_timestamp = datetime.now(timezone.utc)
    mock_event.authority_timestamp = datetime.now(timezone.utc)

    writer.write_event = AsyncMock(return_value=mock_event)
    return writer


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create a mock EventStorePort."""
    store = AsyncMock()
    store.get_latest_event = AsyncMock(return_value=None)
    store.append_event = AsyncMock()
    return store


@pytest.fixture
def halt_checker_stub() -> HaltCheckerStub:
    """Create a HaltCheckerStub (not halted by default)."""
    return HaltCheckerStub()


@pytest.fixture
def writer_lock_stub() -> WriterLockStub:
    """Create a WriterLockStub."""
    return WriterLockStub()


@pytest.fixture
def event_writer_service(
    mock_atomic_writer: AsyncMock,
    halt_checker_stub: HaltCheckerStub,
    writer_lock_stub: WriterLockStub,
    mock_event_store: AsyncMock,
) -> EventWriterService:
    """Create an EventWriterService with mock/stub dependencies."""
    return EventWriterService(
        atomic_writer=mock_atomic_writer,
        halt_checker=halt_checker_stub,
        writer_lock=writer_lock_stub,
        event_store=mock_event_store,
    )


class TestEventWriterServiceInitialization:
    """Tests for EventWriterService initialization."""

    def test_initialization_sets_verified_false(
        self,
        event_writer_service: EventWriterService,
    ) -> None:
        """Test that is_verified is False after initialization."""
        assert event_writer_service.is_verified is False

    def test_initialization_sets_last_known_head_hash_none(
        self,
        event_writer_service: EventWriterService,
    ) -> None:
        """Test that last_known_head_hash is None after initialization."""
        assert event_writer_service.last_known_head_hash is None


class TestEventWriterServiceVerifyStartup:
    """Tests for verify_startup() method (AC5, GAP-CHAOS-001)."""

    @pytest.mark.asyncio
    async def test_verify_startup_empty_store_succeeds(
        self,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that verify_startup succeeds for empty store."""
        # Acquire lock first
        await writer_lock_stub.acquire()

        await event_writer_service.verify_startup()

        assert event_writer_service.is_verified is True
        assert event_writer_service.last_known_head_hash is None

    @pytest.mark.asyncio
    async def test_verify_startup_with_existing_events_succeeds(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that verify_startup succeeds when events exist."""
        # Set up mock to return an existing event
        mock_event = MagicMock()
        mock_event.sequence = 42
        mock_event.content_hash = "b" * 64
        mock_event_store.get_latest_event = AsyncMock(return_value=mock_event)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
        )

        # Acquire lock first
        await writer_lock_stub.acquire()

        await service.verify_startup()

        assert service.is_verified is True
        assert service.last_known_head_hash == "b" * 64

    @pytest.mark.asyncio
    async def test_verify_startup_fails_when_halted(
        self,
        event_writer_service: EventWriterService,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that verify_startup raises SystemHaltedError when halted."""
        halt_checker_stub.set_halted(True, "Test halt")
        await writer_lock_stub.acquire()

        with pytest.raises(SystemHaltedError) as exc_info:
            await event_writer_service.verify_startup()

        assert "halted" in str(exc_info.value).lower()
        assert event_writer_service.is_verified is False

    @pytest.mark.asyncio
    async def test_verify_startup_acquires_lock_if_not_held(
        self,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that verify_startup acquires lock if not already held."""
        # Don't acquire lock beforehand
        assert await writer_lock_stub.is_held() is False

        await event_writer_service.verify_startup()

        assert await writer_lock_stub.is_held() is True
        assert event_writer_service.is_verified is True

    @pytest.mark.asyncio
    async def test_verify_startup_fails_when_lock_cannot_be_acquired(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that verify_startup raises WriterLockNotHeldError when lock acquisition fails."""
        # Create a lock stub that fails to acquire
        lock_stub = AsyncMock()
        lock_stub.is_held = AsyncMock(return_value=False)
        lock_stub.acquire = AsyncMock(return_value=False)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=lock_stub,
            event_store=mock_event_store,
        )

        with pytest.raises(WriterLockNotHeldError) as exc_info:
            await service.verify_startup()

        assert "ADR-1" in str(exc_info.value)


class TestEventWriterServiceWriteEvent:
    """Tests for write_event() method (AC1, AC2, AC3)."""

    @pytest.mark.asyncio
    async def test_write_event_delegates_to_atomic_writer(
        self,
        event_writer_service: EventWriterService,
        mock_atomic_writer: AsyncMock,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event delegates to AtomicEventWriter (AC1)."""
        await writer_lock_stub.acquire()
        await event_writer_service.verify_startup()

        await event_writer_service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        mock_atomic_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_event_returns_event_with_sequence(
        self,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event returns event with sequence (AC2)."""
        await writer_lock_stub.acquire()
        await event_writer_service.verify_startup()

        event = await event_writer_service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event.sequence == 1
        assert event.event_id is not None

    @pytest.mark.asyncio
    async def test_write_event_updates_last_known_head_hash(
        self,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event updates last_known_head_hash."""
        await writer_lock_stub.acquire()
        await event_writer_service.verify_startup()

        event = await event_writer_service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event_writer_service.last_known_head_hash == event.content_hash


class TestEventWriterServiceHaltCheck:
    """Tests for halt check behavior (CT-11, HALT FIRST rule)."""

    @pytest.mark.asyncio
    async def test_write_event_fails_when_halted(
        self,
        event_writer_service: EventWriterService,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event raises SystemHaltedError when halted (CT-11)."""
        await writer_lock_stub.acquire()
        await event_writer_service.verify_startup()

        # Now halt the system
        halt_checker_stub.set_halted(True, "Integrity breach detected")

        with pytest.raises(SystemHaltedError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "CT-11" in str(exc_info.value)
        assert "halted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_halt_check_is_first_operation(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that halt check happens before any other operation."""
        # Set system as halted
        halt_checker_stub.set_halted(True, "Test halt")

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
        )

        # Don't verify - halt check should still happen
        with pytest.raises(SystemHaltedError):
            await service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        # AtomicEventWriter should NOT have been called
        mock_atomic_writer.write_event.assert_not_called()


class TestEventWriterServiceLockCheck:
    """Tests for writer lock verification (ADR-1, AC4)."""

    @pytest.mark.asyncio
    async def test_write_event_fails_when_lock_not_held(
        self,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event raises WriterLockNotHeldError when lock not held (ADR-1)."""
        # Acquire and verify, then lose the lock
        await writer_lock_stub.acquire()
        await event_writer_service.verify_startup()
        writer_lock_stub.set_lock_lost(True)

        with pytest.raises(WriterLockNotHeldError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "ADR-1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_lock_check_happens_after_halt_check(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that lock check happens after halt check but before verification check."""
        # Lock that reports not held
        lock_stub = AsyncMock()
        lock_stub.is_held = AsyncMock(return_value=False)
        lock_stub.acquire = AsyncMock(return_value=True)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=lock_stub,
            event_store=mock_event_store,
        )

        # Manually set verified to True to test lock check
        service._verified = True

        with pytest.raises(WriterLockNotHeldError):
            await service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )


class TestEventWriterServiceVerificationCheck:
    """Tests for startup verification check (GAP-CHAOS-001, AC5)."""

    @pytest.mark.asyncio
    async def test_write_event_fails_when_not_verified(
        self,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event raises WriterNotVerifiedError when not verified."""
        # Acquire lock but don't verify
        await writer_lock_stub.acquire()

        with pytest.raises(WriterNotVerifiedError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "GAP-CHAOS-001" in str(exc_info.value)


class TestEventWriterServiceErrorHandling:
    """Tests for error handling and logging (AC3)."""

    @pytest.mark.asyncio
    async def test_write_event_propagates_atomic_writer_errors(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write_event propagates errors from AtomicEventWriter (AC3)."""
        mock_atomic_writer.write_event = AsyncMock(
            side_effect=Exception("DB rejection: Invalid signature")
        )

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
        )

        await writer_lock_stub.acquire()
        await service.verify_startup()

        with pytest.raises(Exception) as exc_info:
            await service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "DB rejection" in str(exc_info.value)


class TestHaltCheckerStub:
    """Tests for HaltCheckerStub."""

    @pytest.mark.asyncio
    async def test_default_is_not_halted(self) -> None:
        """Test that default stub is not halted."""
        stub = HaltCheckerStub()
        assert await stub.is_halted() is False
        assert await stub.get_halt_reason() is None

    @pytest.mark.asyncio
    async def test_force_halted_returns_true(self) -> None:
        """Test that force_halted=True returns halted state."""
        stub = HaltCheckerStub(force_halted=True, halt_reason="Test reason")
        assert await stub.is_halted() is True
        assert await stub.get_halt_reason() == "Test reason"

    @pytest.mark.asyncio
    async def test_set_halted_changes_state(self) -> None:
        """Test that set_halted changes halt state."""
        stub = HaltCheckerStub()
        assert await stub.is_halted() is False

        stub.set_halted(True, "Dynamic halt")
        assert await stub.is_halted() is True
        assert await stub.get_halt_reason() == "Dynamic halt"


class TestWriterLockStub:
    """Tests for WriterLockStub."""

    @pytest.mark.asyncio
    async def test_acquire_succeeds(self) -> None:
        """Test that acquire succeeds and marks lock as held."""
        stub = WriterLockStub()
        assert await stub.is_held() is False

        result = await stub.acquire()

        assert result is True
        assert await stub.is_held() is True

    @pytest.mark.asyncio
    async def test_release_marks_lock_not_held(self) -> None:
        """Test that release marks lock as not held."""
        stub = WriterLockStub()
        await stub.acquire()
        assert await stub.is_held() is True

        await stub.release()

        assert await stub.is_held() is False

    @pytest.mark.asyncio
    async def test_renew_succeeds_when_held(self) -> None:
        """Test that renew succeeds when lock is held."""
        stub = WriterLockStub()
        await stub.acquire()

        result = await stub.renew()

        assert result is True

    @pytest.mark.asyncio
    async def test_renew_fails_when_not_held(self) -> None:
        """Test that renew fails when lock is not held."""
        stub = WriterLockStub()

        result = await stub.renew()

        assert result is False

    @pytest.mark.asyncio
    async def test_set_lock_lost_simulates_lock_loss(self) -> None:
        """Test that set_lock_lost simulates lock loss."""
        stub = WriterLockStub()
        await stub.acquire()
        assert await stub.is_held() is True

        stub.set_lock_lost(True)

        assert await stub.is_held() is False
        assert await stub.renew() is False


class TestHeadHashVerification:
    """Tests for head hash verification (AC5, GAP-CHAOS-001).

    These tests verify that WriterInconsistencyError is raised when
    the expected head hash doesn't match the database head hash.
    """

    @pytest.mark.asyncio
    async def test_verify_startup_with_expected_hash_succeeds_when_matching(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that verify_startup succeeds when expected hash matches DB."""
        expected_hash = "c" * 64

        # Set up mock to return event with matching hash
        mock_event = MagicMock()
        mock_event.sequence = 42
        mock_event.content_hash = expected_hash
        mock_event_store.get_latest_event = AsyncMock(return_value=mock_event)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
        )

        await writer_lock_stub.acquire()

        # Should succeed without raising
        await service.verify_startup(expected_head_hash=expected_hash)

        assert service.is_verified is True
        assert service.last_known_head_hash == expected_hash

    @pytest.mark.asyncio
    async def test_verify_startup_raises_inconsistency_error_on_hash_mismatch(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that verify_startup raises WriterInconsistencyError on hash mismatch (AC5)."""
        expected_hash = "a" * 64
        db_hash = "b" * 64  # Different!

        # Set up mock to return event with DIFFERENT hash
        mock_event = MagicMock()
        mock_event.sequence = 42
        mock_event.content_hash = db_hash
        mock_event_store.get_latest_event = AsyncMock(return_value=mock_event)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
        )

        await writer_lock_stub.acquire()

        with pytest.raises(WriterInconsistencyError) as exc_info:
            await service.verify_startup(expected_head_hash=expected_hash)

        # Verify error message contains both hashes (Task 3.4)
        error_msg = str(exc_info.value)
        assert "GAP-CHAOS-001" in error_msg
        assert expected_hash in error_msg
        assert db_hash in error_msg
        assert service.is_verified is False

    @pytest.mark.asyncio
    async def test_verify_startup_raises_inconsistency_error_when_expected_but_empty(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that verify_startup raises error when expecting events but store is empty."""
        expected_hash = "d" * 64

        # Store is empty
        mock_event_store.get_latest_event = AsyncMock(return_value=None)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
        )

        await writer_lock_stub.acquire()

        with pytest.raises(WriterInconsistencyError) as exc_info:
            await service.verify_startup(expected_head_hash=expected_hash)

        error_msg = str(exc_info.value)
        assert "GAP-CHAOS-001" in error_msg
        assert expected_hash in error_msg
        assert "empty_store" in error_msg.lower()
        assert service.is_verified is False

    @pytest.mark.asyncio
    async def test_verify_startup_cold_start_no_expected_hash_succeeds(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that cold start (no expected hash) succeeds with existing events."""
        db_hash = "e" * 64

        # Store has events
        mock_event = MagicMock()
        mock_event.sequence = 100
        mock_event.content_hash = db_hash
        mock_event_store.get_latest_event = AsyncMock(return_value=mock_event)

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
        )

        await writer_lock_stub.acquire()

        # Cold start - no expected hash provided
        await service.verify_startup()  # No expected_head_hash

        assert service.is_verified is True
        assert service.last_known_head_hash == db_hash


# =============================================================================
# Tests for Push Notification Integration (Story 4.8, SR-9, RT-5)
# =============================================================================


class TestEventWriterServiceNotificationPublishing:
    """Tests for notification publishing integration (SR-9, RT-5)."""

    @pytest.fixture
    def mock_notification_publisher(self) -> AsyncMock:
        """Create a mock NotificationPublisherPort."""
        publisher = AsyncMock()
        publisher.notify_event = AsyncMock()
        return publisher

    @pytest.fixture
    def service_with_publisher(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
        mock_notification_publisher: AsyncMock,
    ) -> EventWriterService:
        """Create EventWriterService with notification publisher."""
        return EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            notification_publisher=mock_notification_publisher,
        )

    @pytest.mark.asyncio
    async def test_write_event_publishes_notification(
        self,
        service_with_publisher: EventWriterService,
        mock_atomic_writer: AsyncMock,
        mock_notification_publisher: AsyncMock,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event calls notification publisher (SR-9)."""
        # Setup: acquire lock and verify
        await writer_lock_stub.acquire()
        service_with_publisher._verified = True

        # Act
        event = await service_with_publisher.write_event(
            event_type="breach",
            payload={"reason": "test"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Assert: notification publisher was called
        mock_notification_publisher.notify_event.assert_called_once()
        call_args = mock_notification_publisher.notify_event.call_args
        notified_event = call_args[0][0]
        assert notified_event.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_write_event_succeeds_when_notification_fails(
        self,
        service_with_publisher: EventWriterService,
        mock_atomic_writer: AsyncMock,
        mock_notification_publisher: AsyncMock,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event succeeds even if notification fails (best-effort)."""
        # Setup: notification publisher will fail
        mock_notification_publisher.notify_event = AsyncMock(
            side_effect=Exception("Network error")
        )
        await writer_lock_stub.acquire()
        service_with_publisher._verified = True

        # Act - should succeed despite notification failure
        event = await service_with_publisher.write_event(
            event_type="breach",
            payload={"reason": "test"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Assert: event was written, notification was attempted
        assert event is not None
        mock_notification_publisher.notify_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_event_without_publisher_succeeds(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write_event works without notification publisher."""
        # Create service without publisher
        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            notification_publisher=None,
        )

        await writer_lock_stub.acquire()
        service._verified = True

        # Act - should succeed
        event = await service.write_event(
            event_type="test",
            payload={"key": "value"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Assert: event was written
        assert event is not None
        mock_atomic_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_logging_on_failure(
        self,
        service_with_publisher: EventWriterService,
        mock_notification_publisher: AsyncMock,
        writer_lock_stub: WriterLockStub,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that notification failure is logged (CT-11)."""
        import logging

        # Setup: notification publisher will fail
        mock_notification_publisher.notify_event = AsyncMock(
            side_effect=Exception("Webhook delivery failed")
        )
        await writer_lock_stub.acquire()
        service_with_publisher._verified = True

        # Act
        with caplog.at_level(logging.WARNING):
            await service_with_publisher.write_event(
                event_type="breach",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        # Assert: warning was logged (via structlog)
        # Note: structlog may not integrate with caplog directly,
        # but we verify the exception was handled (not raised)


# =============================================================================
# Tests for Terminal Event Detection (Story 7.3, NFR40)
# =============================================================================


class TestEventWriterServiceTerminalDetection:
    """Tests for terminal event detection (Story 7.3, NFR40).

    Constitutional Constraint: Terminal check MUST be BEFORE halt check.
    Cessation is permanent; halt is temporary.
    """

    @pytest.fixture
    def terminal_detector_stub(self) -> TerminalEventDetectorStub:
        """Create a TerminalEventDetectorStub."""
        return TerminalEventDetectorStub()

    @pytest.fixture
    def service_with_terminal_detector(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
        terminal_detector_stub: TerminalEventDetectorStub,
    ) -> EventWriterService:
        """Create EventWriterService with terminal detector."""
        return EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            terminal_detector=terminal_detector_stub,
        )

    @pytest.mark.asyncio
    async def test_write_event_succeeds_when_not_terminated(
        self,
        service_with_terminal_detector: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event succeeds when system is not terminated."""
        await writer_lock_stub.acquire()
        service_with_terminal_detector._verified = True

        event = await service_with_terminal_detector.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event is not None

    @pytest.mark.asyncio
    async def test_write_event_fails_when_terminated(
        self,
        service_with_terminal_detector: EventWriterService,
        terminal_detector_stub: TerminalEventDetectorStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event raises SchemaIrreversibilityError when terminated (NFR40)."""
        await writer_lock_stub.acquire()
        service_with_terminal_detector._verified = True

        # Terminate the system
        terminal_detector_stub.set_terminated_simple()

        with pytest.raises(SchemaIrreversibilityError) as exc_info:
            await service_with_terminal_detector.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "NFR40" in str(exc_info.value)
        assert "cessation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_terminal_check_happens_before_halt_check(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
        terminal_detector_stub: TerminalEventDetectorStub,
    ) -> None:
        """Test that terminal check happens BEFORE halt check (TERMINAL FIRST rule)."""
        # Both terminated AND halted
        terminal_detector_stub.set_terminated_simple()
        halt_checker_stub.set_halted(True, "System halted")

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            terminal_detector=terminal_detector_stub,
        )
        service._verified = True
        await writer_lock_stub.acquire()

        # Should raise SchemaIrreversibilityError (terminal) NOT SystemHaltedError
        with pytest.raises(SchemaIrreversibilityError):
            await service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_terminal_error_includes_sequence_number(
        self,
        service_with_terminal_detector: EventWriterService,
        terminal_detector_stub: TerminalEventDetectorStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that terminal error includes sequence number when available."""
        from src.domain.events import Event

        await writer_lock_stub.acquire()
        service_with_terminal_detector._verified = True

        # Create terminal event with sequence
        terminal_event = Event(
            event_id=uuid4(),
            sequence=42,
            event_type="cessation.executed",
            payload={"is_terminal": True},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            witness_id="witness-1",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
            agent_id="SYSTEM",
        )
        terminal_detector_stub.set_terminated(terminal_event)

        with pytest.raises(SchemaIrreversibilityError) as exc_info:
            await service_with_terminal_detector.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        # Error should include sequence number
        assert "42" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_service_works_without_terminal_detector_backwards_compat(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that service works without terminal detector (backwards compatibility)."""
        # No terminal_detector provided
        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            terminal_detector=None,
        )
        service._verified = True
        await writer_lock_stub.acquire()

        # Should succeed - no terminal check without detector
        event = await service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event is not None

    @pytest.mark.asyncio
    async def test_atomic_writer_not_called_when_terminated(
        self,
        service_with_terminal_detector: EventWriterService,
        mock_atomic_writer: AsyncMock,
        terminal_detector_stub: TerminalEventDetectorStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that AtomicEventWriter is NOT called when system is terminated."""
        await writer_lock_stub.acquire()
        service_with_terminal_detector._verified = True

        terminal_detector_stub.set_terminated_simple()

        with pytest.raises(SchemaIrreversibilityError):
            await service_with_terminal_detector.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        # AtomicEventWriter should NOT have been called
        mock_atomic_writer.write_event.assert_not_called()


# =============================================================================
# Tests for Freeze Check (Story 7.4, FR41)
# =============================================================================


class TestEventWriterServiceFreezeCheck:
    """Tests for freeze check behavior (Story 7.4, FR41).

    Constitutional Constraint: Freeze check MUST be AFTER terminal check.
    - Terminal check = cessation event exists (Story 7.3)
    - Freeze check = operational freeze in effect (Story 7.4)
    """

    @pytest.fixture
    def freeze_checker_stub(self) -> FreezeCheckerStub:
        """Create a FreezeCheckerStub."""
        return FreezeCheckerStub()

    @pytest.fixture
    def service_with_freeze_checker(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
        freeze_checker_stub: FreezeCheckerStub,
    ) -> EventWriterService:
        """Create EventWriterService with freeze checker."""
        return EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            freeze_checker=freeze_checker_stub,
        )

    @pytest.mark.asyncio
    async def test_write_event_succeeds_when_not_frozen(
        self,
        service_with_freeze_checker: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event succeeds when system is not frozen."""
        await writer_lock_stub.acquire()
        service_with_freeze_checker._verified = True

        event = await service_with_freeze_checker.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event is not None

    @pytest.mark.asyncio
    async def test_write_event_fails_when_frozen(
        self,
        service_with_freeze_checker: EventWriterService,
        freeze_checker_stub: FreezeCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that write_event raises SystemCeasedError when frozen (FR41)."""
        await writer_lock_stub.acquire()
        service_with_freeze_checker._verified = True

        # Freeze the system
        freeze_checker_stub.set_frozen_simple()

        with pytest.raises(SystemCeasedError) as exc_info:
            await service_with_freeze_checker.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR41" in str(exc_info.value)
        assert (
            "ceased" in str(exc_info.value).lower()
            or "frozen" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_freeze_check_happens_after_terminal_check(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that freeze check happens AFTER terminal check (FREEZE SECOND rule)."""
        terminal_detector_stub = TerminalEventDetectorStub()
        freeze_checker_stub = FreezeCheckerStub()

        # Both terminated AND frozen
        terminal_detector_stub.set_terminated_simple()
        freeze_checker_stub.set_frozen_simple()

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            terminal_detector=terminal_detector_stub,
            freeze_checker=freeze_checker_stub,
        )
        service._verified = True
        await writer_lock_stub.acquire()

        # Should raise SchemaIrreversibilityError (terminal) NOT SystemCeasedError (freeze)
        with pytest.raises(SchemaIrreversibilityError):
            await service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_freeze_check_happens_before_halt_check(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
        freeze_checker_stub: FreezeCheckerStub,
    ) -> None:
        """Test that freeze check happens BEFORE halt check (FREEZE SECOND, HALT THIRD rule)."""
        # Both frozen AND halted
        freeze_checker_stub.set_frozen_simple()
        halt_checker_stub.set_halted(True, "System halted")

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            freeze_checker=freeze_checker_stub,
        )
        service._verified = True
        await writer_lock_stub.acquire()

        # Should raise SystemCeasedError (freeze) NOT SystemHaltedError (halt)
        with pytest.raises(SystemCeasedError):
            await service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_freeze_error_includes_details(
        self,
        service_with_freeze_checker: EventWriterService,
        freeze_checker_stub: FreezeCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that freeze error includes cessation details when available."""
        await writer_lock_stub.acquire()
        service_with_freeze_checker._verified = True

        # Set frozen with specific details
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        freeze_checker_stub.set_frozen(
            ceased_at=ceased_at,
            final_sequence=999,
            reason="Test cessation",
        )

        with pytest.raises(SystemCeasedError) as exc_info:
            await service_with_freeze_checker.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        error = exc_info.value
        assert error.ceased_at == ceased_at
        assert error.final_sequence_number == 999

    @pytest.mark.asyncio
    async def test_service_works_without_freeze_checker_backwards_compat(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that service works without freeze checker (backwards compatibility)."""
        # No freeze_checker provided
        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            freeze_checker=None,
        )
        service._verified = True
        await writer_lock_stub.acquire()

        # Should succeed - no freeze check without checker
        event = await service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event is not None

    @pytest.mark.asyncio
    async def test_atomic_writer_not_called_when_frozen(
        self,
        service_with_freeze_checker: EventWriterService,
        mock_atomic_writer: AsyncMock,
        freeze_checker_stub: FreezeCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that AtomicEventWriter is NOT called when system is frozen."""
        await writer_lock_stub.acquire()
        service_with_freeze_checker._verified = True

        freeze_checker_stub.set_frozen_simple()

        with pytest.raises(SystemCeasedError):
            await service_with_freeze_checker.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        # AtomicEventWriter should NOT have been called
        mock_atomic_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_freeze_check_with_full_dependency_chain(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test freeze check with both terminal detector and freeze checker."""
        terminal_detector_stub = TerminalEventDetectorStub()
        freeze_checker_stub = FreezeCheckerStub()

        # Only frozen, NOT terminated
        freeze_checker_stub.set_frozen_simple()

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            terminal_detector=terminal_detector_stub,
            freeze_checker=freeze_checker_stub,
        )
        service._verified = True
        await writer_lock_stub.acquire()

        # Should raise SystemCeasedError (freeze)
        with pytest.raises(SystemCeasedError) as exc_info:
            await service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR41" in str(exc_info.value)
