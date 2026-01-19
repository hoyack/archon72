"""Queue Capacity Port for petition overflow protection (Story 1.3, FR-1.4).

This module defines the abstract interface for checking petition queue capacity
to implement backpressure and prevent silent petition drops.

Constitutional Constraints:
- FR-1.4: Return HTTP 503 on queue overflow (no silent drop)
- NFR-3.1: No silent petition loss - every petition either persists or gets explicit rejection
- NFR-7.4: Queue depth monitoring with backpressure before overflow
- CT-11: Silent failure destroys legitimacy - fail loud

Developer Golden Rules:
1. FAIL LOUD - Return 503, never silently drop petitions
2. CHECK BEFORE WRITE - Capacity check should precede halt check (more efficient)
3. CACHE WISELY - Minimize database hits for performance (NFR-1.1 p99 < 200ms)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class QueueCapacityPort(Protocol):
    """Protocol for checking petition queue capacity (Story 1.3, FR-1.4).

    Implementations must provide queue depth monitoring with configurable
    thresholds and hysteresis to prevent oscillation at capacity boundaries.

    Constitutional Constraints:
    - FR-1.4: Return HTTP 503 on queue overflow
    - NFR-3.1: No silent petition loss
    - NFR-7.4: Queue depth monitoring with backpressure
    - CT-11: Fail loud, not silent

    Usage:
        if not await capacity_service.is_accepting_submissions():
            raise HTTPException(
                status_code=503,
                headers={"Retry-After": str(capacity_service.get_retry_after_seconds())},
            )
    """

    async def is_accepting_submissions(self) -> bool:
        """Check if queue has capacity for new submissions.

        Implements hysteresis to prevent rapid state oscillation when
        queue depth hovers near threshold boundary.

        Returns:
            True if queue depth < threshold (or below hysteresis recovery point),
            False if at or above capacity threshold.

        Note:
            This method uses cached queue depth to meet NFR-1.1 latency requirements.
            Cache is refreshed periodically (typically 5 seconds TTL).
        """
        ...

    async def get_queue_depth(self) -> int:
        """Get current number of pending petitions (state = RECEIVED).

        Returns cached value if within TTL, otherwise refreshes from repository.

        Returns:
            Count of petitions currently in RECEIVED state awaiting processing.
        """
        ...

    def get_threshold(self) -> int:
        """Get configured queue threshold.

        Returns:
            Maximum queue depth before 503 responses are returned.
            Default: 10,000 per NFR-2.1.
        """
        ...

    def get_retry_after_seconds(self) -> int:
        """Get Retry-After header value for 503 responses.

        Returns:
            Seconds to include in Retry-After header when queue is full.
            Default: 60 seconds.
        """
        ...
