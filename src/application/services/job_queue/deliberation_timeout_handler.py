"""Deliberation Timeout Job Handler (Story 2B.2, AC-6).

This module provides the DeliberationTimeoutHandler that executes
when a deliberation timeout job fires from the job queue.

Constitutional Constraints:
- FR-11.9: System SHALL enforce deliberation timeout (5 min default)
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - handler MUST complete
- CT-14: Silence is expensive - every petition terminates in witnessed fate
- NFR-3.4: Timeout reliability - 100% timeouts fire
- HP-1: Job queue for reliable deadline execution
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from structlog import get_logger

from src.application.services.deliberation_timeout_service import (
    DELIBERATION_TIMEOUT_JOB_TYPE,
)
from src.application.services.job_queue.job_worker_service import JobHandler
from src.domain.models.scheduled_job import ScheduledJob

if TYPE_CHECKING:
    from src.application.ports.deliberation_timeout import DeliberationTimeoutProtocol

logger = get_logger()


class DeliberationTimeoutHandler(JobHandler):
    """Handler for deliberation timeout jobs (Story 2B.2, AC-6).

    This handler is invoked by the job worker when a deliberation
    timeout job fires. It delegates to the DeliberationTimeoutService
    to execute the timeout logic (mark session timed out, emit event).

    Constitutional Constraints:
    - FR-11.9: Timeout enforcement
    - HC-7: Auto-ESCALATE on timeout
    - CT-11: Handler MUST complete successfully
    - NFR-3.4: 100% timeout reliability

    Attributes:
        _timeout_service: Service that handles timeout execution.
        job_type: The job type this handler processes.
    """

    # Job type this handler processes
    job_type: str = DELIBERATION_TIMEOUT_JOB_TYPE

    def __init__(
        self,
        timeout_service: DeliberationTimeoutProtocol,
    ) -> None:
        """Initialize the timeout handler.

        Args:
            timeout_service: Service that handles timeout execution.
        """
        self._timeout_service = timeout_service

    async def execute(self, job: ScheduledJob) -> None:
        """Execute the deliberation timeout job.

        Called by the job worker when a timeout job is due for execution.
        Extracts session_id from payload and delegates to timeout service.

        Constitutional Constraints:
        - HC-7: This method triggers auto-ESCALATE
        - CT-11: Must raise exception on failure for retry/DLQ

        Args:
            job: The ScheduledJob containing timeout details in payload.

        Raises:
            ValueError: If payload is missing required fields.
            SessionNotFoundError: If session doesn't exist.
            SessionAlreadyCompleteError: If session already completed.
        """
        log = logger.bind(
            job_id=str(job.id),
            job_type=job.job_type,
        )

        # Extract session_id from payload
        session_id_str = job.payload.get("session_id")
        if session_id_str is None:
            log.error(
                "timeout_handler_missing_session_id",
                payload=job.payload,
                message="CT-11: Cannot process timeout without session_id",
            )
            raise ValueError("Job payload missing 'session_id'")

        try:
            session_id = UUID(session_id_str)
        except ValueError as e:
            log.error(
                "timeout_handler_invalid_session_id",
                session_id_str=session_id_str,
                error=str(e),
            )
            raise ValueError(f"Invalid session_id format: {session_id_str}") from e

        petition_id_str = job.payload.get("petition_id", "unknown")

        log = log.bind(
            session_id=session_id_str,
            petition_id=petition_id_str,
        )

        log.info(
            "timeout_handler_executing",
            message="HC-7: Processing deliberation timeout",
        )

        # Execute timeout via service
        session, event = await self._timeout_service.handle_timeout(session_id)

        log.info(
            "timeout_handler_completed",
            session_timed_out=session.is_timed_out,
            session_outcome=session.outcome.value if session.outcome else None,
            event_id=str(event.event_id),
            phase_at_timeout=event.phase_at_timeout.value,
            elapsed_seconds=event.elapsed_seconds,
            message="FR-11.9: Deliberation timeout enforced, auto-ESCALATE triggered",
        )
