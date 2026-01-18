"""Unit tests for configuration floor enforcement errors (Story 6.10, NFR39).

Tests for StartupFloorViolationError, RuntimeFloorViolationError, and FloorModificationAttemptedError.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> Startup failure over running below floor
"""

import pytest

from src.domain.errors.configuration_floor import (
    ConfigurationFloorEnforcementError,
    FloorModificationAttemptedError,
    RuntimeFloorViolationError,
    StartupFloorViolationError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestConfigurationFloorEnforcementError:
    """Tests for ConfigurationFloorEnforcementError base class."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Base class should inherit from ConstitutionalViolationError."""
        assert issubclass(
            ConfigurationFloorEnforcementError, ConstitutionalViolationError
        )


class TestStartupFloorViolationError:
    """Tests for StartupFloorViolationError."""

    def test_inherits_from_base_class(self) -> None:
        """Should inherit from ConfigurationFloorEnforcementError."""
        assert issubclass(
            StartupFloorViolationError, ConfigurationFloorEnforcementError
        )

    def test_message_includes_nfr39(self) -> None:
        """Error message should include NFR39 reference."""
        error = StartupFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        assert "NFR39" in str(error)

    def test_message_includes_threshold_name(self) -> None:
        """Error message should include threshold name."""
        error = StartupFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        assert "cessation_breach_count" in str(error)

    def test_message_includes_attempted_value(self) -> None:
        """Error message should include attempted value."""
        error = StartupFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        assert "5" in str(error)

    def test_message_includes_floor_value(self) -> None:
        """Error message should include constitutional floor."""
        error = StartupFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        assert "10" in str(error)

    def test_message_includes_fr_reference(self) -> None:
        """Error message should include FR reference."""
        error = StartupFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        assert "FR32" in str(error)

    def test_attributes_stored(self) -> None:
        """All attributes should be stored on the exception."""
        error = StartupFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        assert error.threshold_name == "cessation_breach_count"
        assert error.attempted_value == 5
        assert error.constitutional_floor == 10
        assert error.fr_reference == "FR32"

    def test_startup_blocked_in_message(self) -> None:
        """Message should clearly indicate startup is blocked."""
        error = StartupFloorViolationError(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            constitutional_floor=10,
            fr_reference="FR32",
        )

        message = str(error).lower()
        assert "startup" in message and "blocked" in message


class TestRuntimeFloorViolationError:
    """Tests for RuntimeFloorViolationError."""

    def test_inherits_from_base_class(self) -> None:
        """Should inherit from ConfigurationFloorEnforcementError."""
        assert issubclass(
            RuntimeFloorViolationError, ConfigurationFloorEnforcementError
        )

    def test_message_includes_nfr39(self) -> None:
        """Error message should include NFR39 reference."""
        error = RuntimeFloorViolationError(
            threshold_name="recovery_waiting_hours",
            attempted_value=24,
            constitutional_floor=48,
            fr_reference="NFR41",
        )

        assert "NFR39" in str(error)

    def test_message_includes_threshold_details(self) -> None:
        """Error message should include all threshold details."""
        error = RuntimeFloorViolationError(
            threshold_name="recovery_waiting_hours",
            attempted_value=24,
            constitutional_floor=48,
            fr_reference="NFR41",
        )

        message = str(error)
        assert "recovery_waiting_hours" in message
        assert "24" in message
        assert "48" in message

    def test_attributes_stored(self) -> None:
        """All attributes should be stored on the exception."""
        error = RuntimeFloorViolationError(
            threshold_name="recovery_waiting_hours",
            attempted_value=24,
            constitutional_floor=48,
            fr_reference="NFR41",
        )

        assert error.threshold_name == "recovery_waiting_hours"
        assert error.attempted_value == 24
        assert error.constitutional_floor == 48
        assert error.fr_reference == "NFR41"

    def test_runtime_in_message(self) -> None:
        """Message should indicate runtime context."""
        error = RuntimeFloorViolationError(
            threshold_name="recovery_waiting_hours",
            attempted_value=24,
            constitutional_floor=48,
            fr_reference="NFR41",
        )

        message = str(error).lower()
        assert "runtime" in message

    def test_configuration_change_rejected_in_message(self) -> None:
        """Message should indicate configuration change is rejected."""
        error = RuntimeFloorViolationError(
            threshold_name="recovery_waiting_hours",
            attempted_value=24,
            constitutional_floor=48,
            fr_reference="NFR41",
        )

        message = str(error).lower()
        assert "rejected" in message or "cannot" in message


class TestFloorModificationAttemptedError:
    """Tests for FloorModificationAttemptedError."""

    def test_inherits_from_base_class(self) -> None:
        """Should inherit from ConfigurationFloorEnforcementError."""
        assert issubclass(
            FloorModificationAttemptedError, ConfigurationFloorEnforcementError
        )

    def test_message_includes_nfr39(self) -> None:
        """Error message should include NFR39 reference."""
        error = FloorModificationAttemptedError()

        assert "NFR39" in str(error)

    def test_message_indicates_prohibition(self) -> None:
        """Message should indicate floor modification is prohibited."""
        error = FloorModificationAttemptedError()

        message = str(error).lower()
        assert "prohibited" in message or "floor" in message


class TestErrorHierarchy:
    """Tests for error inheritance hierarchy."""

    def test_all_errors_inherit_from_constitutional_violation(self) -> None:
        """All configuration floor errors should inherit from ConstitutionalViolationError."""
        assert issubclass(StartupFloorViolationError, ConstitutionalViolationError)
        assert issubclass(RuntimeFloorViolationError, ConstitutionalViolationError)
        assert issubclass(FloorModificationAttemptedError, ConstitutionalViolationError)

    def test_errors_can_be_caught_by_base_class(self) -> None:
        """All errors should be catchable via ConfigurationFloorEnforcementError."""
        errors = [
            StartupFloorViolationError(
                threshold_name="test",
                attempted_value=1,
                constitutional_floor=2,
                fr_reference="FR1",
            ),
            RuntimeFloorViolationError(
                threshold_name="test",
                attempted_value=1,
                constitutional_floor=2,
                fr_reference="FR1",
            ),
            FloorModificationAttemptedError(),
        ]

        for error in errors:
            with pytest.raises(ConfigurationFloorEnforcementError):
                raise error

    def test_errors_can_be_caught_by_constitutional_violation(self) -> None:
        """All errors should be catchable via ConstitutionalViolationError."""
        errors = [
            StartupFloorViolationError(
                threshold_name="test",
                attempted_value=1,
                constitutional_floor=2,
                fr_reference="FR1",
            ),
            RuntimeFloorViolationError(
                threshold_name="test",
                attempted_value=1,
                constitutional_floor=2,
                fr_reference="FR1",
            ),
            FloorModificationAttemptedError(),
        ]

        for error in errors:
            with pytest.raises(ConstitutionalViolationError):
                raise error
