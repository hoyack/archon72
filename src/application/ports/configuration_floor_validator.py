"""Configuration floor validator port (Story 6.10, NFR39).

This module defines the abstract interface for configuration floor validation.
Implementations validate that configuration values never go below constitutional floors.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> Startup failure over running below floor

Usage:
    validator: ConfigurationFloorValidatorProtocol = ...

    # Startup validation (sync - no async context yet)
    result = validator.validate_startup_configuration()
    if not result.is_valid:
        # Handle violations (log CRITICAL, exit)

    # Runtime change validation (async - uses halt checker)
    change_result = await validator.validate_configuration_change("threshold_name", 5)
    if not change_result.is_valid:
        # Handle rejection
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.domain.models.constitutional_threshold import ConstitutionalThreshold


@dataclass(frozen=True)
class ThresholdViolation:
    """Details of a threshold floor violation.

    Attributes:
        threshold_name: Name of the violated threshold.
        attempted_value: Value that was attempted.
        floor_value: Constitutional floor that was violated.
        fr_reference: FR/NFR reference for the threshold.
    """

    threshold_name: str
    attempted_value: int | float
    floor_value: int | float
    fr_reference: str


@dataclass(frozen=True)
class ThresholdStatus:
    """Status of a single threshold for health checks.

    Attributes:
        threshold_name: Name of the threshold.
        floor_value: Constitutional floor value.
        current_value: Currently configured value.
        is_valid: True if current_value >= floor_value.
    """

    threshold_name: str
    floor_value: int | float
    current_value: int | float
    is_valid: bool


@dataclass(frozen=True)
class ConfigurationValidationResult:
    """Result of startup configuration validation.

    Attributes:
        is_valid: True if all thresholds are at or above their floors.
        violations: Tuple of threshold violations found.
        validated_count: Number of thresholds validated.
        validated_at: Timestamp of validation.
    """

    is_valid: bool
    violations: tuple[ThresholdViolation, ...]
    validated_count: int
    validated_at: datetime


@dataclass(frozen=True)
class ConfigurationChangeResult:
    """Result of a runtime configuration change validation.

    Attributes:
        is_valid: True if the change is allowed.
        threshold_name: Name of threshold being changed.
        requested_value: Value that was requested.
        floor_value: Constitutional floor for this threshold.
        rejection_reason: Reason for rejection if is_valid=False.
    """

    is_valid: bool
    threshold_name: str
    requested_value: int | float
    floor_value: int | float
    rejection_reason: str | None


@dataclass(frozen=True)
class ConfigurationHealthStatus:
    """Health status of all configuration thresholds.

    Attributes:
        is_healthy: True if all thresholds are valid.
        threshold_statuses: Status of each threshold.
        checked_at: Timestamp of health check.
    """

    is_healthy: bool
    threshold_statuses: tuple[ThresholdStatus, ...]
    checked_at: datetime


class ConfigurationFloorValidatorProtocol(ABC):
    """Abstract interface for configuration floor validation (NFR39).

    This port defines the contract for validating configuration values
    against constitutional floors. Implementations must enforce that
    no threshold value can be set below its constitutional floor.

    Constitutional Constraints:
    - NFR39: No configuration SHALL allow thresholds below constitutional floors
    - CT-11: Silent failure destroys legitimacy -> HALT on runtime violations
    - CT-13: Integrity outranks availability -> Startup fails if below floor

    Developer Golden Rules:
    1. HALT FIRST - Check halt state before runtime operations
    2. WITNESS EVERYTHING - Log all violation attempts
    3. FAIL LOUD - Never silently allow floor violations
    """

    @abstractmethod
    async def validate_startup_configuration(self) -> ConfigurationValidationResult:
        """Validate all configuration values against floors at startup.

        This method should be called before the application starts
        serving requests. If any violations are found, startup should fail.

        Constitutional Constraint (CT-13):
        Integrity outranks availability. Startup failure is preferable
        to running with configuration below constitutional minimums.

        Returns:
            ConfigurationValidationResult with validation outcome.
        """
        ...

    @abstractmethod
    async def validate_configuration_change(
        self,
        threshold_name: str,
        new_value: int | float,
    ) -> ConfigurationChangeResult:
        """Validate a single configuration change at runtime.

        HALT CHECK FIRST (CT-11).

        This method should check halt state before validating.
        If the change would violate a floor, it should be rejected.

        Args:
            threshold_name: Name of threshold to change.
            new_value: New value being requested.

        Returns:
            ConfigurationChangeResult with validation outcome.
        """
        ...

    @abstractmethod
    def get_all_floors(self) -> tuple[ConstitutionalThreshold, ...]:
        """Get all constitutional floor definitions.

        This is a sync method - pure domain lookup with no I/O.

        Returns:
            Tuple of all ConstitutionalThreshold definitions.
        """
        ...

    @abstractmethod
    def get_floor(self, threshold_name: str) -> ConstitutionalThreshold:
        """Get a specific floor definition by name.

        This is a sync method - pure domain lookup with no I/O.

        Args:
            threshold_name: Name of the threshold.

        Returns:
            ConstitutionalThreshold for the given name.

        Raises:
            KeyError: If threshold not found.
        """
        ...

    @abstractmethod
    async def get_configuration_health(self) -> ConfigurationHealthStatus:
        """Get health status of all configurations.

        Returns status of each threshold showing current_value,
        floor_value, and is_valid for each.

        Returns:
            ConfigurationHealthStatus with all threshold statuses.
        """
        ...
