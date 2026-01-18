"""Unit tests for HaltGuard service (Story 3.5, Task 5.7).

Tests the HaltGuard application service that enforces read-only mode
during system halt (FR20).
"""

from datetime import datetime, timezone
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
    """Create a fresh halt transport stub for testing."""
    return DualChannelHaltTransportStub()


@pytest.fixture
def halt_guard(halt_transport: DualChannelHaltTransportStub) -> HaltGuard:
    """Create HaltGuard with stub transport."""
    return HaltGuard(halt_transport)


class TestHaltGuardCheckWriteAllowed:
    """Tests for check_write_allowed (AC2)."""

    @pytest.mark.asyncio
    async def test_write_allowed_when_not_halted(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify check_write_allowed passes when system is operational."""
        # Should not raise
        await halt_guard.check_write_allowed()

    @pytest.mark.asyncio
    async def test_write_blocked_when_halted(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify check_write_allowed raises WriteBlockedDuringHaltError when halted."""
        # Trigger halt
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        with pytest.raises(WriteBlockedDuringHaltError):
            await halt_guard.check_write_allowed()

    @pytest.mark.asyncio
    async def test_write_blocked_error_includes_fr20_message(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify error message includes FR20 reference per AC2."""
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        with pytest.raises(WriteBlockedDuringHaltError) as exc_info:
            await halt_guard.check_write_allowed()

        error_message = str(exc_info.value)
        assert "FR20" in error_message
        assert "write operations blocked" in error_message

    @pytest.mark.asyncio
    async def test_write_blocked_error_includes_halt_reason(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify error message includes the halt reason."""
        await halt_transport.write_halt(
            reason="Fork detected - hash collision",
            crisis_event_id=uuid4(),
        )

        with pytest.raises(WriteBlockedDuringHaltError) as exc_info:
            await halt_guard.check_write_allowed()

        error_message = str(exc_info.value)
        assert "Fork detected" in error_message


class TestHaltGuardCheckReadAllowed:
    """Tests for check_read_allowed (AC1)."""

    @pytest.mark.asyncio
    async def test_read_returns_operational_when_not_halted(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify check_read_allowed returns OPERATIONAL when not halted."""
        status = await halt_guard.check_read_allowed()
        assert status.system_status == SYSTEM_STATUS_OPERATIONAL
        assert status.system_status == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_read_returns_halted_status_when_halted(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify check_read_allowed returns HALTED status when halted."""
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        status = await halt_guard.check_read_allowed()
        assert status.system_status == SYSTEM_STATUS_HALTED
        assert status.system_status == "HALTED"

    @pytest.mark.asyncio
    async def test_read_always_succeeds_during_halt(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify reads never raise even when halted (FR20)."""
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        # Should not raise - reads always allowed
        status = await halt_guard.check_read_allowed()
        assert status is not None

    @pytest.mark.asyncio
    async def test_read_includes_halt_reason(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify halted status includes the halt reason."""
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        status = await halt_guard.check_read_allowed()
        assert status.halt_reason == "FR17: Fork detected"

    @pytest.mark.asyncio
    async def test_read_operational_has_no_reason(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify operational status has no halt reason."""
        status = await halt_guard.check_read_allowed()
        assert status.halt_reason is None

    @pytest.mark.asyncio
    async def test_read_halted_includes_timestamp(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify halted status includes halted_at timestamp."""
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        before = datetime.now(timezone.utc)
        status = await halt_guard.check_read_allowed()
        after = datetime.now(timezone.utc)

        assert status.halted_at is not None
        assert before <= status.halted_at <= after


class TestHaltGuardCheckProvisionalAllowed:
    """Tests for check_provisional_allowed (AC3)."""

    @pytest.mark.asyncio
    async def test_provisional_allowed_when_not_halted(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify check_provisional_allowed passes when operational."""
        # Should not raise
        await halt_guard.check_provisional_allowed()

    @pytest.mark.asyncio
    async def test_provisional_blocked_when_halted(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify check_provisional_allowed raises when halted (AC3)."""
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        with pytest.raises(ProvisionalBlockedDuringHaltError):
            await halt_guard.check_provisional_allowed()

    @pytest.mark.asyncio
    async def test_provisional_blocked_error_includes_fr20(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify provisional error includes FR20 reference."""
        await halt_transport.write_halt(
            reason="Fork detected",
            crisis_event_id=uuid4(),
        )

        with pytest.raises(ProvisionalBlockedDuringHaltError) as exc_info:
            await halt_guard.check_provisional_allowed()

        error_message = str(exc_info.value)
        assert "FR20" in error_message
        assert "provisional" in error_message


class TestHaltGuardGetStatus:
    """Tests for get_status convenience method."""

    @pytest.mark.asyncio
    async def test_get_status_when_operational(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify get_status returns operational header."""
        status = await halt_guard.get_status()
        assert status.system_status == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_get_status_when_halted(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify get_status returns halted header."""
        await halt_transport.write_halt(
            reason="Test halt",
            crisis_event_id=uuid4(),
        )

        status = await halt_guard.get_status()
        assert status.system_status == "HALTED"


class TestHaltGuardIsHalted:
    """Tests for is_halted convenience method."""

    @pytest.mark.asyncio
    async def test_is_halted_returns_false_when_operational(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify is_halted returns False when operational."""
        result = await halt_guard.is_halted()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_halted_returns_true_when_halted(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify is_halted returns True when halted."""
        await halt_transport.write_halt(
            reason="Test",
            crisis_event_id=uuid4(),
        )

        result = await halt_guard.is_halted()
        assert result is True


class TestHaltGuardGetHaltReason:
    """Tests for get_halt_reason convenience method."""

    @pytest.mark.asyncio
    async def test_get_halt_reason_returns_none_when_operational(
        self,
        halt_guard: HaltGuard,
    ) -> None:
        """Verify get_halt_reason returns None when operational."""
        result = await halt_guard.get_halt_reason()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_halt_reason_returns_reason_when_halted(
        self,
        halt_guard: HaltGuard,
        halt_transport: DualChannelHaltTransportStub,
    ) -> None:
        """Verify get_halt_reason returns reason when halted."""
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        result = await halt_guard.get_halt_reason()
        assert result == "FR17: Fork detected"


class TestHaltGuardModuleExports:
    """Tests verifying proper module exports."""

    def test_halt_guard_exported_from_services(self) -> None:
        """Verify HaltGuard is exported from services __init__."""
        from src.application.services import HaltGuard as ExportedClass

        assert ExportedClass is HaltGuard
