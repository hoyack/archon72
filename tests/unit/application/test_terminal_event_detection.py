"""Unit tests for TerminalEventDetector (Story 7.6, FR43, NFR40).

Tests for:
- is_system_terminated() returns False before cessation
- is_system_terminated() returns True after cessation event
- get_terminal_event() returns cessation event
- Caching behavior (result cached after True)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.events.event import Event
from src.infrastructure.adapters.persistence.terminal_event_detector import (
    InMemoryTerminalEventDetector,
    TerminalEventDetector,
)


def create_test_event(
    *,
    event_type: str = "test.event",
    payload: dict | None = None,
    sequence: int = 1,
    local_timestamp: datetime | None = None,
) -> Event:
    """Create a test event."""
    return Event(
        event_id=uuid4(),
        sequence=sequence,
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


def create_terminal_event(
    *,
    sequence: int = 100,
    execution_timestamp: datetime | None = None,
) -> Event:
    """Create a terminal cessation event."""
    ts = execution_timestamp or datetime.now(timezone.utc)
    return Event(
        event_id=uuid4(),
        sequence=sequence,
        event_type="cessation.executed",
        payload={
            "is_terminal": True,
            "execution_timestamp": ts.isoformat(),
            "cessation_id": str(uuid4()),
            "final_sequence_number": sequence,
            "final_hash": "b" * 64,
            "reason": "Test cessation",
            "triggering_event_id": str(uuid4()),
        },
        prev_hash="c" * 64,
        content_hash="d" * 64,
        signature="sig456",
        witness_id="witness-2",
        witness_signature="wsig456",
        local_timestamp=ts,
        agent_id="SYSTEM:CESSATION",
    )


def create_mock_event_store(
    *,
    events_by_type: list | None = None,
    events_by_payload_field: list | None = None,
) -> MagicMock:
    """Create a mock event store with only the methods we configure.

    This creates an object with spec=[] so it doesn't auto-create
    attributes, then we explicitly add only the async methods we need.
    """
    store = MagicMock(spec=[])

    if events_by_payload_field is not None:
        store.get_events_by_payload_field = AsyncMock(return_value=events_by_payload_field)
    elif events_by_type is not None:
        store.get_events_by_type = AsyncMock(return_value=events_by_type)

    return store


class TestTerminalEventDetectorBeforeCessation:
    """Tests for is_system_terminated() before cessation."""

    @pytest.mark.asyncio
    async def test_not_terminated_with_empty_store(self) -> None:
        """is_system_terminated() should return False for empty store."""
        event_store = create_mock_event_store(events_by_type=[])

        detector = TerminalEventDetector(event_store)
        result = await detector.is_system_terminated()

        assert result is False

    @pytest.mark.asyncio
    async def test_not_terminated_with_non_terminal_events(self) -> None:
        """is_system_terminated() should return False without terminal events."""
        event_store = create_mock_event_store(events_by_type=[
            create_test_event(event_type="regular.event", sequence=1),
            create_test_event(event_type="another.event", sequence=2),
        ])

        detector = TerminalEventDetector(event_store)
        result = await detector.is_system_terminated()

        assert result is False

    @pytest.mark.asyncio
    async def test_terminal_event_none_before_cessation(self) -> None:
        """get_terminal_event() should return None before cessation."""
        event_store = create_mock_event_store(events_by_type=[])

        detector = TerminalEventDetector(event_store)
        result = await detector.get_terminal_event()

        assert result is None

    @pytest.mark.asyncio
    async def test_termination_timestamp_none_before_cessation(self) -> None:
        """get_termination_timestamp() should return None before cessation."""
        event_store = create_mock_event_store(events_by_type=[])

        detector = TerminalEventDetector(event_store)
        result = await detector.get_termination_timestamp()

        assert result is None


class TestTerminalEventDetectorAfterCessation:
    """Tests for is_system_terminated() after cessation."""

    @pytest.mark.asyncio
    async def test_terminated_with_terminal_event(self) -> None:
        """is_system_terminated() should return True with terminal event."""
        terminal = create_terminal_event()
        event_store = create_mock_event_store(events_by_type=[terminal])

        detector = TerminalEventDetector(event_store)
        result = await detector.is_system_terminated()

        assert result is True

    @pytest.mark.asyncio
    async def test_get_terminal_event_returns_event(self) -> None:
        """get_terminal_event() should return the terminal event."""
        terminal = create_terminal_event()
        event_store = create_mock_event_store(events_by_type=[terminal])

        detector = TerminalEventDetector(event_store)
        result = await detector.get_terminal_event()

        assert result == terminal

    @pytest.mark.asyncio
    async def test_get_termination_timestamp_from_payload(self) -> None:
        """get_termination_timestamp() should extract from payload."""
        ts = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        terminal = create_terminal_event(execution_timestamp=ts)
        event_store = create_mock_event_store(events_by_type=[terminal])

        detector = TerminalEventDetector(event_store)
        result = await detector.get_termination_timestamp()

        assert result is not None
        assert result.isoformat() == ts.isoformat()


class TestTerminalEventDetectorCaching:
    """Tests for caching behavior (NFR40)."""

    @pytest.mark.asyncio
    async def test_cached_after_first_true(self) -> None:
        """Result should be cached after first True."""
        terminal = create_terminal_event()
        event_store = create_mock_event_store(events_by_type=[terminal])

        detector = TerminalEventDetector(event_store)

        # First call
        result1 = await detector.is_system_terminated()
        assert result1 is True

        # Second call - should use cache, not query
        event_store.get_events_by_type.reset_mock()
        result2 = await detector.is_system_terminated()

        assert result2 is True
        event_store.get_events_by_type.assert_not_called()

    @pytest.mark.asyncio
    async def test_false_not_cached(self) -> None:
        """False results should not be cached (allow re-query)."""
        event_store = create_mock_event_store(events_by_type=[])

        detector = TerminalEventDetector(event_store)

        # First call - False
        result1 = await detector.is_system_terminated()
        assert result1 is False

        # Second call - should still query
        event_store.get_events_by_type.reset_mock()
        result2 = await detector.is_system_terminated()

        assert result2 is False
        event_store.get_events_by_type.assert_called()

    @pytest.mark.asyncio
    async def test_terminal_event_cached(self) -> None:
        """Terminal event should be cached after first retrieval."""
        terminal = create_terminal_event()
        event_store = create_mock_event_store(events_by_type=[terminal])

        detector = TerminalEventDetector(event_store)

        # First call
        event1 = await detector.get_terminal_event()
        assert event1 == terminal

        # Second call - should use cache
        event_store.get_events_by_type.reset_mock()
        event2 = await detector.get_terminal_event()

        assert event2 == terminal
        event_store.get_events_by_type.assert_not_called()


class TestInMemoryTerminalEventDetector:
    """Tests for InMemoryTerminalEventDetector."""

    @pytest.mark.asyncio
    async def test_default_not_terminated(self) -> None:
        """By default, system should not be terminated."""
        detector = InMemoryTerminalEventDetector()
        assert await detector.is_system_terminated() is False

    @pytest.mark.asyncio
    async def test_add_non_terminal_event(self) -> None:
        """Adding non-terminal events should not terminate."""
        detector = InMemoryTerminalEventDetector()
        detector.add_event(create_test_event())

        assert await detector.is_system_terminated() is False

    @pytest.mark.asyncio
    async def test_add_terminal_event_terminates(self) -> None:
        """Adding terminal event should terminate system."""
        detector = InMemoryTerminalEventDetector()
        detector.add_event(create_terminal_event())

        assert await detector.is_system_terminated() is True

    @pytest.mark.asyncio
    async def test_get_terminal_event_after_adding(self) -> None:
        """get_terminal_event() should return the terminal event."""
        terminal = create_terminal_event()
        detector = InMemoryTerminalEventDetector()
        detector.add_event(terminal)

        result = await detector.get_terminal_event()
        assert result == terminal

    @pytest.mark.asyncio
    async def test_clear_for_testing(self) -> None:
        """clear_for_testing() should reset state."""
        detector = InMemoryTerminalEventDetector()
        detector.add_event(create_terminal_event())
        assert await detector.is_system_terminated() is True

        detector.clear_for_testing()

        assert await detector.is_system_terminated() is False
        assert await detector.get_terminal_event() is None


class TestTerminalEventDetectorWithPayloadFieldQuery:
    """Tests for event store with get_events_by_payload_field support."""

    @pytest.mark.asyncio
    async def test_uses_payload_field_query_if_available(self) -> None:
        """Should use get_events_by_payload_field if available."""
        terminal = create_terminal_event()
        event_store = create_mock_event_store(events_by_payload_field=[terminal])

        detector = TerminalEventDetector(event_store)
        result = await detector.is_system_terminated()

        assert result is True
        event_store.get_events_by_payload_field.assert_called_once_with(
            field="is_terminal",
            value="true",
            limit=1,
        )


class TestTerminalEventDetectorTimestampExtraction:
    """Tests for timestamp extraction from different formats."""

    @pytest.mark.asyncio
    async def test_extracts_timestamp_from_string(self) -> None:
        """Should extract timestamp from ISO string in payload."""
        ts = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        terminal = create_terminal_event(execution_timestamp=ts)
        event_store = create_mock_event_store(events_by_type=[terminal])

        detector = TerminalEventDetector(event_store)
        result = await detector.get_termination_timestamp()

        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    @pytest.mark.asyncio
    async def test_fallback_to_local_timestamp(self) -> None:
        """Should fallback to event's local_timestamp if no payload."""
        local_ts = datetime(2024, 6, 16, 12, 0, 0, tzinfo=timezone.utc)
        terminal = Event(
            event_id=uuid4(),
            sequence=100,
            event_type="cessation.executed",
            payload={"is_terminal": True},  # No execution_timestamp
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig",
            witness_id="w1",
            witness_signature="ws1",
            local_timestamp=local_ts,
            agent_id="sys",
        )
        event_store = create_mock_event_store(events_by_type=[terminal])

        detector = TerminalEventDetector(event_store)
        result = await detector.get_termination_timestamp()

        assert result == local_ts
