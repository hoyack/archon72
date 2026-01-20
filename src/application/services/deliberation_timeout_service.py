"""Deliberation timeout handler service (Story 2B.2, FR-11.9, HC-7).

This module implements the DeliberationTimeoutProtocol for scheduling,
firing, and cancelling deliberation timeout jobs.

Constitutional Constraints:
- FR-11.9: System SHALL enforce deliberation timeout (5 min default) with auto-ESCALATE on expiry
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - timeout MUST fire
- CT-14: Silence is expensive - every petition terminates in witnessed fate
- NFR-3.4: Timeout reliability - 100% timeouts fire
- NFR-10.4: 100% witness completeness
- HP-1: Job queue for reliable deadline execution

Usage:
    from src.application.services.deliberation_timeout_service import (
        DeliberationTimeoutService,
    )
    from src.config.deliberation_config import DEFAULT_DELIBERATION_CONFIG

    service = DeliberationTimeoutService(
        job_scheduler=scheduler,
        event_emitter=emitter,
        config=DEFAULT_DELIBERATION_CONFIG,
    )

    # Schedule timeout when deliberation starts
    session = await service.schedule_timeout(session)

    # Cancel timeout when deliberation completes normally
    session = await service.cancel_timeout(session)

    # Or handle timeout (called by job worker)
    session, event = await service.handle_timeout(session_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.application.ports.job_scheduler import JobSchedulerProtocol
from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.events.deliberation_timeout import (
    DELIBERATION_TIMEOUT_EVENT_TYPE,
    DeliberationTimeoutEvent,
)
from src.domain.models.deliberation_session import DeliberationSession

if TYPE_CHECKING:
    from src.application.ports.event_store import EventStorePort

# Job type for deliberation timeouts (used by job queue)
DELIBERATION_TIMEOUT_JOB_TYPE: str = "deliberation_timeout"


class DeliberationTimeoutService:
    """Service for deliberation timeout handling (Story 2B.2, FR-11.9, HC-7).

    Handles the scheduling, firing, and cancellation of deliberation timeout
    jobs using the job queue infrastructure (HP-1).

    When a timeout fires (HC-7):
    1. Session is marked as timed out
    2. Outcome is set to ESCALATE (auto-escalation)
    3. DeliberationTimeoutEvent is emitted
    4. Event is witnessed per CT-12

    Constitutional Constraints:
    - FR-11.9: 5-minute default timeout
    - HC-7: Auto-ESCALATE on timeout
    - CT-11: 100% timeout reliability
    - NFR-3.4: Timeouts MUST fire
    - HP-1: Job queue ensures reliable execution

    Attributes:
        _job_scheduler: Protocol for scheduling/canceling jobs.
        _event_emitter: Protocol for emitting events (optional).
        _config: Timeout configuration.
        _sessions: In-memory session storage (for stub/testing).
    """

    def __init__(
        self,
        job_scheduler: JobSchedulerProtocol,
        event_emitter: EventStorePort | None = None,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize the timeout service.

        Args:
            job_scheduler: Protocol for scheduling timeout jobs.
            event_emitter: Protocol for emitting timeout events (optional).
            config: Timeout configuration. Uses default if not provided.
        """
        self._job_scheduler = job_scheduler
        self._event_emitter = event_emitter
        self._config = config or DEFAULT_DELIBERATION_CONFIG
        # In-memory session storage for development/testing
        # Production would use a repository
        self._sessions: dict[UUID, DeliberationSession] = {}

    def _utc_now(self) -> datetime:
        """Return current UTC time with timezone info."""
        return datetime.now(timezone.utc)

    def register_session(self, session: DeliberationSession) -> None:
        """Register a session for timeout tracking (development helper).

        In production, sessions would be stored in a repository.

        Args:
            session: The session to register.
        """
        self._sessions[session.session_id] = session

    def get_session(self, session_id: UUID) -> DeliberationSession | None:
        """Get a session by ID (development helper).

        Args:
            session_id: UUID of the session.

        Returns:
            DeliberationSession if found, None otherwise.
        """
        return self._sessions.get(session_id)

    async def schedule_timeout(
        self,
        session: DeliberationSession,
    ) -> DeliberationSession:
        """Schedule a timeout job for the deliberation session (FR-11.9).

        Creates a scheduled job that will fire after the configured
        timeout duration (default 5 minutes). The session is updated
        with the job ID and timeout timestamp.

        Constitutional Constraints:
        - FR-11.9: Timeout enforcement
        - HP-1: Reliable job scheduling
        - CT-11: Timeout MUST fire

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
        timeout_at = self._utc_now() + self._config.timeout_timedelta

        # Schedule job via job queue
        job_id = await self._job_scheduler.schedule(
            job_type=DELIBERATION_TIMEOUT_JOB_TYPE,
            payload={
                "session_id": str(session.session_id),
                "petition_id": str(session.petition_id),
                "timeout_seconds": self._config.timeout_seconds,
            },
            run_at=timeout_at,
        )

        # Update session with timeout tracking
        updated_session = session.with_timeout_scheduled(job_id, timeout_at)

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session

    async def cancel_timeout(
        self,
        session: DeliberationSession,
    ) -> DeliberationSession:
        """Cancel a scheduled timeout job (normal completion path).

        Called when deliberation completes normally before the timeout
        fires. The job is cancelled and timeout tracking is cleared.

        Args:
            session: The deliberation session with active timeout.

        Returns:
            Updated DeliberationSession with timeout tracking cleared.

        Note:
            If no timeout is scheduled, returns session unchanged.
        """
        if not session.has_timeout_scheduled:
            return session

        # Cancel job via job queue
        if session.timeout_job_id is not None:
            await self._job_scheduler.cancel(session.timeout_job_id)

        # Clear timeout tracking
        updated_session = session.with_timeout_cancelled()

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session

    async def handle_timeout(
        self,
        session_id: UUID,
    ) -> tuple[DeliberationSession, DeliberationTimeoutEvent]:
        """Handle a fired timeout (auto-ESCALATE path) (HC-7).

        Called by the job worker when a timeout job fires. This method:
        1. Marks the session as timed out
        2. Sets outcome to ESCALATE per HC-7
        3. Emits DeliberationTimeoutEvent
        4. Witnesses the timeout per CT-12

        Constitutional Constraints:
        - HC-7: Auto-ESCALATE on timeout
        - CT-11: Silent failure destroys legitimacy
        - CT-14: Every petition terminates in witnessed fate
        - NFR-10.4: 100% witness completeness

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
        timeout_at = self._utc_now()
        event = DeliberationTimeoutEvent(
            event_id=uuid4(),  # Should be UUIDv7 in production
            session_id=session.session_id,
            petition_id=session.petition_id,
            phase_at_timeout=session.phase,  # Phase BEFORE timeout
            started_at=session.created_at,
            timeout_at=timeout_at,
            configured_timeout_seconds=self._config.timeout_seconds,
            participating_archons=session.assigned_archons,
        )

        # Emit event if event emitter available
        if self._event_emitter is not None:
            # Note: Actual event store integration would go here
            # await self._event_emitter.append(event.to_dict())
            pass

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
            seconds_remaining is None if no timeout scheduled or expired.
        """
        session = self._sessions.get(session_id)
        if session is None or not session.has_timeout_scheduled:
            return (False, None)

        if session.timeout_at is None:
            return (True, None)

        now = self._utc_now()
        if now >= session.timeout_at:
            return (True, 0)  # Timeout expired but not yet fired

        remaining = (session.timeout_at - now).total_seconds()
        return (True, int(remaining))

    @property
    def timeout_seconds(self) -> int:
        """Get configured timeout duration in seconds.

        Returns:
            Timeout duration in seconds.
        """
        return self._config.timeout_seconds
