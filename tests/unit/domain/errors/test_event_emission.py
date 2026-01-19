"""Unit tests for FateEventEmissionError (Story 1.7, FR-2.5, HC-1).

Tests cover:
- Error creation and attributes
- Error message formatting
- Cause exception chaining
"""

from uuid import uuid4

import pytest

from src.domain.errors.event_emission import FateEventEmissionError


class TestFateEventEmissionError:
    """Tests for FateEventEmissionError exception."""

    def test_creation_with_all_attributes(self) -> None:
        """Test error creation captures all attributes."""
        petition_id = uuid4()
        cause = RuntimeError("Database connection failed")

        error = FateEventEmissionError(
            petition_id=petition_id,
            new_state="ACKNOWLEDGED",
            cause=cause,
        )

        assert error.petition_id == petition_id
        assert error.new_state == "ACKNOWLEDGED"
        assert error.cause is cause

    def test_error_message_includes_petition_id(self) -> None:
        """Test error message includes petition ID."""
        petition_id = uuid4()
        cause = RuntimeError("Connection timeout")

        error = FateEventEmissionError(
            petition_id=petition_id,
            new_state="REFERRED",
            cause=cause,
        )

        assert str(petition_id) in str(error)

    def test_error_message_includes_state(self) -> None:
        """Test error message includes new state."""
        error = FateEventEmissionError(
            petition_id=uuid4(),
            new_state="ESCALATED",
            cause=RuntimeError("Test error"),
        )

        assert "ESCALATED" in str(error)

    def test_error_message_includes_cause_type(self) -> None:
        """Test error message includes cause exception type."""
        error = FateEventEmissionError(
            petition_id=uuid4(),
            new_state="ACKNOWLEDGED",
            cause=ValueError("Invalid value"),
        )

        assert "ValueError" in str(error)

    def test_error_message_includes_cause_message(self) -> None:
        """Test error message includes cause exception message."""
        error = FateEventEmissionError(
            petition_id=uuid4(),
            new_state="ACKNOWLEDGED",
            cause=RuntimeError("Specific database error"),
        )

        assert "Specific database error" in str(error)

    def test_error_message_mentions_rollback(self) -> None:
        """Test error message mentions rollback (HC-1 compliance hint)."""
        error = FateEventEmissionError(
            petition_id=uuid4(),
            new_state="ACKNOWLEDGED",
            cause=RuntimeError("Test"),
        )

        assert "rollback" in str(error).lower() or "rolled back" in str(error).lower()

    def test_error_is_exception_subclass(self) -> None:
        """Test FateEventEmissionError is a proper Exception subclass."""
        error = FateEventEmissionError(
            petition_id=uuid4(),
            new_state="ACKNOWLEDGED",
            cause=RuntimeError("Test"),
        )

        assert isinstance(error, Exception)

    def test_error_can_be_raised_and_caught(self) -> None:
        """Test error can be properly raised and caught."""
        petition_id = uuid4()
        cause = RuntimeError("Original error")

        with pytest.raises(FateEventEmissionError) as exc_info:
            raise FateEventEmissionError(
                petition_id=petition_id,
                new_state="REFERRED",
                cause=cause,
            )

        assert exc_info.value.petition_id == petition_id
        assert exc_info.value.new_state == "REFERRED"
        assert exc_info.value.cause is cause

    def test_all_three_fate_states_work(self) -> None:
        """Test error works with all three terminal fate states."""
        for state in ["ACKNOWLEDGED", "REFERRED", "ESCALATED"]:
            error = FateEventEmissionError(
                petition_id=uuid4(),
                new_state=state,
                cause=RuntimeError("Test"),
            )
            assert state in str(error)
