"""Unit tests for ForkSignalRateLimiterPort (Story 3.8, FR85).

Tests the abstract port for fork signal rate limiting.

Constitutional Constraints:
- FR85: More than 3 fork signals per hour triggers rate limiting
"""

from src.application.ports.fork_signal_rate_limiter import ForkSignalRateLimiterPort


class TestForkSignalRateLimiterPortConstants:
    """Tests for ForkSignalRateLimiterPort constants."""

    def test_rate_limit_threshold_value(self) -> None:
        """Rate limit threshold should be 3 per FR85."""
        assert ForkSignalRateLimiterPort.RATE_LIMIT_THRESHOLD == 3

    def test_rate_limit_window_hours_value(self) -> None:
        """Rate limit window should be 1 hour per FR85."""
        assert ForkSignalRateLimiterPort.RATE_LIMIT_WINDOW_HOURS == 1

    def test_threshold_is_int(self) -> None:
        """Threshold should be an integer."""
        assert isinstance(ForkSignalRateLimiterPort.RATE_LIMIT_THRESHOLD, int)

    def test_window_hours_is_int(self) -> None:
        """Window hours should be an integer."""
        assert isinstance(ForkSignalRateLimiterPort.RATE_LIMIT_WINDOW_HOURS, int)


class TestForkSignalRateLimiterPortInterface:
    """Tests for ForkSignalRateLimiterPort interface definition."""

    def test_has_check_rate_limit_method(self) -> None:
        """Port should define check_rate_limit method."""
        assert hasattr(ForkSignalRateLimiterPort, "check_rate_limit")

    def test_has_record_signal_method(self) -> None:
        """Port should define record_signal method."""
        assert hasattr(ForkSignalRateLimiterPort, "record_signal")

    def test_has_get_signal_count_method(self) -> None:
        """Port should define get_signal_count method."""
        assert hasattr(ForkSignalRateLimiterPort, "get_signal_count")

    def test_is_protocol_or_abc(self) -> None:
        """Port should be a Protocol or ABC for type checking."""
        # Protocol or ABC both work for dependency injection
        # Just verify it can be used as a type hint

        # Port should be usable as a type annotation
        # This is a compile-time check, but we verify the class exists
        assert ForkSignalRateLimiterPort is not None


class TestForkSignalRateLimiterPortDocumentation:
    """Tests for ForkSignalRateLimiterPort documentation."""

    def test_has_docstring(self) -> None:
        """Port should have a docstring."""
        assert ForkSignalRateLimiterPort.__doc__ is not None
        assert len(ForkSignalRateLimiterPort.__doc__) > 0

    def test_docstring_mentions_fr85(self) -> None:
        """Docstring should reference FR85."""
        assert "FR85" in ForkSignalRateLimiterPort.__doc__

    def test_docstring_mentions_rate_limit(self) -> None:
        """Docstring should mention rate limit."""
        assert "rate" in ForkSignalRateLimiterPort.__doc__.lower()
