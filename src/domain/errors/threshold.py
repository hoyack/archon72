"""Threshold errors for Archon 72 (Story 6.4, FR33-FR34).

This module provides exception classes for constitutional threshold violations.

Constitutional Constraints:
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR34: Threshold changes SHALL NOT reset active counters
- NFR39: No configuration SHALL allow thresholds below constitutional floors
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class ThresholdError(ConstitutionalViolationError):
    """Base class for threshold-related errors.

    All threshold errors inherit from ConstitutionalViolationError
    because threshold violations are constitutional violations.
    """

    pass


class ConstitutionalFloorViolationError(ThresholdError):
    """Raised when attempting to set a threshold below its constitutional floor (FR33).

    Constitutional Constraint (FR33):
    Threshold definitions SHALL be constitutional, not operational.
    Setting any threshold below its floor violates this constraint.

    Attributes:
        threshold_name: Name of the threshold being violated.
        attempted_value: The value that was attempted.
        constitutional_floor: The minimum allowed value.
        fr_reference: FR reference for the threshold.
    """

    def __init__(
        self,
        threshold_name: str,
        attempted_value: int | float,
        constitutional_floor: int | float,
        fr_reference: str,
    ) -> None:
        self.threshold_name = threshold_name
        self.attempted_value = attempted_value
        self.constitutional_floor = constitutional_floor
        self.fr_reference = fr_reference

        message = (
            f"FR33: Constitutional floor violation - "
            f"{threshold_name} cannot be set to {attempted_value}, "
            f"minimum is {constitutional_floor} ({fr_reference})"
        )
        super().__init__(message)


class ThresholdNotFoundError(ThresholdError):
    """Raised when a threshold is not found in the registry.

    Attributes:
        threshold_name: Name of the threshold that was not found.
    """

    def __init__(self, threshold_name: str) -> None:
        self.threshold_name = threshold_name
        message = f"Threshold not found: {threshold_name}"
        super().__init__(message)


class CounterResetAttemptedError(ThresholdError):
    """Raised when a threshold change attempts to reset counters (FR34).

    Constitutional Constraint (FR34):
    Threshold changes SHALL NOT reset active counters.
    Any attempt to reset counters during threshold changes is prohibited.

    Attributes:
        threshold_name: Name of the threshold involved.
        counter_type: Type of counter that would have been reset.
    """

    def __init__(self, threshold_name: str, counter_type: str) -> None:
        self.threshold_name = threshold_name
        self.counter_type = counter_type
        message = (
            f"FR34: Counter reset prohibited - "
            f"threshold change for {threshold_name} cannot reset {counter_type} counters"
        )
        super().__init__(message)
