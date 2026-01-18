"""Stub ConfigurationFloorValidator for testing/development (Story 6.10, NFR39).

This stub implements the ConfigurationFloorValidatorProtocol for testing.
It delegates to the real ConfigurationFloorEnforcementService for actual validation,
but adds test-friendly features like validation counting and reset.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT on runtime violations
- CT-13: Integrity outranks availability -> Startup fails if below floor

Usage:
    # Create stub with mock halt trigger
    halt_trigger = HaltTriggerStub()
    validator = ConfigurationFloorValidatorStub(halt_trigger=halt_trigger)

    # Validate startup configuration
    result = await validator.validate_startup_configuration()

    # Check validation count (for testing)
    assert validator.get_validation_count() == 1
"""

from __future__ import annotations

from structlog import get_logger

from src.application.ports.configuration_floor_validator import (
    ConfigurationChangeResult,
    ConfigurationFloorValidatorProtocol,
    ConfigurationHealthStatus,
    ConfigurationValidationResult,
)
from src.application.ports.halt_trigger import HaltTrigger
from src.application.services.configuration_floor_enforcement_service import (
    ConfigurationFloorEnforcementService,
)
from src.domain.models.constitutional_threshold import ConstitutionalThreshold

logger = get_logger()


class ConfigurationFloorValidatorStub(ConfigurationFloorValidatorProtocol):
    """Stub implementation of ConfigurationFloorValidatorProtocol for testing.

    This stub wraps the real ConfigurationFloorEnforcementService but adds
    test-friendly features like validation counting and reset capabilities.

    Constitutional Constraints:
    - NFR39: No configuration SHALL allow thresholds below constitutional floors
    - CT-11: Silent failure destroys legitimacy -> HALT on runtime violations
    - CT-13: Integrity outranks availability -> Startup fails if below floor

    Attributes:
        _service: The underlying enforcement service
        _validation_count: Counter for validations (for testing)
    """

    def __init__(self, *, halt_trigger: HaltTrigger) -> None:
        """Initialize the stub.

        Args:
            halt_trigger: HaltTrigger port for triggering halt on violations.
        """
        self._service = ConfigurationFloorEnforcementService(halt_trigger=halt_trigger)
        self._validation_count = 0
        self._log = logger.bind(stub="ConfigurationFloorValidatorStub")

    async def validate_startup_configuration(self) -> ConfigurationValidationResult:
        """Validate all configuration values against floors at startup.

        Returns:
            ConfigurationValidationResult with validation outcome.
        """
        self._log.info("validate_startup_configuration_called")
        self._validation_count += 1
        return await self._service.validate_startup_configuration()

    async def validate_configuration_change(
        self,
        threshold_name: str,
        new_value: int | float,
    ) -> ConfigurationChangeResult:
        """Validate a single configuration change at runtime.

        Args:
            threshold_name: Name of threshold to change.
            new_value: New value being requested.

        Returns:
            ConfigurationChangeResult with validation outcome.
        """
        self._log.info(
            "validate_configuration_change_called",
            threshold_name=threshold_name,
            new_value=new_value,
        )
        self._validation_count += 1
        return await self._service.validate_configuration_change(
            threshold_name, new_value
        )

    def get_all_floors(self) -> tuple[ConstitutionalThreshold, ...]:
        """Get all constitutional floor definitions.

        Returns:
            Tuple of all ConstitutionalThreshold definitions.
        """
        return self._service.get_all_floors()

    def get_floor(self, threshold_name: str) -> ConstitutionalThreshold:
        """Get a specific floor definition by name.

        Args:
            threshold_name: Name of the threshold.

        Returns:
            ConstitutionalThreshold for the given name.

        Raises:
            KeyError: If threshold not found.
        """
        return self._service.get_floor(threshold_name)

    async def get_configuration_health(self) -> ConfigurationHealthStatus:
        """Get health status of all configurations.

        Returns:
            ConfigurationHealthStatus with all threshold statuses.
        """
        return await self._service.get_configuration_health()

    # Test helper methods

    def get_validation_count(self) -> int:
        """Get the number of validations performed (for testing)."""
        return self._validation_count

    def reset(self) -> None:
        """Reset the stub state (for testing cleanup)."""
        self._validation_count = 0
        self._log.info("stub_reset")
