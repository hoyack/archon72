"""Unit tests for sequence gap domain errors (FR18-FR19, Story 3.7).

Tests the SequenceGapDetectedError and SequenceGapResolutionRequiredError
which are used when sequence gaps are detected in the event store.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-11: Silent failure destroys legitimacy
"""

from src.domain.errors.sequence_gap import (
    SequenceGapDetectedError,
    SequenceGapResolutionRequiredError,
)
from src.domain.exceptions import ConclaveError


class TestSequenceGapDetectedError:
    """Tests for SequenceGapDetectedError."""

    def test_inherits_from_conclave_error(self) -> None:
        """SequenceGapDetectedError should inherit from ConclaveError."""
        error = SequenceGapDetectedError(
            expected=5,
            actual=10,
            missing=(5, 6, 7, 8, 9),
        )
        assert isinstance(error, ConclaveError)

    def test_stores_expected_sequence(self) -> None:
        """Error should store expected sequence for investigation."""
        error = SequenceGapDetectedError(
            expected=5,
            actual=10,
            missing=(5, 6, 7, 8, 9),
        )
        assert error.expected == 5

    def test_stores_actual_sequence(self) -> None:
        """Error should store actual sequence for investigation."""
        error = SequenceGapDetectedError(
            expected=5,
            actual=10,
            missing=(5, 6, 7, 8, 9),
        )
        assert error.actual == 10

    def test_stores_missing_sequences(self) -> None:
        """Error should store missing sequences for investigation."""
        missing = (5, 6, 7, 8, 9)
        error = SequenceGapDetectedError(
            expected=5,
            actual=10,
            missing=missing,
        )
        assert error.missing == missing

    def test_message_includes_fr18_reference(self) -> None:
        """Error message must include FR18 reference per convention."""
        error = SequenceGapDetectedError(
            expected=5,
            actual=10,
            missing=(5, 6, 7, 8, 9),
        )
        assert "FR18" in str(error)

    def test_message_includes_gap_details(self) -> None:
        """Error message should include gap details for debugging."""
        error = SequenceGapDetectedError(
            expected=5,
            actual=10,
            missing=(5, 6, 7, 8, 9),
        )
        message = str(error)
        assert "5" in message  # expected
        assert "10" in message  # actual

    def test_single_missing_sequence(self) -> None:
        """Error should handle single missing sequence."""
        error = SequenceGapDetectedError(
            expected=5,
            actual=6,
            missing=(5,),
        )
        assert error.expected == 5
        assert error.actual == 6
        assert error.missing == (5,)

    def test_empty_missing_sequences(self) -> None:
        """Error should handle edge case of empty missing tuple."""
        error = SequenceGapDetectedError(
            expected=5,
            actual=5,
            missing=(),
        )
        assert error.missing == ()


class TestSequenceGapResolutionRequiredError:
    """Tests for SequenceGapResolutionRequiredError."""

    def test_inherits_from_conclave_error(self) -> None:
        """SequenceGapResolutionRequiredError should inherit from ConclaveError."""
        error = SequenceGapResolutionRequiredError("Manual resolution required")
        assert isinstance(error, ConclaveError)

    def test_message_preserved(self) -> None:
        """Error message should be preserved."""
        msg = "FR19: Sequence gaps require manual investigation and resolution"
        error = SequenceGapResolutionRequiredError(msg)
        assert str(error) == msg

    def test_default_message(self) -> None:
        """Error should work with default message."""
        error = SequenceGapResolutionRequiredError()
        # Should not raise, even with empty message
        assert isinstance(error, ConclaveError)
