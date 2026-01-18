"""Unit tests for HaltGuardStub (Story 3.5, Task 7.5).

Tests the HaltGuardStub for testing scenarios.
"""

import contextlib
from datetime import datetime, timezone

import pytest

from src.domain.errors.read_only import (
    ProvisionalBlockedDuringHaltError,
    WriteBlockedDuringHaltError,
)
from src.infrastructure.stubs.halt_guard_stub import HaltGuardStub


@pytest.fixture
def stub() -> HaltGuardStub:
    """Create a fresh HaltGuardStub for testing."""
    return HaltGuardStub()


class TestHaltGuardStubInitialState:
    """Tests for initial stub state."""

    @pytest.mark.asyncio
    async def test_starts_not_halted(self, stub: HaltGuardStub) -> None:
        """Verify stub starts in operational state."""
        assert await stub.is_halted() is False

    @pytest.mark.asyncio
    async def test_initial_halt_reason_is_none(self, stub: HaltGuardStub) -> None:
        """Verify stub starts with no halt reason."""
        assert await stub.get_halt_reason() is None


class TestHaltGuardStubCheckWriteAllowed:
    """Tests for check_write_allowed."""

    @pytest.mark.asyncio
    async def test_write_allowed_when_not_halted(self, stub: HaltGuardStub) -> None:
        """Verify write allowed when not halted."""
        await stub.check_write_allowed()  # Should not raise

    @pytest.mark.asyncio
    async def test_write_blocked_when_halted(self, stub: HaltGuardStub) -> None:
        """Verify write blocked when halted."""
        stub.trigger_halt("Test halt")

        with pytest.raises(WriteBlockedDuringHaltError):
            await stub.check_write_allowed()

    @pytest.mark.asyncio
    async def test_write_error_includes_fr20(self, stub: HaltGuardStub) -> None:
        """Verify error includes FR20 message."""
        stub.trigger_halt("Test reason")

        with pytest.raises(WriteBlockedDuringHaltError) as exc_info:
            await stub.check_write_allowed()

        assert "FR20" in str(exc_info.value)
        assert "Test reason" in str(exc_info.value)


class TestHaltGuardStubCheckReadAllowed:
    """Tests for check_read_allowed."""

    @pytest.mark.asyncio
    async def test_read_returns_operational_when_not_halted(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify read returns OPERATIONAL when not halted."""
        status = await stub.check_read_allowed()
        assert status.system_status == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_read_returns_halted_when_halted(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify read returns HALTED when halted."""
        stub.trigger_halt("Test")

        status = await stub.check_read_allowed()
        assert status.system_status == "HALTED"

    @pytest.mark.asyncio
    async def test_read_always_succeeds_even_when_halted(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify reads never raise even when halted."""
        stub.trigger_halt("Test")

        # Should not raise
        status = await stub.check_read_allowed()
        assert status is not None


class TestHaltGuardStubCheckProvisionalAllowed:
    """Tests for check_provisional_allowed."""

    @pytest.mark.asyncio
    async def test_provisional_allowed_when_not_halted(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify provisional allowed when not halted."""
        await stub.check_provisional_allowed()  # Should not raise

    @pytest.mark.asyncio
    async def test_provisional_blocked_when_halted(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify provisional blocked when halted."""
        stub.trigger_halt("Test")

        with pytest.raises(ProvisionalBlockedDuringHaltError):
            await stub.check_provisional_allowed()


class TestHaltGuardStubTriggerHalt:
    """Tests for trigger_halt helper method."""

    @pytest.mark.asyncio
    async def test_trigger_halt_sets_halted_state(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify trigger_halt sets halted state."""
        stub.trigger_halt("Test reason")
        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_trigger_halt_sets_reason(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify trigger_halt sets halt reason."""
        stub.trigger_halt("Fork detected")
        assert await stub.get_halt_reason() == "Fork detected"

    @pytest.mark.asyncio
    async def test_trigger_halt_with_custom_timestamp(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify trigger_halt accepts custom timestamp."""
        custom_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        stub.trigger_halt("Test", halted_at=custom_time)

        status = await stub.check_read_allowed()
        assert status.halted_at == custom_time


class TestHaltGuardStubClearHalt:
    """Tests for clear_halt helper method."""

    @pytest.mark.asyncio
    async def test_clear_halt_clears_halted_state(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify clear_halt clears halted state."""
        stub.trigger_halt("Test")
        stub.clear_halt()

        assert await stub.is_halted() is False

    @pytest.mark.asyncio
    async def test_clear_halt_clears_reason(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify clear_halt clears halt reason."""
        stub.trigger_halt("Test reason")
        stub.clear_halt()

        assert await stub.get_halt_reason() is None


class TestHaltGuardStubCheckCount:
    """Tests for check count tracking."""

    @pytest.mark.asyncio
    async def test_check_count_starts_at_zero(self, stub: HaltGuardStub) -> None:
        """Verify check count starts at zero."""
        assert stub.get_check_count() == 0

    @pytest.mark.asyncio
    async def test_check_count_increments_on_write_check(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify check count increments on write check."""
        await stub.check_write_allowed()
        assert stub.get_check_count() == 1

    @pytest.mark.asyncio
    async def test_check_count_increments_on_read_check(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify check count increments on read check."""
        await stub.check_read_allowed()
        assert stub.get_check_count() == 1

    @pytest.mark.asyncio
    async def test_check_count_increments_on_provisional_check(
        self,
        stub: HaltGuardStub,
    ) -> None:
        """Verify check count increments on provisional check."""
        await stub.check_provisional_allowed()
        assert stub.get_check_count() == 1

    @pytest.mark.asyncio
    async def test_check_count_accumulates(self, stub: HaltGuardStub) -> None:
        """Verify check count accumulates across calls."""
        await stub.check_write_allowed()
        await stub.check_read_allowed()
        await stub.check_provisional_allowed()

        assert stub.get_check_count() == 3


class TestHaltGuardStubReset:
    """Tests for reset method."""

    @pytest.mark.asyncio
    async def test_reset_clears_all_state(self, stub: HaltGuardStub) -> None:
        """Verify reset clears all stub state."""
        stub.trigger_halt("Test")

        # Make a check that raises (to increment counter)
        with contextlib.suppress(WriteBlockedDuringHaltError):
            await stub.check_write_allowed()

        stub.reset()

        assert await stub.is_halted() is False
        assert await stub.get_halt_reason() is None
        assert stub.get_check_count() == 0


class TestHaltGuardStubExports:
    """Tests verifying proper exports."""

    def test_stub_exported_from_stubs_package(self) -> None:
        """Verify HaltGuardStub is exported from stubs __init__."""
        from src.infrastructure.stubs import HaltGuardStub as ExportedClass

        assert ExportedClass is HaltGuardStub
