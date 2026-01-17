"""Periodic Anti-Metrics Verification Job.

Story: consent-gov-10.2: Anti-Metrics Verification

This module implements the periodic verification job that runs
anti-metrics verification on a configurable schedule.

Why Periodic Verification?
    - Schema could change (migrations)
    - Code could change (new endpoints)
    - Continuous assurance
    - Early detection of violations

Schedule:
    - Daily minimum (default)
    - After each deployment (triggered externally)
    - On demand (CLI)
    - After schema migrations (triggered externally)

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from uuid import UUID, uuid4

import structlog

from src.application.ports.time_authority import TimeAuthorityProtocol
from src.application.services.governance.anti_metrics_verification_service import (
    AntiMetricsVerificationService,
)
from src.domain.governance.antimetrics.verification import (
    VerificationReport,
    VerificationStatus,
)

log = structlog.get_logger()


@dataclass(frozen=True)
class VerificationJobConfig:
    """Configuration for periodic verification job.

    Attributes:
        interval_seconds: Time between verification runs (default: 24 hours)
        verifier_id: ID to use as verifier for audit trail
        alert_on_violations: Whether to trigger alerts on violations
        run_on_start: Whether to run verification immediately on startup
    """

    interval_seconds: int = 86400  # 24 hours default
    verifier_id: UUID = field(default_factory=uuid4)
    alert_on_violations: bool = True
    run_on_start: bool = True

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.interval_seconds < 60:
            raise ValueError("interval_seconds must be at least 60 (1 minute)")


@dataclass
class JobRunResult:
    """Result of a single verification job run.

    Attributes:
        run_id: Unique ID for this run
        started_at: When the run started
        completed_at: When the run completed
        report: The verification report (if successful)
        error: Error message (if failed)
        success: Whether the run completed successfully
    """

    run_id: UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    report: Optional[VerificationReport] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Whether the run completed successfully."""
        return self.report is not None and self.error is None

    @property
    def passed(self) -> bool:
        """Whether the verification passed (no violations)."""
        return (
            self.report is not None
            and self.report.overall_status == VerificationStatus.PASS
        )


# Type alias for alert callback
AlertCallback = Callable[[VerificationReport], None]


class PeriodicVerificationJob:
    """Periodic verification job that runs on a schedule.

    This job runs anti-metrics verification at regular intervals
    to provide continuous assurance that the system remains
    surveillance-free.

    Usage:
        job = PeriodicVerificationJob(
            verification_service=service,
            time_authority=time_authority,
            config=VerificationJobConfig(
                interval_seconds=3600,  # Every hour
                run_on_start=True,
            ),
        )

        # Set alert callback (optional)
        job.set_alert_callback(my_alert_function)

        # Start the job
        await job.start()

        # Later, stop the job
        await job.stop()

    Constitutional Reference:
        NFR-CONST-08: Anti-metrics are enforced at data layer;
        collection endpoints do not exist.
    """

    def __init__(
        self,
        verification_service: AntiMetricsVerificationService,
        time_authority: TimeAuthorityProtocol,
        config: VerificationJobConfig | None = None,
    ) -> None:
        """Initialize the periodic verification job.

        Args:
            verification_service: Service to run verifications
            time_authority: Authority for timestamps
            config: Job configuration (defaults used if not provided)
        """
        self._service = verification_service
        self._time = time_authority
        self._config = config or VerificationJobConfig()

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._run_count = 0
        self._last_run: Optional[JobRunResult] = None
        self._history: list[JobRunResult] = []
        self._alert_callback: Optional[AlertCallback] = None

    @property
    def is_running(self) -> bool:
        """Whether the job is currently running."""
        return self._running

    @property
    def run_count(self) -> int:
        """Number of verification runs completed."""
        return self._run_count

    @property
    def last_run(self) -> Optional[JobRunResult]:
        """Result of the most recent run."""
        return self._last_run

    @property
    def history(self) -> list[JobRunResult]:
        """History of all runs (most recent first)."""
        return self._history.copy()

    def set_alert_callback(self, callback: AlertCallback | None) -> None:
        """Set callback to be invoked when violations are found.

        Args:
            callback: Function that receives VerificationReport when
                     violations are detected. Set to None to disable.
        """
        self._alert_callback = callback

    async def start(self) -> None:
        """Start the periodic verification job.

        If run_on_start is True in config, runs verification immediately.
        Then starts the periodic loop.

        Raises:
            RuntimeError: If job is already running
        """
        if self._running:
            raise RuntimeError("Job is already running")

        self._running = True
        log.info(
            "periodic_verification_job_starting",
            interval_seconds=self._config.interval_seconds,
            run_on_start=self._config.run_on_start,
        )

        # Run immediately if configured
        if self._config.run_on_start:
            await self.run_once()

        # Start the periodic loop
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop the periodic verification job.

        Cancels the periodic task and waits for it to finish.
        """
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        log.info("periodic_verification_job_stopped", run_count=self._run_count)

    async def run_once(self) -> JobRunResult:
        """Run a single verification.

        This method can be called independently of the periodic loop.

        Returns:
            JobRunResult with the outcome
        """
        run_id = uuid4()
        started_at = self._time.utcnow()

        log.info("verification_job_run_starting", run_id=str(run_id))

        result = JobRunResult(run_id=run_id, started_at=started_at)

        try:
            report = await self._service.verify_all(
                verifier_id=self._config.verifier_id
            )
            result.report = report
            result.completed_at = self._time.utcnow()

            log.info(
                "verification_job_run_completed",
                run_id=str(run_id),
                status=report.overall_status.value,
                violations=report.total_violations,
            )

            # Alert on violations if configured
            if (
                self._config.alert_on_violations
                and report.overall_status == VerificationStatus.FAIL
            ):
                await self._handle_violations(report)

        except Exception as e:
            result.error = str(e)
            result.completed_at = self._time.utcnow()
            log.error(
                "verification_job_run_failed",
                run_id=str(run_id),
                error=str(e),
            )

        # Update tracking
        self._run_count += 1
        self._last_run = result
        self._history.insert(0, result)

        # Keep history bounded (last 100 runs)
        if len(self._history) > 100:
            self._history = self._history[:100]

        return result

    async def _loop(self) -> None:
        """Internal periodic loop."""
        while self._running:
            try:
                await asyncio.sleep(self._config.interval_seconds)
                if self._running:  # Check again after sleep
                    await self.run_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("verification_job_loop_error", error=str(e))

    async def _handle_violations(self, report: VerificationReport) -> None:
        """Handle violations found during verification.

        Args:
            report: Report containing violations
        """
        log.warning(
            "anti_metrics_violations_detected",
            total_violations=report.total_violations,
            report_id=str(report.report_id),
        )

        # Call alert callback if set
        if self._alert_callback:
            try:
                self._alert_callback(report)
            except Exception as e:
                log.error(
                    "alert_callback_failed",
                    error=str(e),
                )

    def get_stats(self) -> dict:
        """Get job statistics.

        Returns:
            Dict with job statistics
        """
        successful_runs = sum(1 for r in self._history if r.success)
        passed_runs = sum(1 for r in self._history if r.passed)
        failed_runs = sum(1 for r in self._history if not r.success)

        return {
            "running": self._running,
            "total_runs": self._run_count,
            "successful_runs": successful_runs,
            "passed_runs": passed_runs,
            "failed_runs": failed_runs,
            "last_run_at": (
                self._last_run.started_at.isoformat() if self._last_run else None
            ),
            "last_run_passed": self._last_run.passed if self._last_run else None,
            "interval_seconds": self._config.interval_seconds,
        }
