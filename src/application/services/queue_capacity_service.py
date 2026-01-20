"""Queue Capacity Service for petition overflow protection (Story 1.3, FR-1.4).

This service manages petition queue capacity with cached depth tracking
and hysteresis to prevent oscillation at threshold boundaries.

Constitutional Constraints:
- FR-1.4: Return HTTP 503 on queue overflow (no silent drop)
- NFR-3.1: No silent petition loss
- NFR-7.4: Queue depth monitoring with backpressure
- CT-11: Silent failure destroys legitimacy - fail loud

Developer Golden Rules:
1. FAIL LOUD - Return 503, never silently drop
2. CACHE WISELY - 5s TTL balances accuracy vs performance (NFR-1.1)
3. HYSTERESIS - Prevent thundering herd at threshold boundary
4. LOG TRANSITIONS - State changes must be logged for observability
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.application.services.base import LoggingMixin
from src.domain.models.petition_submission import PetitionState

if TYPE_CHECKING:
    from src.application.ports.petition_submission_repository import (
        PetitionSubmissionRepositoryProtocol,
    )


class QueueCapacityService(LoggingMixin):
    """Manages petition queue capacity with cached depth tracking (Story 1.3, FR-1.4).

    Uses time-based caching to avoid database hits on every request, meeting
    NFR-1.1 p99 < 200ms latency requirements. Implements hysteresis to prevent
    rapid state oscillation when queue depth hovers near threshold boundary.

    Constitutional Constraints:
    - FR-1.4: Return HTTP 503 on queue overflow
    - NFR-3.1: No silent petition loss
    - NFR-7.4: Queue depth monitoring with backpressure
    - CT-11: Fail loud, not silent

    Attributes:
        _repository: Petition submission repository for depth queries.
        _threshold: Maximum queue depth before rejecting (default: 10,000).
        _hysteresis: Buffer below threshold to resume accepting (default: 500).
        _cache_ttl: Cache time-to-live in seconds (default: 5.0).
        _retry_after: Seconds for Retry-After header (default: 60).
        _cached_depth: Cached queue depth value.
        _cache_time: Timestamp of last cache update.
        _is_rejecting: Current rejection state for hysteresis tracking.
    """

    def __init__(
        self,
        repository: PetitionSubmissionRepositoryProtocol,
        threshold: int = 10_000,
        hysteresis: int = 500,
        cache_ttl_seconds: float = 5.0,
        retry_after_seconds: int = 60,
    ) -> None:
        """Initialize queue capacity service.

        Args:
            repository: Repository for petition persistence queries.
            threshold: Maximum queue depth before 503 responses (default: 10,000).
            hysteresis: Buffer below threshold to resume (default: 500).
            cache_ttl_seconds: Cache TTL in seconds (default: 5.0).
            retry_after_seconds: Value for Retry-After header (default: 60).
        """
        self._repository = repository
        self._threshold = threshold
        self._hysteresis = hysteresis
        self._cache_ttl = cache_ttl_seconds
        self._retry_after = retry_after_seconds

        # Cache state
        self._cached_depth: int = 0
        self._cache_time: float = 0.0

        # Hysteresis state
        self._is_rejecting: bool = False

        # Initialize logging
        self._init_logger(component="petition")


    async def is_accepting_submissions(self) -> bool:
        """Check if queue has capacity for new submissions.

        Implements hysteresis to prevent rapid state oscillation:
        - When accepting: reject if depth >= threshold
        - When rejecting: resume only if depth < (threshold - hysteresis)

        Returns:
            True if queue has capacity, False if at or above threshold.

        Note:
            State transitions are logged for observability (NFR-7.4).
        """
        log = self._log_operation("is_accepting_submissions")
        depth = await self.get_queue_depth()

        if self._is_rejecting:
            # Currently rejecting - only resume if below threshold minus hysteresis
            resume_threshold = self._threshold - self._hysteresis
            if depth < resume_threshold:
                self._is_rejecting = False
                log.info(
                    "queue_capacity_resumed",
                    depth=depth,
                    threshold=self._threshold,
                    hysteresis=self._hysteresis,
                )
                return True
            log.debug(
                "queue_still_rejecting",
                depth=depth,
                resume_at=resume_threshold,
            )
            return False
        else:
            # Currently accepting - reject if at or above threshold
            if depth >= self._threshold:
                self._is_rejecting = True
                log.warning(
                    "queue_capacity_exceeded",
                    depth=depth,
                    threshold=self._threshold,
                )
                return False
            log.debug(
                "queue_accepting",
                depth=depth,
                threshold=self._threshold,
            )
            return True

    async def get_queue_depth(self) -> int:
        """Get current number of pending petitions (state = RECEIVED).

        Uses caching with TTL to minimize database hits while maintaining
        reasonable accuracy for capacity decisions.

        Returns:
            Count of petitions currently in RECEIVED state.

        Note:
            Cache refreshes automatically when TTL expires.
        """
        now = time.time()
        cache_age = now - self._cache_time

        if cache_age > self._cache_ttl:
            log = self._log_operation("refresh_queue_depth")
            # Refresh cache - we only need the count, not the items
            _, total_count = await self._repository.list_by_state(
                state=PetitionState.RECEIVED,
                limit=1,  # Minimize data transfer
            )
            self._cached_depth = total_count
            self._cache_time = now

            log.debug(
                "queue_depth_refreshed",
                depth=total_count,
                cache_age_seconds=cache_age,
            )

        return self._cached_depth

    def get_threshold(self) -> int:
        """Get configured queue threshold.

        Returns:
            Maximum queue depth before 503 responses (default: 10,000).
        """
        return self._threshold

    def get_retry_after_seconds(self) -> int:
        """Get Retry-After header value.

        Returns:
            Seconds to include in Retry-After header (default: 60).
        """
        return self._retry_after

    def get_hysteresis(self) -> int:
        """Get configured hysteresis buffer.

        Returns:
            Buffer below threshold before resuming accepting (default: 500).
        """
        return self._hysteresis

    def is_rejecting(self) -> bool:
        """Check if service is currently in rejecting state.

        Returns:
            True if currently rejecting due to capacity, False if accepting.

        Note:
            This is the hysteresis state, not just a threshold comparison.
        """
        return self._is_rejecting

    def force_cache_refresh(self) -> None:
        """Force next get_queue_depth call to refresh cache.

        Used for testing or when immediate accuracy is needed.
        """
        self._cache_time = 0.0

    def _set_cached_depth(self, depth: int) -> None:
        """Set cached depth directly (for testing only).

        Args:
            depth: Queue depth to cache.

        Note:
            This method is for testing purposes only. In production,
            cache is updated via get_queue_depth().
        """
        self._cached_depth = depth
        self._cache_time = time.time()

    def record_rejection(self) -> None:
        """Record a 503 rejection (Story 1.3, AC4).

        Called when a petition submission is rejected due to queue overflow.
        This enables alerting on rejection spikes.
        """
        log = self._log_operation("record_rejection")
        log.info(
            "petition_rejected_queue_overflow",
            threshold=self._threshold,
            cached_depth=self._cached_depth,
        )
