"""Event Store port definition (Story 1.1, Task 4; Story 1.5, Task 2; Story 4.3; Story 4.5, Task 4; Story 8.2).

Defines the abstract interface for event store operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR102: Append-only enforcement - NO delete methods
- FR1: Events must be witnessed
- FR7: Sequence numbers are monotonically increasing and unique (Story 1.5)
- FR46: Query interface supports date range and event type filtering (Story 4.3)
- FR88: Query for state as of any sequence number or timestamp (Story 4.5)
- FR89: Historical queries return hash chain proof to current head (Story 4.5)
- FR52: Operational-Constitutional Separation (Story 8.2)
  - ONLY constitutional event types are allowed in the event store
  - Operational metrics (uptime, latency, error rates) MUST NOT enter event store
  - Use EventTypeRegistry to validate event types before writing
- CT-12: Witnessing creates accountability

ADR-1: Event Store Implementation
- Supabase Postgres as storage backend
- DB-level functions/triggers enforce hash chaining and append-only

Exceptions:
- EventStoreError: For storage-related failures (from src.domain.errors)
- ConstitutionalViolationError: For constitutional constraint violations
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.errors import EventStoreError  # noqa: F401
    from src.domain.events import Event


def validate_sequence_continuity(
    sequences: list[int],
    expected_start: int | None = None,
    expected_end: int | None = None,
) -> tuple[bool, list[int]]:
    """Validate that a sequence has no gaps.

    This helper validates sequence continuity for external observers
    to verify event ordering integrity (FR7, AC2, AC3).

    Args:
        sequences: List of sequence numbers to validate.
        expected_start: If provided, sequences should start from this value.
        expected_end: If provided, sequences should end at this value.

    Returns:
        Tuple of (is_continuous, missing_sequences).
        If continuous, missing_sequences is empty list.

    Note:
        Gaps may be valid for documented ceremonies (AC2 exception).
        Caller must interpret gaps in context.

    Example:
        >>> validate_sequence_continuity([1, 2, 3, 4, 5])
        (True, [])
        >>> validate_sequence_continuity([1, 2, 4, 5])
        (False, [3])
    """
    if not sequences:
        return True, []

    # Get unique sorted sequences
    sorted_seqs = sorted(set(sequences))

    # Determine range to check
    start = expected_start if expected_start is not None else sorted_seqs[0]
    end = expected_end if expected_end is not None else sorted_seqs[-1]

    # Find expected full range
    expected = set(range(start, end + 1))
    actual = set(sorted_seqs)

    # Find missing sequences
    missing = sorted(expected - actual)

    return len(missing) == 0, missing


class EventStorePort(ABC):
    """Abstract protocol for event store operations.

    All event store implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific storage implementations.

    Constitutional Constraints:
    - FR102: Append-only enforcement - NO delete methods are defined
    - FR1: Events must be witnessed (witness_id, witness_signature required)
    - CT-12: Witnessing creates accountability

    Note:
        This port deliberately does NOT include delete methods.
        The Event entity uses DeletePreventionMixin to raise
        ConstitutionalViolationError if delete() is called.
        The database enforces append-only via triggers.
    """

    @abstractmethod
    async def append_event(self, event: "Event") -> "Event":
        """Append a new event to the store.

        This is the ONLY write operation allowed. Events cannot be
        updated or deleted (FR102 - append-only enforcement).

        Args:
            event: The event to append. Must have:
                - Valid witness_id and witness_signature
                - Correct prev_hash linking to previous event
                - Valid content_hash and signature

        Returns:
            The persisted event with sequence and authority_timestamp
            filled in by the database.

        Raises:
            ConstitutionalViolationError: If event fails validation.
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_latest_event(self) -> "Event | None":
        """Get the most recent event from the store.

        Used for hash chaining - new events must reference
        the hash of the previous event.

        Returns:
            The latest event, or None if the store is empty.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_event_by_sequence(self, sequence: int) -> "Event | None":
        """Get an event by its sequence number.

        Args:
            sequence: The monotonic sequence number of the event.

        Returns:
            The event with the given sequence, or None if not found.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_event_by_id(self, event_id: UUID) -> "Event | None":
        """Get an event by its unique identifier.

        Args:
            event_id: The UUID of the event.

        Returns:
            The event with the given ID, or None if not found.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_events_by_type(
        self,
        event_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list["Event"]:
        """Get events filtered by type.

        Args:
            event_type: The event type to filter by.
            limit: Maximum number of events to return.
            offset: Number of events to skip.

        Returns:
            List of events matching the type, ordered by sequence.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def count_events(self) -> int:
        """Get the total count of events in the store.

        Returns:
            The total number of events.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    # =========================================================================
    # Filtered Query Methods (Story 4.3 - FR46)
    # =========================================================================

    @abstractmethod
    async def get_events_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> list["Event"]:
        """Get events with optional filters (FR46).

        Used by observer API for filtered queries. Filters combine with AND logic.

        Args:
            limit: Maximum number of events to return.
            offset: Number of events to skip.
            start_date: Filter events from this timestamp (authority_timestamp).
            end_date: Filter events until this timestamp (authority_timestamp).
            event_types: Filter by event types (OR within types, AND with dates).

        Returns:
            List of events matching filters, ordered by sequence.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def count_events_filtered(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> int:
        """Count events matching filters (FR46).

        Args:
            start_date: Filter events from this timestamp.
            end_date: Filter events until this timestamp.
            event_types: Filter by event types.

        Returns:
            Count of matching events.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    # =========================================================================
    # Observer Query Methods (Story 1.5 - FR7, AC3)
    # =========================================================================

    @abstractmethod
    async def get_max_sequence(self) -> int:
        """Get the current maximum sequence number.

        Used by external observers to verify sequence continuity (FR7).
        Sequence is the authoritative ordering mechanism - timestamps
        are for informational/debugging purposes only (AC3).

        Returns:
            The highest sequence number in the store, or 0 if empty.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_events_by_sequence_range(
        self,
        start: int,
        end: int,
    ) -> list["Event"]:
        """Get events within a sequence range (inclusive).

        Used by external observers to retrieve events for verification.
        Events are returned ordered by sequence number (authoritative order).

        Args:
            start: Start of sequence range (inclusive).
            end: End of sequence range (inclusive).

        Returns:
            List of events ordered by sequence.

        Raises:
            EventStoreError: For storage-related failures.

        Note:
            Per AC3, sequence is the authoritative order. Timestamps
            (local_timestamp, authority_timestamp) are informational only.
        """
        ...

    @abstractmethod
    async def verify_sequence_continuity(
        self,
        start: int,
        end: int,
    ) -> tuple[bool, list[int]]:
        """Verify no gaps exist in sequence range.

        Used by external observers to verify event ordering integrity.
        This is a key method for AC2 (unique sequential numbers) and
        AC3 (sequence as authoritative order).

        Args:
            start: Start of range to verify.
            end: End of range to verify.

        Returns:
            Tuple of (is_continuous, missing_sequences).
            If continuous, missing_sequences is empty.

        Note:
            Gaps may be valid for documented ceremonies (AC2 exception).
            Caller must interpret gaps in context. Use the helper
            function validate_sequence_continuity() for pure validation.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    # =========================================================================
    # Orphaning Methods for Rollback (Story 3.10 - FR143, PREVENT_DELETE)
    # =========================================================================

    @abstractmethod
    async def mark_events_orphaned(
        self,
        start_sequence: int,
        end_sequence: int,
    ) -> int:
        """Mark events in range as orphaned (not deleted).

        Per PREVENT_DELETE: Events are never deleted, only marked as orphaned.
        Orphaned events are excluded from normal queries but remain queryable
        with include_orphaned=True for audit purposes.

        Constitutional Constraint (FR143, PREVENT_DELETE):
        - Events are NEVER deleted, only marked
        - Orphaned events remain in the database for audit trail
        - This is the mechanism for rollback without data loss

        Args:
            start_sequence: Start of sequence range to mark (inclusive).
            end_sequence: End of sequence range to mark (exclusive).

        Returns:
            Count of events marked as orphaned.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_head_sequence(self) -> int:
        """Get current HEAD sequence number.

        HEAD represents the latest valid (non-orphaned) event sequence.
        After rollback, HEAD moves to the checkpoint sequence.

        Returns:
            Current HEAD sequence number, or 0 if store is empty.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def set_head_sequence(self, sequence: int) -> None:
        """Set HEAD to specific sequence (for rollback).

        Moves the HEAD pointer to a specific sequence number.
        Used during rollback to checkpoint.

        Constitutional Constraint:
        This does NOT delete events - it only moves the pointer.
        Events after HEAD become orphaned (see mark_events_orphaned).

        Args:
            sequence: The sequence number to set as HEAD.

        Raises:
            EventStoreError: For storage-related failures.
            ValueError: If sequence is invalid (negative or beyond max).
        """
        ...

    @abstractmethod
    async def get_events_by_sequence_range_with_orphaned(
        self,
        start: int,
        end: int,
        include_orphaned: bool = False,
    ) -> list["Event"]:
        """Get events within a sequence range with orphaned flag control.

        Like get_events_by_sequence_range but with explicit control over
        whether orphaned events are included.

        Constitutional Constraint (FR143, PREVENT_DELETE):
        - Orphaned events are excluded by default (include_orphaned=False)
        - Orphaned events can be queried for audit (include_orphaned=True)
        - Events are NEVER deleted, ensuring audit trail integrity

        Args:
            start: Start of sequence range (inclusive).
            end: End of sequence range (inclusive).
            include_orphaned: If True, include orphaned events. Default False.

        Returns:
            List of events ordered by sequence.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    # =========================================================================
    # Historical Query Methods (Story 4.5 - FR88, FR89)
    # =========================================================================

    @abstractmethod
    async def get_events_up_to_sequence(
        self,
        max_sequence: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list["Event"]:
        """Get events with sequence <= max_sequence (FR88).

        Used for historical queries where we want to see the state
        as of a specific sequence number.

        Args:
            max_sequence: Maximum sequence number to include.
            limit: Maximum number of events to return.
            offset: Number of events to skip.

        Returns:
            List of events with sequence <= max_sequence, ordered by sequence.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def count_events_up_to_sequence(
        self,
        max_sequence: int,
    ) -> int:
        """Count events with sequence <= max_sequence (FR88).

        Args:
            max_sequence: Maximum sequence number to include.

        Returns:
            Count of matching events.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def find_sequence_for_timestamp(
        self,
        timestamp: datetime,
    ) -> int | None:
        """Find sequence number for last event before timestamp (FR88).

        Used for timestamp-based historical queries. Returns the sequence
        of the last event whose authority_timestamp is <= timestamp.

        Args:
            timestamp: Target timestamp.

        Returns:
            Sequence of last event before/at timestamp, or None if no events.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    # =========================================================================
    # Streaming Export Methods (Story 4.7 - FR139)
    # =========================================================================

    @abstractmethod
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
        Supports regulatory reporting export requirements.

        Args:
            start_sequence: First sequence to include (optional).
            end_sequence: Last sequence to include (optional).
            start_date: Filter events from this timestamp (optional).
            end_date: Filter events until this timestamp (optional).
            event_types: Filter by event types (optional).
            batch_size: Number of events per DB query (default 100).

        Yields:
            Events matching criteria, ordered by sequence.

        Raises:
            EventStoreError: For storage-related failures.

        Note:
            Filters combine with AND logic, same as get_events_filtered.
            This is designed for large exports - use batch_size to control
            memory usage vs DB round trips.
        """
        ...
        yield  # type: ignore[misc]

    @abstractmethod
    async def count_events_in_range(
        self,
        start_sequence: int,
        end_sequence: int,
    ) -> int:
        """Count events in a sequence range (FR139).

        Used for attestation metadata generation - allows getting
        event count for a range without loading all events.

        Args:
            start_sequence: Start of sequence range (inclusive).
            end_sequence: End of sequence range (inclusive).

        Returns:
            Count of events in the range.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    # =========================================================================
    # Hash Verification Methods (Story 6.8 - FR125)
    # =========================================================================

    @abstractmethod
    async def get_all(
        self,
        limit: int | None = None,
    ) -> list["Event"]:
        """Get all events from the store (FR125).

        Used by hash verification to scan entire chain.

        Args:
            limit: Optional maximum number of events to return.

        Returns:
            List of all non-orphaned events, ordered by sequence.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_by_id(self, event_id: str) -> "Event | None":
        """Get an event by its string ID (FR125).

        Alias for get_event_by_id that accepts string ID directly.

        Args:
            event_id: String ID of the event.

        Returns:
            The event if found, None otherwise.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...

    @abstractmethod
    async def get_by_sequence(self, sequence: int) -> "Event | None":
        """Get an event by its sequence number (FR125).

        Alias for get_event_by_sequence.

        Args:
            sequence: The sequence number.

        Returns:
            The event if found, None otherwise.

        Raises:
            EventStoreError: For storage-related failures.
        """
        ...
