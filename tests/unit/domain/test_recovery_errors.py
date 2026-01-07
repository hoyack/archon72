"""Unit tests for recovery domain errors (Story 3.6, FR21).

Tests that all recovery-related error classes:
- Inherit from ConstitutionalViolationError
- Can be instantiated with proper messages
- Include remaining time display for elapsed errors
"""

from datetime import timedelta

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.recovery import (
    RecoveryAlreadyInProgressError,
    RecoveryNotPermittedError,
    RecoveryWaitingPeriodNotElapsedError,
    RecoveryWaitingPeriodNotStartedError,
)


class TestRecoveryWaitingPeriodNotElapsedError:
    """Tests for RecoveryWaitingPeriodNotElapsedError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Error inherits from ConstitutionalViolationError."""
        error = RecoveryWaitingPeriodNotElapsedError("FR21: 48h not elapsed")
        assert isinstance(error, ConstitutionalViolationError)

    def test_includes_fr21_reference(self) -> None:
        """Error message should reference FR21."""
        remaining = timedelta(hours=23, minutes=45)
        error = RecoveryWaitingPeriodNotElapsedError(
            f"FR21: 48-hour waiting period not elapsed. Remaining: {remaining}"
        )
        assert "FR21" in str(error)

    def test_includes_remaining_time(self) -> None:
        """Error message includes remaining time per AC3."""
        remaining = timedelta(hours=23, minutes=45)
        error = RecoveryWaitingPeriodNotElapsedError(
            f"FR21: 48-hour waiting period not elapsed. Remaining: {remaining}"
        )
        assert "23:45" in str(error) or "Remaining" in str(error)

    def test_can_be_raised_and_caught(self) -> None:
        """Error can be raised and caught properly."""
        with pytest.raises(RecoveryWaitingPeriodNotElapsedError) as exc_info:
            raise RecoveryWaitingPeriodNotElapsedError("Test message")
        assert "Test message" in str(exc_info.value)


class TestRecoveryWaitingPeriodNotStartedError:
    """Tests for RecoveryWaitingPeriodNotStartedError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Error inherits from ConstitutionalViolationError."""
        error = RecoveryWaitingPeriodNotStartedError("No waiting period active")
        assert isinstance(error, ConstitutionalViolationError)

    def test_error_message_preserved(self) -> None:
        """Error message is preserved."""
        msg = "No recovery waiting period active"
        error = RecoveryWaitingPeriodNotStartedError(msg)
        assert msg in str(error)

    def test_can_be_raised_and_caught(self) -> None:
        """Error can be raised and caught properly."""
        with pytest.raises(RecoveryWaitingPeriodNotStartedError) as exc_info:
            raise RecoveryWaitingPeriodNotStartedError("Test message")
        assert "Test message" in str(exc_info.value)


class TestRecoveryAlreadyInProgressError:
    """Tests for RecoveryAlreadyInProgressError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Error inherits from ConstitutionalViolationError."""
        error = RecoveryAlreadyInProgressError("Recovery in progress")
        assert isinstance(error, ConstitutionalViolationError)

    def test_includes_end_time_info(self) -> None:
        """Error can include end timestamp."""
        error = RecoveryAlreadyInProgressError(
            "Recovery already in progress, ends at 2025-12-29T15:00:00Z"
        )
        assert "2025-12-29" in str(error) or "ends at" in str(error)

    def test_can_be_raised_and_caught(self) -> None:
        """Error can be raised and caught properly."""
        with pytest.raises(RecoveryAlreadyInProgressError) as exc_info:
            raise RecoveryAlreadyInProgressError("Test message")
        assert "Test message" in str(exc_info.value)


class TestRecoveryNotPermittedError:
    """Tests for RecoveryNotPermittedError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Error inherits from ConstitutionalViolationError."""
        error = RecoveryNotPermittedError("System not halted")
        assert isinstance(error, ConstitutionalViolationError)

    def test_error_message_preserved(self) -> None:
        """Error message is preserved."""
        msg = "Cannot initiate recovery - system not halted"
        error = RecoveryNotPermittedError(msg)
        assert msg in str(error)

    def test_can_be_raised_and_caught(self) -> None:
        """Error can be raised and caught properly."""
        with pytest.raises(RecoveryNotPermittedError) as exc_info:
            raise RecoveryNotPermittedError("Test message")
        assert "Test message" in str(exc_info.value)
