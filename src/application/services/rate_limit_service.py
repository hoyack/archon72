"""Rate Limit Service for per-submitter petition rate limiting (Story 1.4, FR-1.5, HC-4).

This service manages per-submitter rate limits using PostgreSQL time-bucket counters
with a sliding window per architecture decision D4.

Constitutional Constraints:
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- NFR-5.1: Rate limiting per identity: Configurable per type
- D4: PostgreSQL time-bucket counters with minute buckets summed over sliding window
- CT-11: Silent failure destroys legitimacy - return 429, never silently drop

Developer Golden Rules:
1. RATE LIMIT AFTER CAPACITY - Check rate limit AFTER queue capacity check (more specific)
2. RECORD AFTER SUCCESS - Only increment rate limit counter after successful submission
3. FAIL LOUD - Return 429 with full rate limit info, never silently drop
4. WITNESS BLOCKS - Rate limit blocks are governance-relevant events (per D4)
5. D4 COMPLIANCE - Use PostgreSQL time-bucket counters, NOT Redis or in-memory
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from src.application.ports.rate_limiter import RateLimitResult
from src.application.services.base import LoggingMixin
from src.infrastructure.monitoring.metrics import get_metrics_collector

if TYPE_CHECKING:
    from src.application.ports.rate_limit_store import RateLimitStorePort


class RateLimitService(LoggingMixin):
    """Manages per-submitter rate limits with PostgreSQL time-bucket counters (Story 1.4).

    Implements D4 architecture decision: minute buckets summed over sliding window.
    Each submitter has a configurable limit (default 10 per HC-4) over a configurable
    window (default 60 minutes).

    Constitutional Constraints:
    - FR-1.5: Enforce rate limits per submitter_id
    - HC-4: 10 petitions/user/hour (configurable)
    - NFR-5.1: Rate limiting per identity
    - D4: PostgreSQL time-bucket counters
    - CT-11: Fail loud, not silent

    Attributes:
        _store: Rate limit bucket storage (PostgreSQL adapter).
        _limit: Maximum submissions per submitter per window (default: 10).
        _window_minutes: Sliding window size in minutes (default: 60).
    """

    def __init__(
        self,
        store: RateLimitStorePort,
        limit_per_hour: int = 10,  # HC-4 default
        window_minutes: int = 60,
    ) -> None:
        """Initialize rate limit service.

        Args:
            store: Rate limit bucket storage port (PostgreSQL adapter).
            limit_per_hour: Maximum submissions per submitter per window (default: 10).
            window_minutes: Sliding window size in minutes (default: 60).
        """
        self._store = store
        self._limit = limit_per_hour
        self._window_minutes = window_minutes

        # Initialize logging
        self._init_logger(component="petition.rate_limit")

    async def check_rate_limit(self, submitter_id: UUID) -> RateLimitResult:
        """Check if submitter is within rate limit using sliding window.

        Uses minute buckets summed over the configured window (default 60 minutes)
        per architecture decision D4.

        Args:
            submitter_id: UUID of the submitter to check.

        Returns:
            RateLimitResult with:
            - allowed: True if under limit, False if at/over limit
            - remaining: Number of submissions remaining
            - reset_at: When the window resets (oldest bucket expires)
            - current_count: Current submissions in window
            - limit: Configured limit
        """
        log = self._log_operation(
            "check_rate_limit",
            submitter_id=str(submitter_id),
        )

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self._window_minutes)

        # Get total submissions in sliding window
        current_count = await self._store.get_submission_count(
            submitter_id=submitter_id,
            since=window_start,
        )

        remaining = max(0, self._limit - current_count)
        allowed = current_count < self._limit

        # Calculate reset time (when oldest bucket expires from window)
        reset_at = await self._store.get_oldest_bucket_expiry(
            submitter_id=submitter_id,
            since=window_start,
        )
        # If no buckets exist, reset is at window end from now
        if reset_at is None:
            reset_at = now + timedelta(minutes=self._window_minutes)

        if not allowed:
            log.info(
                "rate_limit_exceeded",
                current_count=current_count,
                limit=self._limit,
                reset_at=reset_at.isoformat(),
            )
            # Record rate limit hit metric (AC4)
            metrics = get_metrics_collector()
            metrics.increment_petition_rate_limit_hits()

        log.debug(
            "rate_limit_checked",
            current_count=current_count,
            limit=self._limit,
            remaining=remaining,
            allowed=allowed,
        )

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            current_count=current_count,
            limit=self._limit,
        )

    async def record_submission(self, submitter_id: UUID) -> None:
        """Record a submission in the current minute bucket.

        CRITICAL: Must be called AFTER successful submission persistence,
        not before. This ensures we don't count failed submissions.

        Increments the current minute bucket for the submitter using UPSERT:
        INSERT ... ON CONFLICT (submitter_id, bucket_minute) DO UPDATE SET count = count + 1

        Args:
            submitter_id: UUID of the submitter who submitted.
        """
        log = self._log_operation(
            "record_submission",
            submitter_id=str(submitter_id),
        )

        now = datetime.now(timezone.utc)
        # Truncate to minute boundary
        bucket_minute = now.replace(second=0, microsecond=0)

        await self._store.increment_bucket(
            submitter_id=submitter_id,
            bucket_minute=bucket_minute,
        )

        log.debug(
            "submission_recorded",
            bucket_minute=bucket_minute.isoformat(),
        )

    async def get_remaining(self, submitter_id: UUID) -> int:
        """Get remaining submissions in current window.

        Convenience method that calls check_rate_limit and returns just
        the remaining count.

        Args:
            submitter_id: UUID of the submitter to check.

        Returns:
            Number of submissions remaining before rate limit.
        """
        result = await self.check_rate_limit(submitter_id)
        return result.remaining

    def get_limit(self) -> int:
        """Get configured rate limit per hour.

        Returns:
            Maximum submissions per submitter per hour (default: 10 per HC-4).
        """
        return self._limit

    def get_window_minutes(self) -> int:
        """Get configured sliding window size in minutes.

        Returns:
            Window size in minutes (default: 60).
        """
        return self._window_minutes
