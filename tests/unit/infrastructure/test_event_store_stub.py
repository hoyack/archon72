"""Unit tests for EventStoreStub (Story 4.3, Task 4).

Tests the in-memory event store stub implementation.

Constitutional Constraints Tested:
- FR46: Query interface supports date range and event type filtering
- FR102: Append-only enforcement
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events import Event
from src.infrastructure.stubs.event_store_stub import EventStoreStub


def _make_event(
    sequence: int,
    event_type: str = "test.event",
    authority_timestamp: datetime | None = None,
) -> Event:
    """Create a test event with the given parameters."""
    if authority_timestamp is None:
        authority_timestamp = datetime.now(timezone.utc)

    return Event(
        event_id=uuid4(),
        sequence=sequence,
        event_type=event_type,
        payload={"test": "data"},
        prev_hash="0" * 64,
        content_hash="a" * 64,
        signature="sig123",
        hash_alg_version=1,
        sig_alg_version=1,
        agent_id="test-agent",
        witness_id="test-witness",
        witness_signature="wsig123",
        local_timestamp=datetime.now(timezone.utc),
        authority_timestamp=authority_timestamp,
    )


class TestEventStoreStubBasicOperations:
    """Basic stub operations tests."""

    @pytest.fixture
    def stub(self) -> EventStoreStub:
        """Create a fresh stub for each test."""
        return EventStoreStub()

    @pytest.mark.asyncio
    async def test_append_and_get_event(self, stub: EventStoreStub) -> None:
        """Append event and retrieve by ID."""
        event = _make_event(sequence=1)
        await stub.append_event(event)

        retrieved = await stub.get_event_by_id(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_get_event_by_sequence(self, stub: EventStoreStub) -> None:
        """Get event by sequence number."""
        event = _make_event(sequence=42)
        await stub.append_event(event)

        retrieved = await stub.get_event_by_sequence(42)
        assert retrieved is not None
        assert retrieved.sequence == 42

    @pytest.mark.asyncio
    async def test_count_events(self, stub: EventStoreStub) -> None:
        """Count events in store."""
        assert await stub.count_events() == 0

        await stub.append_event(_make_event(sequence=1))
        await stub.append_event(_make_event(sequence=2))

        assert await stub.count_events() == 2


class TestEventStoreStubFilteredQueries:
    """Tests for filtered query methods (FR46)."""

    @pytest.fixture
    def stub_with_events(self) -> EventStoreStub:
        """Create stub with test events."""
        stub = EventStoreStub()

        # Create events with different types and dates
        base_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        events = [
            _make_event(1, "vote", base_time),
            _make_event(2, "vote", base_time + timedelta(hours=1)),
            _make_event(3, "halt", base_time + timedelta(hours=2)),
            _make_event(4, "breach", base_time + timedelta(days=1)),
            _make_event(5, "vote", base_time + timedelta(days=2)),
        ]

        for event in events:
            stub.add_event(event)

        return stub

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_no_filter(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Get all events when no filters applied."""
        events = await stub_with_events.get_events_filtered()
        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_by_start_date(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter events from start date."""
        start = datetime(2026, 1, 16, 0, 0, 0, tzinfo=timezone.utc)
        events = await stub_with_events.get_events_filtered(start_date=start)

        assert len(events) == 2  # Events on Jan 16 and 17
        for event in events:
            assert event.authority_timestamp >= start

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_by_end_date(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter events until end date."""
        end = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
        events = await stub_with_events.get_events_filtered(end_date=end)

        assert len(events) == 3  # Events on Jan 15
        for event in events:
            assert event.authority_timestamp <= end

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_by_date_range(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter events within date range."""
        start = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)

        events = await stub_with_events.get_events_filtered(
            start_date=start, end_date=end
        )

        # Events 1, 2, 3 on Jan 15, event 4 at start of Jan 16
        assert len(events) == 4
        for event in events:
            assert start <= event.authority_timestamp <= end

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_by_single_type(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter events by single event type."""
        events = await stub_with_events.get_events_filtered(event_types=["vote"])

        assert len(events) == 3
        for event in events:
            assert event.event_type == "vote"

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_by_multiple_types(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter events by multiple types (OR logic)."""
        events = await stub_with_events.get_events_filtered(
            event_types=["vote", "halt"]
        )

        assert len(events) == 4  # 3 votes + 1 halt
        for event in events:
            assert event.event_type in ["vote", "halt"]

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_combined(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter with both date range and type (AND logic)."""
        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)

        events = await stub_with_events.get_events_filtered(
            start_date=start,
            end_date=end,
            event_types=["vote"],
        )

        assert len(events) == 2  # Only votes on Jan 15
        for event in events:
            assert event.event_type == "vote"
            assert start <= event.authority_timestamp <= end

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_with_pagination(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter with pagination."""
        # Get first 2 events
        page1 = await stub_with_events.get_events_filtered(limit=2, offset=0)
        assert len(page1) == 2
        assert page1[0].sequence == 1
        assert page1[1].sequence == 2

        # Get next 2 events
        page2 = await stub_with_events.get_events_filtered(limit=2, offset=2)
        assert len(page2) == 2
        assert page2[0].sequence == 3
        assert page2[1].sequence == 4

    @pytest.mark.asyncio
    async def test_stub_count_events_filtered(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Count filtered events."""
        # No filter
        assert await stub_with_events.count_events_filtered() == 5

        # By type
        assert (
            await stub_with_events.count_events_filtered(event_types=["vote"]) == 3
        )

        # By date range
        start = datetime(2026, 1, 16, 0, 0, 0, tzinfo=timezone.utc)
        assert await stub_with_events.count_events_filtered(start_date=start) == 2

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_empty_result(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filter that matches no events."""
        events = await stub_with_events.get_events_filtered(
            event_types=["nonexistent.type"]
        )
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_stub_get_events_filtered_ordered_by_sequence(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """Filtered events should be ordered by sequence."""
        events = await stub_with_events.get_events_filtered()

        sequences = [e.sequence for e in events]
        assert sequences == sorted(sequences)


class TestEventStoreStubOrphaning:
    """Tests for orphaning behavior with filters."""

    @pytest.fixture
    def stub(self) -> EventStoreStub:
        """Create stub with events."""
        stub = EventStoreStub()
        for i in range(1, 6):
            stub.add_event(_make_event(sequence=i, event_type="test"))
        return stub

    @pytest.mark.asyncio
    async def test_filtered_queries_exclude_orphaned(
        self, stub: EventStoreStub
    ) -> None:
        """Orphaned events should be excluded from filtered queries."""
        # Mark events 3-4 as orphaned
        await stub.mark_events_orphaned(3, 5)

        events = await stub.get_events_filtered()
        assert len(events) == 3  # 1, 2, 5 remain
        sequences = [e.sequence for e in events]
        assert 3 not in sequences
        assert 4 not in sequences

    @pytest.mark.asyncio
    async def test_count_filtered_excludes_orphaned(
        self, stub: EventStoreStub
    ) -> None:
        """Count should exclude orphaned events."""
        await stub.mark_events_orphaned(3, 5)

        count = await stub.count_events_filtered()
        assert count == 3


# =============================================================================
# Tests for Historical Query Methods (Story 4.5, Task 4 - FR88, FR89)
# =============================================================================


class TestEventStoreStubHistoricalQueries:
    """Tests for EventStoreStub historical query methods (Story 4.5, Task 4).

    Constitutional Constraints:
    - FR88: Query for state as of any sequence number or timestamp
    - FR89: Historical queries return hash chain proof to current head
    """

    @pytest.fixture
    def stub_with_events(self) -> EventStoreStub:
        """Create stub with test events spanning multiple days."""
        stub = EventStoreStub()

        # Create events with increasing timestamps
        base_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(1, 11):  # 10 events
            stub.add_event(
                _make_event(
                    sequence=i,
                    event_type="test.event",
                    authority_timestamp=base_time + timedelta(hours=i),
                )
            )

        return stub

    @pytest.mark.asyncio
    async def test_stub_get_events_up_to_sequence_returns_filtered(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """get_events_up_to_sequence returns events with sequence <= max."""
        events = await stub_with_events.get_events_up_to_sequence(max_sequence=5)

        assert len(events) == 5
        for event in events:
            assert event.sequence <= 5

    @pytest.mark.asyncio
    async def test_stub_get_events_up_to_sequence_respects_limit_offset(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """get_events_up_to_sequence respects limit and offset parameters."""
        # Get first 3 events up to sequence 5
        events = await stub_with_events.get_events_up_to_sequence(
            max_sequence=5, limit=3, offset=0
        )
        assert len(events) == 3
        assert [e.sequence for e in events] == [1, 2, 3]

        # Get next 3 (only 2 available)
        events = await stub_with_events.get_events_up_to_sequence(
            max_sequence=5, limit=3, offset=3
        )
        assert len(events) == 2
        assert [e.sequence for e in events] == [4, 5]

    @pytest.mark.asyncio
    async def test_stub_get_events_up_to_sequence_1_returns_first(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """get_events_up_to_sequence=1 returns only first event."""
        events = await stub_with_events.get_events_up_to_sequence(max_sequence=1)

        assert len(events) == 1
        assert events[0].sequence == 1

    @pytest.mark.asyncio
    async def test_stub_get_events_up_to_sequence_excludes_orphaned(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """get_events_up_to_sequence excludes orphaned events."""
        # Mark events 3-4 as orphaned
        await stub_with_events.mark_events_orphaned(3, 5)

        events = await stub_with_events.get_events_up_to_sequence(max_sequence=5)

        # Should have 3 events: 1, 2, 5 (3 and 4 are orphaned)
        sequences = [e.sequence for e in events]
        assert 3 not in sequences
        assert 4 not in sequences

    @pytest.mark.asyncio
    async def test_stub_count_events_up_to_sequence(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """count_events_up_to_sequence returns correct count."""
        assert await stub_with_events.count_events_up_to_sequence(max_sequence=5) == 5
        assert await stub_with_events.count_events_up_to_sequence(max_sequence=10) == 10
        assert await stub_with_events.count_events_up_to_sequence(max_sequence=1) == 1

    @pytest.mark.asyncio
    async def test_stub_count_events_up_to_sequence_excludes_orphaned(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """count_events_up_to_sequence excludes orphaned events."""
        await stub_with_events.mark_events_orphaned(3, 5)

        # 5 events total up to seq 5, minus 2 orphaned = 3
        assert await stub_with_events.count_events_up_to_sequence(max_sequence=5) == 3

    @pytest.mark.asyncio
    async def test_stub_find_sequence_for_timestamp(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """find_sequence_for_timestamp finds correct sequence."""
        # Base time is 2026-01-15 12:00:00, each event adds 1 hour
        # Event 1: 13:00, Event 2: 14:00, Event 3: 15:00, etc.

        # Timestamp between event 3 and 4 should return sequence 3
        timestamp = datetime(2026, 1, 15, 15, 30, 0, tzinfo=timezone.utc)
        seq = await stub_with_events.find_sequence_for_timestamp(timestamp)
        assert seq == 3

    @pytest.mark.asyncio
    async def test_stub_find_sequence_for_timestamp_exact_match(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """find_sequence_for_timestamp returns exact match."""
        # Exact timestamp of event 5 (12:00 + 5 hours = 17:00)
        timestamp = datetime(2026, 1, 15, 17, 0, 0, tzinfo=timezone.utc)
        seq = await stub_with_events.find_sequence_for_timestamp(timestamp)
        assert seq == 5

    @pytest.mark.asyncio
    async def test_stub_find_sequence_for_timestamp_no_events_before(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """find_sequence_for_timestamp returns None if no events before timestamp."""
        # Timestamp before any events
        timestamp = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        seq = await stub_with_events.find_sequence_for_timestamp(timestamp)
        assert seq is None

    @pytest.mark.asyncio
    async def test_stub_find_sequence_for_timestamp_after_all(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """find_sequence_for_timestamp returns last sequence if after all events."""
        # Timestamp after all events
        timestamp = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        seq = await stub_with_events.find_sequence_for_timestamp(timestamp)
        assert seq == 10  # Last event

    @pytest.mark.asyncio
    async def test_stub_find_sequence_for_timestamp_excludes_orphaned(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """find_sequence_for_timestamp excludes orphaned events."""
        # Mark events 3-5 as orphaned
        await stub_with_events.mark_events_orphaned(3, 6)

        # Timestamp between event 4 and 5 (both orphaned)
        # Should skip to event 2 (last non-orphaned before timestamp)
        timestamp = datetime(2026, 1, 15, 16, 30, 0, tzinfo=timezone.utc)
        seq = await stub_with_events.find_sequence_for_timestamp(timestamp)
        assert seq == 2  # Last non-orphaned before timestamp


# =============================================================================
# Tests for Streaming Export Methods (Story 4.7, Task 4 - FR139)
# =============================================================================


class TestEventStoreStubStreamingExport:
    """Tests for EventStoreStub streaming export methods (Story 4.7, Task 4).

    Constitutional Constraints:
    - FR139: Export SHALL support structured audit format
    """

    @pytest.fixture
    def stub_with_events(self) -> EventStoreStub:
        """Create stub with test events for streaming tests."""
        stub = EventStoreStub()
        base_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(1, 11):
            event_type = "vote" if i <= 5 else "halt"
            event = _make_event(
                sequence=i,
                event_type=event_type,
                authority_timestamp=base_time + timedelta(hours=i),
            )
            stub.add_event(event)

        return stub

    @pytest.mark.asyncio
    async def test_stream_events_yields_all_events(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """stream_events yields all events when no filters."""
        events = []
        async for event in stub_with_events.stream_events():
            events.append(event)

        assert len(events) == 10

    @pytest.mark.asyncio
    async def test_stream_events_ordered_by_sequence(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """stream_events yields events in sequence order."""
        events = []
        async for event in stub_with_events.stream_events():
            events.append(event)

        sequences = [e.sequence for e in events]
        assert sequences == list(range(1, 11))

    @pytest.mark.asyncio
    async def test_stream_events_with_sequence_range(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """stream_events respects sequence range filters."""
        events = []
        async for event in stub_with_events.stream_events(
            start_sequence=3, end_sequence=7
        ):
            events.append(event)

        assert len(events) == 5
        sequences = [e.sequence for e in events]
        assert sequences == [3, 4, 5, 6, 7]

    @pytest.mark.asyncio
    async def test_stream_events_with_event_types(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """stream_events filters by event types."""
        events = []
        async for event in stub_with_events.stream_events(event_types=["vote"]):
            events.append(event)

        assert len(events) == 5
        for e in events:
            assert e.event_type == "vote"

    @pytest.mark.asyncio
    async def test_stream_events_with_date_range(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """stream_events filters by date range."""
        start = datetime(2026, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, 18, 0, 0, tzinfo=timezone.utc)

        events = []
        async for event in stub_with_events.stream_events(
            start_date=start, end_date=end
        ):
            events.append(event)

        # Events 3, 4, 5, 6 should be in this range (15:00-18:00)
        assert len(events) == 4

    @pytest.mark.asyncio
    async def test_stream_events_excludes_orphaned(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """stream_events excludes orphaned events."""
        await stub_with_events.mark_events_orphaned(3, 6)

        events = []
        async for event in stub_with_events.stream_events():
            events.append(event)

        # 10 total - 3 orphaned (3, 4, 5) = 7
        assert len(events) == 7
        sequences = [e.sequence for e in events]
        assert 3 not in sequences
        assert 4 not in sequences
        assert 5 not in sequences

    @pytest.mark.asyncio
    async def test_stream_events_empty_store(self) -> None:
        """stream_events yields nothing for empty store."""
        stub = EventStoreStub()

        events = []
        async for event in stub.stream_events():
            events.append(event)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_count_events_in_range_basic(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """count_events_in_range counts events in range."""
        count = await stub_with_events.count_events_in_range(
            start_sequence=1, end_sequence=10
        )
        assert count == 10

    @pytest.mark.asyncio
    async def test_count_events_in_range_partial(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """count_events_in_range counts partial range."""
        count = await stub_with_events.count_events_in_range(
            start_sequence=3, end_sequence=7
        )
        assert count == 5

    @pytest.mark.asyncio
    async def test_count_events_in_range_excludes_orphaned(
        self, stub_with_events: EventStoreStub
    ) -> None:
        """count_events_in_range excludes orphaned events."""
        await stub_with_events.mark_events_orphaned(3, 6)

        count = await stub_with_events.count_events_in_range(
            start_sequence=1, end_sequence=10
        )
        # 10 total - 3 orphaned = 7
        assert count == 7
