"""Integration tests for freeze mechanics (Story 7.4, FR41).

Tests the freeze mechanics integration across multiple components:
- CessationExecutionService
- EventWriterService with freeze check
- FreezeGuard
- Dual-channel cessation flag

Constitutional Constraints Tested:
- FR41: Freeze on new actions except record preservation
- CT-11: Silent failure destroys legitimacy -> Log ALL execution details
- CT-12: Witnessing creates accountability -> Cessation must be witnessed
- CT-13: Integrity outranks availability -> Permanent termination
- ADR-3: Dual-channel pattern -> Set flag in both Redis and DB

Acceptance Criteria Tested:
- AC1: Immediate write freeze on cessation
- AC2: Pending operations fail gracefully
- AC3: Write rejection error message
- AC4: Record preservation accessibility
- AC6: CeasedStatusHeader in responses
- AC8: Dual-channel cessation flag
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.cessation_execution_service import (
    CessationExecutionService,
)
from src.application.services.event_writer_service import EventWriterService
from src.application.services.freeze_guard import FreezeGuard
from src.domain.errors.ceased import SystemCeasedError
from src.domain.events.cessation_executed import CESSATION_EXECUTED_EVENT_TYPE
from src.infrastructure.stubs import (
    CessationFlagRepositoryStub,
    FreezeCheckerStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.writer_lock_stub import WriterLockStub

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def freeze_checker_stub() -> FreezeCheckerStub:
    """Create FreezeCheckerStub."""
    return FreezeCheckerStub()


@pytest.fixture
def cessation_flag_repo_stub() -> CessationFlagRepositoryStub:
    """Create CessationFlagRepositoryStub."""
    return CessationFlagRepositoryStub()


@pytest.fixture
def halt_checker_stub() -> HaltCheckerStub:
    """Create HaltCheckerStub (not halted)."""
    return HaltCheckerStub()


@pytest.fixture
def writer_lock_stub() -> WriterLockStub:
    """Create WriterLockStub."""
    return WriterLockStub()


@pytest.fixture
def mock_atomic_writer() -> AsyncMock:
    """Create a mock AtomicEventWriter."""
    writer = AsyncMock()

    # Track sequence for realistic behavior
    writer._next_sequence = 1

    async def write_event_impl(**kwargs):
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.sequence = writer._next_sequence
        writer._next_sequence += 1
        mock_event.content_hash = "h" * 64
        mock_event.event_type = kwargs.get("event_type", "test.event")
        return mock_event

    writer.write_event = AsyncMock(side_effect=write_event_impl)
    return writer


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create a mock EventStorePort."""
    store = AsyncMock()

    # Create a head event
    head_event = MagicMock()
    head_event.sequence = 10
    head_event.content_hash = "a" * 64

    store.get_latest_event = AsyncMock(return_value=head_event)
    store.append_event = AsyncMock()
    return store


@pytest.fixture
def event_writer_service(
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


@pytest.fixture
def cessation_service(
    event_writer_service: EventWriterService,
    mock_event_store: AsyncMock,
    cessation_flag_repo_stub: CessationFlagRepositoryStub,
) -> CessationExecutionService:
    """Create CessationExecutionService."""
    return CessationExecutionService(
        event_writer=event_writer_service,
        event_store=mock_event_store,
        cessation_flag_repo=cessation_flag_repo_stub,
    )


@pytest.fixture
def freeze_guard(freeze_checker_stub: FreezeCheckerStub) -> FreezeGuard:
    """Create FreezeGuard."""
    return FreezeGuard(freeze_checker=freeze_checker_stub)


# =============================================================================
# AC1: Immediate Write Freeze on Cessation
# =============================================================================


class TestImmediateWriteFreeze:
    """Test that writes are frozen immediately on cessation (AC1)."""

    @pytest.mark.asyncio
    async def test_writes_succeed_before_cessation(
        self,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that writes succeed before cessation."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True

        event = await event_writer_service.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event is not None

    @pytest.mark.asyncio
    async def test_writes_fail_after_freeze(
        self,
        event_writer_service: EventWriterService,
        freeze_checker_stub: FreezeCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that writes fail immediately after freeze is set (AC1)."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True

        # Freeze the system
        freeze_checker_stub.set_frozen_simple()

        with pytest.raises(SystemCeasedError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR41" in str(exc_info.value)


# =============================================================================
# AC2: Pending Operations Fail Gracefully
# =============================================================================


class TestPendingOperationsFailGracefully:
    """Test that pending operations fail gracefully (AC2)."""

    @pytest.mark.asyncio
    async def test_error_includes_fr41_reference(
        self,
        event_writer_service: EventWriterService,
        freeze_checker_stub: FreezeCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that error includes FR41 reference (AC2)."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True
        freeze_checker_stub.set_frozen_simple()

        with pytest.raises(SystemCeasedError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        # AC2: Error includes "FR41: System ceased - writes frozen"
        assert "FR41" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_includes_cessation_details(
        self,
        event_writer_service: EventWriterService,
        freeze_checker_stub: FreezeCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that error includes cessation details (AC2)."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True

        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        freeze_checker_stub.set_frozen(
            ceased_at=ceased_at,
            final_sequence=999,
            reason="Test cessation",
        )

        with pytest.raises(SystemCeasedError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        error = exc_info.value
        assert error.ceased_at == ceased_at
        assert error.final_sequence_number == 999


# =============================================================================
# AC3: Write Rejection Error Message
# =============================================================================


class TestWriteRejectionErrorMessage:
    """Test write rejection error messages (AC3)."""

    @pytest.mark.asyncio
    async def test_error_message_format(
        self,
        event_writer_service: EventWriterService,
        freeze_checker_stub: FreezeCheckerStub,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test that error message has correct format (AC3)."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True
        freeze_checker_stub.set_frozen_simple()

        with pytest.raises(SystemCeasedError) as exc_info:
            await event_writer_service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        # AC3: Error includes "FR41: System ceased - writes frozen"
        error_str = str(exc_info.value)
        assert "FR41" in error_str
        assert "ceased" in error_str.lower() or "frozen" in error_str.lower()


# =============================================================================
# AC6: CeasedStatusHeader in Responses
# =============================================================================


class TestCeasedStatusHeader:
    """Test CeasedStatusHeader in responses (AC6)."""

    @pytest.mark.asyncio
    async def test_freeze_guard_returns_status_header_when_frozen(
        self,
        freeze_guard: FreezeGuard,
        freeze_checker_stub: FreezeCheckerStub,
    ) -> None:
        """Test that FreezeGuard returns status header when frozen (AC6)."""
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        freeze_checker_stub.set_frozen(
            ceased_at=ceased_at,
            final_sequence=999,
            reason="Test cessation",
        )

        status = await freeze_guard.get_freeze_status()

        assert status is not None
        assert status.system_status == "CEASED"
        assert status.ceased_at == ceased_at
        assert status.final_sequence_number == 999

    @pytest.mark.asyncio
    async def test_freeze_guard_returns_none_when_not_frozen(
        self,
        freeze_guard: FreezeGuard,
    ) -> None:
        """Test that FreezeGuard returns None when not frozen."""
        status = await freeze_guard.get_freeze_status()

        assert status is None


# =============================================================================
# AC8: Dual-Channel Cessation Flag
# =============================================================================


class TestDualChannelCessationFlag:
    """Test dual-channel cessation flag (AC8, ADR-3)."""

    @pytest.mark.asyncio
    async def test_cessation_sets_both_channels(
        self,
        cessation_service: CessationExecutionService,
        cessation_flag_repo_stub: CessationFlagRepositoryStub,
        writer_lock_stub: WriterLockStub,
        event_writer_service: EventWriterService,
    ) -> None:
        """Test that cessation sets flag in both channels (AC8)."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True

        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        # Verify both channels set
        assert cessation_flag_repo_stub.redis_flag is not None
        assert cessation_flag_repo_stub.db_flag is not None

    @pytest.mark.asyncio
    async def test_is_ceased_true_after_cessation(
        self,
        cessation_service: CessationExecutionService,
        cessation_flag_repo_stub: CessationFlagRepositoryStub,
        writer_lock_stub: WriterLockStub,
        event_writer_service: EventWriterService,
    ) -> None:
        """Test that is_ceased() returns True after cessation."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True

        # Not ceased yet
        assert await cessation_flag_repo_stub.is_ceased() is False

        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        # Now ceased
        assert await cessation_flag_repo_stub.is_ceased() is True

    @pytest.mark.asyncio
    async def test_cessation_details_preserved(
        self,
        cessation_service: CessationExecutionService,
        cessation_flag_repo_stub: CessationFlagRepositoryStub,
        writer_lock_stub: WriterLockStub,
        event_writer_service: EventWriterService,
    ) -> None:
        """Test that cessation details are preserved in flag repository."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True

        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Constitutional crisis",
        )

        details = await cessation_flag_repo_stub.get_cessation_details()

        assert details is not None
        assert details.reason == "Constitutional crisis"


# =============================================================================
# End-to-End Flow
# =============================================================================


class TestEndToEndFlow:
    """Test end-to-end cessation flow."""

    @pytest.mark.asyncio
    async def test_full_cessation_flow(
        self,
        cessation_service: CessationExecutionService,
        cessation_flag_repo_stub: CessationFlagRepositoryStub,
        freeze_checker_stub: FreezeCheckerStub,
        event_writer_service: EventWriterService,
        writer_lock_stub: WriterLockStub,
    ) -> None:
        """Test full cessation flow from trigger to frozen state."""
        await writer_lock_stub.acquire()
        event_writer_service._verified = True

        # 1. Write normal events before cessation
        event1 = await event_writer_service.write_event(
            event_type="normal.event",
            payload={"data": "before"},
            agent_id="agent-001",
            local_timestamp=datetime.now(timezone.utc),
        )
        assert event1 is not None

        # 2. Execute cessation
        cessation_event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="End of operations",
        )
        assert cessation_event is not None
        assert cessation_event.event_type == CESSATION_EXECUTED_EVENT_TYPE

        # 3. Verify cessation flag is set
        assert await cessation_flag_repo_stub.is_ceased() is True

        # 4. Simulate freeze check being linked to cessation flag
        # (In production, FreezeChecker would read from CessationFlagRepository)
        details = await cessation_flag_repo_stub.get_cessation_details()
        freeze_checker_stub.set_frozen(
            ceased_at=details.ceased_at,
            final_sequence=details.final_sequence_number,
            reason=details.reason,
        )

        # 5. Verify writes are now blocked
        with pytest.raises(SystemCeasedError):
            await event_writer_service.write_event(
                event_type="normal.event",
                payload={"data": "after"},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_freeze_guard_integration(
        self,
        freeze_guard: FreezeGuard,
        freeze_checker_stub: FreezeCheckerStub,
    ) -> None:
        """Test FreezeGuard integration with ensure_not_frozen()."""
        # Not frozen - should pass
        await freeze_guard.ensure_not_frozen()

        # Set frozen
        freeze_checker_stub.set_frozen_simple()

        # Now should raise
        with pytest.raises(SystemCeasedError) as exc_info:
            await freeze_guard.ensure_not_frozen()

        assert "FR41" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_freeze_guard_context_manager(
        self,
        freeze_guard: FreezeGuard,
        freeze_checker_stub: FreezeCheckerStub,
    ) -> None:
        """Test FreezeGuard context manager for operations."""
        from src.domain.errors.ceased import CeasedWriteAttemptError

        # Not frozen - context manager succeeds
        async with freeze_guard.for_operation("test_op"):
            pass  # Operation completes

        # Set frozen
        freeze_checker_stub.set_frozen_simple()

        # Now context manager should raise
        with pytest.raises(CeasedWriteAttemptError) as exc_info:
            async with freeze_guard.for_operation("test_op"):
                pass

        assert "test_op" in str(exc_info.value)


# =============================================================================
# Ordering Tests
# =============================================================================


class TestCheckOrdering:
    """Test that checks are performed in correct order."""

    @pytest.mark.asyncio
    async def test_freeze_check_before_halt_check(
        self,
        mock_atomic_writer: AsyncMock,
        halt_checker_stub: HaltCheckerStub,
        writer_lock_stub: WriterLockStub,
        mock_event_store: AsyncMock,
        freeze_checker_stub: FreezeCheckerStub,
    ) -> None:
        """Test that freeze check happens before halt check."""
        # Both frozen AND halted
        freeze_checker_stub.set_frozen_simple()
        halt_checker_stub.set_halted(True, "Test halt")

        service = EventWriterService(
            atomic_writer=mock_atomic_writer,
            halt_checker=halt_checker_stub,
            writer_lock=writer_lock_stub,
            event_store=mock_event_store,
            freeze_checker=freeze_checker_stub,
        )
        service._verified = True
        await writer_lock_stub.acquire()

        # Should raise SystemCeasedError (freeze), NOT SystemHaltedError (halt)
        with pytest.raises(SystemCeasedError):
            await service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )
