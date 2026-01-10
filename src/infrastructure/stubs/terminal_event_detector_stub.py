"""Terminal event detector stub for testing (Story 7.3, FR40, NFR40).

This stub implements TerminalEventDetectorProtocol for development
and testing environments. It allows test code to simulate system
termination without actual cessation events.

Constitutional Constraints:
- FR40: No cessation_reversal event type in schema
- NFR40: Cessation reversal is architecturally prohibited
- CT-11: Silent failure destroys legitimacy -> Log all terminal checks

Usage:
    stub = TerminalEventDetectorStub()

    # Not terminated by default
    assert not await stub.is_system_terminated()

    # Simulate termination
    terminal_event = create_cessation_event(...)
    stub.set_terminated(terminal_event)
    assert await stub.is_system_terminated()

    # Reset for next test
    stub.clear_termination()
    assert not await stub.is_system_terminated()

WARNING: This stub is NOT for production use.
Production implementations will query the event store directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.events.event import Event


class TerminalEventDetectorStub:
    """Stub implementation of TerminalEventDetectorProtocol (Story 7.3).

    This stub provides configurable terminal state detection for testing.
    By default, the system is NOT terminated (is_system_terminated returns False).

    Developers can use set_terminated() to simulate cessation and
    clear_termination() to reset the state between tests.

    Constitutional Constraint (NFR40):
    Once set_terminated() is called, the stub SHOULD NOT allow clearing
    in production code. The clear_termination() method exists ONLY for
    test isolation purposes. Production implementations MUST NOT allow
    clearing terminal state.

    Attributes:
        _terminated: Whether the system is terminated.
        _terminal_event: The terminal event if one exists.
        _termination_timestamp: When termination occurred.

    Example:
        # Test that EventWriterService rejects post-cessation writes
        detector = TerminalEventDetectorStub()
        service = EventWriterService(
            atomic_writer=...,
            halt_checker=...,
            terminal_detector=detector,
        )

        # Simulate cessation
        detector.set_terminated(cessation_event)

        # Verify writes are rejected
        with pytest.raises(SchemaIrreversibilityError):
            await service.write_event(...)
    """

    def __init__(self) -> None:
        """Initialize the stub with system NOT terminated."""
        self._terminated: bool = False
        self._terminal_event: Event | None = None
        self._termination_timestamp: datetime | None = None

    async def is_system_terminated(self) -> bool:
        """Check if system has been terminated via cessation event.

        Constitutional Constraint (NFR40):
        Once this method returns True, it MUST always return True.
        Terminal state is permanent and irreversible.

        Note: This stub allows clearing for test isolation ONLY.
        Production implementations MUST NOT allow clearing.

        Returns:
            True if set_terminated() was called, False otherwise.
        """
        return self._terminated

    async def get_terminal_event(self) -> Event | None:
        """Get the terminal event (CESSATION_EXECUTED) if one exists.

        Returns:
            The Event passed to set_terminated(), or None if not terminated.
        """
        return self._terminal_event

    async def get_termination_timestamp(self) -> datetime | None:
        """Get the timestamp when system was terminated.

        Returns:
            The datetime extracted from the terminal event payload,
            or the timestamp passed to set_terminated(),
            or None if system has not been terminated.
        """
        return self._termination_timestamp

    def set_terminated(
        self,
        terminal_event: Event,
        timestamp: datetime | None = None,
    ) -> None:
        """Simulate system termination (test helper).

        Call this method to simulate that a CESSATION_EXECUTED event
        has been written. After calling this, is_system_terminated()
        will return True.

        Constitutional Constraint (NFR40):
        In production, this operation is triggered by writing a
        CESSATION_EXECUTED event. The stub simulates this for testing.

        Args:
            terminal_event: The cessation event that terminated the system.
            timestamp: Optional explicit timestamp. If not provided,
                attempts to extract from event payload.
        """
        self._terminated = True
        self._terminal_event = terminal_event

        # Extract timestamp from payload if not provided
        if timestamp is not None:
            self._termination_timestamp = timestamp
        elif terminal_event.payload and "execution_timestamp" in terminal_event.payload:
            # Try to parse from payload
            ts_value = terminal_event.payload["execution_timestamp"]
            if isinstance(ts_value, datetime):
                self._termination_timestamp = ts_value
            elif isinstance(ts_value, str):
                self._termination_timestamp = datetime.fromisoformat(ts_value)
        else:
            # Fallback to event's local_timestamp
            self._termination_timestamp = terminal_event.local_timestamp

    def clear_termination(self) -> None:
        """Reset terminal state (test helper ONLY).

        WARNING: This method exists ONLY for test isolation.
        Production implementations MUST NOT allow clearing terminal state.

        Constitutional Constraint (NFR40):
        Cessation is architecturally irreversible. This method exists
        solely to allow test fixtures to reset state between tests.

        Call this in test teardown to ensure test isolation.
        """
        self._terminated = False
        self._terminal_event = None
        self._termination_timestamp = None

    def set_terminated_simple(self, timestamp: datetime | None = None) -> None:
        """Simulate termination without an event (minimal test helper).

        For tests that just need is_system_terminated() to return True
        without caring about the actual terminal event details.

        Args:
            timestamp: Optional termination timestamp. Defaults to now.
        """
        self._terminated = True
        self._terminal_event = None
        self._termination_timestamp = timestamp or datetime.utcnow()
