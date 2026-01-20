"""Deliberation timeout handler protocol (Story 2B.2, FR-11.9, HC-7).

This module defines the protocol for deliberation timeout handling
including scheduling, firing, and cancellation of timeout jobs.

Constitutional Constraints:
- FR-11.9: System SHALL enforce deliberation timeout (5 min default) with auto-ESCALATE on expiry
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - timeout MUST fire
- CT-14: Silence is expensive - every petition terminates in witnessed fate
- NFR-3.4: Timeout reliability - 100% timeouts fire
- NFR-10.4: 100% witness completeness
- HP-1: Job queue for reliable deadline execution
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.events.deliberation_timeout import DeliberationTimeoutEvent
from src.domain.models.deliberation_session import DeliberationSession


class DeliberationTimeoutProtocol(Protocol):
    """Protocol for deliberation timeout handling (Story 2B.2, FR-11.9, HC-7).

    Implementations handle scheduling, firing, and cancellation of
    deliberation timeout jobs via the job queue infrastructure.

    Constitutional Constraints:
    - FR-11.9: 5-minute default timeout with auto-ESCALATE
    - HC-7: Prevent stuck petitions
    - CT-11: Timeouts MUST fire (100% reliability)
    - NFR-3.4: Timeout reliability
    - HP-1: Job queue for reliable execution
    """

    async def schedule_timeout(
        self,
        session: DeliberationSession,
    ) -> DeliberationSession:
        """Schedule a timeout job for the deliberation session (FR-11.9).

        Creates a scheduled job that will fire after the configured
        timeout duration (default 5 minutes). If the deliberation
        completes before the timeout, cancel_timeout should be called.

        Args:
            session: The deliberation session to schedule timeout for.

        Returns:
            Updated DeliberationSession with timeout_job_id and timeout_at set.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If timeout already scheduled for this session.
        """
        ...

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
        ...

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

        Constitutional Constraint (HC-7): The petition is auto-escalated
        to prevent it from being stuck forever in deliberation.

        Args:
            session_id: UUID of the session that timed out.

        Returns:
            Tuple of (updated session with timed_out=True, timeout event).

        Raises:
            SessionNotFoundError: If session doesn't exist.
            SessionAlreadyCompleteError: If session already completed.
        """
        ...

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
        ...
