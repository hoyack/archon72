"""Unit tests for cessation domain errors (Story 6.3, FR32).

Tests cover:
- CessationError base class
- CessationAlreadyTriggeredError
- CessationConsiderationNotFoundError
- InvalidCessationDecisionError
- BelowThresholdError
- Error inheritance hierarchy
- FR32 reference in error messages
"""

from __future__ import annotations

from uuid import UUID

import pytest

from src.domain.errors.cessation import (
    BelowThresholdError,
    CessationAlreadyTriggeredError,
    CessationConsiderationNotFoundError,
    CessationError,
    InvalidCessationDecisionError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestCessationErrorBase:
    """Tests for CessationError base class."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Test CessationError inherits from ConstitutionalViolationError."""
        assert issubclass(CessationError, ConstitutionalViolationError)

    def test_can_be_instantiated_with_message(self) -> None:
        """Test CessationError can be created with a message."""
        error = CessationError("Test cessation error")
        assert str(error) == "Test cessation error"

    def test_can_be_raised_and_caught(self) -> None:
        """Test CessationError can be raised and caught."""
        with pytest.raises(CessationError) as exc_info:
            raise CessationError("Test error")
        assert "Test error" in str(exc_info.value)


class TestCessationAlreadyTriggeredError:
    """Tests for CessationAlreadyTriggeredError."""

    def test_inherits_from_cessation_error(self) -> None:
        """Test inherits from CessationError."""
        assert issubclass(CessationAlreadyTriggeredError, CessationError)

    def test_error_message_includes_fr32_reference(self) -> None:
        """Test error message references FR32."""
        error = CessationAlreadyTriggeredError(
            consideration_id=UUID("12345678-1234-5678-1234-567812345678")
        )
        message = str(error)
        assert "FR32" in message

    def test_error_message_includes_consideration_id(self) -> None:
        """Test error message includes the consideration ID."""
        consideration_id = UUID("12345678-1234-5678-1234-567812345678")
        error = CessationAlreadyTriggeredError(consideration_id=consideration_id)
        assert str(consideration_id) in str(error)

    def test_stores_consideration_id(self) -> None:
        """Test error stores the consideration ID."""
        consideration_id = UUID("12345678-1234-5678-1234-567812345678")
        error = CessationAlreadyTriggeredError(consideration_id=consideration_id)
        assert error.consideration_id == consideration_id


class TestCessationConsiderationNotFoundError:
    """Tests for CessationConsiderationNotFoundError."""

    def test_inherits_from_cessation_error(self) -> None:
        """Test inherits from CessationError."""
        assert issubclass(CessationConsiderationNotFoundError, CessationError)

    def test_error_message_includes_fr32_reference(self) -> None:
        """Test error message references FR32."""
        error = CessationConsiderationNotFoundError(
            consideration_id=UUID("12345678-1234-5678-1234-567812345678")
        )
        message = str(error)
        assert "FR32" in message

    def test_error_message_includes_consideration_id(self) -> None:
        """Test error message includes the consideration ID."""
        consideration_id = UUID("12345678-1234-5678-1234-567812345678")
        error = CessationConsiderationNotFoundError(consideration_id=consideration_id)
        assert str(consideration_id) in str(error)

    def test_stores_consideration_id(self) -> None:
        """Test error stores the consideration ID."""
        consideration_id = UUID("12345678-1234-5678-1234-567812345678")
        error = CessationConsiderationNotFoundError(consideration_id=consideration_id)
        assert error.consideration_id == consideration_id


class TestInvalidCessationDecisionError:
    """Tests for InvalidCessationDecisionError."""

    def test_inherits_from_cessation_error(self) -> None:
        """Test inherits from CessationError."""
        assert issubclass(InvalidCessationDecisionError, CessationError)

    def test_error_message_includes_fr32_reference(self) -> None:
        """Test error message references FR32."""
        error = InvalidCessationDecisionError(
            consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
            reason="Decision already recorded",
        )
        message = str(error)
        assert "FR32" in message

    def test_error_message_includes_reason(self) -> None:
        """Test error message includes the reason."""
        error = InvalidCessationDecisionError(
            consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
            reason="Decision already recorded",
        )
        assert "Decision already recorded" in str(error)

    def test_stores_consideration_id_and_reason(self) -> None:
        """Test error stores consideration ID and reason."""
        consideration_id = UUID("12345678-1234-5678-1234-567812345678")
        error = InvalidCessationDecisionError(
            consideration_id=consideration_id,
            reason="Test reason",
        )
        assert error.consideration_id == consideration_id
        assert error.reason == "Test reason"


class TestBelowThresholdError:
    """Tests for BelowThresholdError."""

    def test_inherits_from_cessation_error(self) -> None:
        """Test inherits from CessationError."""
        assert issubclass(BelowThresholdError, CessationError)

    def test_error_message_includes_fr32_reference(self) -> None:
        """Test error message references FR32."""
        error = BelowThresholdError(current_count=5, threshold=10)
        message = str(error)
        assert "FR32" in message

    def test_error_message_includes_counts(self) -> None:
        """Test error message includes current and threshold counts."""
        error = BelowThresholdError(current_count=5, threshold=10)
        message = str(error)
        assert "5" in message
        assert "10" in message

    def test_stores_current_count_and_threshold(self) -> None:
        """Test error stores current count and threshold."""
        error = BelowThresholdError(current_count=5, threshold=10)
        assert error.current_count == 5
        assert error.threshold == 10


class TestErrorHierarchy:
    """Tests for overall error hierarchy."""

    def test_all_cessation_errors_caught_by_base(self) -> None:
        """Test all specific errors can be caught by CessationError."""
        errors = [
            CessationAlreadyTriggeredError(
                consideration_id=UUID("12345678-1234-5678-1234-567812345678")
            ),
            CessationConsiderationNotFoundError(
                consideration_id=UUID("12345678-1234-5678-1234-567812345678")
            ),
            InvalidCessationDecisionError(
                consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
                reason="Test",
            ),
            BelowThresholdError(current_count=5, threshold=10),
        ]

        for error in errors:
            with pytest.raises(CessationError):
                raise error

    def test_all_cessation_errors_caught_by_constitutional_violation(self) -> None:
        """Test all specific errors can be caught by ConstitutionalViolationError."""
        errors = [
            CessationAlreadyTriggeredError(
                consideration_id=UUID("12345678-1234-5678-1234-567812345678")
            ),
            CessationConsiderationNotFoundError(
                consideration_id=UUID("12345678-1234-5678-1234-567812345678")
            ),
            InvalidCessationDecisionError(
                consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
                reason="Test",
            ),
            BelowThresholdError(current_count=5, threshold=10),
        ]

        for error in errors:
            with pytest.raises(ConstitutionalViolationError):
                raise error
