"""Job Worker Service for deadline monitoring (Story 0.4, AC5).

This module provides the JobWorkerService that polls and executes
scheduled jobs for deadline monitoring in the Three Fates petition system.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All failures logged
- CT-12: Witnessing creates accountability → Job execution auditable
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
- NFR-7.5: 10-second polling interval with heartbeat monitoring
- FM-7.1: Persistent job queue prevents "timeout never fires" failure mode

Architecture:
- Polls for pending jobs at configurable interval (default 10 seconds)
- Claims jobs atomically to prevent double-processing
- Executes job handlers registered by job type
- Moves failed jobs to dead letter queue after max retries
- Emits heartbeat for monitoring (NFR-7.5)
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.job_scheduler import JobSchedulerProtocol
from src.domain.models.scheduled_job import ScheduledJob

if TYPE_CHECKING:
    pass

logger = get_logger()

# NFR-7.5: 10-second polling interval
DEFAULT_POLL_INTERVAL_SECONDS = 10

# Maximum jobs to claim per poll cycle
DEFAULT_BATCH_SIZE = 10


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class JobHandler(ABC):
    """Abstract base class for job handlers.

    Implement this class to define custom job execution logic for
    specific job types (referral_timeout, deliberation_timeout, etc.).

    Constitutional Constraint (CT-11):
    Handlers MUST NOT silently fail. All errors must be raised to
    allow proper retry/DLQ handling.
    """

    @abstractmethod
    async def execute(self, job: ScheduledJob) -> None:
        """Execute the job.

        Args:
            job: The ScheduledJob to execute.

        Raises:
            Exception: Any exception will trigger retry or DLQ.
        """
        ...


class JobWorkerService:
    """Service for polling and executing scheduled jobs (AC5).

    This service implements the worker loop for deadline monitoring.
    It polls for pending jobs, claims them atomically, and executes
    registered handlers based on job type.

    Constitutional Constraints:
    - HP-1: Reliable deadline execution
    - HC-6: Dead-letter alerting for failed jobs
    - NFR-7.5: 10-second polling interval with heartbeat
    - FM-7.1: Prevents "timeout never fires" failure mode

    Architecture:
    - Polls scheduler at configurable interval (default 10s)
    - Uses atomic claim to prevent double-processing
    - Routes jobs to registered handlers by job type
    - Emits heartbeat for external monitoring

    Attributes:
        _scheduler: JobSchedulerProtocol for job persistence
        _halt_checker: HaltChecker to respect system halt state
        _handlers: Dictionary mapping job_type to handler factory
        _poll_interval: Seconds between poll cycles
        _batch_size: Max jobs to process per cycle
        _running: Flag to control worker loop
        _last_heartbeat: Timestamp of last heartbeat

    Example:
        scheduler = PostgresJobScheduler(session_factory)
        halt_checker = HaltCheckerStub()

        worker = JobWorkerService(scheduler, halt_checker)
        worker.register_handler("referral_timeout", ReferralTimeoutHandler())

        # Start worker (runs until stopped)
        await worker.start()

        # Stop worker gracefully
        await worker.stop()
    """

    def __init__(
        self,
        scheduler: JobSchedulerProtocol,
        halt_checker: HaltChecker,
        poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        """Initialize the job worker service.

        Args:
            scheduler: Job scheduler port for persistence.
            halt_checker: Halt checker to respect system halt.
            poll_interval: Seconds between poll cycles (default 10).
            batch_size: Max jobs to process per cycle (default 10).
        """
        self._scheduler = scheduler
        self._halt_checker = halt_checker
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._handlers: dict[str, JobHandler] = {}
        self._running = False
        self._last_heartbeat: datetime | None = None
        self._worker_task: asyncio.Task[None] | None = None

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """Register a handler for a job type.

        Args:
            job_type: The job type string (e.g., "referral_timeout").
            handler: The JobHandler instance to handle this job type.
        """
        self._handlers[job_type] = handler
        logger.info(
            "handler_registered",
            job_type=job_type,
            handler_type=type(handler).__name__,
        )

    async def start(self) -> None:
        """Start the worker loop.

        Runs until stop() is called. Polls for pending jobs
        at the configured interval and executes them.

        NFR-7.5: Emits heartbeat at each poll cycle.
        """
        if self._running:
            logger.warning("worker_already_running")
            return

        self._running = True
        logger.info(
            "worker_starting",
            poll_interval=self._poll_interval,
            batch_size=self._batch_size,
            registered_handlers=list(self._handlers.keys()),
        )

        while self._running:
            await self._poll_cycle()
            await asyncio.sleep(self._poll_interval)

        logger.info("worker_stopped")

    async def start_background(self) -> None:
        """Start the worker loop in the background.

        Returns immediately, worker runs as background task.
        Use stop() to stop the worker.
        """
        if self._running:
            logger.warning("worker_already_running")
            return

        self._worker_task = asyncio.create_task(self.start())
        logger.info("worker_started_background")

    async def stop(self) -> None:
        """Stop the worker loop gracefully.

        Sets running flag to False and waits for current
        poll cycle to complete.
        """
        if not self._running:
            logger.warning("worker_not_running")
            return

        logger.info("worker_stopping")
        self._running = False

        # Wait for background task if running
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("worker_stop_timeout", timeout=30)
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    logger.info("worker_task_cancelled")
            finally:
                self._worker_task = None

    async def _poll_cycle(self) -> None:
        """Execute one poll cycle.

        1. Emit heartbeat
        2. Check halt state
        3. Get pending jobs
        4. Claim and execute each job
        """
        log = logger.bind(cycle_time=_utc_now().isoformat())

        # NFR-7.5: Emit heartbeat
        self._emit_heartbeat()

        # Developer Golden Rule: HALT FIRST
        if await self._halt_checker.is_halted():
            halt_reason = await self._halt_checker.get_halt_reason()
            log.warning(
                "poll_skipped_halted",
                halt_reason=halt_reason,
                message="CT-11: System halted, skipping job execution",
            )
            return

        # Get pending jobs
        try:
            pending_jobs = await self._scheduler.get_pending_jobs(
                limit=self._batch_size
            )
        except Exception as e:
            log.error(
                "poll_get_pending_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return

        if not pending_jobs:
            log.debug("poll_no_pending_jobs")
            return

        log.info("poll_found_jobs", count=len(pending_jobs))

        # Process each job
        for job in pending_jobs:
            await self._process_job(job)

    async def _process_job(self, job: ScheduledJob) -> None:
        """Process a single job.

        1. Claim the job
        2. Find handler
        3. Execute handler
        4. Mark completed or failed

        Args:
            job: The ScheduledJob to process.
        """
        log = logger.bind(
            job_id=str(job.id),
            job_type=job.job_type,
        )

        # Claim the job atomically
        claimed = await self._scheduler.claim_job(job.id)
        if not claimed:
            log.debug("job_already_claimed")
            return

        log.info("job_claimed")

        # Find handler for this job type
        handler = self._handlers.get(job.job_type)
        if handler is None:
            log.error(
                "job_no_handler",
                available_handlers=list(self._handlers.keys()),
            )
            await self._scheduler.mark_failed(
                job.id,
                f"No handler registered for job type: {job.job_type}",
            )
            return

        # Execute handler
        try:
            await handler.execute(claimed)
            await self._scheduler.mark_completed(job.id)
            log.info("job_completed")
        except Exception as e:
            log.error(
                "job_execution_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            dlq_job = await self._scheduler.mark_failed(job.id, str(e))
            if dlq_job:
                log.warning(
                    "job_moved_to_dlq",
                    dlq_id=str(dlq_job.id),
                    attempts=dlq_job.attempts,
                    message="HC-6: Job moved to dead letter queue",
                )

    def _emit_heartbeat(self) -> None:
        """Emit heartbeat for monitoring (NFR-7.5).

        Logs heartbeat timestamp for external monitoring systems
        to detect if worker has stopped.
        """
        self._last_heartbeat = _utc_now()
        logger.debug(
            "worker_heartbeat",
            timestamp=self._last_heartbeat.isoformat(),
            poll_interval=self._poll_interval,
            message="NFR-7.5: Worker heartbeat emitted",
        )

    def get_last_heartbeat(self) -> datetime | None:
        """Get the timestamp of the last heartbeat.

        Returns:
            The last heartbeat timestamp, or None if never emitted.
        """
        return self._last_heartbeat

    def is_running(self) -> bool:
        """Check if the worker is currently running.

        Returns:
            True if worker is running, False otherwise.
        """
        return self._running

    async def process_single_job(self, job_id: UUID) -> bool:
        """Process a single job by ID (for testing).

        Args:
            job_id: UUID of the job to process.

        Returns:
            True if job was processed, False if not found or failed.
        """
        job = await self._scheduler.get_job(job_id)
        if not job:
            return False

        await self._process_job(job)
        return True
