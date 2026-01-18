"""Unit tests for read-only mode errors (Story 3.5, Task 2.5).

Tests the FR20-specific error classes for write and provisional
operation blocking during halt.
"""

import pytest

from src.domain.errors import (
    ProvisionalBlockedDuringHaltError,
    WriteBlockedDuringHaltError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestWriteBlockedDuringHaltError:
    """Tests for WriteBlockedDuringHaltError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Verify error inherits from ConstitutionalViolationError."""
        error = WriteBlockedDuringHaltError("test")
        assert isinstance(error, ConstitutionalViolationError)

    def test_error_message_preserved(self) -> None:
        """Verify custom error message is preserved."""
        message = (
            "FR20: System halted - write operations blocked. Reason: Fork detected"
        )
        error = WriteBlockedDuringHaltError(message)
        assert str(error) == message

    def test_fr20_message_format(self) -> None:
        """Verify error message includes FR20 reference per AC2."""
        message = "FR20: System halted - write operations blocked"
        error = WriteBlockedDuringHaltError(message)
        assert "FR20" in str(error)
        assert "write operations blocked" in str(error)

    def test_can_be_raised_and_caught(self) -> None:
        """Verify error can be raised and caught."""
        with pytest.raises(WriteBlockedDuringHaltError) as exc_info:
            raise WriteBlockedDuringHaltError(
                "FR20: System halted - write operations blocked"
            )
        assert "FR20" in str(exc_info.value)

    def test_catchable_as_constitutional_violation(self) -> None:
        """Verify error can be caught as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise WriteBlockedDuringHaltError(
                "FR20: System halted - write operations blocked"
            )


class TestProvisionalBlockedDuringHaltError:
    """Tests for ProvisionalBlockedDuringHaltError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Verify error inherits from ConstitutionalViolationError."""
        error = ProvisionalBlockedDuringHaltError("test")
        assert isinstance(error, ConstitutionalViolationError)

    def test_error_message_preserved(self) -> None:
        """Verify custom error message is preserved."""
        message = "FR20: System halted - provisional operations blocked"
        error = ProvisionalBlockedDuringHaltError(message)
        assert str(error) == message

    def test_fr20_message_format(self) -> None:
        """Verify error message includes FR20 reference per AC3."""
        message = "FR20: System halted - provisional operations blocked"
        error = ProvisionalBlockedDuringHaltError(message)
        assert "FR20" in str(error)
        assert "provisional" in str(error)

    def test_can_be_raised_and_caught(self) -> None:
        """Verify error can be raised and caught."""
        with pytest.raises(ProvisionalBlockedDuringHaltError) as exc_info:
            raise ProvisionalBlockedDuringHaltError(
                "FR20: System halted - provisional operations blocked"
            )
        assert "provisional" in str(exc_info.value)

    def test_catchable_as_constitutional_violation(self) -> None:
        """Verify error can be caught as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise ProvisionalBlockedDuringHaltError(
                "FR20: System halted - provisional operations blocked"
            )


class TestErrorModuleExports:
    """Tests verifying errors are properly exported from package."""

    def test_write_blocked_exported_from_errors_package(self) -> None:
        """Verify WriteBlockedDuringHaltError is exported from errors __init__."""
        from src.domain.errors import WriteBlockedDuringHaltError as ExportedError

        assert ExportedError is WriteBlockedDuringHaltError

    def test_provisional_blocked_exported_from_errors_package(self) -> None:
        """Verify ProvisionalBlockedDuringHaltError is exported from errors __init__."""
        from src.domain.errors import ProvisionalBlockedDuringHaltError as ExportedError

        assert ExportedError is ProvisionalBlockedDuringHaltError
