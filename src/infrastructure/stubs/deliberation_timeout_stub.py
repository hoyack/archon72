"""Deliberation timeout stub implementation (Story 2B.2, AC-6).

This module provides an in-memory stub implementation of
DeliberationTimeoutProtocol for development and testing purposes.

Constitutional Constraints:
- FR-11.9: System SHALL enforce deliberation timeout (5 min default)
- HC-7: Deliberation timeout auto-ESCALATE
- CT-11: Silent failure destroys legitimacy
- NFR-3.4: Timeout reliability - 100% timeouts fire
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.application.ports.deliberation_timeout import DeliberationTimeoutProtocol
from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.events.deliberation_timeout import DeliberationTimeoutEvent
from src.domain.models.deliberation_session import DeliberationSession

if TYPE_CHECKING:
    pass


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class DeliberationTimeoutStub(DeliberationTimeoutProtocol):
    """In-memory stub implementation of DeliberationTimeoutProtocol.

    This stub provides a simple implementation for development and testing
    that does NOT require the job scheduler infrastructure. It stores
    sessions and timeout state in memory.

    NOT suitable for production use.

    Constitutional Compliance:
    - FR-11.9: Timeout scheduling (simulated)
    - HC-7: Auto-ESCALATE on timeout (simulated)
    - NFR-3.4: Timeout reliability (simulated)

    Attributes:
        _sessions: Dictionary mapping session_id to DeliberationSession
        _timeouts: Dictionary mapping session_id to (job_id, timeout_at)
        _fired_timeouts: Set of session IDs where timeout has fired
        _cancelled_timeouts: Set of session IDs where timeout was cancelled
        _config: Timeout configuration
    """

    def __init__(
        self,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize the stub with empty storage.

        Args:
            config: Timeout configuration. Uses default if not provided.
        """
        self._sessions: dict[UUID, DeliberationSession] = {}
        self._timeouts: dict[UUID, tuple[UUID, datetime]] = {}
        self._fired_timeouts: set[UUID] = set()
        self._cancelled_timeouts: set[UUID] = set()
        self._config = config or DEFAULT_DELIBERATION_CONFIG
        self._events_emitted: list[DeliberationTimeoutEvent] = []

    def register_session(self, session: DeliberationSession) -> None:
        """Register a session for timeout tracking (test helper).

        Args:
            session: The session to register.
        """
        self._sessions[session.session_id] = session

    async def schedule_timeout(
        self,
        session: DeliberationSession,
    ) -> DeliberationSession:
        """Schedule a timeout for the deliberation session.

        Args:
            session: The deliberation session to schedule timeout for.

        Returns:
            Updated DeliberationSession with timeout_job_id and timeout_at set.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If timeout already scheduled for this session.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        # Validate session is not complete
        if session.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(session.session_id),
                message="Cannot schedule timeout on completed session",
            )

        # Validate no existing timeout
        if session.has_timeout_scheduled:
            raise ValueError(
                f"Timeout already scheduled for session {session.session_id}"
            )

        # Calculate timeout time
        timeout_at = _utc_now() + self._config.timeout_timedelta
        job_id = uuid4()

        # Store timeout tracking
        self._timeouts[session.session_id] = (job_id, timeout_at)

        # Update session with timeout tracking
        updated_session = session.with_timeout_scheduled(job_id, timeout_at)

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session

    async def cancel_timeout(
        self,
        session: DeliberationSession,
    ) -> DeliberationSession:
        """Cancel a scheduled timeout (normal completion path).

        Args:
            session: The deliberation session with active timeout.

        Returns:
            Updated DeliberationSession with timeout tracking cleared.
        """
        if not session.has_timeout_scheduled:
            return session

        # Remove timeout tracking
        if session.session_id in self._timeouts:
            del self._timeouts[session.session_id]

        # Track cancellation
        self._cancelled_timeouts.add(session.session_id)

        # Clear timeout tracking on session
        updated_session = session.with_timeout_cancelled()

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session

    async def handle_timeout(
        self,
        session_id: UUID,
    ) -> tuple[DeliberationSession, DeliberationTimeoutEvent]:
        """Handle a fired timeout (auto-ESCALATE path).

        Args:
            session_id: UUID of the session that timed out.

        Returns:
            Tuple of (updated session with timed_out=True, timeout event).

        Raises:
            SessionNotFoundError: If session doesn't exist.
            SessionAlreadyCompleteError: If session already completed.
        """
        from src.domain.errors.deliberation import (
            SessionAlreadyCompleteError,
            SessionNotFoundError,
        )

        # Get session
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                session_id=str(session_id),
                message=f"Session {session_id} not found for timeout handling",
            )

        # Validate session is not already complete
        if session.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(session_id),
                message="Cannot timeout already completed session",
            )

        # Mark session as timed out (sets outcome to ESCALATE per HC-7)
        updated_session = session.with_timeout_triggered()

        # Create timeout event
        timeout_at = _utc_now()
        event = DeliberationTimeoutEvent(
            event_id=uuid4(),
            session_id=session.session_id,
            petition_id=session.petition_id,
            phase_at_timeout=session.phase,
            started_at=session.created_at,
            timeout_at=timeout_at,
            configured_timeout_seconds=self._config.timeout_seconds,
            participating_archons=session.assigned_archons,
        )

        # Track fired timeout
        self._fired_timeouts.add(session_id)
        self._events_emitted.append(event)

        # Remove from pending timeouts
        if session_id in self._timeouts:
            del self._timeouts[session_id]

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session, event

    async def get_timeout_status(
        self,
        session_id: UUID,
    ) -> tuple[bool, int | None]:
        """Get timeout status for a session.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            Tuple of (is_timeout_scheduled, seconds_remaining).
        """
        session = self._sessions.get(session_id)
        if session is None or not session.has_timeout_scheduled:
            return (False, None)

        if session.timeout_at is None:
            return (True, None)

        now = _utc_now()
        if now >= session.timeout_at:
            return (True, 0)

        remaining = (session.timeout_at - now).total_seconds()
        return (True, int(remaining))

    # Test helper methods

    def clear(self) -> None:
        """Clear all sessions and timeout state (for testing)."""
        self._sessions.clear()
        self._timeouts.clear()
        self._fired_timeouts.clear()
        self._cancelled_timeouts.clear()
        self._events_emitted.clear()

    def get_session(self, session_id: UUID) -> DeliberationSession | None:
        """Get a session by ID (for testing).

        Args:
            session_id: UUID of the session.

        Returns:
            DeliberationSession if found, None otherwise.
        """
        return self._sessions.get(session_id)

    def get_scheduled_timeouts(self) -> dict[UUID, tuple[UUID, datetime]]:
        """Get all scheduled timeouts (for testing).

        Returns:
            Dictionary mapping session_id to (job_id, timeout_at).
        """
        return self._timeouts.copy()

    def get_fired_timeouts(self) -> set[UUID]:
        """Get set of session IDs where timeout fired (for testing).

        Returns:
            Set of session UUIDs.
        """
        return self._fired_timeouts.copy()

    def get_cancelled_timeouts(self) -> set[UUID]:
        """Get set of session IDs where timeout was cancelled (for testing).

        Returns:
            Set of session UUIDs.
        """
        return self._cancelled_timeouts.copy()

    def get_emitted_events(self) -> list[DeliberationTimeoutEvent]:
        """Get list of emitted timeout events (for testing).

        Returns:
            List of DeliberationTimeoutEvent instances.
        """
        return self._events_emitted.copy()

    def simulate_timeout_fire(self, session_id: UUID) -> None:
        """Simulate a timeout firing (for testing).

        This is a synchronous test helper that marks a timeout
        as fired without actually waiting for time to pass.

        Args:
            session_id: UUID of the session to fire timeout for.

        Note:
            Call handle_timeout() after this to process the timeout.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return

        if session.timeout_at is not None:
            # Backdated the timeout_at to simulate it being past due
            past_time = _utc_now() - timedelta(seconds=1)
            updated_session = session.with_timeout_scheduled(
                session.timeout_job_id or uuid4(),
                past_time,
            )
            self._sessions[session_id] = updated_session

    @property
    def timeout_seconds(self) -> int:
        """Get configured timeout duration in seconds.

        Returns:
            Timeout duration in seconds.
        """
        return self._config.timeout_seconds
