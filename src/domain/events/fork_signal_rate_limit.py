"""Fork signal rate limit event payload for FR85, Story 3.8.

This module defines the ForkSignalRateLimitPayload for rate limit events.
Created when a source exceeds the fork signal rate limit of 3 signals
per hour.

Constitutional Constraints:
- FR85: More than 3 fork signals per hour triggers rate limiting
- CT-11: Silent failure destroys legitimacy - rate limits MUST be logged

Security Note:
    Rate limit events may indicate:
    - DoS attack via fake fork spam
    - Misconfigured monitoring service
    - Actual cascade of constitutional crises
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Event type constant for fork signal rate limit
FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE: str = "fork.signal_rate_limit"


@dataclass(frozen=True, eq=True)
class ForkSignalRateLimitPayload:
    """Payload for fork signal rate limit events - immutable.

    Created when a source exceeds the fork signal rate limit
    (FR85: 3 signals per hour per source).

    Constitutional Constraints:
    - FR85: Rate limiting prevents DoS via fork spam
    - CT-11: Silent failure destroys legitimacy

    Attributes:
        source_service_id: Service that exceeded the limit
        signal_count: Number of signals in the window
        window_start: Start of the rate limit window (UTC)
        window_hours: Duration of the window (default 1)
        rate_limited_at: When the rate limit was applied (UTC)
    """

    # Service that exceeded the rate limit
    source_service_id: str

    # Number of signals from this source in the window
    signal_count: int

    # Start of the rate limit window (should be UTC)
    window_start: datetime

    # When the rate limit was applied (should be UTC)
    rate_limited_at: datetime

    # Window duration in hours (default 1 per FR85)
    window_hours: int = field(default=1)

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing/witnessing.

        Creates deterministic byte representation for cryptographic
        signing and verification.

        Returns:
            bytes: Canonical byte representation for signing
        """
        content = (
            f"fork_signal_rate_limit"
            f":source:{self.source_service_id}"
            f":signal_count:{self.signal_count}"
            f":window_start:{self.window_start.isoformat()}"
            f":window_hours:{self.window_hours}"
            f":rate_limited_at:{self.rate_limited_at.isoformat()}"
        )
        return content.encode("utf-8")
