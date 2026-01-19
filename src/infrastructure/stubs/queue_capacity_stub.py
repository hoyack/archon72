"""Queue Capacity Stub for testing (Story 1.3, FR-1.4).

This module provides a configurable stub implementation of QueueCapacityPort
for use in unit and integration tests.

Constitutional Constraints:
- FR-1.4: Return HTTP 503 on queue overflow
- NFR-3.1: No silent petition loss
- CT-11: Fail loud, not silent
"""

from __future__ import annotations


class QueueCapacityStub:
    """Stub implementation of QueueCapacityPort for testing (Story 1.3, FR-1.4).

    Provides full control over queue capacity behavior for testing
    different scenarios including:
    - Normal operation (accepting submissions)
    - Queue overflow (rejecting submissions)
    - Threshold boundary testing
    - Hysteresis behavior simulation

    Attributes:
        _threshold: Configured threshold (default: 10,000).
        _hysteresis: Buffer below threshold to resume (default: 500).
        _retry_after: Seconds for Retry-After header (default: 60).
        _current_depth: Simulated queue depth.
        _is_rejecting: Simulated hysteresis state.
    """

    def __init__(
        self,
        threshold: int = 10_000,
        hysteresis: int = 500,
        retry_after_seconds: int = 60,
        initial_depth: int = 0,
        is_rejecting: bool = False,
    ) -> None:
        """Initialize queue capacity stub.

        Args:
            threshold: Maximum queue depth before 503 responses (default: 10,000).
            hysteresis: Buffer below threshold to resume (default: 500).
            retry_after_seconds: Value for Retry-After header (default: 60).
            initial_depth: Starting queue depth (default: 0).
            is_rejecting: Initial rejection state for hysteresis (default: False).
        """
        self._threshold = threshold
        self._hysteresis = hysteresis
        self._retry_after = retry_after_seconds
        self._current_depth = initial_depth
        self._is_rejecting = is_rejecting

    async def is_accepting_submissions(self) -> bool:
        """Check if queue has capacity for new submissions.

        Implements hysteresis logic matching QueueCapacityService behavior.

        Returns:
            True if queue has capacity, False if at or above threshold.
        """
        if self._is_rejecting:
            # Currently rejecting - only resume if below threshold minus hysteresis
            resume_threshold = self._threshold - self._hysteresis
            if self._current_depth < resume_threshold:
                self._is_rejecting = False
                return True
            return False
        else:
            # Currently accepting - reject if at or above threshold
            if self._current_depth >= self._threshold:
                self._is_rejecting = True
                return False
            return True

    async def get_queue_depth(self) -> int:
        """Get current simulated queue depth.

        Returns:
            Configured queue depth value.
        """
        return self._current_depth

    def get_threshold(self) -> int:
        """Get configured queue threshold.

        Returns:
            Maximum queue depth before 503 responses.
        """
        return self._threshold

    def get_retry_after_seconds(self) -> int:
        """Get Retry-After header value.

        Returns:
            Seconds to include in Retry-After header.
        """
        return self._retry_after

    # Test helper methods

    def set_depth(self, depth: int) -> None:
        """Set queue depth for testing.

        Args:
            depth: Queue depth to simulate.
        """
        self._current_depth = depth

    def set_rejecting(self, is_rejecting: bool) -> None:
        """Set rejection state for hysteresis testing.

        Args:
            is_rejecting: Whether currently in rejection state.
        """
        self._is_rejecting = is_rejecting

    def set_threshold(self, threshold: int) -> None:
        """Set threshold for testing.

        Args:
            threshold: New threshold value.
        """
        self._threshold = threshold

    def set_hysteresis(self, hysteresis: int) -> None:
        """Set hysteresis buffer for testing.

        Args:
            hysteresis: New hysteresis value.
        """
        self._hysteresis = hysteresis

    def set_retry_after(self, seconds: int) -> None:
        """Set Retry-After value for testing.

        Args:
            seconds: New Retry-After value.
        """
        self._retry_after = seconds

    def is_rejecting(self) -> bool:
        """Get current rejection state.

        Returns:
            True if currently in rejection state.
        """
        return self._is_rejecting

    def get_hysteresis(self) -> int:
        """Get configured hysteresis buffer.

        Returns:
            Hysteresis value.
        """
        return self._hysteresis

    def record_rejection(self) -> None:
        """Record a 503 rejection (stub implementation).

        Matches QueueCapacityService interface for testing.
        In the stub, this increments an internal counter for verification.
        """
        self._rejection_count = getattr(self, "_rejection_count", 0) + 1

    def get_rejection_count(self) -> int:
        """Get total rejections recorded (test helper).

        Returns:
            Number of times record_rejection was called.
        """
        return getattr(self, "_rejection_count", 0)

    def reset_rejection_count(self) -> None:
        """Reset rejection counter (test helper)."""
        self._rejection_count = 0

    @classmethod
    def accepting(
        cls,
        depth: int = 0,
        threshold: int = 10_000,
    ) -> "QueueCapacityStub":
        """Factory for stub that accepts submissions.

        Args:
            depth: Queue depth (default: 0).
            threshold: Threshold (default: 10,000).

        Returns:
            QueueCapacityStub configured to accept submissions.
        """
        return cls(
            threshold=threshold,
            initial_depth=depth,
            is_rejecting=False,
        )

    @classmethod
    def rejecting(
        cls,
        depth: int = 10_000,
        threshold: int = 10_000,
        retry_after: int = 60,
    ) -> "QueueCapacityStub":
        """Factory for stub that rejects submissions due to capacity.

        Args:
            depth: Queue depth (default: threshold).
            threshold: Threshold (default: 10,000).
            retry_after: Retry-After header value (default: 60).

        Returns:
            QueueCapacityStub configured to reject submissions.
        """
        return cls(
            threshold=threshold,
            initial_depth=depth,
            is_rejecting=True,
            retry_after_seconds=retry_after,
        )
