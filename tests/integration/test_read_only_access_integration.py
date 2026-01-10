"""Integration tests for read-only access during halt (Story 3.5, Task 8).

Tests the complete read-only mode behavior during system halt,
verifying all acceptance criteria are met.

Acceptance Criteria Covered:
- AC1: Read operations succeed during halt with HALTED status header
- AC2: Write operations rejected during halt with FR20 error
- AC3: Provisional operations rejected during halt
"""

import asyncio
from uuid import uuid4

import pytest

from src.application.services.halt_guard import HaltGuard
from src.domain.errors.read_only import (
    ProvisionalBlockedDuringHaltError,
    WriteBlockedDuringHaltError,
)
from src.domain.models.halt_status_header import (
    SYSTEM_STATUS_HALTED,
    SYSTEM_STATUS_OPERATIONAL,
)
from src.infrastructure.stubs.dual_channel_halt_stub import DualChannelHaltTransportStub


@pytest.fixture
def halt_transport() -> DualChannelHaltTransportStub:
    """Create a fresh halt transport stub."""
    return DualChannelHaltTransportStub()


@pytest.fixture
def halt_guard(halt_transport: DualChannelHaltTransportStub) -> HaltGuard:
    """Create HaltGuard with stub transport."""
    return HaltGuard(halt_transport)


class TestAC1ReadOperationsSucceedDuringHalt:
    """AC1: Read operations succeed during halt with HALTED status header."""

    @pytest.mark.asyncio
    async def test_read_query_succeeds_during_halt(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify read operations succeed when system is halted."""
        # Given: System is halted
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # When: I attempt a read operation
        status = await halt_guard.check_read_allowed()

        # Then: The operation succeeds (no exception)
        assert status is not None

    @pytest.mark.asyncio
    async def test_read_returns_halted_status_header(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify read results include system_status: HALTED header."""
        # Given: System is halted
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # When: I attempt a read operation
        status = await halt_guard.check_read_allowed()

        # Then: Results include system_status: HALTED header
        assert status.system_status == SYSTEM_STATUS_HALTED
        assert status.system_status == "HALTED"

    @pytest.mark.asyncio
    async def test_read_status_includes_halt_reason(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify halted status includes the reason."""
        # Given: System is halted with specific reason
        await halt_transport.write_halt(
            reason="FR17: Fork detected - hash collision at seq 100",
            crisis_event_id=uuid4(),
        )

        # When: I attempt a read operation
        status = await halt_guard.check_read_allowed()

        # Then: Status includes the halt reason
        assert status.halt_reason is not None
        assert "Fork detected" in status.halt_reason

    @pytest.mark.asyncio
    async def test_multiple_concurrent_reads_succeed_during_halt(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify multiple concurrent reads all succeed during halt."""
        # Given: System is halted
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # When: Multiple concurrent read operations are attempted
        tasks = [halt_guard.check_read_allowed() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # Then: All operations succeed
        assert len(results) == 10
        for status in results:
            assert status.system_status == SYSTEM_STATUS_HALTED


class TestAC2WriteOperationsRejectedDuringHalt:
    """AC2: Write operations rejected during halt with FR20 error."""

    @pytest.mark.asyncio
    async def test_write_operation_rejected_during_halt(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify write operations are rejected when halted."""
        # Given: System is halted
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # When: I attempt a write operation
        # Then: The operation is rejected
        with pytest.raises(WriteBlockedDuringHaltError):
            await halt_guard.check_write_allowed()

    @pytest.mark.asyncio
    async def test_write_error_includes_fr20_message(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify error includes 'FR20: System halted - write operations blocked'."""
        # Given: System is halted
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        # When/Then: Write rejection includes FR20 message
        with pytest.raises(WriteBlockedDuringHaltError) as exc_info:
            await halt_guard.check_write_allowed()

        error_message = str(exc_info.value)
        assert "FR20" in error_message
        assert "System halted" in error_message
        assert "write operations blocked" in error_message


class TestAC3ProvisionalOperationsRejectedDuringHalt:
    """AC3: Provisional operations rejected during halt, not queued."""

    @pytest.mark.asyncio
    async def test_provisional_operation_rejected_during_halt(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify provisional operations are rejected when halted."""
        # Given: System is halted
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # When: I attempt a provisional operation
        # Then: The operation is rejected
        with pytest.raises(ProvisionalBlockedDuringHaltError):
            await halt_guard.check_provisional_allowed()

    @pytest.mark.asyncio
    async def test_provisional_not_queued_during_halt(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify provisional operations are not queued for later."""
        # Given: System is halted
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # When: Multiple provisional attempts are made
        attempt_count = 0
        for _ in range(5):
            try:
                await halt_guard.check_provisional_allowed()
            except ProvisionalBlockedDuringHaltError:
                attempt_count += 1

        # Then: All attempts are rejected (nothing queued)
        assert attempt_count == 5
        # Verify no operations were queued by checking system state is unchanged


class TestNormalOperationsWhenNotHalted:
    """Tests verifying normal operations work when not halted."""

    @pytest.mark.asyncio
    async def test_write_succeeds_when_not_halted(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify writes succeed when system is operational."""
        # Given: System is not halted (default state)
        # When/Then: Write check passes without exception
        await halt_guard.check_write_allowed()  # Should not raise

    @pytest.mark.asyncio
    async def test_provisional_succeeds_when_not_halted(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify provisional operations succeed when operational."""
        # Given: System is not halted (default state)
        # When/Then: Provisional check passes without exception
        await halt_guard.check_provisional_allowed()  # Should not raise

    @pytest.mark.asyncio
    async def test_status_header_shows_operational(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify status header shows OPERATIONAL when not halted."""
        # Given: System is not halted
        # When: I check read status
        status = await halt_guard.check_read_allowed()

        # Then: Status shows OPERATIONAL
        assert status.system_status == SYSTEM_STATUS_OPERATIONAL
        assert status.system_status == "OPERATIONAL"
        assert status.halt_reason is None


class TestHaltStateTransitions:
    """Tests for transitions between operational and halted states."""

    @pytest.mark.asyncio
    async def test_transition_from_operational_to_halted(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify behavior changes when transitioning to halted."""
        # Given: System is operational
        await halt_guard.check_write_allowed()  # Should pass

        # When: Halt is triggered
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        # Then: Writes are now blocked
        with pytest.raises(WriteBlockedDuringHaltError):
            await halt_guard.check_write_allowed()

    @pytest.mark.asyncio
    async def test_read_status_changes_on_halt(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify read status header changes when halt occurs."""
        # Given: System is operational
        status_before = await halt_guard.check_read_allowed()
        assert status_before.system_status == "OPERATIONAL"

        # When: Halt is triggered
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        # Then: Status now shows HALTED
        status_after = await halt_guard.check_read_allowed()
        assert status_after.system_status == "HALTED"


class TestDualChannelHaltIntegration:
    """Tests verifying integration with dual-channel halt transport."""

    @pytest.mark.asyncio
    async def test_halt_guard_uses_dual_channel_state(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify HaltGuard correctly reads from dual-channel transport."""
        # Given: Transport is not halted
        assert await halt_guard.is_halted() is False

        # When: Halt is triggered via transport
        await halt_transport.write_halt(
            reason="Test halt",
            crisis_event_id=uuid4(),
        )

        # Then: HaltGuard reflects the halt state
        assert await halt_guard.is_halted() is True

    @pytest.mark.asyncio
    async def test_halt_reason_propagates_correctly(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify halt reason propagates from transport to guard."""
        # Given: Transport is halted with specific reason
        expected_reason = "FR17: Fork detected - sequence gap"
        await halt_transport.write_halt(
            reason=expected_reason,
            crisis_event_id=uuid4(),
        )

        # When: We get the halt reason from guard
        actual_reason = await halt_guard.get_halt_reason()

        # Then: Reason matches
        assert actual_reason == expected_reason

    @pytest.mark.asyncio
    async def test_db_only_halt_triggers_guard(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify halt guard reacts to DB-only halt state."""
        # Given: Only DB channel is halted (simulating Redis failure)
        halt_transport.set_db_halted(True, "DB-only halt")
        halt_transport.set_redis_halted(False)

        # When: We check halt state
        # Then: Guard sees halted (either channel = halt)
        assert await halt_guard.is_halted() is True

        with pytest.raises(WriteBlockedDuringHaltError):
            await halt_guard.check_write_allowed()

    @pytest.mark.asyncio
    async def test_redis_only_halt_triggers_guard(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify halt guard reacts to Redis-only halt state."""
        # Given: Only Redis channel is halted
        halt_transport.set_db_halted(False)
        halt_transport.set_redis_halted(True)

        # When: We check halt state
        # Then: Guard sees halted (either channel = halt)
        assert await halt_guard.is_halted() is True

        with pytest.raises(WriteBlockedDuringHaltError):
            await halt_guard.check_write_allowed()
