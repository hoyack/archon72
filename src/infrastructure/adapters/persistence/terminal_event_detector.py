"""Terminal Event Detector adapter for PostgreSQL (Story 7.6, FR43, NFR40).

This module provides the production implementation of TerminalEventDetectorProtocol
that queries the events table for terminal cessation events.

Constitutional Constraints:
- FR43: Cessation as final recorded event (not silent disappearance)
- NFR40: Cessation reversal is architecturally prohibited
- CT-11: Silent failure destroys legitimacy -> Log all terminal checks
- CT-12: Witnessing creates accountability -> Terminal event is witnessed
- CT-13: Integrity outranks availability -> Permanent termination

Developer Golden Rules:
1. TERMINAL STATE IS PERMANENT - Once is_system_terminated() returns True,
   it MUST always return True. There is no reversal (NFR40).
2. CACHE AFTER TRUE - Since terminal state is permanent, we cache after
   first True detection for efficiency.
3. QUERY IS SIMPLE - Use payload->>'is_terminal' = 'true' to find terminal events.
4. LOG EVERYTHING - Log terminal state checks for accountability.

Architecture:
- Uses Supabase/PostgreSQL to query events table
- Leverages partial index idx_events_terminal for fast lookup
- Caches terminal state once detected (permanent state)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from structlog import get_logger

from src.application.ports.terminal_event_detector import TerminalEventDetectorProtocol

if TYPE_CHECKING:
    from src.domain.events.event import Event

logger = get_logger()


class TerminalEventDetector(TerminalEventDetectorProtocol):
    """PostgreSQL implementation of terminal event detection (FR43, NFR40).

    This adapter queries the events table for cessation events with
    is_terminal=true in their payload. Once a terminal event is found,
    the result is cached since terminal state is permanent.

    Constitutional Constraint (NFR40):
    Once is_system_terminated() returns True, it MUST always return True.
    Terminal state is permanent and irreversible.

    Attributes:
        _event_store: Event store port for querying events.
        _cached_terminated: Cached terminal state (None = not yet checked).
        _cached_terminal_event: Cached terminal event if found.
        _cached_timestamp: Cached termination timestamp if found.

    Example:
        detector = TerminalEventDetector(event_store)

        if await detector.is_system_terminated():
            terminal_event = await detector.get_terminal_event()
            raise SchemaIrreversibilityError(
                f"System terminated at seq {terminal_event.sequence}"
            )
    """

    def __init__(self, event_store: Any) -> None:
        """Initialize the terminal event detector.

        Args:
            event_store: Event store port with get_events_by_type() method.
                In production, this is typically a Supabase-backed store.
        """
        self._event_store = event_store
        # Cache state once terminal is detected (permanent)
        self._cached_terminated: Optional[bool] = None
        self._cached_terminal_event: Optional[Event] = None
        self._cached_timestamp: Optional[datetime] = None

    async def is_system_terminated(self) -> bool:
        """Check if system has been terminated via cessation event.

        Constitutional Constraint (NFR40):
        Once this method returns True, it MUST always return True.
        Terminal state is permanent and irreversible.

        This implementation:
        1. Returns cached True immediately if previously detected
        2. Queries for events with payload->>'is_terminal' = 'true'
        3. Caches result if True (permanent state)
        4. Returns False (but doesn't cache) if not found

        Returns:
            True if a CESSATION_EXECUTED event has been recorded,
            False otherwise.
        """
        log = logger.bind(operation="is_system_terminated")

        # NFR40: Once terminated, always terminated (use cache)
        if self._cached_terminated is True:
            log.debug("terminal_check_cached", terminated=True)
            return True

        # Query for terminal event
        try:
            terminal_event = await self._find_terminal_event()

            if terminal_event is not None:
                # Cache the terminal state (permanent)
                self._cached_terminated = True
                self._cached_terminal_event = terminal_event
                self._cached_timestamp = self._extract_timestamp(terminal_event)

                log.info(
                    "terminal_event_detected",
                    event_id=str(terminal_event.event_id),
                    sequence=terminal_event.sequence,
                    message="FR43: System has been permanently terminated",
                )
                return True

            log.debug("terminal_check_not_terminated")
            return False

        except Exception as e:
            # CT-11: Silent failure destroys legitimacy - log and fail loud
            log.error(
                "terminal_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # In case of error, don't cache - allow retry
            # But also don't assume not terminated (fail safe)
            raise

    async def get_terminal_event(self) -> Optional[Event]:
        """Get the terminal event (CESSATION_EXECUTED) if one exists.

        This method returns the actual cessation event that terminated
        the system, or None if the system has not been terminated.

        Returns:
            The CESSATION_EXECUTED Event if system is terminated,
            None otherwise.
        """
        # Use cached event if available
        if self._cached_terminal_event is not None:
            return self._cached_terminal_event

        # Query for terminal event
        terminal_event = await self._find_terminal_event()

        if terminal_event is not None:
            # Cache for future calls
            self._cached_terminated = True
            self._cached_terminal_event = terminal_event
            self._cached_timestamp = self._extract_timestamp(terminal_event)

        return terminal_event

    async def get_termination_timestamp(self) -> Optional[datetime]:
        """Get the timestamp when system was terminated.

        Returns the execution_timestamp from the CESSATION_EXECUTED
        payload, or None if the system has not been terminated.

        Returns:
            The datetime when cessation occurred (UTC),
            or None if system has not been terminated.
        """
        # Use cached timestamp if available
        if self._cached_timestamp is not None:
            return self._cached_timestamp

        # Need to find the terminal event first
        if self._cached_terminal_event is None:
            terminal_event = await self._find_terminal_event()
            if terminal_event is not None:
                self._cached_terminated = True
                self._cached_terminal_event = terminal_event
                self._cached_timestamp = self._extract_timestamp(terminal_event)

        return self._cached_timestamp

    async def _find_terminal_event(self) -> Optional[Event]:
        """Find the terminal cessation event in the event store.

        Queries for events with payload->>'is_terminal' = 'true'.
        Uses the partial index idx_events_terminal for efficiency.

        Returns:
            The terminal Event if found, None otherwise.
        """
        # Query events with terminal flag
        # The event_store should support querying by payload field
        try:
            # Try using get_events_by_payload_field if available
            if hasattr(self._event_store, "get_events_by_payload_field"):
                events = await self._event_store.get_events_by_payload_field(
                    field="is_terminal",
                    value="true",
                    limit=1,
                )
                return events[0] if events else None

            # Fallback: query by event type and filter
            if hasattr(self._event_store, "get_events_by_type"):
                events = await self._event_store.get_events_by_type(
                    event_type="cessation.executed",
                    limit=1,
                )
                for event in events:
                    if (
                        event.payload
                        and event.payload.get("is_terminal") is True
                    ):
                        return event
                return None

            # Last resort: query latest and check
            if hasattr(self._event_store, "get_latest_event"):
                latest = await self._event_store.get_latest_event()
                if (
                    latest
                    and latest.payload
                    and latest.payload.get("is_terminal") is True
                ):
                    return latest
                return None

            raise NotImplementedError(
                "Event store does not support terminal event queries"
            )

        except Exception as e:
            logger.error(
                "terminal_event_query_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def _extract_timestamp(self, event: Event) -> Optional[datetime]:
        """Extract execution timestamp from event payload.

        Args:
            event: The terminal event to extract timestamp from.

        Returns:
            The execution_timestamp from payload, or event's local_timestamp
            as fallback, or None if neither available.
        """
        if event.payload and "execution_timestamp" in event.payload:
            ts_value = event.payload["execution_timestamp"]
            if isinstance(ts_value, datetime):
                return ts_value
            if isinstance(ts_value, str):
                try:
                    return datetime.fromisoformat(ts_value)
                except ValueError:
                    pass

        # Fallback to event's local_timestamp
        return event.local_timestamp


class InMemoryTerminalEventDetector(TerminalEventDetectorProtocol):
    """In-memory terminal event detector for testing.

    Unlike TerminalEventDetectorStub which allows manual set/clear,
    this implementation maintains an internal event list and detects
    terminal events from actual event data.

    This is useful for integration tests that need to simulate
    the full terminal detection flow without database access.
    """

    def __init__(self) -> None:
        """Initialize with empty event list."""
        self._events: list[Event] = []
        self._cached_terminated: Optional[bool] = None
        self._cached_terminal_event: Optional[Event] = None
        self._cached_timestamp: Optional[datetime] = None

    def add_event(self, event: Event) -> None:
        """Add an event to the in-memory store.

        Args:
            event: Event to add.
        """
        self._events.append(event)
        # Invalidate cache on new events
        if not self._cached_terminated:
            self._cached_terminated = None

    async def is_system_terminated(self) -> bool:
        """Check if system has been terminated."""
        if self._cached_terminated is True:
            return True

        for event in self._events:
            if event.payload and event.payload.get("is_terminal") is True:
                self._cached_terminated = True
                self._cached_terminal_event = event
                self._cached_timestamp = self._extract_timestamp(event)
                return True

        return False

    async def get_terminal_event(self) -> Optional[Event]:
        """Get the terminal event if exists."""
        await self.is_system_terminated()  # Ensure cache is populated
        return self._cached_terminal_event

    async def get_termination_timestamp(self) -> Optional[datetime]:
        """Get termination timestamp if terminated."""
        await self.is_system_terminated()  # Ensure cache is populated
        return self._cached_timestamp

    def _extract_timestamp(self, event: Event) -> Optional[datetime]:
        """Extract timestamp from event."""
        if event.payload and "execution_timestamp" in event.payload:
            ts_value = event.payload["execution_timestamp"]
            if isinstance(ts_value, datetime):
                return ts_value
            if isinstance(ts_value, str):
                try:
                    return datetime.fromisoformat(ts_value)
                except ValueError:
                    pass
        return event.local_timestamp

    def clear_for_testing(self) -> None:
        """Reset state for testing (NOT FOR PRODUCTION)."""
        self._events = []
        self._cached_terminated = None
        self._cached_terminal_event = None
        self._cached_timestamp = None
