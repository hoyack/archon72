"""Configuration floor enforcement service (Story 6.10, NFR39).

This service enforces constitutional floors on configuration values,
preventing any configuration from being set below its constitutional minimum.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT on runtime violations
- CT-13: Integrity outranks availability -> Startup fails if below floor

Developer Golden Rules:
1. HALT FIRST - Check halt state before runtime operations
2. WITNESS EVERYTHING - Log all violation attempts
3. FAIL LOUD - Never silently allow floor violations

Usage:
    service = ConfigurationFloorEnforcementService(halt_trigger=halt_trigger)

    # At startup
    result = await service.validate_startup_configuration()
    if not result.is_valid:
        # Log CRITICAL and exit

    # At runtime
    change_result = await service.validate_configuration_change("threshold_name", 5)
    if not change_result.is_valid:
        # Handle rejection (already triggered halt)
"""

from datetime import datetime, timezone

from src.application.ports.configuration_floor_validator import (
    ConfigurationChangeResult,
    ConfigurationFloorValidatorProtocol,
    ConfigurationHealthStatus,
    ConfigurationValidationResult,
    ThresholdStatus,
    ThresholdViolation,
)
from src.application.ports.halt_trigger import HaltTrigger
from src.domain.models.constitutional_threshold import ConstitutionalThreshold
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
)


class ConfigurationFloorEnforcementService(ConfigurationFloorValidatorProtocol):
    """Service that enforces configuration floors (NFR39).

    This service validates configuration values against their constitutional
    floors at startup and runtime. Runtime violations trigger system halt
    per CT-11 (silent failure destroys legitimacy).

    Constitutional Constraints:
    - NFR39: No configuration SHALL allow thresholds below constitutional floors
    - CT-11: Silent failure destroys legitimacy -> HALT on runtime violations
    - CT-13: Integrity outranks availability -> Startup fails if below floor

    Attributes:
        _halt_trigger: Port for triggering system halt on runtime violations.
    """

    def __init__(self, halt_trigger: HaltTrigger) -> None:
        """Initialize the service.

        Args:
            halt_trigger: Port for triggering system halt on violations.
        """
        self._halt_trigger = halt_trigger

    async def validate_startup_configuration(self) -> ConfigurationValidationResult:
        """Validate all configuration values against floors at startup.

        Constitutional Constraint (CT-13):
        Integrity outranks availability. Startup failure is preferable
        to running with configuration below constitutional minimums.

        Returns:
            ConfigurationValidationResult with validation outcome.
            If is_valid=False, startup should be blocked.
        """
        violations: list[ThresholdViolation] = []

        for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY:
            if threshold.current_value < threshold.constitutional_floor:
                violations.append(
                    ThresholdViolation(
                        threshold_name=threshold.threshold_name,
                        attempted_value=threshold.current_value,
                        floor_value=threshold.constitutional_floor,
                        fr_reference=threshold.fr_reference,
                    )
                )

        return ConfigurationValidationResult(
            is_valid=len(violations) == 0,
            violations=tuple(violations),
            validated_count=len(CONSTITUTIONAL_THRESHOLD_REGISTRY),
            validated_at=datetime.now(timezone.utc),
        )

    async def validate_configuration_change(
        self,
        threshold_name: str,
        new_value: int | float,
    ) -> ConfigurationChangeResult:
        """Validate a single configuration change at runtime.

        Constitutional Constraint (CT-11):
        Silent failure destroys legitimacy. Runtime floor violations
        trigger system halt to prevent silent degradation.

        Args:
            threshold_name: Name of threshold to change.
            new_value: New value being requested.

        Returns:
            ConfigurationChangeResult with validation outcome.
            If is_valid=False, halt has already been triggered.
        """
        # Try to find the threshold
        try:
            threshold = CONSTITUTIONAL_THRESHOLD_REGISTRY.get_threshold(threshold_name)
        except KeyError:
            return ConfigurationChangeResult(
                is_valid=False,
                threshold_name=threshold_name,
                requested_value=new_value,
                floor_value=0,  # Unknown threshold
                rejection_reason=f"Unknown threshold: {threshold_name}",
            )

        floor = threshold.constitutional_floor

        # Check if new value is at or above floor
        if new_value >= floor:
            return ConfigurationChangeResult(
                is_valid=True,
                threshold_name=threshold_name,
                requested_value=new_value,
                floor_value=floor,
                rejection_reason=None,
            )

        # Violation detected - trigger halt per CT-11
        reason = (
            f"NFR39: Configuration floor violation - {threshold_name} "
            f"cannot be set to {new_value}, floor is {floor}"
        )
        await self._halt_trigger.trigger_halt(reason=reason)

        return ConfigurationChangeResult(
            is_valid=False,
            threshold_name=threshold_name,
            requested_value=new_value,
            floor_value=floor,
            rejection_reason=f"Value {new_value} is below constitutional floor {floor}",
        )

    def get_all_floors(self) -> tuple[ConstitutionalThreshold, ...]:
        """Get all constitutional floor definitions.

        Returns:
            Tuple of all ConstitutionalThreshold definitions.
        """
        return CONSTITUTIONAL_THRESHOLD_REGISTRY.get_all_thresholds()

    def get_floor(self, threshold_name: str) -> ConstitutionalThreshold:
        """Get a specific floor definition by name.

        Args:
            threshold_name: Name of the threshold.

        Returns:
            ConstitutionalThreshold for the given name.

        Raises:
            KeyError: If threshold not found.
        """
        return CONSTITUTIONAL_THRESHOLD_REGISTRY.get_threshold(threshold_name)

    async def get_configuration_health(self) -> ConfigurationHealthStatus:
        """Get health status of all configurations.

        Returns status of each threshold showing current_value,
        floor_value, and is_valid for each.

        Returns:
            ConfigurationHealthStatus with all threshold statuses.
        """
        statuses: list[ThresholdStatus] = []

        for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY:
            is_valid = threshold.current_value >= threshold.constitutional_floor
            statuses.append(
                ThresholdStatus(
                    threshold_name=threshold.threshold_name,
                    floor_value=threshold.constitutional_floor,
                    current_value=threshold.current_value,
                    is_valid=is_valid,
                )
            )

        all_valid = all(s.is_valid for s in statuses)

        return ConfigurationHealthStatus(
            is_healthy=all_valid,
            threshold_statuses=tuple(statuses),
            checked_at=datetime.now(timezone.utc),
        )
