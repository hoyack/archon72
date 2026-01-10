"""Configuration floor enforcement errors (Story 6.10, NFR39).

This module provides exception classes for configuration floor violations:
- ConfigurationFloorEnforcementError: Base class for all floor enforcement errors
- StartupFloorViolationError: Startup blocked due to floor violation
- RuntimeFloorViolationError: Runtime configuration change rejected
- FloorModificationAttemptedError: Attempt to modify immutable floor value

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> Startup failure over running below floor
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class ConfigurationFloorEnforcementError(ConstitutionalViolationError):
    """Base class for configuration floor enforcement errors.

    All floor enforcement errors inherit from ConstitutionalViolationError
    because floor violations are constitutional violations (NFR39).
    """

    pass


class StartupFloorViolationError(ConfigurationFloorEnforcementError):
    """Raised when startup configuration violates a constitutional floor (NFR39, AC1).

    Constitutional Constraint (NFR39):
    No configuration SHALL allow thresholds below constitutional floors.
    Startup MUST fail immediately if any configuration is below its floor.

    Constitutional Truth (CT-13):
    Integrity outranks availability. Startup failure is preferable
    to running with configuration below constitutional minimums.

    Attributes:
        threshold_name: Name of the threshold being violated.
        attempted_value: The value that was configured.
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
            f"NFR39: Startup blocked - {threshold_name} cannot be configured to "
            f"{attempted_value}, constitutional minimum is {constitutional_floor} "
            f"({fr_reference})"
        )
        super().__init__(message)


class RuntimeFloorViolationError(ConfigurationFloorEnforcementError):
    """Raised when runtime configuration change violates a constitutional floor (NFR39, AC2).

    Constitutional Constraint (NFR39):
    No configuration SHALL allow thresholds below constitutional floors.
    Runtime configuration changes MUST be rejected if below floor.

    Constitutional Truth (CT-11):
    Silent failure destroys legitimacy. Runtime floor violations
    trigger halt to prevent silent degradation.

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
            f"NFR39: Configuration change rejected - {threshold_name} cannot be set to "
            f"{attempted_value} at runtime, constitutional minimum is {constitutional_floor}"
        )
        super().__init__(message)


class FloorModificationAttemptedError(ConfigurationFloorEnforcementError):
    """Raised when attempting to modify a constitutional floor value (NFR39, AC3).

    Constitutional Constraint (NFR39):
    Constitutional floors are immutable. Any attempt to modify
    a floor value at runtime is prohibited.

    This error is raised when code attempts to modify the
    constitutional_floor field of a threshold definition.
    """

    def __init__(self) -> None:
        message = "NFR39: Constitutional floor modification is prohibited"
        super().__init__(message)
