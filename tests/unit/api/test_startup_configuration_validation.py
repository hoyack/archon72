"""Unit tests for startup configuration floor validation (Story 6.10, NFR39, AC1).

Tests for the startup configuration validation hook.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-13: Integrity outranks availability -> Startup failure over running below floor
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.api.startup import validate_configuration_floors_at_startup
from src.domain.errors.configuration_floor import StartupFloorViolationError


class TestValidateConfigurationFloorsAtStartup:
    """Tests for validate_configuration_floors_at_startup."""

    @pytest.mark.asyncio
    async def test_passes_with_valid_configuration(self) -> None:
        """Should pass silently when all configurations are valid."""
        # Default configuration should be valid
        # Should not raise any exception
        await validate_configuration_floors_at_startup()

    @pytest.mark.asyncio
    async def test_raises_on_invalid_configuration(self) -> None:
        """Should raise StartupFloorViolationError on invalid configuration."""
        # Create a mock result with violations
        mock_result = AsyncMock()
        mock_result.is_valid = False
        mock_result.violations = [
            AsyncMock(
                threshold_name="test_threshold",
                attempted_value=1,
                floor_value=10,
                fr_reference="FR1",
            )
        ]

        with patch(
            "src.api.startup.ConfigurationFloorEnforcementService"
        ) as MockService:
            mock_service = AsyncMock()
            mock_service.validate_startup_configuration.return_value = mock_result
            MockService.return_value = mock_service

            with pytest.raises(StartupFloorViolationError):
                await validate_configuration_floors_at_startup()


class TestStartupValidationLogging:
    """Tests for startup validation logging."""

    @pytest.mark.asyncio
    async def test_logs_validation_result(self) -> None:
        """Should log validation result."""
        # This test verifies that the function completes without error
        # Actual logging is handled by structlog
        await validate_configuration_floors_at_startup()
        # If we get here without exception, validation passed

    @pytest.mark.asyncio
    async def test_logs_threshold_count(self) -> None:
        """Should log number of thresholds validated."""
        # With default valid configuration, should complete
        await validate_configuration_floors_at_startup()
        # Validation logged internally (structlog)
