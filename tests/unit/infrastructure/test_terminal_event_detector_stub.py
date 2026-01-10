"""Unit tests for TerminalEventDetectorStub (Story 7.3, FR40, NFR40).

Tests for:
- Default state (not terminated)
- set_terminated() behavior
- clear_termination() for test isolation
- Timestamp extraction from event payload
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.event import Event
from src.infrastructure.stubs.terminal_event_detector_stub import (
    TerminalEventDetectorStub,
)


def create_test_event(
    *,
    event_type: str = "cessation.executed",
    payload: dict | None = None,
    local_timestamp: datetime | None = None,
) -> Event:
    """Create a test event for stub testing."""
    return Event(
        event_id=uuid4(),
        sequence=1,
        event_type=event_type,
        payload=payload or {},
        prev_hash="0" * 64,
        content_hash="a" * 64,
        signature="sig123",
        witness_id="witness-1",
        witness_signature="wsig123",
        local_timestamp=local_timestamp or datetime.now(timezone.utc),
        agent_id="test-agent",
    )


class TestTerminalEventDetectorStubDefaults:
    """Tests for default stub state."""

    @pytest.mark.asyncio
    async def test_default_not_terminated(self) -> None:
        """By default, system should not be terminated."""
        stub = TerminalEventDetectorStub()
        assert await stub.is_system_terminated() is False

    @pytest.mark.asyncio
    async def test_default_no_terminal_event(self) -> None:
        """By default, terminal event should be None."""
        stub = TerminalEventDetectorStub()
        assert await stub.get_terminal_event() is None

    @pytest.mark.asyncio
    async def test_default_no_termination_timestamp(self) -> None:
        """By default, termination timestamp should be None."""
        stub = TerminalEventDetectorStub()
        assert await stub.get_termination_timestamp() is None


class TestSetTerminated:
    """Tests for set_terminated() method."""

    @pytest.mark.asyncio
    async def test_set_terminated_makes_system_terminated(self) -> None:
        """set_terminated() should make is_system_terminated() return True."""
        stub = TerminalEventDetectorStub()
        event = create_test_event()

        stub.set_terminated(event)

        assert await stub.is_system_terminated() is True

    @pytest.mark.asyncio
    async def test_set_terminated_stores_event(self) -> None:
        """set_terminated() should store the terminal event."""
        stub = TerminalEventDetectorStub()
        event = create_test_event()

        stub.set_terminated(event)

        stored_event = await stub.get_terminal_event()
        assert stored_event is event

    @pytest.mark.asyncio
    async def test_set_terminated_with_explicit_timestamp(self) -> None:
        """set_terminated() should use explicit timestamp if provided."""
        stub = TerminalEventDetectorStub()
        event = create_test_event()
        explicit_ts = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        stub.set_terminated(event, timestamp=explicit_ts)

        assert await stub.get_termination_timestamp() == explicit_ts

    @pytest.mark.asyncio
    async def test_set_terminated_extracts_timestamp_from_payload(self) -> None:
        """set_terminated() should extract timestamp from payload."""
        stub = TerminalEventDetectorStub()
        execution_timestamp = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = create_test_event(
            payload={"execution_timestamp": execution_timestamp.isoformat()}
        )

        stub.set_terminated(event)

        result_ts = await stub.get_termination_timestamp()
        # Compare as ISO strings since parsing might drop tzinfo
        assert result_ts is not None
        assert result_ts.isoformat() == execution_timestamp.isoformat()

    @pytest.mark.asyncio
    async def test_set_terminated_extracts_datetime_from_payload(self) -> None:
        """set_terminated() should handle datetime objects in payload."""
        stub = TerminalEventDetectorStub()
        execution_timestamp = datetime(2024, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        event = create_test_event(
            payload={"execution_timestamp": execution_timestamp}
        )

        stub.set_terminated(event)

        assert await stub.get_termination_timestamp() == execution_timestamp

    @pytest.mark.asyncio
    async def test_set_terminated_fallback_to_local_timestamp(self) -> None:
        """set_terminated() should fallback to event's local_timestamp."""
        stub = TerminalEventDetectorStub()
        local_ts = datetime(2024, 6, 15, 16, 0, 0, tzinfo=timezone.utc)
        event = create_test_event(
            payload={},  # No execution_timestamp
            local_timestamp=local_ts,
        )

        stub.set_terminated(event)

        assert await stub.get_termination_timestamp() == local_ts


class TestClearTermination:
    """Tests for clear_termination() method."""

    @pytest.mark.asyncio
    async def test_clear_termination_resets_state(self) -> None:
        """clear_termination() should reset to not terminated."""
        stub = TerminalEventDetectorStub()
        event = create_test_event()
        stub.set_terminated(event)

        stub.clear_termination()

        assert await stub.is_system_terminated() is False

    @pytest.mark.asyncio
    async def test_clear_termination_clears_event(self) -> None:
        """clear_termination() should clear the terminal event."""
        stub = TerminalEventDetectorStub()
        event = create_test_event()
        stub.set_terminated(event)

        stub.clear_termination()

        assert await stub.get_terminal_event() is None

    @pytest.mark.asyncio
    async def test_clear_termination_clears_timestamp(self) -> None:
        """clear_termination() should clear the timestamp."""
        stub = TerminalEventDetectorStub()
        event = create_test_event()
        stub.set_terminated(event)

        stub.clear_termination()

        assert await stub.get_termination_timestamp() is None

    @pytest.mark.asyncio
    async def test_multiple_set_clear_cycles(self) -> None:
        """Should support multiple set/clear cycles."""
        stub = TerminalEventDetectorStub()

        for i in range(3):
            # Not terminated
            assert await stub.is_system_terminated() is False

            # Set terminated
            event = create_test_event()
            stub.set_terminated(event)
            assert await stub.is_system_terminated() is True

            # Clear
            stub.clear_termination()
            assert await stub.is_system_terminated() is False


class TestSetTerminatedSimple:
    """Tests for set_terminated_simple() method."""

    @pytest.mark.asyncio
    async def test_simple_termination_no_event(self) -> None:
        """set_terminated_simple() should terminate without event."""
        stub = TerminalEventDetectorStub()

        stub.set_terminated_simple()

        assert await stub.is_system_terminated() is True
        assert await stub.get_terminal_event() is None

    @pytest.mark.asyncio
    async def test_simple_termination_with_timestamp(self) -> None:
        """set_terminated_simple() should use provided timestamp."""
        stub = TerminalEventDetectorStub()
        ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

        stub.set_terminated_simple(timestamp=ts)

        assert await stub.get_termination_timestamp() == ts

    @pytest.mark.asyncio
    async def test_simple_termination_default_timestamp(self) -> None:
        """set_terminated_simple() should set a timestamp if none provided."""
        stub = TerminalEventDetectorStub()
        before = datetime.utcnow()

        stub.set_terminated_simple()

        ts = await stub.get_termination_timestamp()
        after = datetime.utcnow()

        assert ts is not None
        assert before <= ts <= after


class TestStubIsolation:
    """Tests for stub isolation in testing scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_stubs_are_independent(self) -> None:
        """Different stub instances should be independent."""
        stub1 = TerminalEventDetectorStub()
        stub2 = TerminalEventDetectorStub()

        stub1.set_terminated_simple()

        assert await stub1.is_system_terminated() is True
        assert await stub2.is_system_terminated() is False

    @pytest.mark.asyncio
    async def test_stub_in_fixture_pattern(self) -> None:
        """Stub should work with pytest fixture pattern."""
        # Simulating a fixture that creates fresh stub
        def create_detector() -> TerminalEventDetectorStub:
            return TerminalEventDetectorStub()

        # Test 1
        detector = create_detector()
        assert await detector.is_system_terminated() is False
        detector.set_terminated_simple()
        assert await detector.is_system_terminated() is True

        # Test 2 (fresh instance)
        detector = create_detector()
        assert await detector.is_system_terminated() is False  # Should be fresh
