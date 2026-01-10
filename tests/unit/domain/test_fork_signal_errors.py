"""Unit tests for fork signal errors (Story 3.8, FR84-FR85).

Tests domain errors for fork signal signing and rate limiting.

Constitutional Constraints:
- FR84: Fork detection signals MUST be signed
- FR85: Fork signal rate limiting prevents DoS
- CT-11: Silent failure destroys legitimacy - invalid signatures MUST be logged
- CT-13: Integrity outranks availability - reject unsigned/invalid signals
"""

import pytest

from src.domain.errors.fork_signal import (
    ForkSignalRateLimitExceededError,
    InvalidForkSignatureError,
    UnsignedForkSignalError,
)


class TestUnsignedForkSignalError:
    """Tests for UnsignedForkSignalError."""

    def test_create_with_default_message(self) -> None:
        """Should create error with default message."""
        error = UnsignedForkSignalError()
        assert "unsigned" in str(error).lower() or "signature" in str(error).lower()

    def test_create_with_custom_message(self) -> None:
        """Should create error with custom message."""
        error = UnsignedForkSignalError("Custom message")
        assert "Custom message" in str(error)

    def test_is_exception(self) -> None:
        """Error should be an Exception."""
        error = UnsignedForkSignalError()
        assert isinstance(error, Exception)

    def test_can_be_raised(self) -> None:
        """Error should be raisable."""
        with pytest.raises(UnsignedForkSignalError):
            raise UnsignedForkSignalError("Test error")


class TestInvalidForkSignatureError:
    """Tests for InvalidForkSignatureError."""

    def test_create_with_default_message(self) -> None:
        """Should create error with default message."""
        error = InvalidForkSignatureError()
        assert (
            "invalid" in str(error).lower()
            or "signature" in str(error).lower()
            or "verification" in str(error).lower()
        )

    def test_create_with_custom_message(self) -> None:
        """Should create error with custom message."""
        error = InvalidForkSignatureError("Signature verification failed")
        assert "Signature verification failed" in str(error)

    def test_create_with_key_id(self) -> None:
        """Should create error with key ID context."""
        error = InvalidForkSignatureError(key_id="key-001")
        assert "key-001" in str(error)

    def test_is_exception(self) -> None:
        """Error should be an Exception."""
        error = InvalidForkSignatureError()
        assert isinstance(error, Exception)

    def test_can_be_raised(self) -> None:
        """Error should be raisable."""
        with pytest.raises(InvalidForkSignatureError):
            raise InvalidForkSignatureError("Test error")


class TestForkSignalRateLimitExceededError:
    """Tests for ForkSignalRateLimitExceededError."""

    def test_create_with_default_message(self) -> None:
        """Should create error with default message."""
        error = ForkSignalRateLimitExceededError()
        assert "rate" in str(error).lower() or "limit" in str(error).lower()

    def test_create_with_custom_message(self) -> None:
        """Should create error with custom message."""
        error = ForkSignalRateLimitExceededError("Rate limit exceeded")
        assert "Rate limit exceeded" in str(error)

    def test_create_with_source_id(self) -> None:
        """Should create error with source ID context."""
        error = ForkSignalRateLimitExceededError(source_id="fork-monitor-001")
        assert "fork-monitor-001" in str(error)

    def test_create_with_signal_count(self) -> None:
        """Should create error with signal count context."""
        error = ForkSignalRateLimitExceededError(
            source_id="fork-monitor-001", signal_count=5
        )
        assert "5" in str(error)

    def test_is_exception(self) -> None:
        """Error should be an Exception."""
        error = ForkSignalRateLimitExceededError()
        assert isinstance(error, Exception)

    def test_can_be_raised(self) -> None:
        """Error should be raisable."""
        with pytest.raises(ForkSignalRateLimitExceededError):
            raise ForkSignalRateLimitExceededError("Test error")


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_unsigned_error_has_correct_base(self) -> None:
        """UnsignedForkSignalError should have correct base class."""
        error = UnsignedForkSignalError()
        # Should be Exception or subclass
        assert isinstance(error, Exception)

    def test_invalid_signature_error_has_correct_base(self) -> None:
        """InvalidForkSignatureError should have correct base class."""
        error = InvalidForkSignatureError()
        # Should be Exception or subclass
        assert isinstance(error, Exception)

    def test_rate_limit_error_has_correct_base(self) -> None:
        """ForkSignalRateLimitExceededError should have correct base class."""
        error = ForkSignalRateLimitExceededError()
        # Should be Exception or subclass
        assert isinstance(error, Exception)
