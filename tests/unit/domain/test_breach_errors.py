"""Unit tests for breach domain errors (Story 6.1, FR30).

Tests for BreachError hierarchy: BreachError, BreachDeclarationError,
InvalidBreachTypeError, BreachQueryError.

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events
- CT-11: Silent failure destroys legitimacy -> All errors include FR reference
"""

from __future__ import annotations

import pytest

from src.domain.errors.breach import (
    BreachDeclarationError,
    BreachError,
    BreachQueryError,
    InvalidBreachTypeError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestBreachError:
    """Tests for BreachError base class."""

    def test_breach_error_inherits_from_constitutional_violation(self) -> None:
        """BreachError inherits from ConstitutionalViolationError."""
        assert issubclass(BreachError, ConstitutionalViolationError)

    def test_breach_error_can_be_raised(self) -> None:
        """BreachError can be raised with message."""
        with pytest.raises(BreachError) as exc_info:
            raise BreachError("Test breach error")

        assert str(exc_info.value) == "Test breach error"

    def test_breach_error_is_exception(self) -> None:
        """BreachError is an Exception."""
        assert issubclass(BreachError, Exception)


class TestBreachDeclarationError:
    """Tests for BreachDeclarationError."""

    def test_inherits_from_breach_error(self) -> None:
        """BreachDeclarationError inherits from BreachError."""
        assert issubclass(BreachDeclarationError, BreachError)

    def test_can_be_raised_with_custom_message(self) -> None:
        """BreachDeclarationError can be raised with custom message."""
        with pytest.raises(BreachDeclarationError) as exc_info:
            raise BreachDeclarationError("Failed to declare breach")

        assert "Failed to declare breach" in str(exc_info.value)

    def test_default_message_includes_fr30(self) -> None:
        """BreachDeclarationError default message includes FR30 reference."""
        error = BreachDeclarationError()
        assert "FR30" in str(error)

    def test_caught_by_breach_error_handler(self) -> None:
        """BreachDeclarationError is caught by BreachError handler."""
        with pytest.raises(BreachError):
            raise BreachDeclarationError("Test")

    def test_caught_by_constitutional_violation_handler(self) -> None:
        """BreachDeclarationError is caught by ConstitutionalViolationError handler."""
        with pytest.raises(ConstitutionalViolationError):
            raise BreachDeclarationError("Test")


class TestInvalidBreachTypeError:
    """Tests for InvalidBreachTypeError."""

    def test_inherits_from_breach_error(self) -> None:
        """InvalidBreachTypeError inherits from BreachError."""
        assert issubclass(InvalidBreachTypeError, BreachError)

    def test_can_be_raised_with_invalid_type(self) -> None:
        """InvalidBreachTypeError can be raised with invalid type value."""
        invalid_type = "UNKNOWN_BREACH_TYPE"

        with pytest.raises(InvalidBreachTypeError) as exc_info:
            raise InvalidBreachTypeError(invalid_type)

        assert invalid_type in str(exc_info.value)

    def test_stores_invalid_type_attribute(self) -> None:
        """InvalidBreachTypeError stores the invalid type."""
        invalid_type = "BAD_TYPE"
        error = InvalidBreachTypeError(invalid_type)

        assert error.invalid_type == invalid_type

    def test_message_includes_fr30(self) -> None:
        """InvalidBreachTypeError message includes FR30 reference."""
        error = InvalidBreachTypeError("UNKNOWN")
        assert "FR30" in str(error)


class TestBreachQueryError:
    """Tests for BreachQueryError."""

    def test_inherits_from_breach_error(self) -> None:
        """BreachQueryError inherits from BreachError."""
        assert issubclass(BreachQueryError, BreachError)

    def test_can_be_raised_with_custom_message(self) -> None:
        """BreachQueryError can be raised with custom message."""
        with pytest.raises(BreachQueryError) as exc_info:
            raise BreachQueryError("Failed to query breaches")

        assert "Failed to query breaches" in str(exc_info.value)

    def test_default_message_includes_fr30(self) -> None:
        """BreachQueryError default message includes FR30 reference."""
        error = BreachQueryError()
        assert "FR30" in str(error)

    def test_caught_by_breach_error_handler(self) -> None:
        """BreachQueryError is caught by BreachError handler."""
        with pytest.raises(BreachError):
            raise BreachQueryError("Test")
