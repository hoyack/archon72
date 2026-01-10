"""Event query port for reading events from the event store (Story 9.5, FR108).

This port defines the interface for querying events from the constitutional
record. It complements EventStorePort which handles writes.

Architecture Pattern:
- EventStorePort: WRITE events (Story 1-6)
- EventQueryProtocol: READ events (Story 9.5 - this story)

Constitutional Constraints:
- FR108: Audit results logged as events, audit history queryable
- CT-11: HALT CHECK FIRST (checked by services, not this port)
- CT-12: Events are witnessed when written (not this port's concern for reads)
"""

from __future__ import annotations

from typing import Optional, Protocol


class EventQueryProtocol(Protocol):
    """Protocol for querying events from the event store (FR108).

    This protocol defines read-only operations for retrieving events
    from the constitutional record. It's designed for query services
    that need to analyze event history.

    Note: HALT CHECK is the responsibility of the service layer,
    not this port. This port focuses purely on data access.
    """

    async def query_events_by_type_prefix(
        self,
        type_prefix: str,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events where type starts with a prefix (FR108).

        Retrieves events matching a type prefix, useful for querying
        all events in a category (e.g., "audit." for all audit events).

        Args:
            type_prefix: Prefix to match event types (e.g., "audit.").
            limit: Maximum number of events to return.

        Returns:
            List of events as dictionaries, ordered by timestamp (oldest first).
            Each dictionary contains: event_id, event_type, timestamp, payload.

        Note:
            Empty prefix matches all events.
            Results are ordered chronologically (oldest first).
        """
        ...

    async def query_events_by_type(
        self,
        event_type: str,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events with an exact type match (FR108).

        Retrieves events matching a specific type string exactly.

        Args:
            event_type: Exact event type to match (e.g., "audit.completed").
            limit: Maximum number of events to return.

        Returns:
            List of events as dictionaries, ordered by timestamp (oldest first).
            Each dictionary contains: event_id, event_type, timestamp, payload.
        """
        ...

    async def query_events_with_payload_filter(
        self,
        event_type: str,
        payload_filter: dict[str, object],
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events with specific payload values (FR108).

        Retrieves events of a given type where payload fields match
        specified values. Useful for filtering by quarter, audit_id, etc.

        Args:
            event_type: Event type to match.
            payload_filter: Dictionary of payload field:value pairs to match.
                            All specified fields must match (AND logic).
            limit: Maximum number of events to return.

        Returns:
            List of events as dictionaries, ordered by timestamp (oldest first).
            Each dictionary contains: event_id, event_type, timestamp, payload.

        Example:
            # Get completed audits for Q1 2026
            await query_events_with_payload_filter(
                event_type="audit.completed",
                payload_filter={"quarter": "2026-Q1"},
                limit=10,
            )
        """
        ...

    async def count_events_by_type(
        self,
        event_type: str,
    ) -> int:
        """Count events of a specific type (FR108).

        Efficiently counts events without retrieving full payloads.
        Useful for statistics and trend analysis.

        Args:
            event_type: Exact event type to count.

        Returns:
            Number of events matching the type.
        """
        ...

    async def get_distinct_payload_values(
        self,
        event_type: str,
        payload_field: str,
    ) -> list[object]:
        """Get distinct values for a payload field (FR108).

        Retrieves all unique values for a specific field across events
        of a given type. Useful for discovering available quarters, etc.

        Args:
            event_type: Event type to search.
            payload_field: Name of the payload field to get distinct values for.

        Returns:
            List of distinct values found for the field.
        """
        ...

    async def query_events_by_time_range(
        self,
        type_prefix: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events within a time range (FR108).

        Retrieves events matching a type prefix within an optional time range.
        Times are ISO 8601 formatted strings.

        Args:
            type_prefix: Prefix to match event types.
            start_time: ISO 8601 start time (inclusive), None for no lower bound.
            end_time: ISO 8601 end time (inclusive), None for no upper bound.
            limit: Maximum number of events to return.

        Returns:
            List of events as dictionaries, ordered by timestamp (oldest first).
        """
        ...
