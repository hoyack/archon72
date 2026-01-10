"""Public Override Service (Story 5.3, FR25).

Service for querying override events with public visibility.
All overrides are publicly accessible without authentication.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication required for read endpoints
- FR48: Rate limits identical for anonymous and authenticated users
- CT-12: Witnessing creates accountability - witness attribution included

This service provides read-only access to override events.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from src.domain.events.override_event import OVERRIDE_EVENT_TYPE

if TYPE_CHECKING:
    from src.application.ports.event_store import EventStorePort
    from src.domain.events import Event


class PublicOverrideService:
    """Public override query service (FR25).

    Provides read-only access to override events for public transparency.
    All override data is visible without authentication (FR44).

    Constitutional Constraints:
    - FR25: All overrides publicly visible
    - FR44: No authentication required
    - FR48: Rate limits identical for all users
    - CT-12: Witnessing creates accountability
    """

    def __init__(self, event_store: "EventStorePort") -> None:
        """Initialize service with event store.

        Args:
            event_store: Event store port for reading override events.
        """
        self._event_store = event_store

    async def get_overrides(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list["Event"], int]:
        """Get override events with optional filters (FR25, FR46).

        Returns all override events (event_type == "override.initiated")
        with optional date range filtering.

        Args:
            limit: Maximum number of events to return.
            offset: Number of events to skip.
            start_date: Filter events from this timestamp (authority_timestamp).
            end_date: Filter events until this timestamp (authority_timestamp).

        Returns:
            Tuple of (events, total_count) for pagination support.

        Note:
            Per FR25, all override data is publicly visible.
            Keeper identity is NOT anonymized.
        """
        # Get filtered override events
        events = await self._event_store.get_events_filtered(
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            event_types=[OVERRIDE_EVENT_TYPE],
        )

        # Get total count for pagination
        total_count = await self._event_store.count_events_filtered(
            start_date=start_date,
            end_date=end_date,
            event_types=[OVERRIDE_EVENT_TYPE],
        )

        return events, total_count

    async def get_override_by_id(self, override_id: str) -> "Event | None":
        """Get a single override event by ID.

        Args:
            override_id: The UUID string of the override event.

        Returns:
            The override event if found and is of type override.initiated,
            None otherwise.
        """
        from uuid import UUID

        try:
            event_uuid = UUID(override_id)
        except ValueError:
            return None

        event = await self._event_store.get_event_by_id(event_uuid)

        if event is None:
            return None

        # Verify it's an override event
        if event.event_type != OVERRIDE_EVENT_TYPE:
            return None

        return event
