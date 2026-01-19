"""Dead Letter Queue Alert Service (Story 0.4, AC6, HC-6).

This module provides the DLQAlertService that monitors the dead letter
queue and triggers alerts when jobs fail permanently.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Failed jobs MUST be visible
- HC-6: Dead-letter alerting for failed jobs → Alert when DLQ depth > 0
- NFR-7.5: Timeout monitoring → Missed deadline visibility

Architecture:
- Polls DLQ depth at configurable interval
- Triggers alert callback when depth > 0
- Logs all DLQ state changes for audit trail
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable

from structlog import get_logger

from src.application.ports.job_scheduler import JobSchedulerProtocol
from src.domain.models.scheduled_job import DeadLetterJob

logger = get_logger()

# Default polling interval for DLQ checks
DEFAULT_DLQ_CHECK_INTERVAL_SECONDS = 60

# Alert severity levels
ALERT_SEVERITY_WARNING = "warning"
ALERT_SEVERITY_CRITICAL = "critical"

# Threshold for critical alerts (jobs in DLQ)
CRITICAL_DLQ_DEPTH_THRESHOLD = 10


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


# Type alias for alert callback
AlertCallback = Callable[[str, str, int, list[DeadLetterJob]], None]


class DLQAlertService:
    """Service for monitoring and alerting on dead letter queue (AC6, HC-6).

    This service monitors the dead letter queue and triggers alerts
    when jobs fail permanently and are moved to the DLQ.

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy → DLQ visibility
    - HC-6: Dead-letter alerting for failed jobs

    Alert Levels:
    - WARNING: DLQ depth > 0 (any failed jobs)
    - CRITICAL: DLQ depth >= CRITICAL_DLQ_DEPTH_THRESHOLD (10)

    Attributes:
        _scheduler: JobSchedulerProtocol for DLQ access
        _check_interval: Seconds between DLQ checks
        _alert_callback: Optional callback for alerts
        _running: Flag to control monitor loop
        _last_alert_depth: Last DLQ depth that triggered alert
        _last_check: Timestamp of last check

    Example:
        scheduler = PostgresJobScheduler(session_factory)

        def alert_callback(severity, message, depth, jobs):
            send_slack_alert(severity, message)

        alert_service = DLQAlertService(scheduler, alert_callback=alert_callback)
        await alert_service.start()
    """

    def __init__(
        self,
        scheduler: JobSchedulerProtocol,
        check_interval: int = DEFAULT_DLQ_CHECK_INTERVAL_SECONDS,
        alert_callback: AlertCallback | None = None,
    ) -> None:
        """Initialize the DLQ alert service.

        Args:
            scheduler: Job scheduler port for DLQ access.
            check_interval: Seconds between DLQ checks (default 60).
            alert_callback: Optional callback for alerts.
        """
        self._scheduler = scheduler
        self._check_interval = check_interval
        self._alert_callback = alert_callback
        self._running = False
        self._last_alert_depth = 0
        self._last_check: datetime | None = None
        self._monitor_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the DLQ monitoring loop.

        Runs until stop() is called. Checks DLQ depth at the
        configured interval and triggers alerts when needed.
        """
        if self._running:
            logger.warning("dlq_monitor_already_running")
            return

        self._running = True
        logger.info(
            "dlq_monitor_starting",
            check_interval=self._check_interval,
        )

        while self._running:
            await self._check_cycle()
            await asyncio.sleep(self._check_interval)

        logger.info("dlq_monitor_stopped")

    async def start_background(self) -> None:
        """Start the DLQ monitoring loop in the background.

        Returns immediately, monitor runs as background task.
        Use stop() to stop the monitor.
        """
        if self._running:
            logger.warning("dlq_monitor_already_running")
            return

        self._monitor_task = asyncio.create_task(self.start())
        logger.info("dlq_monitor_started_background")

    async def stop(self) -> None:
        """Stop the DLQ monitoring loop gracefully."""
        if not self._running:
            logger.warning("dlq_monitor_not_running")
            return

        logger.info("dlq_monitor_stopping")
        self._running = False

        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("dlq_monitor_stop_timeout")
                self._monitor_task.cancel()
            finally:
                self._monitor_task = None

    async def _check_cycle(self) -> None:
        """Execute one DLQ check cycle."""
        log = logger.bind(cycle_time=_utc_now().isoformat())
        self._last_check = _utc_now()

        try:
            depth = await self._scheduler.get_dlq_depth()
        except Exception as e:
            log.error(
                "dlq_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return

        log.debug("dlq_check_completed", depth=depth)

        # Check if alert needed
        if depth > 0:
            await self._trigger_alert(depth)
        elif self._last_alert_depth > 0:
            # DLQ was cleared
            log.info(
                "dlq_cleared",
                previous_depth=self._last_alert_depth,
                message="HC-6: Dead letter queue cleared",
            )
            self._last_alert_depth = 0

    async def _trigger_alert(self, depth: int) -> None:
        """Trigger an alert for DLQ depth.

        Args:
            depth: Current DLQ depth.
        """
        log = logger.bind(dlq_depth=depth)

        # Determine severity
        if depth >= CRITICAL_DLQ_DEPTH_THRESHOLD:
            severity = ALERT_SEVERITY_CRITICAL
        else:
            severity = ALERT_SEVERITY_WARNING

        # Only alert on depth change or severity escalation
        if depth == self._last_alert_depth:
            log.debug("dlq_alert_suppressed", reason="depth unchanged")
            return

        # Get DLQ jobs for alert context
        try:
            dlq_jobs, _ = await self._scheduler.get_dlq_jobs(limit=10)
        except Exception as e:
            log.error("dlq_get_jobs_failed", error=str(e))
            dlq_jobs = []

        # Build alert message
        message = self._build_alert_message(depth, severity, dlq_jobs)

        # Log alert
        log.warning(
            "dlq_alert_triggered",
            severity=severity,
            depth=depth,
            message=message,
            job_types=[job.job_type for job in dlq_jobs],
            alert_message="HC-6: Dead letter queue alert triggered",
        )

        # Call alert callback if registered
        if self._alert_callback:
            try:
                self._alert_callback(severity, message, depth, dlq_jobs)
            except Exception as e:
                log.error(
                    "dlq_alert_callback_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        self._last_alert_depth = depth

    def _build_alert_message(
        self,
        depth: int,
        severity: str,
        jobs: list[DeadLetterJob],
    ) -> str:
        """Build human-readable alert message.

        Args:
            depth: Current DLQ depth.
            severity: Alert severity level.
            jobs: List of DLQ jobs.

        Returns:
            Alert message string.
        """
        job_types = set(job.job_type for job in jobs)
        job_types_str = ", ".join(job_types) if job_types else "unknown"

        if severity == ALERT_SEVERITY_CRITICAL:
            return (
                f"CRITICAL: Dead letter queue depth ({depth}) exceeds threshold "
                f"({CRITICAL_DLQ_DEPTH_THRESHOLD}). Job types affected: {job_types_str}. "
                "Immediate investigation required."
            )
        else:
            return (
                f"WARNING: {depth} job(s) in dead letter queue. "
                f"Job types affected: {job_types_str}. "
                "Review and resolve failed jobs."
            )

    async def check_now(self) -> int:
        """Check DLQ depth immediately (for testing).

        Returns:
            Current DLQ depth.
        """
        return await self._scheduler.get_dlq_depth()

    def get_last_check(self) -> datetime | None:
        """Get timestamp of last DLQ check.

        Returns:
            Last check timestamp, or None if never checked.
        """
        return self._last_check

    def get_last_alert_depth(self) -> int:
        """Get the DLQ depth that last triggered an alert.

        Returns:
            Last alert depth.
        """
        return self._last_alert_depth

    def is_running(self) -> bool:
        """Check if the monitor is currently running.

        Returns:
            True if monitor is running, False otherwise.
        """
        return self._running


def create_log_alert_callback() -> AlertCallback:
    """Create a simple alert callback that logs alerts.

    Useful for development and testing.

    Returns:
        AlertCallback function that logs alerts.
    """

    def log_alert(
        severity: str,
        message: str,
        depth: int,
        jobs: list[DeadLetterJob],
    ) -> None:
        alert_logger = logger.bind(
            alert_type="dlq_alert",
            severity=severity,
            depth=depth,
        )
        if severity == ALERT_SEVERITY_CRITICAL:
            alert_logger.error(message)
        else:
            alert_logger.warning(message)

    return log_alert
