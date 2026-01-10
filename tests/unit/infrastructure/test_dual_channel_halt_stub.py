"""Unit tests for DualChannelHaltTransportStub (Story 3.3, Task 6).

Tests the stub implementation for testing/development scenarios.

ADR-3: Partition Behavior + Halt Durability
- Stub simulates dual-channel behavior for testing
- Allows independent control of DB/Redis channel states
"""

from uuid import uuid4

import pytest

from src.application.ports.dual_channel_halt import (
    CONFIRMATION_TIMEOUT_SECONDS,
    DualChannelHaltTransport,
)
from src.infrastructure.stubs.dual_channel_halt_stub import (
    DualChannelHaltTransportStub,
)


class TestDualChannelHaltTransportStub:
    """Test DualChannelHaltTransportStub interface compliance."""

    def test_implements_dual_channel_halt_transport(self) -> None:
        """Stub should implement DualChannelHaltTransport interface."""
        stub = DualChannelHaltTransportStub()
        assert isinstance(stub, DualChannelHaltTransport)

    def test_confirmation_timeout_seconds(self) -> None:
        """Should return correct timeout constant."""
        stub = DualChannelHaltTransportStub()
        assert stub.confirmation_timeout_seconds == CONFIRMATION_TIMEOUT_SECONDS


class TestWriteHalt:
    """Test write_halt method."""

    @pytest.mark.asyncio
    async def test_write_halt_sets_both_channels(self) -> None:
        """write_halt should set both DB and Redis channels."""
        stub = DualChannelHaltTransportStub()
        crisis_id = uuid4()

        await stub.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        assert await stub.is_halted() is True
        assert await stub.get_halt_reason() == "FR17: Fork detected"

    @pytest.mark.asyncio
    async def test_write_halt_tracks_crisis_event_id(self) -> None:
        """write_halt should track crisis event ID."""
        stub = DualChannelHaltTransportStub()
        crisis_id = uuid4()

        await stub.write_halt(
            reason="Test halt",
            crisis_event_id=crisis_id,
        )

        assert stub.get_crisis_event_id() == crisis_id

    @pytest.mark.asyncio
    async def test_write_halt_increments_trigger_count(self) -> None:
        """write_halt should increment trigger count for testing."""
        stub = DualChannelHaltTransportStub()

        assert stub.get_trigger_count() == 0

        await stub.write_halt(reason="First halt", crisis_event_id=uuid4())
        assert stub.get_trigger_count() == 1

        await stub.write_halt(reason="Second halt", crisis_event_id=uuid4())
        assert stub.get_trigger_count() == 2


class TestIsHalted:
    """Test is_halted method."""

    @pytest.mark.asyncio
    async def test_is_halted_initially_false(self) -> None:
        """is_halted should return False initially."""
        stub = DualChannelHaltTransportStub()
        assert await stub.is_halted() is False

    @pytest.mark.asyncio
    async def test_is_halted_true_after_write_halt(self) -> None:
        """is_halted should return True after write_halt."""
        stub = DualChannelHaltTransportStub()

        await stub.write_halt(reason="Test halt", crisis_event_id=uuid4())

        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_is_halted_true_when_db_halted_only(self) -> None:
        """is_halted should return True when only DB channel halted."""
        stub = DualChannelHaltTransportStub()

        stub.set_db_halted(True, "DB halt only")

        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_is_halted_true_when_redis_halted_only(self) -> None:
        """is_halted should return True when only Redis channel halted."""
        stub = DualChannelHaltTransportStub()

        stub.set_redis_halted(True)

        assert await stub.is_halted() is True


class TestGetHaltReason:
    """Test get_halt_reason method."""

    @pytest.mark.asyncio
    async def test_get_halt_reason_none_when_not_halted(self) -> None:
        """get_halt_reason should return None when not halted."""
        stub = DualChannelHaltTransportStub()
        assert await stub.get_halt_reason() is None

    @pytest.mark.asyncio
    async def test_get_halt_reason_returns_db_reason(self) -> None:
        """get_halt_reason should return DB reason (canonical)."""
        stub = DualChannelHaltTransportStub()

        stub.set_db_halted(True, "FR17: Fork detected")

        assert await stub.get_halt_reason() == "FR17: Fork detected"


class TestCheckChannelsConsistent:
    """Test check_channels_consistent method."""

    @pytest.mark.asyncio
    async def test_consistent_when_both_not_halted(self) -> None:
        """Should be consistent when both channels not halted."""
        stub = DualChannelHaltTransportStub()
        assert await stub.check_channels_consistent() is True

    @pytest.mark.asyncio
    async def test_consistent_when_both_halted(self) -> None:
        """Should be consistent when both channels halted."""
        stub = DualChannelHaltTransportStub()

        await stub.write_halt(reason="Test", crisis_event_id=uuid4())

        assert await stub.check_channels_consistent() is True

    @pytest.mark.asyncio
    async def test_inconsistent_when_only_db_halted(self) -> None:
        """Should be inconsistent when only DB halted."""
        stub = DualChannelHaltTransportStub()

        stub.set_db_halted(True, "DB only")

        assert await stub.check_channels_consistent() is False

    @pytest.mark.asyncio
    async def test_inconsistent_when_only_redis_halted(self) -> None:
        """Should be inconsistent when only Redis halted."""
        stub = DualChannelHaltTransportStub()

        stub.set_redis_halted(True)

        assert await stub.check_channels_consistent() is False


class TestResolveConflict:
    """Test resolve_conflict method."""

    @pytest.mark.asyncio
    async def test_resolve_conflict_when_db_halted_redis_not(self) -> None:
        """Should propagate DB halt to Redis."""
        stub = DualChannelHaltTransportStub()

        stub.set_db_halted(True, "DB halt", uuid4())
        stub.set_redis_halted(False)

        assert await stub.check_channels_consistent() is False

        await stub.resolve_conflict()

        assert await stub.check_channels_consistent() is True

    @pytest.mark.asyncio
    async def test_resolve_conflict_logs_phantom_halt(self) -> None:
        """Phantom halt (Redis halted, DB not) should be logged, not cleared."""
        stub = DualChannelHaltTransportStub()

        stub.set_redis_halted(True)
        stub.set_db_halted(False, None)

        # Phantom halt - Redis not cleared (security measure)
        await stub.resolve_conflict()

        # Redis still halted (not cleared for security)
        assert stub._redis_halted is True


class TestStubTestHelpers:
    """Test stub-specific helper methods for testing."""

    def test_reset_clears_all_state(self) -> None:
        """reset should clear all halt state."""
        stub = DualChannelHaltTransportStub()

        stub.set_db_halted(True, "Test", uuid4())
        stub.set_redis_halted(True)

        stub.reset()

        assert stub._db_halted is False
        assert stub._redis_halted is False
        assert stub._halt_reason is None
        assert stub._crisis_event_id is None
        assert stub._trigger_count == 0

    def test_get_trigger_count(self) -> None:
        """get_trigger_count should return number of write_halt calls."""
        stub = DualChannelHaltTransportStub()
        assert stub.get_trigger_count() == 0

    def test_get_crisis_event_id(self) -> None:
        """get_crisis_event_id should return last crisis ID."""
        stub = DualChannelHaltTransportStub()
        assert stub.get_crisis_event_id() is None

    def test_set_db_halted_for_testing(self) -> None:
        """set_db_halted allows direct channel control for testing."""
        stub = DualChannelHaltTransportStub()

        stub.set_db_halted(True, "Test reason")

        assert stub._db_halted is True
        assert stub._halt_reason == "Test reason"

    def test_set_redis_halted_for_testing(self) -> None:
        """set_redis_halted allows direct channel control for testing."""
        stub = DualChannelHaltTransportStub()

        stub.set_redis_halted(True)

        assert stub._redis_halted is True


class TestFailureSimulation:
    """Test failure simulation capabilities."""

    @pytest.mark.asyncio
    async def test_simulate_db_failure(self) -> None:
        """Should be able to simulate DB failure."""
        stub = DualChannelHaltTransportStub()
        stub.set_db_failure(True)

        # DB failure during is_halted - falls back to Redis
        stub.set_redis_halted(True)

        # Should still work (Redis fallback)
        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_simulate_redis_failure(self) -> None:
        """Should be able to simulate Redis failure."""
        stub = DualChannelHaltTransportStub()
        stub.set_redis_failure(True)

        stub.set_db_halted(True, "DB halt")

        # Should use DB (canonical)
        assert await stub.is_halted() is True
