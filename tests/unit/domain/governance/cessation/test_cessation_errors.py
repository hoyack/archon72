"""Unit tests for cessation error types.

Story: consent-gov-8.1: System Cessation Trigger
AC2: Cessation blocks new motions (FR49)
AC6: Cessation trigger is irreversible (no "undo")
"""

from datetime import datetime, timezone
from uuid import uuid4

from src.domain.governance.cessation.errors import (
    CessationAlreadyTriggeredError,
    CessationError,
    ExecutionBlockedByCessationError,
    MotionBlockedByCessationError,
)


class TestCessationError:
    """Tests for base CessationError."""

    def test_is_exception(self) -> None:
        """CessationError is an Exception."""
        error = CessationError("test")
        assert isinstance(error, Exception)


class TestCessationAlreadyTriggeredError:
    """Tests for CessationAlreadyTriggeredError."""

    def test_create_error_with_details(self) -> None:
        """Can create error with trigger details."""
        trigger_id = uuid4()
        triggered_at = datetime.now(timezone.utc)
        operator_id = uuid4()

        error = CessationAlreadyTriggeredError(
            original_trigger_id=trigger_id,
            original_triggered_at=triggered_at,
            original_operator_id=operator_id,
        )

        assert error.original_trigger_id == trigger_id
        assert error.original_triggered_at == triggered_at
        assert error.original_operator_id == operator_id

    def test_error_message_includes_timestamp(self) -> None:
        """Error message includes trigger timestamp."""
        triggered_at = datetime.now(timezone.utc)

        error = CessationAlreadyTriggeredError(
            original_trigger_id=uuid4(),
            original_triggered_at=triggered_at,
        )

        assert triggered_at.isoformat() in str(error)

    def test_error_message_includes_trigger_id(self) -> None:
        """Error message includes trigger ID."""
        trigger_id = uuid4()

        error = CessationAlreadyTriggeredError(
            original_trigger_id=trigger_id,
            original_triggered_at=datetime.now(timezone.utc),
        )

        assert str(trigger_id) in str(error)

    def test_custom_message(self) -> None:
        """Can provide custom message."""
        error = CessationAlreadyTriggeredError(
            original_trigger_id=uuid4(),
            original_triggered_at=datetime.now(timezone.utc),
            message="Custom error message",
        )

        assert str(error) == "Custom error message"

    def test_is_cessation_error(self) -> None:
        """CessationAlreadyTriggeredError is a CessationError."""
        error = CessationAlreadyTriggeredError(
            original_trigger_id=uuid4(),
            original_triggered_at=datetime.now(timezone.utc),
        )

        assert isinstance(error, CessationError)


class TestMotionBlockedByCessationError:
    """Tests for MotionBlockedByCessationError."""

    def test_create_error_with_details(self) -> None:
        """Can create error with cessation details."""
        trigger_id = uuid4()
        triggered_at = datetime.now(timezone.utc)
        motion_id = uuid4()

        error = MotionBlockedByCessationError(
            trigger_id=trigger_id,
            triggered_at=triggered_at,
            motion_id=motion_id,
        )

        assert error.trigger_id == trigger_id
        assert error.triggered_at == triggered_at
        assert error.motion_id == motion_id

    def test_error_message_indicates_cessation(self) -> None:
        """Error message indicates cessation in progress."""
        error = MotionBlockedByCessationError(
            trigger_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
        )

        assert "cessation" in str(error).lower()
        assert "blocked" in str(error).lower()

    def test_is_cessation_error(self) -> None:
        """MotionBlockedByCessationError is a CessationError."""
        error = MotionBlockedByCessationError(
            trigger_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
        )

        assert isinstance(error, CessationError)

    def test_custom_message(self) -> None:
        """Can provide custom message."""
        error = MotionBlockedByCessationError(
            trigger_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            message="Custom blocked message",
        )

        assert str(error) == "Custom blocked message"


class TestExecutionBlockedByCessationError:
    """Tests for ExecutionBlockedByCessationError."""

    def test_create_error_with_trigger_id(self) -> None:
        """Can create error with trigger ID."""
        trigger_id = uuid4()

        error = ExecutionBlockedByCessationError(trigger_id=trigger_id)

        assert error.trigger_id == trigger_id

    def test_error_message_indicates_ceased(self) -> None:
        """Error message indicates system has ceased."""
        error = ExecutionBlockedByCessationError(trigger_id=uuid4())

        assert "ceased" in str(error).lower()
        assert "execution" in str(error).lower().replace(
            "executionblocked", "execution"
        )

    def test_is_cessation_error(self) -> None:
        """ExecutionBlockedByCessationError is a CessationError."""
        error = ExecutionBlockedByCessationError(trigger_id=uuid4())

        assert isinstance(error, CessationError)


class TestNoReverseErrors:
    """Tests ensuring no cancellation/reversal error types exist.

    There should be NO errors for "cannot cancel" because
    cancel doesn't exist as a concept.
    """

    def test_no_cancellation_error_type(self) -> None:
        """No CessationCancellationError type exists."""
        import src.domain.governance.cessation.errors as errors_module

        assert not hasattr(errors_module, "CessationCancellationError")
        assert not hasattr(errors_module, "CessationCancelledError")

    def test_no_rollback_error_type(self) -> None:
        """No CessationRollbackError type exists."""
        import src.domain.governance.cessation.errors as errors_module

        assert not hasattr(errors_module, "CessationRollbackError")
        assert not hasattr(errors_module, "CessationRevertError")

    def test_no_resume_error_type(self) -> None:
        """No CessationResumeError type exists."""
        import src.domain.governance.cessation.errors as errors_module

        assert not hasattr(errors_module, "CessationResumeError")
        assert not hasattr(errors_module, "OperationsResumedError")
