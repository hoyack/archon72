"""Unit tests for FR11ViolationError (Story 2.3, FR11).

Tests the domain error for Collective Output Irreducibility violations.

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-11: Silent failure destroys legitimacy
"""

import pytest


class TestFR11ViolationError:
    """Tests for FR11ViolationError domain error."""

    def test_error_exists(self) -> None:
        """FR11ViolationError should be importable."""
        from src.domain.errors.collective import FR11ViolationError

        assert FR11ViolationError is not None

    def test_inherits_from_constitutional_violation(self) -> None:
        """FR11ViolationError should inherit from ConstitutionalViolationError."""
        from src.domain.errors.collective import FR11ViolationError
        from src.domain.errors.constitutional import ConstitutionalViolationError

        assert issubclass(FR11ViolationError, ConstitutionalViolationError)

    def test_can_be_raised(self) -> None:
        """FR11ViolationError should be raiseable with message."""
        from src.domain.errors.collective import FR11ViolationError

        with pytest.raises(FR11ViolationError) as exc_info:
            raise FR11ViolationError(
                "FR11: Collective output requires multiple participants"
            )
        assert "FR11" in str(exc_info.value)
        assert "multiple participants" in str(exc_info.value)

    def test_message_preserved(self) -> None:
        """FR11ViolationError should preserve error message."""
        from src.domain.errors.collective import FR11ViolationError

        msg = "FR11: Cannot claim collective authorship with single agent"
        error = FR11ViolationError(msg)
        assert str(error) == msg

    def test_exportable_from_errors_package(self) -> None:
        """FR11ViolationError should be exportable from domain.errors."""
        from src.domain.errors import FR11ViolationError

        assert FR11ViolationError is not None
