"""Unit tests for HaltCheckerStub (Story 3.2/3.3).

Tests all three modes of operation:
1. DualChannelHaltTransport mode (Story 3.3)
2. Shared state mode (Story 3.2)
3. Standalone mode (legacy)

ADR-3: Partition Behavior + Halt Durability
- DualChannelHaltTransport checks Redis Streams + DB halt flag
- If EITHER channel indicates halt -> is_halted() returns True
"""

from uuid import uuid4

import pytest

from src.infrastructure.stubs.dual_channel_halt_stub import (
    DualChannelHaltTransportStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.halt_state import HaltState


class TestHaltCheckerStubStandaloneMode:
    """Test standalone mode (force_halted parameter)."""

    @pytest.mark.asyncio
    async def test_is_halted_false_by_default(self) -> None:
        """Should return False when not halted."""
        stub = HaltCheckerStub()
        assert await stub.is_halted() is False

    @pytest.mark.asyncio
    async def test_is_halted_true_when_force_halted(self) -> None:
        """Should return True when force_halted=True."""
        stub = HaltCheckerStub(force_halted=True)
        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_get_halt_reason_none_when_not_halted(self) -> None:
        """Should return None when not halted."""
        stub = HaltCheckerStub()
        assert await stub.get_halt_reason() is None

    @pytest.mark.asyncio
    async def test_get_halt_reason_with_custom_reason(self) -> None:
        """Should return custom reason when halted."""
        stub = HaltCheckerStub(force_halted=True, halt_reason="Test reason")
        assert await stub.get_halt_reason() == "Test reason"

    @pytest.mark.asyncio
    async def test_get_halt_reason_default_when_no_reason(self) -> None:
        """Should return default reason when halted without custom reason."""
        stub = HaltCheckerStub(force_halted=True)
        reason = await stub.get_halt_reason()
        assert reason is not None
        assert "Stub" in reason

    def test_set_halted(self) -> None:
        """Test helper method to set halt state."""
        stub = HaltCheckerStub()
        stub.set_halted(True, "Manual halt")
        assert stub._force_halted is True
        assert stub._halt_reason == "Manual halt"


class TestHaltCheckerStubSharedStateMode:
    """Test shared state mode (halt_state parameter)."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.fixture
    def halt_state(self) -> HaltState:
        """Create shared halt state."""
        return HaltState.get_instance(f"checker-test-{uuid4()}")

    @pytest.mark.asyncio
    async def test_is_halted_via_shared_state(self, halt_state: HaltState) -> None:
        """Should return True when shared state is halted."""
        stub = HaltCheckerStub(halt_state=halt_state)
        assert await stub.is_halted() is False

        halt_state.set_halted_sync(True, "Shared state halt")
        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_get_halt_reason_from_shared_state(
        self, halt_state: HaltState
    ) -> None:
        """Should return reason from shared state."""
        stub = HaltCheckerStub(halt_state=halt_state)
        halt_state.set_halted_sync(True, "FR17: Fork detected")

        reason = await stub.get_halt_reason()
        assert reason == "FR17: Fork detected"

    def test_init_with_halt_state_name(self) -> None:
        """Should get named HaltState instance."""
        stub = HaltCheckerStub(halt_state_name="test-named-state")
        assert stub.halt_state is not None
        assert stub.halt_state == HaltState.get_instance("test-named-state")


class TestHaltCheckerStubDualChannelMode:
    """Test DualChannelHaltTransport mode (Story 3.3)."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create DualChannelHaltTransportStub."""
        return DualChannelHaltTransportStub()

    @pytest.mark.asyncio
    async def test_is_halted_via_dual_channel(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Should return True when dual-channel indicates halt."""
        stub = HaltCheckerStub(dual_channel_halt=dual_channel_stub)
        assert await stub.is_halted() is False

        await dual_channel_stub.write_halt("Test halt", uuid4())
        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_get_halt_reason_from_dual_channel(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Should return reason from dual-channel transport."""
        stub = HaltCheckerStub(dual_channel_halt=dual_channel_stub)
        await dual_channel_stub.write_halt("FR17: Fork detected", uuid4())

        reason = await stub.get_halt_reason()
        assert reason == "FR17: Fork detected"

    @pytest.mark.asyncio
    async def test_dual_channel_db_only_halted(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Should return True when only DB channel halted."""
        stub = HaltCheckerStub(dual_channel_halt=dual_channel_stub)
        dual_channel_stub.set_db_halted(True, "DB halt only")

        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_dual_channel_redis_only_halted(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Should return True when only Redis channel halted."""
        stub = HaltCheckerStub(dual_channel_halt=dual_channel_stub)
        dual_channel_stub.set_redis_halted(True)

        assert await stub.is_halted() is True

    def test_dual_channel_halt_property(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Should expose dual_channel_halt property."""
        stub = HaltCheckerStub(dual_channel_halt=dual_channel_stub)
        assert stub.dual_channel_halt is dual_channel_stub


class TestHaltCheckerStubModePriority:
    """Test priority order between modes."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.mark.asyncio
    async def test_dual_channel_has_highest_priority(self) -> None:
        """Dual-channel halt should take priority over other modes."""
        dual_channel_stub = DualChannelHaltTransportStub()
        halt_state = HaltState.get_instance(f"priority-test-{uuid4()}")

        stub = HaltCheckerStub(
            dual_channel_halt=dual_channel_stub,
            halt_state=halt_state,
            force_halted=False,
        )

        # Only dual-channel halted
        await dual_channel_stub.write_halt("Dual channel halt", uuid4())
        assert await stub.is_halted() is True

        # Reason should come from dual-channel
        reason = await stub.get_halt_reason()
        assert reason == "Dual channel halt"

    @pytest.mark.asyncio
    async def test_shared_state_has_second_priority(self) -> None:
        """Shared state should be checked when dual-channel not halted."""
        dual_channel_stub = DualChannelHaltTransportStub()
        halt_state = HaltState.get_instance(f"priority-test-2-{uuid4()}")

        stub = HaltCheckerStub(
            dual_channel_halt=dual_channel_stub,
            halt_state=halt_state,
            force_halted=False,
        )

        # Only shared state halted
        halt_state.set_halted_sync(True, "Shared state halt")
        assert await stub.is_halted() is True

        # Reason should come from shared state
        reason = await stub.get_halt_reason()
        assert reason == "Shared state halt"

    @pytest.mark.asyncio
    async def test_force_halted_is_last_resort(self) -> None:
        """force_halted should only be used when no other mode indicates halt."""
        dual_channel_stub = DualChannelHaltTransportStub()
        halt_state = HaltState.get_instance(f"priority-test-3-{uuid4()}")

        stub = HaltCheckerStub(
            dual_channel_halt=dual_channel_stub,
            halt_state=halt_state,
            force_halted=True,
            halt_reason="Forced halt",
        )

        # force_halted should still work if no other halt
        assert await stub.is_halted() is True

        # Reason from force_halted
        reason = await stub.get_halt_reason()
        assert reason == "Forced halt"

    @pytest.mark.asyncio
    async def test_any_halt_source_returns_true(self) -> None:
        """is_halted should return True if ANY source is halted."""
        dual_channel_stub = DualChannelHaltTransportStub()
        halt_state = HaltState.get_instance(f"any-test-{uuid4()}")

        stub = HaltCheckerStub(
            dual_channel_halt=dual_channel_stub,
            halt_state=halt_state,
            force_halted=False,
        )

        # Initially not halted
        assert await stub.is_halted() is False

        # Any source should trigger halt
        halt_state.set_halted_sync(True, "Any halt")
        assert await stub.is_halted() is True


class TestHaltCheckerStubBackwardCompatibility:
    """Test backward compatibility with existing code."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.mark.asyncio
    async def test_default_constructor_works(self) -> None:
        """Default constructor should work (standalone mode, not halted)."""
        stub = HaltCheckerStub()
        assert await stub.is_halted() is False
        assert await stub.get_halt_reason() is None

    @pytest.mark.asyncio
    async def test_halt_state_only_mode_works(self) -> None:
        """halt_state-only mode should work (Story 3.2 compatibility)."""
        halt_state = HaltState.get_instance(f"compat-test-{uuid4()}")
        stub = HaltCheckerStub(halt_state=halt_state)

        assert await stub.is_halted() is False
        halt_state.set_halted_sync(True, "Compat test")
        assert await stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_force_halted_only_mode_works(self) -> None:
        """force_halted-only mode should work (legacy compatibility)."""
        stub = HaltCheckerStub(force_halted=True, halt_reason="Legacy test")
        assert await stub.is_halted() is True
        assert await stub.get_halt_reason() == "Legacy test"
