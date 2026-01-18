"""Unit tests for halt clear errors (Story 3.4, AC #1, #3, #4).

Tests the domain errors for halt clearing operations.
These errors enforce the sticky halt semantics per ADR-3.
"""

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.halt_clear import (
    HaltClearDeniedError,
    InsufficientApproversError,
    InvalidCeremonyError,
)


class TestHaltClearDeniedError:
    """Tests for HaltClearDeniedError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Test that HaltClearDeniedError inherits from ConstitutionalViolationError."""
        error = HaltClearDeniedError("Test message")
        assert isinstance(error, ConstitutionalViolationError)

    def test_error_message(self) -> None:
        """Test that error message is preserved."""
        message = "ADR-3: Halt flag protected - ceremony required"
        error = HaltClearDeniedError(message)
        assert str(error) == message

    def test_raises_correctly(self) -> None:
        """Test that the error can be raised and caught."""
        with pytest.raises(HaltClearDeniedError) as exc_info:
            raise HaltClearDeniedError("ADR-3: Halt flag protected - ceremony required")
        assert "ceremony required" in str(exc_info.value)


class TestInvalidCeremonyError:
    """Tests for InvalidCeremonyError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Test that InvalidCeremonyError inherits from ConstitutionalViolationError."""
        error = InvalidCeremonyError("Test message")
        assert isinstance(error, ConstitutionalViolationError)

    def test_error_message(self) -> None:
        """Test that error message is preserved."""
        message = "Invalid signature from keeper-001"
        error = InvalidCeremonyError(message)
        assert str(error) == message

    def test_raises_correctly(self) -> None:
        """Test that the error can be raised and caught."""
        with pytest.raises(InvalidCeremonyError) as exc_info:
            raise InvalidCeremonyError("Invalid ceremony evidence")
        assert "Invalid ceremony" in str(exc_info.value)


class TestInsufficientApproversError:
    """Tests for InsufficientApproversError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Test that InsufficientApproversError inherits from ConstitutionalViolationError."""
        error = InsufficientApproversError("Test message")
        assert isinstance(error, ConstitutionalViolationError)

    def test_error_message(self) -> None:
        """Test that error message is preserved."""
        message = "ADR-6: Halt clear requires 2 Keepers, got 1"
        error = InsufficientApproversError(message)
        assert str(error) == message

    def test_raises_correctly(self) -> None:
        """Test that the error can be raised and caught."""
        with pytest.raises(InsufficientApproversError) as exc_info:
            raise InsufficientApproversError(
                "ADR-6: Halt clear requires 2 Keepers, got 0"
            )
        assert "2 Keepers" in str(exc_info.value)


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_all_errors_are_constitutional_violations(self) -> None:
        """Test that all halt clear errors are constitutional violations."""
        errors = [
            HaltClearDeniedError("test"),
            InvalidCeremonyError("test"),
            InsufficientApproversError("test"),
        ]
        for error in errors:
            assert isinstance(error, ConstitutionalViolationError)

    def test_errors_are_catchable_as_constitutional_violation(self) -> None:
        """Test that all errors can be caught as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise HaltClearDeniedError("test")

        with pytest.raises(ConstitutionalViolationError):
            raise InvalidCeremonyError("test")

        with pytest.raises(ConstitutionalViolationError):
            raise InsufficientApproversError("test")
