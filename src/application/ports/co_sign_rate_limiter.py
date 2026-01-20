"""Co-Sign Rate Limiter Port (Story 5.4, FR-6.6, SYBIL-1).

This module defines the abstract interface for checking per-signer co-sign rate limits
using PostgreSQL time-bucket counters per architecture decision D4.

Constitutional Constraints:
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- NFR-5.1: Rate limiting per identity: Configurable per type
- SYBIL-1: Identity verification + rate limiting per verified identity
- D4: PostgreSQL time-bucket counters with minute buckets summed over sliding window
- CT-11: Silent failure destroys legitimacy - return 429, never silently drop

Developer Golden Rules:
1. RATE LIMIT AFTER IDENTITY VERIFICATION - Check rate limit AFTER identity verified
2. RECORD AFTER SUCCESS - Only increment rate limit counter after successful co-sign
3. FAIL LOUD - Return 429 with full rate limit info, never silently drop
4. WITNESS BLOCKS - Rate limit blocks are governance-relevant events (per D4)
5. D4 COMPLIANCE - Use PostgreSQL time-bucket counters, NOT Redis or in-memory
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class CoSignRateLimitResult:
    """Result of co-sign rate limit check (Story 5.4, AC1).

    Attributes:
        allowed: Whether the co-sign is allowed (under rate limit).
        remaining: Number of co-signs remaining before rate limit.
        reset_at: UTC datetime when the rate limit window resets.
        current_count: Current number of co-signs in the window.
        limit: Configured rate limit per hour.
    """

    allowed: bool
    remaining: int
    reset_at: datetime
    current_count: int
    limit: int


@runtime_checkable
class CoSignRateLimiterProtocol(Protocol):
    """Protocol for checking per-signer co-sign rate limits (Story 5.4, FR-6.6).

    Implementations must use PostgreSQL time-bucket counters per architecture
    decision D4. Minute buckets are summed over the sliding window (default 60 min).

    Constitutional Constraints:
    - FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
    - NFR-5.1: Rate limiting per identity: Configurable per type
    - SYBIL-1: Identity verification + rate limiting
    - D4: PostgreSQL time-bucket counters
    - CT-11: Fail loud, not silent

    Usage:
        rate_result = await rate_limiter.check_rate_limit(signer_id)
        if not rate_result.allowed:
            raise CoSignRateLimitExceededError(
                signer_id=signer_id,
                current_count=rate_result.current_count,
                limit=rate_result.limit,
                reset_at=rate_result.reset_at,
            )

        # After successful co-sign:
        await rate_limiter.record_co_sign(signer_id)
    """

    async def check_rate_limit(self, signer_id: UUID) -> CoSignRateLimitResult:
        """Check if signer is within co-sign rate limit using sliding window.

        Uses minute buckets summed over the configured window (default 60 minutes)
        per architecture decision D4.

        Args:
            signer_id: UUID of the signer to check.

        Returns:
            CoSignRateLimitResult with:
            - allowed: True if under limit, False if at/over limit
            - remaining: Number of co-signs remaining
            - reset_at: When the window resets (oldest bucket expires)
            - current_count: Current co-signs in window
            - limit: Configured limit

        Note:
            Rate limit blocks should be witnessed as governance-relevant events
            per D4 architecture decision.
        """
        ...

    async def record_co_sign(self, signer_id: UUID) -> None:
        """Record a co-sign against the signer's rate limit.

        CRITICAL: Must be called AFTER successful co-sign persistence,
        not before. This ensures we don't count failed co-signs.

        Increments the current minute bucket for the signer using UPSERT:
        INSERT ... ON CONFLICT (signer_id, bucket_minute) DO UPDATE SET count = count + 1

        Args:
            signer_id: UUID of the signer who co-signed.
        """
        ...

    async def get_remaining(self, signer_id: UUID) -> int:
        """Get remaining co-signs in current window.

        Convenience method that calls check_rate_limit and returns just
        the remaining count.

        Args:
            signer_id: UUID of the signer to check.

        Returns:
            Number of co-signs remaining before rate limit.
        """
        ...

    def get_limit(self) -> int:
        """Get configured rate limit per hour.

        Returns:
            Maximum co-signs per signer per hour (default: 50 per FR-6.6).
        """
        ...

    def get_window_minutes(self) -> int:
        """Get configured sliding window size in minutes.

        Returns:
            Window size in minutes (default: 60).
        """
        ...
