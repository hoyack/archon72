"""Unit tests for Duration validation domain service (Story 5.2, FR24).

Tests verify that:
- Valid durations pass validation
- Duration below minimum raises DurationValidationError
- Duration above maximum raises DurationValidationError
- Zero and negative durations are rejected
"""

import pytest

from src.domain.errors.override import DurationValidationError
from src.domain.services.duration_validator import (
    MAX_DURATION_SECONDS,
    MIN_DURATION_SECONDS,
    validate_duration,
)


class TestDurationConstants:
    """Tests for duration constants."""

    def test_min_duration_is_60_seconds(self) -> None:
        """Test MIN_DURATION_SECONDS is 1 minute."""
        assert MIN_DURATION_SECONDS == 60

    def test_max_duration_is_7_days(self) -> None:
        """Test MAX_DURATION_SECONDS is 7 days (604800 seconds)."""
        assert MAX_DURATION_SECONDS == 604800

    def test_max_duration_calculation(self) -> None:
        """Verify max duration calculation is correct."""
        # 7 days * 24 hours * 60 minutes * 60 seconds
        expected = 7 * 24 * 60 * 60
        assert MAX_DURATION_SECONDS == expected


class TestValidDurations:
    """Tests for valid duration values."""

    def test_minimum_duration_passes(self) -> None:
        """Test that minimum duration (60 seconds) is valid."""
        # Should not raise
        validate_duration(MIN_DURATION_SECONDS)

    def test_maximum_duration_passes(self) -> None:
        """Test that maximum duration (7 days) is valid."""
        # Should not raise
        validate_duration(MAX_DURATION_SECONDS)

    def test_mid_range_duration_passes(self) -> None:
        """Test that mid-range duration is valid."""
        # 1 hour = 3600 seconds
        validate_duration(3600)

    def test_one_day_duration_passes(self) -> None:
        """Test that 1 day duration is valid."""
        one_day = 24 * 60 * 60
        validate_duration(one_day)


class TestInvalidDurations:
    """Tests for invalid duration values."""

    def test_zero_duration_fails(self) -> None:
        """Test that zero duration raises DurationValidationError."""
        with pytest.raises(DurationValidationError) as exc_info:
            validate_duration(0)
        assert "FR24" in str(exc_info.value)
        assert "Duration" in str(exc_info.value) or "duration" in str(exc_info.value)

    def test_negative_duration_fails(self) -> None:
        """Test that negative duration raises DurationValidationError."""
        with pytest.raises(DurationValidationError) as exc_info:
            validate_duration(-100)
        assert "FR24" in str(exc_info.value)

    def test_below_minimum_fails(self) -> None:
        """Test that duration below minimum raises DurationValidationError."""
        with pytest.raises(DurationValidationError) as exc_info:
            validate_duration(MIN_DURATION_SECONDS - 1)
        assert "FR24" in str(exc_info.value)
        assert str(MIN_DURATION_SECONDS) in str(exc_info.value)

    def test_above_maximum_fails(self) -> None:
        """Test that duration above maximum raises DurationValidationError."""
        with pytest.raises(DurationValidationError) as exc_info:
            validate_duration(MAX_DURATION_SECONDS + 1)
        assert "FR24" in str(exc_info.value)
        assert "7 days" in str(exc_info.value) or str(MAX_DURATION_SECONDS) in str(exc_info.value)

    def test_very_large_duration_fails(self) -> None:
        """Test that very large duration raises DurationValidationError."""
        # 30 days is way over the limit
        with pytest.raises(DurationValidationError):
            validate_duration(30 * 24 * 60 * 60)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_one_second_below_min_fails(self) -> None:
        """Test duration 1 second below minimum fails."""
        with pytest.raises(DurationValidationError):
            validate_duration(59)

    def test_one_second_above_max_fails(self) -> None:
        """Test duration 1 second above maximum fails."""
        with pytest.raises(DurationValidationError):
            validate_duration(604801)

    def test_one_second_above_min_passes(self) -> None:
        """Test duration 1 second above minimum passes."""
        validate_duration(61)  # Should not raise

    def test_one_second_below_max_passes(self) -> None:
        """Test duration 1 second below maximum passes."""
        validate_duration(604799)  # Should not raise
