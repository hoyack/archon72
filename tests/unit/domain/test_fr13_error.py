"""Unit tests for FR13ViolationError (Story 2.5, FR13).

Tests the FR13ViolationError domain error class which is raised when
the No Silent Edits constraint is violated (hash mismatch on publish).

Constitutional Constraints Verified:
- FR13: Published hash must equal canonical hash
- CT-11: Silent failure destroys legitimacy → Violations raise errors
- CT-13: Integrity outranks availability → Block publish on mismatch
"""

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.silent_edit import FR13ViolationError


class TestFR13ViolationError:
    """Test suite for FR13ViolationError."""

    def test_fr13_error_inherits_from_constitutional_violation(self) -> None:
        """FR13ViolationError must inherit from ConstitutionalViolationError.

        This ensures FR13 violations are treated as constitutional violations,
        honoring CT-11 (silent failure destroys legitimacy).
        """
        error = FR13ViolationError("FR13: Silent edit detected")
        assert isinstance(error, ConstitutionalViolationError)

    def test_fr13_error_can_be_raised(self) -> None:
        """FR13ViolationError can be raised and caught."""
        with pytest.raises(FR13ViolationError) as exc_info:
            raise FR13ViolationError("FR13: Silent edit detected - hash mismatch")

        assert "FR13" in str(exc_info.value)
        assert "hash mismatch" in str(exc_info.value)

    def test_fr13_error_message_includes_context(self) -> None:
        """Error message should include relevant context per FR13 requirements.

        AC2 requires: error includes "FR13: Silent edit detected - hash mismatch"
        """
        expected_message = "FR13: Silent edit detected - hash mismatch"
        error = FR13ViolationError(expected_message)
        assert str(error) == expected_message

    def test_fr13_error_is_exception(self) -> None:
        """FR13ViolationError must be an Exception for proper error handling."""
        error = FR13ViolationError("FR13: Test")
        assert isinstance(error, Exception)
