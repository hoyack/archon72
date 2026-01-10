"""Unit tests for SystemCeasedError and related errors (Story 7.4, FR41).

Tests the error classes for write rejections after cessation.

Constitutional Constraints Tested:
- FR41: System ceased - writes frozen
- AC2: Error includes FR41 reference
- AC3: Error includes cessation timestamp and final sequence
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError


class TestSystemCeasedError:
    """Test SystemCeasedError class."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """SystemCeasedError should inherit from ConstitutionalViolationError."""
        from src.domain.errors.ceased import SystemCeasedError

        assert issubclass(SystemCeasedError, ConstitutionalViolationError)

    def test_create_with_message(self) -> None:
        """Should create error with message."""
        from src.domain.errors.ceased import SystemCeasedError

        error = SystemCeasedError("FR41: System ceased - writes frozen")

        assert "FR41" in str(error)
        assert "ceased" in str(error).lower()

    def test_create_with_cessation_details(self) -> None:
        """Should create error with cessation timestamp and sequence."""
        from src.domain.errors.ceased import SystemCeasedError

        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        error = SystemCeasedError(
            message="FR41: System ceased - writes frozen",
            ceased_at=ceased_at,
            final_sequence_number=12345,
        )

        assert error.ceased_at == ceased_at
        assert error.final_sequence_number == 12345

    def test_from_details_factory(self) -> None:
        """Should create error from CessationDetails."""
        from src.domain.errors.ceased import SystemCeasedError
        from src.domain.models.ceased_status_header import CessationDetails
        from uuid import uuid4

        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=500,
            reason="Test cessation",
            cessation_event_id=uuid4(),
        )

        error = SystemCeasedError.from_details(details)

        assert error.ceased_at == details.ceased_at
        assert error.final_sequence_number == 500
        assert "FR41" in str(error)

    def test_error_message_includes_fr41(self) -> None:
        """Error message must include FR41 reference per AC2/AC3."""
        from src.domain.errors.ceased import SystemCeasedError

        error = SystemCeasedError.from_details_values(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
        )

        assert "FR41" in str(error)

    def test_error_message_includes_writes_frozen(self) -> None:
        """Error message must include 'writes frozen' per AC2/AC3."""
        from src.domain.errors.ceased import SystemCeasedError

        error = SystemCeasedError.from_details_values(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
        )

        assert "writes frozen" in str(error).lower()

    def test_default_values_when_not_provided(self) -> None:
        """Should handle missing ceased_at and final_sequence_number."""
        from src.domain.errors.ceased import SystemCeasedError

        error = SystemCeasedError("FR41: System ceased - writes frozen")

        # Should have default None values
        assert error.ceased_at is None
        assert error.final_sequence_number is None


class TestCeasedWriteAttemptError:
    """Test CeasedWriteAttemptError class."""

    def test_inherits_from_system_ceased_error(self) -> None:
        """CeasedWriteAttemptError should inherit from SystemCeasedError."""
        from src.domain.errors.ceased import (
            CeasedWriteAttemptError,
            SystemCeasedError,
        )

        assert issubclass(CeasedWriteAttemptError, SystemCeasedError)

    def test_create_for_specific_operation(self) -> None:
        """Should create error for a specific write operation."""
        from src.domain.errors.ceased import CeasedWriteAttemptError

        error = CeasedWriteAttemptError.for_operation(
            operation="write_event",
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
        )

        assert "write_event" in str(error)
        assert "FR41" in str(error)

    def test_includes_all_details(self) -> None:
        """Should include all cessation details."""
        from src.domain.errors.ceased import CeasedWriteAttemptError

        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        error = CeasedWriteAttemptError.for_operation(
            operation="create_deliberation",
            ceased_at=ceased_at,
            final_sequence_number=999,
        )

        assert error.ceased_at == ceased_at
        assert error.final_sequence_number == 999
        assert error.operation == "create_deliberation"


class TestExportFromInit:
    """Test exports from domain.errors.__init__.py."""

    def test_system_ceased_error_exported(self) -> None:
        """SystemCeasedError should be exported from domain.errors."""
        from src.domain.errors import SystemCeasedError

        assert SystemCeasedError is not None

    def test_ceased_write_attempt_error_exported(self) -> None:
        """CeasedWriteAttemptError should be exported from domain.errors."""
        from src.domain.errors import CeasedWriteAttemptError

        assert CeasedWriteAttemptError is not None


class TestErrorBehavior:
    """Test error behavior for exception handling."""

    def test_can_be_raised_and_caught(self) -> None:
        """SystemCeasedError should be raiseable and catchable."""
        from src.domain.errors.ceased import SystemCeasedError

        with pytest.raises(SystemCeasedError):
            raise SystemCeasedError("FR41: Test error")

    def test_can_catch_as_constitutional_violation(self) -> None:
        """Should be catchable as ConstitutionalViolationError."""
        from src.domain.errors.ceased import SystemCeasedError

        with pytest.raises(ConstitutionalViolationError):
            raise SystemCeasedError("FR41: Test error")

    def test_ceased_write_attempt_can_catch_as_system_ceased(self) -> None:
        """CeasedWriteAttemptError should be catchable as SystemCeasedError."""
        from src.domain.errors.ceased import (
            CeasedWriteAttemptError,
            SystemCeasedError,
        )

        error = CeasedWriteAttemptError.for_operation(
            operation="test",
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=1,
        )

        with pytest.raises(SystemCeasedError):
            raise error
