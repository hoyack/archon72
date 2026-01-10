"""Unit tests for rollback domain errors (Story 3.10, Task 6).

Tests the error types for rollback operations.

Constitutional Constraints:
- FR143: Rollback operations must fail loudly with clear errors
- CT-11: Silent failure destroys legitimacy
"""

from __future__ import annotations

import pytest

from src.domain.errors.rollback import (
    CheckpointNotFoundError,
    InvalidRollbackTargetError,
    RollbackAlreadyInProgressError,
    RollbackNotPermittedError,
)


class TestCheckpointNotFoundError:
    """Tests for CheckpointNotFoundError."""

    def test_checkpoint_not_found_error(self) -> None:
        """CheckpointNotFoundError should be raisable with message."""
        error = CheckpointNotFoundError("Checkpoint abc123 not found")

        assert str(error) == "Checkpoint abc123 not found"

    def test_checkpoint_not_found_is_value_error(self) -> None:
        """CheckpointNotFoundError should inherit from ValueError."""
        error = CheckpointNotFoundError("test")

        assert isinstance(error, ValueError)


class TestRollbackNotPermittedError:
    """Tests for RollbackNotPermittedError."""

    def test_rollback_not_permitted_error(self) -> None:
        """RollbackNotPermittedError should be raisable with message."""
        error = RollbackNotPermittedError("System not halted")

        assert str(error) == "System not halted"

    def test_rollback_not_permitted_is_value_error(self) -> None:
        """RollbackNotPermittedError should inherit from ValueError."""
        error = RollbackNotPermittedError("test")

        assert isinstance(error, ValueError)


class TestInvalidRollbackTargetError:
    """Tests for InvalidRollbackTargetError."""

    def test_invalid_rollback_target_error(self) -> None:
        """InvalidRollbackTargetError should be raisable with message."""
        error = InvalidRollbackTargetError("Checkpoint sequence beyond current HEAD")

        assert "beyond current HEAD" in str(error)

    def test_invalid_rollback_target_is_value_error(self) -> None:
        """InvalidRollbackTargetError should inherit from ValueError."""
        error = InvalidRollbackTargetError("test")

        assert isinstance(error, ValueError)


class TestRollbackAlreadyInProgressError:
    """Tests for RollbackAlreadyInProgressError."""

    def test_rollback_already_in_progress_error(self) -> None:
        """RollbackAlreadyInProgressError should be raisable with message."""
        error = RollbackAlreadyInProgressError("Rollback already in progress")

        assert str(error) == "Rollback already in progress"

    def test_rollback_already_in_progress_is_value_error(self) -> None:
        """RollbackAlreadyInProgressError should inherit from ValueError."""
        error = RollbackAlreadyInProgressError("test")

        assert isinstance(error, ValueError)


class TestErrorsAreValueErrors:
    """Tests that all errors inherit from ValueError."""

    def test_errors_are_value_errors(self) -> None:
        """All rollback errors should inherit from ValueError."""
        errors = [
            CheckpointNotFoundError("test"),
            RollbackNotPermittedError("test"),
            InvalidRollbackTargetError("test"),
            RollbackAlreadyInProgressError("test"),
        ]

        for error in errors:
            assert isinstance(error, ValueError)

    def test_errors_can_be_raised_and_caught(self) -> None:
        """All errors should be raisable and catchable."""
        with pytest.raises(CheckpointNotFoundError):
            raise CheckpointNotFoundError("not found")

        with pytest.raises(RollbackNotPermittedError):
            raise RollbackNotPermittedError("not permitted")

        with pytest.raises(InvalidRollbackTargetError):
            raise InvalidRollbackTargetError("invalid target")

        with pytest.raises(RollbackAlreadyInProgressError):
            raise RollbackAlreadyInProgressError("already in progress")
