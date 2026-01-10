"""Unit tests for ConfigurationFloorValidatorStub (Story 6.10, NFR39).

Tests for the stub implementation of the configuration floor validator.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.configuration_floor_validator import (
    ConfigurationFloorValidatorProtocol,
)
from src.infrastructure.stubs.configuration_floor_validator_stub import (
    ConfigurationFloorValidatorStub,
)
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
)


class TestConfigurationFloorValidatorStub:
    """Tests for ConfigurationFloorValidatorStub."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def stub(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorValidatorStub:
        """Create stub with mock dependencies."""
        return ConfigurationFloorValidatorStub(halt_trigger=mock_halt_trigger)

    def test_implements_protocol(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Stub should implement ConfigurationFloorValidatorProtocol."""
        assert isinstance(stub, ConfigurationFloorValidatorProtocol)


class TestValidateStartupConfiguration:
    """Tests for validate_startup_configuration on stub."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def stub(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorValidatorStub:
        """Create stub with mock dependencies."""
        return ConfigurationFloorValidatorStub(halt_trigger=mock_halt_trigger)

    @pytest.mark.asyncio
    async def test_passes_with_default_values(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Stub should pass validation with default values."""
        result = await stub.validate_startup_configuration()

        assert result.is_valid is True
        assert len(result.violations) == 0


class TestValidateConfigurationChange:
    """Tests for validate_configuration_change on stub."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def stub(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorValidatorStub:
        """Create stub with mock dependencies."""
        return ConfigurationFloorValidatorStub(halt_trigger=mock_halt_trigger)

    @pytest.mark.asyncio
    async def test_valid_change_passes(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Valid configuration change should pass."""
        result = await stub.validate_configuration_change("cessation_breach_count", 15)

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_invalid_change_rejected(
        self,
        stub: ConfigurationFloorValidatorStub,
        mock_halt_trigger: AsyncMock,
    ) -> None:
        """Invalid configuration change should be rejected."""
        result = await stub.validate_configuration_change("cessation_breach_count", 5)

        assert result.is_valid is False
        mock_halt_trigger.trigger_halt.assert_called_once()


class TestGetAllFloors:
    """Tests for get_all_floors on stub."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def stub(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorValidatorStub:
        """Create stub with mock dependencies."""
        return ConfigurationFloorValidatorStub(halt_trigger=mock_halt_trigger)

    def test_returns_all_thresholds(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Should return all thresholds."""
        floors = stub.get_all_floors()

        assert len(floors) == len(CONSTITUTIONAL_THRESHOLD_REGISTRY)


class TestGetFloor:
    """Tests for get_floor on stub."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def stub(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorValidatorStub:
        """Create stub with mock dependencies."""
        return ConfigurationFloorValidatorStub(halt_trigger=mock_halt_trigger)

    def test_returns_specific_threshold(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Should return specific threshold by name."""
        threshold = stub.get_floor("cessation_breach_count")

        assert threshold.threshold_name == "cessation_breach_count"
        assert threshold.constitutional_floor == 10


class TestGetConfigurationHealth:
    """Tests for get_configuration_health on stub."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def stub(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorValidatorStub:
        """Create stub with mock dependencies."""
        return ConfigurationFloorValidatorStub(halt_trigger=mock_halt_trigger)

    @pytest.mark.asyncio
    async def test_returns_healthy_status(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Should return healthy status with default values."""
        health = await stub.get_configuration_health()

        assert health.is_healthy is True
        assert len(health.threshold_statuses) > 0


class TestTestHelpers:
    """Tests for stub test helper methods."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def stub(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorValidatorStub:
        """Create stub with mock dependencies."""
        return ConfigurationFloorValidatorStub(halt_trigger=mock_halt_trigger)

    def test_get_validation_count(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Should track validation count."""
        initial_count = stub.get_validation_count()
        assert initial_count == 0

    @pytest.mark.asyncio
    async def test_validation_count_increments(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Validation count should increment on validation."""
        await stub.validate_startup_configuration()
        assert stub.get_validation_count() == 1

        await stub.validate_configuration_change("cessation_breach_count", 15)
        assert stub.get_validation_count() == 2

    def test_reset_clears_state(self, stub: ConfigurationFloorValidatorStub) -> None:
        """Reset should clear test state."""
        stub.reset()
        assert stub.get_validation_count() == 0
