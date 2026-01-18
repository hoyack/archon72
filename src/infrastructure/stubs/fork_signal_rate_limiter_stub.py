"""Fork signal rate limiter stub for Story 3.8, FR85.

Test stub implementation of ForkSignalRateLimiterPort.
Provides in-memory rate limiting for testing scenarios.

Constitutional Constraints:
- FR85: More than 3 fork signals per hour triggers rate limiting
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.application.ports.fork_signal_rate_limiter import ForkSignalRateLimiterPort


class ForkSignalRateLimiterStub:
    """Stub implementation of ForkSignalRateLimiterPort for testing.

    Provides in-memory rate limiting with configurable thresholds.
    Supports test helper methods for simulating rate limit scenarios.

    Constitutional Constraints:
    - FR85: 3 signals per hour threshold (default)

    Attributes:
        _signal_counts: Per-source signal timestamps
        _rate_limit_threshold: Maximum signals per window
        _window_hours: Window duration in hours
        _forced_rate_limited: Sources forced into rate-limited state
    """

    # Class-level constants to match the Port protocol
    RATE_LIMIT_THRESHOLD: int = ForkSignalRateLimiterPort.RATE_LIMIT_THRESHOLD
    RATE_LIMIT_WINDOW_HOURS: int = ForkSignalRateLimiterPort.RATE_LIMIT_WINDOW_HOURS

    def __init__(
        self,
        rate_limit_threshold: int = ForkSignalRateLimiterPort.RATE_LIMIT_THRESHOLD,
        window_hours: int = ForkSignalRateLimiterPort.RATE_LIMIT_WINDOW_HOURS,
    ) -> None:
        """Initialize the stub.

        Args:
            rate_limit_threshold: Maximum signals per window (default 3)
            window_hours: Window duration in hours (default 1)
        """
        self._signal_counts: dict[str, list[datetime]] = {}
        self._rate_limit_threshold = rate_limit_threshold
        self._window_hours = window_hours
        self._forced_rate_limited: dict[str, bool] = {}

    async def check_rate_limit(self, source_id: str) -> bool:
        """Check if source is within rate limit.

        Args:
            source_id: ID of the service sending fork signals

        Returns:
            True if signal is allowed, False if rate-limited
        """
        # Check if forced rate-limited for testing
        if self._forced_rate_limited.get(source_id, False):
            return False

        # Count signals in current window
        count = await self.get_signal_count(source_id, self._window_hours)
        return count < self._rate_limit_threshold

    async def record_signal(self, source_id: str) -> None:
        """Record a fork signal from source.

        Args:
            source_id: ID of the service that sent the signal
        """
        now = datetime.now(timezone.utc)
        if source_id not in self._signal_counts:
            self._signal_counts[source_id] = []
        self._signal_counts[source_id].append(now)

    async def get_signal_count(
        self,
        source_id: str,
        window_hours: int = ForkSignalRateLimiterPort.RATE_LIMIT_WINDOW_HOURS,
    ) -> int:
        """Get the number of signals from source in the window.

        Args:
            source_id: ID of the service to check
            window_hours: Time window in hours

        Returns:
            Number of signals received in the window
        """
        if source_id not in self._signal_counts:
            return 0

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=window_hours)

        # Count signals within window
        signals_in_window = [
            ts for ts in self._signal_counts[source_id] if ts > window_start
        ]
        return len(signals_in_window)

    # Test helper methods

    def reset(self) -> None:
        """Reset all signal data. Test helper."""
        self._signal_counts.clear()
        self._forced_rate_limited.clear()

    def set_rate_limited(self, source_id: str, rate_limited: bool) -> None:
        """Force a source into/out of rate-limited state. Test helper.

        Args:
            source_id: Source to set state for
            rate_limited: True to force rate-limited, False to clear
        """
        if rate_limited:
            self._forced_rate_limited[source_id] = True
        else:
            self._forced_rate_limited.pop(source_id, None)
