"""Rate Limit Bucket Cleanup Service (Story 1.4, AC3, D4).

This module provides the RateLimitCleanupService that removes expired
rate limit buckets from the PostgreSQL time-bucket store.

Constitutional Constraints:
- D4: PostgreSQL time-bucket counters - buckets must be cleaned up after TTL
- CT-11: Silent failure destroys legitimacy → All operations logged
- CT-12: Witnessing creates accountability → Cleanup is auditable
- NFR-5.1: Rate limiting per identity → Maintains data hygiene

Architecture:
- Called by scheduled job or can be invoked manually
- Default TTL: 2 hours (configurable via PETITION_RATE_LIMIT_TTL_HOURS)
- Deletes buckets with bucket_minute < (NOW() - TTL)
- Logs deletion count for monitoring

Usage:
    # In a scheduled job or worker:
    cleanup_service = RateLimitCleanupService(
        store=postgres_rate_limit_store,
        ttl_hours=2,
    )
    deleted = await cleanup_service.cleanup()

    # Or with config:
    config = PetitionRateLimitConfig.from_environment()
    cleanup_service = RateLimitCleanupService(
        store=postgres_rate_limit_store,
        ttl_hours=config.bucket_ttl_hours,
    )
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.application.services.base import LoggingMixin
from src.infrastructure.monitoring.metrics import get_metrics_collector

if TYPE_CHECKING:
    from src.application.ports.rate_limit_store import RateLimitStorePort


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class RateLimitCleanupService(LoggingMixin):
    """Service for cleaning up expired rate limit buckets (Story 1.4, AC3, D4).

    This service implements TTL-based cleanup of rate limit buckets.
    Buckets older than the configured TTL are deleted to maintain
    database hygiene and performance.

    Constitutional Compliance:
    - D4: PostgreSQL time-bucket counters require TTL cleanup
    - CT-11: Cleanup failures are logged, not silently ignored
    - CT-12: Cleanup operations are auditable via logs

    Configuration:
    - ttl_hours: Hours before buckets expire (default: 2)
                 MUST be > window_minutes (default: 60 min = 1 hour)
                 The extra buffer ensures buckets don't expire mid-window

    Scheduling Recommendations:
    - Run cleanup job every 30 minutes
    - Can safely run more frequently without issues
    - Each run is idempotent (deletes already-expired buckets)

    Attributes:
        _store: RateLimitStorePort for bucket deletion
        _ttl_hours: Hours before buckets are considered expired
    """

    def __init__(
        self,
        store: RateLimitStorePort,
        ttl_hours: int = 2,
    ) -> None:
        """Initialize the cleanup service.

        Args:
            store: Rate limit store with cleanup capability.
            ttl_hours: Hours before buckets expire (default: 2).
                      Should be > window_minutes to prevent race conditions.
        """
        self._store = store
        self._ttl_hours = ttl_hours

        # Initialize logging
        self._init_logger(component="petition.rate_limit.cleanup")

    async def cleanup(self) -> int:
        """Clean up expired rate limit buckets.

        Deletes all buckets with bucket_minute older than (NOW() - TTL hours).

        Returns:
            Number of buckets deleted.

        Logs:
            - INFO: Number of buckets deleted (for monitoring)
            - DEBUG: Cutoff time used for deletion
        """
        log = self._log_operation("cleanup_expired_buckets")

        # Calculate cutoff time
        now = _utc_now()
        cutoff = now - timedelta(hours=self._ttl_hours)

        log.debug(
            "cleanup_starting",
            ttl_hours=self._ttl_hours,
            cutoff=cutoff.isoformat(),
        )

        # Perform cleanup
        deleted_count = await self._store.cleanup_expired_buckets(cutoff)

        # Log results
        log.info(
            "cleanup_completed",
            deleted_count=deleted_count,
            ttl_hours=self._ttl_hours,
            cutoff=cutoff.isoformat(),
        )

        return deleted_count

    async def cleanup_and_report(self) -> dict:
        """Clean up and return detailed report.

        Useful for manual invocation or monitoring endpoints.

        Returns:
            Dictionary with cleanup results:
            - deleted_count: Number of buckets deleted
            - cutoff: ISO timestamp of cutoff time
            - ttl_hours: Configured TTL
            - executed_at: ISO timestamp of execution
        """
        log = self._log_operation("cleanup_and_report")

        now = _utc_now()
        cutoff = now - timedelta(hours=self._ttl_hours)

        deleted_count = await self._store.cleanup_expired_buckets(cutoff)

        report = {
            "deleted_count": deleted_count,
            "cutoff": cutoff.isoformat(),
            "ttl_hours": self._ttl_hours,
            "executed_at": now.isoformat(),
        }

        log.info(
            "cleanup_report_generated",
            **report,
        )

        return report

    def get_ttl_hours(self) -> int:
        """Get configured TTL in hours.

        Returns:
            TTL in hours.
        """
        return self._ttl_hours


class RateLimitCleanupJobHandler:
    """Job handler for rate limit cleanup (JobWorkerService integration).

    This handler can be registered with the JobWorkerService to
    run rate limit cleanup as a scheduled job.

    Usage with JobWorkerService:
        cleanup_handler = RateLimitCleanupJobHandler(store=postgres_store)
        worker = JobWorkerService(scheduler=scheduler, halt_checker=halt_checker)
        worker.register_handler("rate_limit_cleanup", lambda: cleanup_handler)
    """

    # Job type constant for registration
    JOB_TYPE = "rate_limit_cleanup"

    def __init__(
        self,
        store: RateLimitStorePort,
        ttl_hours: int = 2,
    ) -> None:
        """Initialize the job handler.

        Args:
            store: Rate limit store with cleanup capability.
            ttl_hours: Hours before buckets expire.
        """
        self._service = RateLimitCleanupService(
            store=store,
            ttl_hours=ttl_hours,
        )

    async def execute(self, job) -> None:
        """Execute the cleanup job.

        Args:
            job: The ScheduledJob (not used, but required by interface).

        Raises:
            Exception: Propagated from cleanup for retry/DLQ handling.
        """
        await self._service.cleanup()
