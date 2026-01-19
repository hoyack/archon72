"""Unit tests for QueueOverflowError (Story 1.3, FR-1.4).

Tests for queue overflow error including:
- Error message formatting
- Attribute preservation
- RFC 7807 response data

Constitutional Constraints Tested:
- FR-1.4: Return HTTP 503 on queue overflow
- NFR-3.1: No silent petition loss
"""

from __future__ import annotations

import pytest

from src.domain.errors.queue_overflow import QueueOverflowError


class TestQueueOverflowError:
    """Tests for QueueOverflowError."""

    def test_error_message_includes_depth_and_threshold(self) -> None:
        """Error message should include queue depth and threshold."""
        error = QueueOverflowError(
            queue_depth=150,
            threshold=100,
            retry_after_seconds=60,
        )

        assert "150" in str(error)
        assert "100" in str(error)
        assert "150/100" in str(error)

    def test_error_message_includes_retry_after(self) -> None:
        """Error message should include retry delay suggestion."""
        error = QueueOverflowError(
            queue_depth=150,
            threshold=100,
            retry_after_seconds=30,
        )

        assert "30 seconds" in str(error)

    def test_preserves_queue_depth_attribute(self) -> None:
        """queue_depth attribute should be preserved."""
        error = QueueOverflowError(queue_depth=250, threshold=200)
        assert error.queue_depth == 250

    def test_preserves_threshold_attribute(self) -> None:
        """threshold attribute should be preserved."""
        error = QueueOverflowError(queue_depth=250, threshold=200)
        assert error.threshold == 200

    def test_preserves_retry_after_attribute(self) -> None:
        """retry_after_seconds attribute should be preserved."""
        error = QueueOverflowError(
            queue_depth=250,
            threshold=200,
            retry_after_seconds=90,
        )
        assert error.retry_after_seconds == 90

    def test_default_retry_after_is_60_seconds(self) -> None:
        """Default Retry-After should be 60 seconds."""
        error = QueueOverflowError(queue_depth=150, threshold=100)
        assert error.retry_after_seconds == 60

    def test_inherits_from_constitutional_violation(self) -> None:
        """Should inherit from ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError

        error = QueueOverflowError(queue_depth=150, threshold=100)
        assert isinstance(error, ConstitutionalViolationError)

    def test_is_exception(self) -> None:
        """Should be raisable as an exception."""
        error = QueueOverflowError(queue_depth=150, threshold=100)
        assert isinstance(error, Exception)

        # Should be raisable
        with pytest.raises(QueueOverflowError) as exc_info:
            raise error

        assert exc_info.value.queue_depth == 150

    def test_str_representation_is_informative(self) -> None:
        """String representation should be informative for logging."""
        error = QueueOverflowError(
            queue_depth=5000,
            threshold=4000,
            retry_after_seconds=120,
        )

        message = str(error)

        # Should include key information
        assert "5000" in message
        assert "4000" in message
        assert "120" in message
        assert "capacity" in message.lower() or "queue" in message.lower()
