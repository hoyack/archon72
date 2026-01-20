"""Event Store stub for testing (Story 4.3, Task 4; Story 4.5, Task 4; Story 8.2).

In-memory implementation of EventStorePort for unit testing.
Supports filtered queries per FR46 and historical queries per FR88/FR89.

Constitutional Constraints:
- FR102: Append-only enforcement (no delete/update)
- FR46: Query interface supports date range and event type filtering
- FR88: Query for state as of any sequence number or timestamp
- FR89: Historical queries return hash chain proof to current head
- FR52: Operational-Constitutional Separation (Story 8.2)
  - Validates event types before appending
  - Rejects operational metric types (uptime, latency, etc.)
  - Only constitutional event types allowed
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from src.application.ports.event_store import EventStorePort
from src.domain.errors.separation import OperationalToEventStoreError
from src.domain.models.event_type_registry import EventTypeRegistry

if TYPE_CHECKING:
    from src.domain.events import Event


class EventStoreStub(EventStorePort):
    """In-memory event store implementation for testing.

    Stores events in a dictionary keyed by event_id.
    Implements all EventStorePort methods including filtered queries.
    """

    def __init__(self) -> None:
        """Initialize empty event store."""
        self._events: dict[UUID, Event] = {}
        self._head_sequence: int = 0
        self._orphaned_sequences: set[int] = set()

    def _get_non_orphaned_events(self) -> list["Event"]:
        """Get all non-orphaned events sorted by sequence."""
        return sorted(
            [
                e
                for e in self._events.values()
                if e.sequence not in self._orphaned_sequences
            ],
            key=lambda e: e.sequence,
        )

    async def append_event(self, event: "Event") -> "Event":
        """Append event to the in-memory store.

        Validates event type per FR52 - only constitutional types allowed.

        Args:
            event: The event to append.

        Returns:
            The appended event.

        Raises:
            OperationalToEventStoreError: If event type is operational.
        """
        # FR52: Validate event type is constitutional
        if EventTypeRegistry.is_operational_type(event.event_type):
            raise OperationalToEventStoreError(
                data_type=event.event_type,
                intended_target="event_store",
                correct_target="prometheus",
            )

        self._events[event.event_id] = event
        if event.sequence > self._head_sequence:
            self._head_sequence = event.sequence
        return event

    async def get_latest_event(self) -> "Event | None":
        """Get the most recent non-orphaned event."""
        events = self._get_non_orphaned_events()
        return events[-1] if events else None

    async def get_event_by_sequence(self, sequence: int) -> "Event | None":
        """Get event by sequence number."""
        for event in self._events.values():
            if event.sequence == sequence and sequence not in self._orphaned_sequences:
                return event
        return None

    async def get_event_by_id(self, event_id: UUID) -> "Event | None":
        """Get event by ID."""
        event = self._events.get(event_id)
        if event and event.sequence not in self._orphaned_sequences:
            return event
        return None

    async def get_events_by_type(
        self,
        event_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list["Event"]:
        """Get events filtered by type."""
        events = self._get_non_orphaned_events()
        filtered = [e for e in events if e.event_type == event_type]
        return filtered[offset : offset + limit]

    async def count_events(self) -> int:
        """Get total count of non-orphaned events."""
        return len(self._get_non_orphaned_events())

    # =========================================================================
    # Filtered Query Methods (Story 4.3 - FR46)
    # =========================================================================

    async def get_events_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> list["Event"]:
        """Get events with optional filters (FR46).

        Filters combine with AND logic. Event types use OR within the list.
        """
        # Start with all non-orphaned events ordered by sequence
        filtered = self._get_non_orphaned_events()

        # Apply date range filter on authority_timestamp
        if start_date:
            filtered = [
                e
                for e in filtered
                if e.authority_timestamp is not None
                and e.authority_timestamp >= start_date
            ]
        if end_date:
            filtered = [
                e
                for e in filtered
                if e.authority_timestamp is not None
                and e.authority_timestamp <= end_date
            ]

        # Apply event type filter (OR within types)
        if event_types:
            filtered = [e for e in filtered if e.event_type in event_types]

        # Apply pagination
        return filtered[offset : offset + limit]

    async def count_events_filtered(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> int:
        """Count events matching filters (FR46)."""
        # Reuse filter logic with no pagination
        events = await self.get_events_filtered(
            limit=len(self._events) + 1,  # Large limit to get all
            offset=0,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )
        return len(events)

    # =========================================================================
    # Observer Query Methods (Story 1.5)
    # =========================================================================

    async def get_max_sequence(self) -> int:
        """Get current maximum sequence number."""
        events = self._get_non_orphaned_events()
        return events[-1].sequence if events else 0

    async def get_events_by_sequence_range(
        self,
        start: int,
        end: int,
    ) -> list["Event"]:
        """Get events within sequence range."""
        events = self._get_non_orphaned_events()
        return [e for e in events if start <= e.sequence <= end]

    async def verify_sequence_continuity(
        self,
        start: int,
        end: int,
    ) -> tuple[bool, list[int]]:
        """Verify no gaps in sequence range."""
        events = await self.get_events_by_sequence_range(start, end)
        sequences = {e.sequence for e in events}
        expected = set(range(start, end + 1))
        missing = sorted(expected - sequences)
        return len(missing) == 0, missing

    # =========================================================================
    # Orphaning Methods (Story 3.10)
    # =========================================================================

    async def mark_events_orphaned(
        self,
        start_sequence: int,
        end_sequence: int,
    ) -> int:
        """Mark events in range as orphaned."""
        count = 0
        for event in self._events.values():
            if start_sequence <= event.sequence < end_sequence:
                self._orphaned_sequences.add(event.sequence)
                count += 1
        return count

    async def get_head_sequence(self) -> int:
        """Get current HEAD sequence."""
        return self._head_sequence

    async def set_head_sequence(self, sequence: int) -> None:
        """Set HEAD to specific sequence."""
        if sequence < 0:
            raise ValueError("Sequence must be non-negative")
        self._head_sequence = sequence

    async def get_events_by_sequence_range_with_orphaned(
        self,
        start: int,
        end: int,
        include_orphaned: bool = False,
    ) -> list["Event"]:
        """Get events with orphaned flag control."""
        if include_orphaned:
            events = sorted(self._events.values(), key=lambda e: e.sequence)
        else:
            events = self._get_non_orphaned_events()
        return [e for e in events if start <= e.sequence <= end]

    # =========================================================================
    # Historical Query Methods (Story 4.5 - FR88, FR89)
    # =========================================================================

    async def get_events_up_to_sequence(
        self,
        max_sequence: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list["Event"]:
        """Get events with sequence <= max_sequence (FR88).

        Returns non-orphaned events up to the specified sequence.
        """
        events = self._get_non_orphaned_events()
        filtered = [e for e in events if e.sequence <= max_sequence]
        return filtered[offset : offset + limit]

    async def count_events_up_to_sequence(
        self,
        max_sequence: int,
    ) -> int:
        """Count events with sequence <= max_sequence (FR88)."""
        events = self._get_non_orphaned_events()
        return len([e for e in events if e.sequence <= max_sequence])

    async def find_sequence_for_timestamp(
        self,
        timestamp: datetime,
    ) -> int | None:
        """Find sequence number for last event before timestamp (FR88).

        Returns the sequence of the last event whose authority_timestamp
        is <= timestamp, or None if no events exist before that time.
        """
        events = self._get_non_orphaned_events()

        # Find all events with authority_timestamp <= timestamp
        matching = [
            e
            for e in events
            if e.authority_timestamp is not None
            and e.authority_timestamp <= timestamp
        ]

        if not matching:
            return None

        # Return the sequence of the last matching event (highest timestamp)
        return max(matching, key=lambda e: e.authority_timestamp).sequence

    # =========================================================================
    # Test Helpers
    # =========================================================================

    def clear(self) -> None:
        """Clear all events (for test setup/teardown)."""
        self._events.clear()
        self._head_sequence = 0
        self._orphaned_sequences.clear()

    def add_event(self, event: "Event") -> None:
        """Synchronous helper to add event for test setup."""
        self._events[event.event_id] = event
        if event.sequence > self._head_sequence:
            self._head_sequence = event.sequence

    # =========================================================================
    # Streaming Export Methods (Story 4.7 - FR139)
    # =========================================================================

    async def stream_events(
        self,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[str] | None = None,
        batch_size: int = 100,
    ) -> AsyncIterator["Event"]:
        """Stream events matching criteria for export (FR139).

        Yields events in batches for memory-efficient export.
        """
        events = self._get_non_orphaned_events()

        # Apply sequence range filter
        if start_sequence is not None:
            events = [e for e in events if e.sequence >= start_sequence]
        if end_sequence is not None:
            events = [e for e in events if e.sequence <= end_sequence]

        # Apply date filter
        if start_date is not None:
            events = [
                e
                for e in events
                if e.authority_timestamp is not None
                and e.authority_timestamp >= start_date
            ]
        if end_date is not None:
            events = [
                e
                for e in events
                if e.authority_timestamp is not None
                and e.authority_timestamp <= end_date
            ]

        # Apply event type filter
        if event_types is not None:
            events = [e for e in events if e.event_type in event_types]

        # Yield events (batch_size ignored in stub - no real DB)
        for event in events:
            yield event

    async def count_events_in_range(
        self,
        start_sequence: int,
        end_sequence: int,
    ) -> int:
        """Count events in a sequence range (FR139).

        Used for attestation metadata generation.
        """
        events = self._get_non_orphaned_events()
        return len([e for e in events if start_sequence <= e.sequence <= end_sequence])

    # =========================================================================
    # Hash Verification Methods (Story 6.8 - FR125)
    # =========================================================================

    async def get_all(
        self,
        limit: int | None = None,
    ) -> list["Event"]:
        """Get all events from the store (FR125).

        Used by hash verification to scan entire chain.
        """
        events = self._get_non_orphaned_events()
        if limit is not None:
            return events[:limit]
        return events

    async def get_by_id(self, event_id: str) -> "Event | None":
        """Get an event by its string ID (FR125).

        Alias for get_event_by_id that accepts string ID directly.
        """
        # Convert string to UUID for lookup
        try:
            uid = UUID(event_id)
            return await self.get_event_by_id(uid)
        except (ValueError, TypeError):
            return None

    async def get_by_sequence(self, sequence: int) -> "Event | None":
        """Get an event by its sequence number (FR125).

        Alias for get_event_by_sequence.
        """
        return await self.get_event_by_sequence(sequence)
