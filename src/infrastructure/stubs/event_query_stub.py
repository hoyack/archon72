"""Event query stub for testing (Story 9.5, FR108).

In-memory implementation of EventQueryProtocol for testing audit event
queries without requiring a real database.

WARNING: This stub is NOT for production use.
Production implementations are in src/infrastructure/adapters/.
"""

from __future__ import annotations

from datetime import datetime


class EventQueryStub:
    """In-memory event query stub for testing (FR108).

    Implements EventQueryProtocol for unit and integration tests.
    Stores events in memory and provides filtering capabilities.

    Usage:
        stub = EventQueryStub()
        stub.add_event({
            "event_id": "evt-1",
            "event_type": "audit.completed",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"audit_id": "audit-1", "quarter": "2026-Q1", "status": "clean"}
        })
        events = await stub.query_events_by_type("audit.completed")
    """

    def __init__(self) -> None:
        """Initialize empty event store."""
        self._events: list[dict[str, object]] = []

    def add_event(self, event: dict[str, object]) -> None:
        """Add an event to the stub store.

        Args:
            event: Event dictionary with event_id, event_type, timestamp, payload.
        """
        self._events.append(event)

    def add_events(self, events: list[dict[str, object]]) -> None:
        """Add multiple events to the stub store.

        Args:
            events: List of event dictionaries.
        """
        self._events.extend(events)

    def clear(self) -> None:
        """Clear all events from the stub store."""
        self._events.clear()

    def get_all_events(self) -> list[dict[str, object]]:
        """Get all stored events.

        Returns:
            List of all events in the store.
        """
        return list(self._events)

    def count(self) -> int:
        """Get total number of stored events.

        Returns:
            Number of events in the store.
        """
        return len(self._events)

    async def query_events_by_type_prefix(
        self,
        type_prefix: str,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events where type starts with a prefix.

        Args:
            type_prefix: Prefix to match event types.
            limit: Maximum number of events to return.

        Returns:
            List of matching events, ordered by timestamp.
        """
        matching = [
            e
            for e in self._events
            if str(e.get("event_type", "")).startswith(type_prefix)
        ]
        # Sort by timestamp
        matching.sort(key=lambda e: str(e.get("timestamp", "")))
        return matching[:limit]

    async def query_events_by_type(
        self,
        event_type: str,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events with an exact type match.

        Args:
            event_type: Exact event type to match.
            limit: Maximum number of events to return.

        Returns:
            List of matching events, ordered by timestamp.
        """
        matching = [e for e in self._events if e.get("event_type") == event_type]
        # Sort by timestamp
        matching.sort(key=lambda e: str(e.get("timestamp", "")))
        return matching[:limit]

    async def query_events_with_payload_filter(
        self,
        event_type: str,
        payload_filter: dict[str, object],
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events with specific payload values.

        Args:
            event_type: Event type to match.
            payload_filter: Payload field:value pairs to match.
            limit: Maximum number of events to return.

        Returns:
            List of matching events, ordered by timestamp.
        """
        matching = []
        for event in self._events:
            if event.get("event_type") != event_type:
                continue

            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue

            # Check all filter conditions
            matches = True
            for key, value in payload_filter.items():
                if payload.get(key) != value:
                    matches = False
                    break

            if matches:
                matching.append(event)

        # Sort by timestamp
        matching.sort(key=lambda e: str(e.get("timestamp", "")))
        return matching[:limit]

    async def count_events_by_type(
        self,
        event_type: str,
    ) -> int:
        """Count events of a specific type.

        Args:
            event_type: Exact event type to count.

        Returns:
            Number of matching events.
        """
        return sum(1 for e in self._events if e.get("event_type") == event_type)

    async def get_distinct_payload_values(
        self,
        event_type: str,
        payload_field: str,
    ) -> list[object]:
        """Get distinct values for a payload field.

        Args:
            event_type: Event type to search.
            payload_field: Payload field to get distinct values for.

        Returns:
            List of distinct values.
        """
        values: set[object] = set()
        for event in self._events:
            if event.get("event_type") != event_type:
                continue

            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue

            if payload_field in payload:
                value = payload[payload_field]
                # Only add hashable values
                try:
                    values.add(value)
                except TypeError:
                    # Skip unhashable values
                    pass

        return list(values)

    async def query_events_by_time_range(
        self,
        type_prefix: str,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Query events within a time range.

        Args:
            type_prefix: Prefix to match event types.
            start_time: ISO 8601 start time (inclusive).
            end_time: ISO 8601 end time (inclusive).
            limit: Maximum number of events to return.

        Returns:
            List of matching events, ordered by timestamp.
        """
        matching = []
        for event in self._events:
            event_type = str(event.get("event_type", ""))
            if not event_type.startswith(type_prefix):
                continue

            timestamp_str = str(event.get("timestamp", ""))
            if not timestamp_str:
                continue

            # Parse timestamp for comparison
            try:
                event_time = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            except ValueError:
                continue

            # Check time range
            if start_time:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                if event_time < start_dt:
                    continue

            if end_time:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                if event_time > end_dt:
                    continue

            matching.append(event)

        # Sort by timestamp
        matching.sort(key=lambda e: str(e.get("timestamp", "")))
        return matching[:limit]

    # Test configuration helpers

    def configure_audit_events(
        self,
        audit_id: str,
        quarter: str,
        status: str = "clean",
        violations_found: int = 0,
        materials_scanned: int = 10,
    ) -> None:
        """Configure a complete audit event sequence for testing.

        Creates started and completed events for an audit.

        Args:
            audit_id: Unique audit identifier.
            quarter: Quarter identifier (e.g., "2026-Q1").
            status: Completion status ("clean", "violations_found", "failed").
            violations_found: Number of violations found.
            materials_scanned: Number of materials scanned.
        """
        base_time = datetime.now().isoformat() + "Z"

        # Add started event
        self.add_event(
            {
                "event_id": f"{audit_id}-started",
                "event_type": "audit.started",
                "timestamp": base_time,
                "payload": {
                    "audit_id": audit_id,
                    "quarter": quarter,
                    "scheduled_at": base_time,
                    "started_at": base_time,
                },
            }
        )

        # Add completed event
        completed_payload: dict[str, object] = {
            "audit_id": audit_id,
            "quarter": quarter,
            "status": status,
            "materials_scanned": materials_scanned,
            "violations_found": violations_found,
            "started_at": base_time,
            "completed_at": base_time,
        }
        if status == "violations_found":
            completed_payload["remediation_deadline"] = base_time

        self.add_event(
            {
                "event_id": f"{audit_id}-completed",
                "event_type": "audit.completed",
                "timestamp": base_time,
                "payload": completed_payload,
            }
        )
