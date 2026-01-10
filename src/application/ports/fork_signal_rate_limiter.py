"""Fork signal rate limiter port for FR85, Story 3.8.

Abstract port for fork signal rate limiting. Implementations track
fork signal counts per source and enforce the FR85 rate limit of
3 signals per hour per source.

Constitutional Constraints:
- FR85: More than 3 fork signals per hour triggers rate limiting
- Prevents denial-of-service via fake fork spam

Security Note:
    Rate limiting is critical for preventing DoS attacks where
    an attacker spams fake fork signals to trigger unnecessary
    system halts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ForkSignalRateLimiterPort(Protocol):
    """Port for fork signal rate limiting (FR85).

    Abstract interface for tracking fork signal counts per source
    and enforcing rate limits.

    Constitutional Constraints:
    - FR85: 3 signals per hour threshold
    - Prevents DoS via fake fork spam

    Rate Limit Configuration:
    - RATE_LIMIT_THRESHOLD: 3 signals maximum
    - RATE_LIMIT_WINDOW_HOURS: 1 hour window

    Implementation Notes:
    - Implementations track signal timestamps per source
    - Sliding window approach recommended for accuracy
    - Thread-safe implementations required for production
    """

    # FR85: 3 signals per hour threshold
    RATE_LIMIT_THRESHOLD: int = 3

    # FR85: 1 hour window
    RATE_LIMIT_WINDOW_HOURS: int = 1

    async def check_rate_limit(self, source_id: str) -> bool:
        """Check if source is within rate limit.

        Determines if the source is allowed to send another fork
        signal without exceeding the rate limit.

        Args:
            source_id: ID of the service sending fork signals

        Returns:
            True if signal is allowed (within limit),
            False if rate-limited (would exceed limit)
        """
        ...

    async def record_signal(self, source_id: str) -> None:
        """Record a fork signal from source.

        Tracks that a fork signal was received from the given source.
        Should be called after check_rate_limit returns True.

        Args:
            source_id: ID of the service that sent the signal
        """
        ...

    async def get_signal_count(
        self, source_id: str, window_hours: int = RATE_LIMIT_WINDOW_HOURS
    ) -> int:
        """Get the number of signals from source in the window.

        Returns the count of fork signals received from the source
        within the specified time window.

        Args:
            source_id: ID of the service to check
            window_hours: Time window in hours (default: 1)

        Returns:
            Number of signals received in the window
        """
        ...
