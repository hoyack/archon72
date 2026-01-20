"""Co-Sign Rate Limiter Stub for testing (Story 5.4, FR-6.6, SYBIL-1).

This module provides a configurable stub implementation of CoSignRateLimiterProtocol
for use in unit and integration tests.

Constitutional Constraints:
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- NFR-5.1: Rate limiting per identity: Configurable per type
- CT-11: Fail loud, not silent - return 429 with rate limit info
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.ports.co_sign_rate_limiter import CoSignRateLimitResult


class CoSignRateLimiterStub:
    """Stub implementation of CoSignRateLimiterProtocol for testing (Story 5.4).

    Provides full control over rate limiting behavior for testing
    different scenarios including:
    - Normal operation (within rate limit)
    - Rate limit exceeded (blocking co-signs)
    - Window reset timing
    - Per-signer tracking

    Attributes:
        _limit: Maximum co-signs per window (default: 50 per FR-6.6).
        _window_minutes: Sliding window size in minutes (default: 60).
        _counts: Per-signer co-sign counts.
        _reset_at: Per-signer reset times.
    """

    def __init__(
        self,
        limit: int = 50,
        window_minutes: int = 60,
    ) -> None:
        """Initialize co-sign rate limiter stub.

        Args:
            limit: Maximum co-signs per signer per window (default: 50).
            window_minutes: Sliding window size in minutes (default: 60).
        """
        self._limit = limit
        self._window_minutes = window_minutes
        self._counts: dict[UUID, int] = {}
        self._reset_at: dict[UUID, datetime] = {}

    async def check_rate_limit(self, signer_id: UUID) -> CoSignRateLimitResult:
        """Check if signer is within co-sign rate limit.

        Args:
            signer_id: UUID of the signer to check.

        Returns:
            CoSignRateLimitResult with allowed status and rate limit info.
        """
        current_count = self._counts.get(signer_id, 0)
        remaining = max(0, self._limit - current_count)
        allowed = current_count < self._limit

        # Calculate reset time
        reset_at = self._reset_at.get(signer_id)
        if reset_at is None:
            reset_at = datetime.now(timezone.utc) + timedelta(
                minutes=self._window_minutes
            )

        return CoSignRateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            current_count=current_count,
            limit=self._limit,
        )

    async def record_co_sign(self, signer_id: UUID) -> None:
        """Record a co-sign against the signer's rate limit.

        Args:
            signer_id: UUID of the signer who co-signed.
        """
        current = self._counts.get(signer_id, 0)
        self._counts[signer_id] = current + 1

        # Set reset time if first co-sign
        if signer_id not in self._reset_at:
            self._reset_at[signer_id] = datetime.now(timezone.utc) + timedelta(
                minutes=self._window_minutes
            )

    async def get_remaining(self, signer_id: UUID) -> int:
        """Get remaining co-signs in current window.

        Args:
            signer_id: UUID of the signer to check.

        Returns:
            Number of co-signs remaining before rate limit.
        """
        current_count = self._counts.get(signer_id, 0)
        return max(0, self._limit - current_count)

    def get_limit(self) -> int:
        """Get configured rate limit per hour.

        Returns:
            Maximum co-signs per signer per hour.
        """
        return self._limit

    def get_window_minutes(self) -> int:
        """Get configured sliding window size in minutes.

        Returns:
            Window size in minutes.
        """
        return self._window_minutes

    # Test helper methods

    def set_count(self, signer_id: UUID, count: int) -> None:
        """Set co-sign count for a signer (test helper).

        Args:
            signer_id: UUID of the signer.
            count: Co-sign count to set.
        """
        self._counts[signer_id] = count

    def set_limit(self, limit: int) -> None:
        """Set rate limit (test helper).

        Args:
            limit: New rate limit value.
        """
        self._limit = limit

    def set_reset_at(self, signer_id: UUID, reset_at: datetime) -> None:
        """Set reset time for a signer (test helper).

        Args:
            signer_id: UUID of the signer.
            reset_at: Reset time to set.
        """
        self._reset_at[signer_id] = reset_at

    def get_count(self, signer_id: UUID) -> int:
        """Get current count for a signer (test helper).

        Args:
            signer_id: UUID of the signer.

        Returns:
            Current co-sign count.
        """
        return self._counts.get(signer_id, 0)

    def reset(self) -> None:
        """Reset all counters and state (test helper)."""
        self._counts.clear()
        self._reset_at.clear()

    def reset_signer(self, signer_id: UUID) -> None:
        """Reset a specific signer's state (test helper).

        Args:
            signer_id: UUID of the signer to reset.
        """
        self._counts.pop(signer_id, None)
        self._reset_at.pop(signer_id, None)

    @classmethod
    def allowing(cls, limit: int = 50) -> CoSignRateLimiterStub:
        """Factory for stub that allows co-signs.

        Args:
            limit: Rate limit (default: 50).

        Returns:
            CoSignRateLimiterStub configured to allow co-signs.
        """
        return cls(limit=limit)

    @classmethod
    def at_limit(
        cls,
        signer_id: UUID,
        limit: int = 50,
        reset_in_seconds: int = 1800,
    ) -> CoSignRateLimiterStub:
        """Factory for stub at rate limit for a signer.

        Args:
            signer_id: UUID of the signer at limit.
            limit: Rate limit (default: 50).
            reset_in_seconds: Seconds until reset (default: 1800).

        Returns:
            CoSignRateLimiterStub configured at rate limit for signer.
        """
        stub = cls(limit=limit)
        stub._counts[signer_id] = limit
        stub._reset_at[signer_id] = datetime.now(timezone.utc) + timedelta(
            seconds=reset_in_seconds
        )
        return stub

    @classmethod
    def over_limit(
        cls,
        signer_id: UUID,
        limit: int = 50,
        current_count: int = 55,
        reset_in_seconds: int = 1800,
    ) -> CoSignRateLimiterStub:
        """Factory for stub over rate limit for a signer.

        Args:
            signer_id: UUID of the signer over limit.
            limit: Rate limit (default: 50).
            current_count: Current co-sign count (default: 55).
            reset_in_seconds: Seconds until reset (default: 1800).

        Returns:
            CoSignRateLimiterStub configured over rate limit for signer.
        """
        stub = cls(limit=limit)
        stub._counts[signer_id] = current_count
        stub._reset_at[signer_id] = datetime.now(timezone.utc) + timedelta(
            seconds=reset_in_seconds
        )
        return stub
