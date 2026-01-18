"""Unit tests for schema irreversibility errors (Story 7.3, FR40, NFR40).

Tests for:
- Error inheritance from ConstitutionalViolationError
- Error message formatting
- NFR40 reference in error messages
"""

from __future__ import annotations

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.schema_irreversibility import (
    CessationReversalAttemptError,
    EventTypeProhibitedError,
    SchemaIrreversibilityError,
    TerminalEventViolationError,
)


class TestSchemaIrreversibilityError:
    """Tests for SchemaIrreversibilityError."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Should inherit from ConstitutionalViolationError."""
        assert issubclass(SchemaIrreversibilityError, ConstitutionalViolationError)

    def test_can_be_raised(self) -> None:
        """Should be raisable with message."""
        with pytest.raises(SchemaIrreversibilityError) as exc_info:
            raise SchemaIrreversibilityError(
                "NFR40: Cannot write events after cessation"
            )

        assert "NFR40" in str(exc_info.value)
        assert "cessation" in str(exc_info.value)

    def test_message_preserved(self) -> None:
        """Error message should be preserved."""
        message = (
            "NFR40: Cannot write events after cessation. System terminated at seq 42"
        )
        error = SchemaIrreversibilityError(message)
        assert str(error) == message

    def test_caught_as_constitutional_violation(self) -> None:
        """Should be catchable as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise SchemaIrreversibilityError("Test")


class TestEventTypeProhibitedError:
    """Tests for EventTypeProhibitedError."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Should inherit from ConstitutionalViolationError."""
        assert issubclass(EventTypeProhibitedError, ConstitutionalViolationError)

    def test_can_be_raised(self) -> None:
        """Should be raisable with message."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            raise EventTypeProhibitedError(
                "NFR40: Cessation reversal prohibited by schema"
            )

        assert "NFR40" in str(exc_info.value)
        assert "prohibited" in str(exc_info.value).lower()

    def test_message_includes_event_type(self) -> None:
        """Message can include the prohibited event type."""
        event_type = "cessation.reversal"
        error = EventTypeProhibitedError(
            f"NFR40: Cessation reversal prohibited by schema. "
            f"Detected prohibited event type: {event_type}"
        )
        assert event_type in str(error)

    def test_caught_as_constitutional_violation(self) -> None:
        """Should be catchable as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise EventTypeProhibitedError("Test")


class TestTerminalEventViolationError:
    """Tests for TerminalEventViolationError."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Should inherit from ConstitutionalViolationError."""
        assert issubclass(TerminalEventViolationError, ConstitutionalViolationError)

    def test_can_be_raised(self) -> None:
        """Should be raisable with message."""
        with pytest.raises(TerminalEventViolationError) as exc_info:
            raise TerminalEventViolationError(
                "NFR40: Write rejected - terminal event detected"
            )

        assert "NFR40" in str(exc_info.value)
        assert "terminal" in str(exc_info.value).lower()

    def test_message_includes_timestamp(self) -> None:
        """Message can include termination timestamp."""
        timestamp = "2024-06-15T10:30:00Z"
        error = TerminalEventViolationError(
            f"NFR40: Write rejected - terminal event detected. "
            f"System terminated at {timestamp}"
        )
        assert timestamp in str(error)

    def test_caught_as_constitutional_violation(self) -> None:
        """Should be catchable as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise TerminalEventViolationError("Test")


class TestCessationReversalAttemptError:
    """Tests for CessationReversalAttemptError."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Should inherit from ConstitutionalViolationError."""
        assert issubclass(CessationReversalAttemptError, ConstitutionalViolationError)

    def test_can_be_raised(self) -> None:
        """Should be raisable with message."""
        with pytest.raises(CessationReversalAttemptError) as exc_info:
            raise CessationReversalAttemptError(
                "NFR40: Cessation reversal is architecturally prohibited"
            )

        assert "NFR40" in str(exc_info.value)
        assert "reversal" in str(exc_info.value).lower()

    def test_message_emphasizes_permanence(self) -> None:
        """Message can emphasize that cessation is permanent."""
        error = CessationReversalAttemptError(
            "NFR40: Cessation reversal is architecturally prohibited. "
            "Cessation is permanent and irreversible by design."
        )
        assert "permanent" in str(error)
        assert "irreversible" in str(error)

    def test_caught_as_constitutional_violation(self) -> None:
        """Should be catchable as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise CessationReversalAttemptError("Test")


class TestErrorHierarchy:
    """Tests for error hierarchy relationships."""

    def test_all_errors_inherit_from_constitutional(self) -> None:
        """All schema irreversibility errors should inherit from ConstitutionalViolationError."""
        error_classes = [
            SchemaIrreversibilityError,
            EventTypeProhibitedError,
            TerminalEventViolationError,
            CessationReversalAttemptError,
        ]

        for error_class in error_classes:
            assert issubclass(error_class, ConstitutionalViolationError), (
                f"{error_class.__name__} should inherit from ConstitutionalViolationError"
            )

    def test_all_errors_are_distinct(self) -> None:
        """All error classes should be distinct."""
        error_classes = [
            SchemaIrreversibilityError,
            EventTypeProhibitedError,
            TerminalEventViolationError,
            CessationReversalAttemptError,
        ]

        # Check that each class is unique
        assert len(error_classes) == len(set(error_classes))

        # Check that they are not the same class
        for i, cls1 in enumerate(error_classes):
            for j, cls2 in enumerate(error_classes):
                if i != j:
                    assert cls1 is not cls2


class TestNFR40Reference:
    """Tests ensuring NFR40 is referenced in standard error messages."""

    def test_recommended_schema_irreversibility_message(self) -> None:
        """Standard SchemaIrreversibilityError message format."""
        # Recommended format includes NFR40 reference
        message = (
            "NFR40: Cannot write events after cessation. System terminated at seq 42"
        )
        error = SchemaIrreversibilityError(message)
        assert "NFR40" in str(error)

    def test_recommended_event_type_prohibited_message(self) -> None:
        """Standard EventTypeProhibitedError message format."""
        message = (
            "NFR40: Cessation reversal prohibited by schema. "
            "Detected prohibited event type: cessation.reversal"
        )
        error = EventTypeProhibitedError(message)
        assert "NFR40" in str(error)

    def test_recommended_terminal_event_message(self) -> None:
        """Standard TerminalEventViolationError message format."""
        message = (
            "NFR40: Write rejected - terminal event detected. "
            "System terminated at 2024-06-15T10:30:00Z"
        )
        error = TerminalEventViolationError(message)
        assert "NFR40" in str(error)

    def test_recommended_reversal_attempt_message(self) -> None:
        """Standard CessationReversalAttemptError message format."""
        message = (
            "NFR40: Cessation reversal is architecturally prohibited. "
            "Cessation is permanent and irreversible by design."
        )
        error = CessationReversalAttemptError(message)
        assert "NFR40" in str(error)
