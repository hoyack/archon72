"""Unit tests for HaltState shared state (Story 3.2, Task 5.6).

Tests the shared halt state module that coordinates between
HaltCheckerStub and HaltTriggerStub.

Constitutional Constraints:
- AC4: HaltChecker reflects halt state after trigger
- Thread-safe state updates
"""

from uuid import uuid4

import pytest

from src.infrastructure.stubs.halt_state import HaltState


class TestHaltStateBasic:
    """Basic tests for HaltState."""

    @pytest.fixture(autouse=True)
    def reset_instances(self) -> None:
        """Reset all instances before each test."""
        HaltState.reset_all()

    def test_initial_state_not_halted(self) -> None:
        """Test initial state is not halted."""
        state = HaltState()
        assert state.is_halted is False
        assert state.halt_reason is None
        assert state.crisis_event_id is None
        assert state.trigger_count == 0

    @pytest.mark.asyncio
    async def test_set_halted_true(self) -> None:
        """Test setting halted to True."""
        state = HaltState()
        await state.set_halted(True, "Test halt reason")

        assert state.is_halted is True
        assert state.halt_reason == "Test halt reason"
        assert state.trigger_count == 1

    @pytest.mark.asyncio
    async def test_set_halted_with_crisis_event_id(self) -> None:
        """Test setting halted with crisis event ID."""
        state = HaltState()
        crisis_id = uuid4()
        await state.set_halted(True, "Crisis halt", crisis_id)

        assert state.is_halted is True
        assert state.halt_reason == "Crisis halt"
        assert state.crisis_event_id == crisis_id

    @pytest.mark.asyncio
    async def test_set_halted_false_clears_state(self) -> None:
        """Test setting halted to False clears state."""
        state = HaltState()
        await state.set_halted(True, "Test halt")
        await state.set_halted(False)

        assert state.is_halted is False
        assert state.halt_reason is None
        assert state.crisis_event_id is None

    @pytest.mark.asyncio
    async def test_set_halted_requires_reason(self) -> None:
        """Test setting halted=True requires reason."""
        state = HaltState()
        with pytest.raises(ValueError, match="Reason required"):
            await state.set_halted(True, None)

    @pytest.mark.asyncio
    async def test_trigger_count_increments_on_new_halts(self) -> None:
        """Test trigger count only increments on new halts."""
        state = HaltState()

        # First halt
        await state.set_halted(True, "Halt 1")
        assert state.trigger_count == 1

        # Clear halt
        await state.set_halted(False)
        assert state.trigger_count == 1  # Should not change

        # Second halt
        await state.set_halted(True, "Halt 2")
        assert state.trigger_count == 2

    @pytest.mark.asyncio
    async def test_repeated_halt_while_halted_does_not_increment(self) -> None:
        """Test repeated halt while already halted doesn't increment count."""
        state = HaltState()
        await state.set_halted(True, "Halt 1")
        await state.set_halted(True, "Halt 2")  # Already halted

        assert state.trigger_count == 1
        assert state.halt_reason == "Halt 2"  # Reason should update


class TestHaltStateSyncMethods:
    """Tests for synchronous methods."""

    @pytest.fixture(autouse=True)
    def reset_instances(self) -> None:
        """Reset all instances before each test."""
        HaltState.reset_all()

    def test_set_halted_sync(self) -> None:
        """Test synchronous set_halted."""
        state = HaltState()
        crisis_id = uuid4()
        state.set_halted_sync(True, "Sync halt", crisis_id)

        assert state.is_halted is True
        assert state.halt_reason == "Sync halt"
        assert state.crisis_event_id == crisis_id
        assert state.trigger_count == 1

    def test_set_halted_sync_requires_reason(self) -> None:
        """Test set_halted_sync requires reason when halted=True."""
        state = HaltState()
        with pytest.raises(ValueError, match="Reason required"):
            state.set_halted_sync(True)

    def test_reset(self) -> None:
        """Test reset clears all state."""
        state = HaltState()
        state.set_halted_sync(True, "Test halt", uuid4())
        state.reset()

        assert state.is_halted is False
        assert state.halt_reason is None
        assert state.crisis_event_id is None
        assert state.trigger_count == 0


class TestHaltStateInstances:
    """Tests for named instance management."""

    @pytest.fixture(autouse=True)
    def reset_instances(self) -> None:
        """Reset all instances before each test."""
        HaltState.reset_all()

    def test_get_instance_creates_new(self) -> None:
        """Test get_instance creates new instance if not exists."""
        state = HaltState.get_instance("test-1")
        assert state is not None
        assert state.is_halted is False

    def test_get_instance_returns_same(self) -> None:
        """Test get_instance returns same instance for same name."""
        state1 = HaltState.get_instance("test-1")
        state2 = HaltState.get_instance("test-1")
        assert state1 is state2

    def test_get_instance_different_names(self) -> None:
        """Test different names get different instances."""
        state1 = HaltState.get_instance("test-1")
        state2 = HaltState.get_instance("test-2")
        assert state1 is not state2

    @pytest.mark.asyncio
    async def test_instances_are_isolated(self) -> None:
        """Test named instances are isolated."""
        state1 = HaltState.get_instance("test-1")
        state2 = HaltState.get_instance("test-2")

        await state1.set_halted(True, "Halt instance 1")

        assert state1.is_halted is True
        assert state2.is_halted is False

    def test_reset_all_clears_instances(self) -> None:
        """Test reset_all clears all instances."""
        state1 = HaltState.get_instance("test-1")
        state2 = HaltState.get_instance("test-2")

        HaltState.reset_all()

        new_state1 = HaltState.get_instance("test-1")
        new_state2 = HaltState.get_instance("test-2")

        assert new_state1 is not state1
        assert new_state2 is not state2

    def test_reset_instance(self) -> None:
        """Test reset_instance clears specific instance."""
        state1 = HaltState.get_instance("test-1")
        state2 = HaltState.get_instance("test-2")

        HaltState.reset_instance("test-1")

        new_state1 = HaltState.get_instance("test-1")
        assert new_state1 is not state1
        assert HaltState.get_instance("test-2") is state2

    def test_default_instance_name(self) -> None:
        """Test default instance name is 'default'."""
        state1 = HaltState.get_instance()
        state2 = HaltState.get_instance("default")
        assert state1 is state2
