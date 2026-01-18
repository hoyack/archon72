"""Unit tests for threshold errors (Story 6.4, FR33-FR34).

Tests the threshold error classes.
"""

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.threshold import (
    ConstitutionalFloorViolationError,
    CounterResetAttemptedError,
    ThresholdError,
    ThresholdNotFoundError,
)


class TestThresholdError:
    """Tests for ThresholdError base class."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Test ThresholdError inherits from ConstitutionalViolationError."""
        assert issubclass(ThresholdError, ConstitutionalViolationError)


class TestConstitutionalFloorViolationError:
    """Tests for ConstitutionalFloorViolationError."""

    def test_message_includes_fr33_reference(self) -> None:
        """Test error message includes FR33 reference (AC2)."""
        error = ConstitutionalFloorViolationError(
            threshold_name="test_threshold",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR33",
        )

        assert "FR33: Constitutional floor violation" in str(error)

    def test_includes_threshold_details(self) -> None:
        """Test error includes all threshold details."""
        error = ConstitutionalFloorViolationError(
            threshold_name="test_threshold",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        assert error.threshold_name == "test_threshold"
        assert error.attempted_value == 5
        assert error.constitutional_floor == 10
        assert error.fr_reference == "FR32"

    def test_message_format(self) -> None:
        """Test error message format is correct."""
        error = ConstitutionalFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        message = str(error)

        assert "cessation_breach_count" in message
        assert "5" in message
        assert "10" in message
        assert "FR32" in message

    def test_inherits_from_threshold_error(self) -> None:
        """Test ConstitutionalFloorViolationError inherits from ThresholdError."""
        assert issubclass(ConstitutionalFloorViolationError, ThresholdError)

    def test_inherits_from_constitutional_violation(self) -> None:
        """Test error inherits from ConstitutionalViolationError."""
        assert issubclass(
            ConstitutionalFloorViolationError, ConstitutionalViolationError
        )

    def test_with_float_values(self) -> None:
        """Test error works with float values."""
        error = ConstitutionalFloorViolationError(
            threshold_name="diversity",
            attempted_value=0.25,
            constitutional_floor=0.30,
            fr_reference="FR73",
        )

        assert error.attempted_value == 0.25
        assert error.constitutional_floor == 0.30


class TestThresholdNotFoundError:
    """Tests for ThresholdNotFoundError."""

    def test_message_includes_threshold_name(self) -> None:
        """Test error message includes threshold name."""
        error = ThresholdNotFoundError("unknown_threshold")

        assert "unknown_threshold" in str(error)

    def test_stores_threshold_name(self) -> None:
        """Test error stores threshold_name attribute."""
        error = ThresholdNotFoundError("test_threshold")

        assert error.threshold_name == "test_threshold"

    def test_inherits_from_threshold_error(self) -> None:
        """Test ThresholdNotFoundError inherits from ThresholdError."""
        assert issubclass(ThresholdNotFoundError, ThresholdError)


class TestCounterResetAttemptedError:
    """Tests for CounterResetAttemptedError."""

    def test_message_includes_fr34_reference(self) -> None:
        """Test error message includes FR34 reference."""
        error = CounterResetAttemptedError(
            threshold_name="cessation_breach_count",
            counter_type="breach",
        )

        assert "FR34: Counter reset prohibited" in str(error)

    def test_includes_threshold_and_counter_type(self) -> None:
        """Test error includes threshold name and counter type."""
        error = CounterResetAttemptedError(
            threshold_name="cessation_breach_count",
            counter_type="breach",
        )

        assert error.threshold_name == "cessation_breach_count"
        assert error.counter_type == "breach"
        assert "cessation_breach_count" in str(error)
        assert "breach" in str(error)

    def test_inherits_from_threshold_error(self) -> None:
        """Test CounterResetAttemptedError inherits from ThresholdError."""
        assert issubclass(CounterResetAttemptedError, ThresholdError)


class TestErrorInheritanceHierarchy:
    """Tests for error inheritance hierarchy."""

    def test_all_threshold_errors_are_constitutional_violations(self) -> None:
        """Test all threshold errors are constitutional violations."""
        error_classes = [
            ThresholdError,
            ConstitutionalFloorViolationError,
            ThresholdNotFoundError,
            CounterResetAttemptedError,
        ]

        for error_class in error_classes:
            assert issubclass(error_class, ConstitutionalViolationError)
