"""Unit tests for QueueCapacityPort protocol (Story 1.3, FR-1.4).

Tests verify the protocol interface contract for queue capacity checking.

Constitutional Constraints:
- FR-1.4: Return HTTP 503 on queue overflow
- NFR-3.1: No silent petition loss
- CT-11: Fail loud, not silent
"""

from src.application.ports.queue_capacity import QueueCapacityPort


class TestQueueCapacityPort:
    """Tests for QueueCapacityPort protocol definition."""

    def test_protocol_has_is_accepting_submissions_method(self) -> None:
        """QueueCapacityPort MUST define is_accepting_submissions async method."""
        # Protocol defines required method
        assert hasattr(QueueCapacityPort, "is_accepting_submissions")

    def test_protocol_has_get_queue_depth_method(self) -> None:
        """QueueCapacityPort MUST define get_queue_depth async method."""
        assert hasattr(QueueCapacityPort, "get_queue_depth")

    def test_protocol_has_get_threshold_method(self) -> None:
        """QueueCapacityPort MUST define get_threshold method."""
        assert hasattr(QueueCapacityPort, "get_threshold")

    def test_protocol_has_get_retry_after_seconds_method(self) -> None:
        """QueueCapacityPort MUST define get_retry_after_seconds method."""
        assert hasattr(QueueCapacityPort, "get_retry_after_seconds")
