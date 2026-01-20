"""Rate Limiter Stub for testing (Story 1.4, FR-1.5, HC-4).

This module provides a configurable stub implementation of RateLimiterPort
for use in unit and integration tests.

Constitutional Constraints:
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- CT-11: Fail loud, not silent - return 429 with rate limit info
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.ports.rate_limiter import RateLimitResult


class RateLimiterStub:
    """Stub implementation of RateLimiterPort for testing (Story 1.4, FR-1.5, HC-4).

    Provides full control over rate limiting behavior for testing
    different scenarios including:
    - Normal operation (within rate limit)
    - Rate limit exceeded (blocking submissions)
    - Window reset timing
    - Per-submitter tracking

    Attributes:
        _limit: Maximum submissions per window (default: 10 per HC-4).
        _window_minutes: Sliding window size in minutes (default: 60).
        _counts: Per-submitter submission counts.
        _reset_at: Per-submitter reset times.
    """

    def __init__(
        self,
        limit: int = 10,
        window_minutes: int = 60,
    ) -> None:
        """Initialize rate limiter stub.

        Args:
            limit: Maximum submissions per submitter per window (default: 10).
            window_minutes: Sliding window size in minutes (default: 60).
        """
        self._limit = limit
        self._window_minutes = window_minutes
        self._counts: dict[UUID, int] = {}
        self._reset_at: dict[UUID, datetime] = {}

    async def check_rate_limit(self, submitter_id: UUID) -> RateLimitResult:
        """Check if submitter is within rate limit.

        Args:
            submitter_id: UUID of the submitter to check.

        Returns:
            RateLimitResult with allowed status and rate limit info.
        """
        current_count = self._counts.get(submitter_id, 0)
        remaining = max(0, self._limit - current_count)
        allowed = current_count < self._limit

        # Calculate reset time
        reset_at = self._reset_at.get(submitter_id)
        if reset_at is None:
            reset_at = datetime.now(timezone.utc) + timedelta(
                minutes=self._window_minutes
            )

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            current_count=current_count,
            limit=self._limit,
        )

    async def record_submission(self, submitter_id: UUID) -> None:
        """Record a submission against the submitter's rate limit.

        Args:
            submitter_id: UUID of the submitter who submitted.
        """
        current = self._counts.get(submitter_id, 0)
        self._counts[submitter_id] = current + 1

        # Set reset time if first submission
        if submitter_id not in self._reset_at:
            self._reset_at[submitter_id] = datetime.now(timezone.utc) + timedelta(
                minutes=self._window_minutes
            )

    async def get_remaining(self, submitter_id: UUID) -> int:
        """Get remaining submissions in current window.

        Args:
            submitter_id: UUID of the submitter to check.

        Returns:
            Number of submissions remaining before rate limit.
        """
        current_count = self._counts.get(submitter_id, 0)
        return max(0, self._limit - current_count)

    def get_limit(self) -> int:
        """Get configured rate limit per hour.

        Returns:
            Maximum submissions per submitter per hour.
        """
        return self._limit

    def get_window_minutes(self) -> int:
        """Get configured sliding window size in minutes.

        Returns:
            Window size in minutes.
        """
        return self._window_minutes

    # Test helper methods

    def set_count(self, submitter_id: UUID, count: int) -> None:
        """Set submission count for a submitter (test helper).

        Args:
            submitter_id: UUID of the submitter.
            count: Submission count to set.
        """
        self._counts[submitter_id] = count

    def set_limit(self, limit: int) -> None:
        """Set rate limit (test helper).

        Args:
            limit: New rate limit value.
        """
        self._limit = limit

    def set_reset_at(self, submitter_id: UUID, reset_at: datetime) -> None:
        """Set reset time for a submitter (test helper).

        Args:
            submitter_id: UUID of the submitter.
            reset_at: Reset time to set.
        """
        self._reset_at[submitter_id] = reset_at

    def get_count(self, submitter_id: UUID) -> int:
        """Get current count for a submitter (test helper).

        Args:
            submitter_id: UUID of the submitter.

        Returns:
            Current submission count.
        """
        return self._counts.get(submitter_id, 0)

    def reset(self) -> None:
        """Reset all counters and state (test helper)."""
        self._counts.clear()
        self._reset_at.clear()

    def reset_submitter(self, submitter_id: UUID) -> None:
        """Reset a specific submitter's state (test helper).

        Args:
            submitter_id: UUID of the submitter to reset.
        """
        self._counts.pop(submitter_id, None)
        self._reset_at.pop(submitter_id, None)

    @classmethod
    def allowing(cls, limit: int = 10) -> RateLimiterStub:
        """Factory for stub that allows submissions.

        Args:
            limit: Rate limit (default: 10).

        Returns:
            RateLimiterStub configured to allow submissions.
        """
        return cls(limit=limit)

    @classmethod
    def at_limit(
        cls,
        submitter_id: UUID,
        limit: int = 10,
        reset_in_seconds: int = 1800,
    ) -> RateLimiterStub:
        """Factory for stub at rate limit for a submitter.

        Args:
            submitter_id: UUID of the submitter at limit.
            limit: Rate limit (default: 10).
            reset_in_seconds: Seconds until reset (default: 1800).

        Returns:
            RateLimiterStub configured at rate limit for submitter.
        """
        stub = cls(limit=limit)
        stub._counts[submitter_id] = limit
        stub._reset_at[submitter_id] = datetime.now(timezone.utc) + timedelta(
            seconds=reset_in_seconds
        )
        return stub

    @classmethod
    def over_limit(
        cls,
        submitter_id: UUID,
        limit: int = 10,
        current_count: int = 15,
        reset_in_seconds: int = 1800,
    ) -> RateLimiterStub:
        """Factory for stub over rate limit for a submitter.

        Args:
            submitter_id: UUID of the submitter over limit.
            limit: Rate limit (default: 10).
            current_count: Current submission count (default: 15).
            reset_in_seconds: Seconds until reset (default: 1800).

        Returns:
            RateLimiterStub configured over rate limit for submitter.
        """
        stub = cls(limit=limit)
        stub._counts[submitter_id] = current_count
        stub._reset_at[submitter_id] = datetime.now(timezone.utc) + timedelta(
            seconds=reset_in_seconds
        )
        return stub
