"""Unit tests for HaltTriggerStub (Story 3.2, Task 3.6).

Tests the HaltTrigger stub implementation and its coordination
with HaltState and HaltCheckerStub.

Constitutional Constraints:
- AC1: Immediate halt on fork detection
- AC3: Writer stops accepting events after halt
- AC4: HaltChecker reflects halt state
"""

from uuid import uuid4

import pytest

from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.halt_state import HaltState
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub


class TestHaltTriggerStubBasic:
    """Basic tests for HaltTriggerStub."""

    @pytest.fixture(autouse=True)
    def reset_instances(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.fixture
    def halt_state(self) -> HaltState:
        """Create a fresh halt state for each test."""
        return HaltState.get_instance(f"test-{uuid4()}")

    @pytest.fixture
    def halt_trigger(self, halt_state: HaltState) -> HaltTriggerStub:
        """Create a halt trigger stub with shared state."""
        return HaltTriggerStub(halt_state=halt_state)

    def test_halt_propagation_timeout(self, halt_trigger: HaltTriggerStub) -> None:
        """Test halt propagation timeout is 1 second (AC1)."""
        assert halt_trigger.halt_propagation_timeout_seconds == 1.0

    @pytest.mark.asyncio
    async def test_trigger_halt_sets_state(self, halt_trigger: HaltTriggerStub) -> None:
        """Test trigger_halt sets halt state."""
        await halt_trigger.trigger_halt("FR17: Fork detected")

        assert halt_trigger.is_halted() is True
        assert halt_trigger.get_halt_reason() == "FR17: Fork detected"

    @pytest.mark.asyncio
    async def test_trigger_halt_with_crisis_event_id(
        self, halt_trigger: HaltTriggerStub
    ) -> None:
        """Test trigger_halt stores crisis event ID."""
        crisis_id = uuid4()
        await halt_trigger.trigger_halt("Crisis halt", crisis_id)

        assert halt_trigger.get_last_crisis_event_id() == crisis_id

    @pytest.mark.asyncio
    async def test_trigger_count_increments(
        self, halt_trigger: HaltTriggerStub
    ) -> None:
        """Test trigger count tracks halt events."""
        assert halt_trigger.get_trigger_count() == 0

        await halt_trigger.trigger_halt("Halt 1")
        assert halt_trigger.get_trigger_count() == 1

        # Reset and trigger again
        halt_trigger.reset()
        await halt_trigger.trigger_halt("Halt 2")
        assert halt_trigger.get_trigger_count() == 1  # Reset also resets count

    @pytest.mark.asyncio
    async def test_set_halt_state(self, halt_trigger: HaltTriggerStub) -> None:
        """Test set_halt_state for direct state manipulation."""
        await halt_trigger.set_halt_state(True, "Manual halt")
        assert halt_trigger.is_halted() is True
        assert halt_trigger.get_halt_reason() == "Manual halt"

        await halt_trigger.set_halt_state(False)
        assert halt_trigger.is_halted() is False

    def test_reset(self, halt_trigger: HaltTriggerStub) -> None:
        """Test reset clears halt state."""
        halt_trigger.halt_state.set_halted_sync(True, "Test halt", uuid4())
        halt_trigger.reset()

        assert halt_trigger.is_halted() is False
        assert halt_trigger.get_halt_reason() is None
        assert halt_trigger.get_last_crisis_event_id() is None
        assert halt_trigger.get_trigger_count() == 0


class TestHaltTriggerCheckerCoordination:
    """Tests for coordination between HaltTriggerStub and HaltCheckerStub."""

    @pytest.fixture(autouse=True)
    def reset_instances(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.fixture
    def shared_state(self) -> HaltState:
        """Create shared halt state."""
        return HaltState.get_instance(f"coordination-{uuid4()}")

    @pytest.fixture
    def halt_trigger(self, shared_state: HaltState) -> HaltTriggerStub:
        """Create halt trigger with shared state."""
        return HaltTriggerStub(halt_state=shared_state)

    @pytest.fixture
    def halt_checker(self, shared_state: HaltState) -> HaltCheckerStub:
        """Create halt checker with same shared state."""
        return HaltCheckerStub(halt_state=shared_state)

    @pytest.mark.asyncio
    async def test_checker_reflects_trigger_halt(
        self,
        halt_trigger: HaltTriggerStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test HaltChecker reflects halt after trigger (AC4)."""
        # Initially not halted
        assert await halt_checker.is_halted() is False
        assert await halt_checker.get_halt_reason() is None

        # Trigger halt
        await halt_trigger.trigger_halt("FR17: Constitutional crisis")

        # Checker should reflect halt state
        assert await halt_checker.is_halted() is True
        assert await halt_checker.get_halt_reason() == "FR17: Constitutional crisis"

    @pytest.mark.asyncio
    async def test_checker_reflects_halt_clear(
        self,
        halt_trigger: HaltTriggerStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test HaltChecker reflects halt clear."""
        # Trigger and clear halt
        await halt_trigger.trigger_halt("Test halt")
        await halt_trigger.set_halt_state(False)

        assert await halt_checker.is_halted() is False
        assert await halt_checker.get_halt_reason() is None

    @pytest.mark.asyncio
    async def test_named_instance_coordination(self) -> None:
        """Test coordination using named instances."""
        instance_name = f"named-test-{uuid4()}"

        # Create stubs with same named instance
        halt_trigger = HaltTriggerStub(halt_state_name=instance_name)
        halt_checker = HaltCheckerStub(halt_state_name=instance_name)

        # Trigger halt
        await halt_trigger.trigger_halt("Named instance halt")

        # Checker should see halt
        assert await halt_checker.is_halted() is True
        assert await halt_checker.get_halt_reason() == "Named instance halt"


class TestHaltCheckerStubModes:
    """Tests for HaltCheckerStub operating modes."""

    @pytest.fixture(autouse=True)
    def reset_instances(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.mark.asyncio
    async def test_standalone_mode_force_halted(self) -> None:
        """Test standalone mode with force_halted."""
        checker = HaltCheckerStub(force_halted=True, halt_reason="Forced halt")

        assert await checker.is_halted() is True
        assert await checker.get_halt_reason() == "Forced halt"

    @pytest.mark.asyncio
    async def test_standalone_mode_default_reason(self) -> None:
        """Test standalone mode with default reason."""
        checker = HaltCheckerStub(force_halted=True)

        assert await checker.is_halted() is True
        assert await checker.get_halt_reason() == "Stub: Forced halt for testing"

    @pytest.mark.asyncio
    async def test_standalone_mode_not_halted(self) -> None:
        """Test standalone mode not halted."""
        checker = HaltCheckerStub()

        assert await checker.is_halted() is False
        assert await checker.get_halt_reason() is None

    @pytest.mark.asyncio
    async def test_shared_state_takes_precedence(self) -> None:
        """Test shared state takes precedence over force_halted."""
        halt_state = HaltState.get_instance(f"precedence-{uuid4()}")
        checker = HaltCheckerStub(
            halt_state=halt_state, force_halted=False, halt_reason="Standalone reason"
        )

        # Set halt via shared state
        await halt_state.set_halted(True, "Shared state halt")

        # Shared state should take precedence
        assert await checker.is_halted() is True
        assert await checker.get_halt_reason() == "Shared state halt"

    @pytest.mark.asyncio
    async def test_fallback_to_force_halted(self) -> None:
        """Test fallback to force_halted when shared state not halted."""
        halt_state = HaltState.get_instance(f"fallback-{uuid4()}")
        checker = HaltCheckerStub(
            halt_state=halt_state, force_halted=True, halt_reason="Fallback reason"
        )

        # Shared state not halted, but force_halted is True
        assert await checker.is_halted() is True
        assert await checker.get_halt_reason() == "Fallback reason"

    def test_set_halted_helper(self) -> None:
        """Test set_halted helper for standalone mode."""
        checker = HaltCheckerStub()
        checker.set_halted(True, "Helper set")

        # This sets standalone mode, not shared state
        assert checker._force_halted is True
        assert checker._halt_reason == "Helper set"
