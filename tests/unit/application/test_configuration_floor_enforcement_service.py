"""Unit tests for ConfigurationFloorEnforcementService (Story 6.10, NFR39).

Tests for the service that enforces configuration floors at startup and runtime.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> Startup failure over running below floor
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.services.configuration_floor_enforcement_service import (
    ConfigurationFloorEnforcementService,
)
from src.domain.errors.configuration_floor import (
    RuntimeFloorViolationError,
    StartupFloorViolationError,
)
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
)


class TestConfigurationFloorEnforcementService:
    """Tests for ConfigurationFloorEnforcementService."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorEnforcementService:
        """Create service with mock dependencies."""
        return ConfigurationFloorEnforcementService(
            halt_trigger=mock_halt_trigger,
        )


class TestValidateStartupConfiguration:
    """Tests for validate_startup_configuration (AC1)."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorEnforcementService:
        """Create service with mock dependencies."""
        return ConfigurationFloorEnforcementService(
            halt_trigger=mock_halt_trigger,
        )

    @pytest.mark.asyncio
    async def test_valid_configuration_passes(self, service: ConfigurationFloorEnforcementService) -> None:
        """Startup should pass when all values are at or above floors."""
        result = await service.validate_startup_configuration()

        assert result.is_valid is True
        assert len(result.violations) == 0
        assert result.validated_count == len(CONSTITUTIONAL_THRESHOLD_REGISTRY)

    @pytest.mark.asyncio
    async def test_valid_configuration_returns_timestamp(self, service: ConfigurationFloorEnforcementService) -> None:
        """Startup validation should include timestamp."""
        before = datetime.now(timezone.utc)
        result = await service.validate_startup_configuration()
        after = datetime.now(timezone.utc)

        assert before <= result.validated_at <= after


class TestValidateConfigurationChange:
    """Tests for validate_configuration_change (AC2)."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorEnforcementService:
        """Create service with mock dependencies."""
        return ConfigurationFloorEnforcementService(
            halt_trigger=mock_halt_trigger,
        )

    @pytest.mark.asyncio
    async def test_valid_change_passes(self, service: ConfigurationFloorEnforcementService) -> None:
        """Runtime change at or above floor should be valid."""
        # cessation_breach_count has floor of 10
        result = await service.validate_configuration_change("cessation_breach_count", 15)

        assert result.is_valid is True
        assert result.threshold_name == "cessation_breach_count"
        assert result.requested_value == 15
        assert result.floor_value == 10
        assert result.rejection_reason is None

    @pytest.mark.asyncio
    async def test_value_at_floor_passes(self, service: ConfigurationFloorEnforcementService) -> None:
        """Runtime change exactly at floor should be valid."""
        # cessation_breach_count has floor of 10
        result = await service.validate_configuration_change("cessation_breach_count", 10)

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_value_below_floor_rejected(
        self,
        service: ConfigurationFloorEnforcementService,
        mock_halt_trigger: AsyncMock,
    ) -> None:
        """Runtime change below floor should be rejected (AC2)."""
        # cessation_breach_count has floor of 10
        result = await service.validate_configuration_change("cessation_breach_count", 5)

        assert result.is_valid is False
        assert result.rejection_reason is not None
        assert "floor" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_below_floor_triggers_halt(
        self,
        service: ConfigurationFloorEnforcementService,
        mock_halt_trigger: AsyncMock,
    ) -> None:
        """Runtime floor violation should trigger halt (CT-11)."""
        # cessation_breach_count has floor of 10
        await service.validate_configuration_change("cessation_breach_count", 5)

        mock_halt_trigger.trigger_halt.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_threshold_rejected(self, service: ConfigurationFloorEnforcementService) -> None:
        """Unknown threshold name should be rejected."""
        result = await service.validate_configuration_change("unknown_threshold", 100)

        assert result.is_valid is False
        assert result.rejection_reason is not None


class TestGetAllFloors:
    """Tests for get_all_floors."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorEnforcementService:
        """Create service with mock dependencies."""
        return ConfigurationFloorEnforcementService(
            halt_trigger=mock_halt_trigger,
        )

    def test_returns_all_thresholds(self, service: ConfigurationFloorEnforcementService) -> None:
        """Should return all constitutional thresholds."""
        floors = service.get_all_floors()

        assert len(floors) == len(CONSTITUTIONAL_THRESHOLD_REGISTRY)

    def test_includes_expected_thresholds(self, service: ConfigurationFloorEnforcementService) -> None:
        """Should include known thresholds."""
        floors = service.get_all_floors()
        names = {t.threshold_name for t in floors}

        assert "cessation_breach_count" in names
        assert "recovery_waiting_hours" in names
        assert "minimum_keeper_quorum" in names


class TestGetFloor:
    """Tests for get_floor."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorEnforcementService:
        """Create service with mock dependencies."""
        return ConfigurationFloorEnforcementService(
            halt_trigger=mock_halt_trigger,
        )

    def test_returns_specific_threshold(self, service: ConfigurationFloorEnforcementService) -> None:
        """Should return specific threshold by name."""
        threshold = service.get_floor("cessation_breach_count")

        assert threshold.threshold_name == "cessation_breach_count"
        assert threshold.constitutional_floor == 10
        assert threshold.fr_reference == "FR32"

    def test_raises_key_error_for_unknown(self, service: ConfigurationFloorEnforcementService) -> None:
        """Should raise KeyError for unknown threshold."""
        with pytest.raises(KeyError):
            service.get_floor("unknown_threshold")


class TestGetConfigurationHealth:
    """Tests for get_configuration_health (AC6)."""

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_halt_trigger: AsyncMock) -> ConfigurationFloorEnforcementService:
        """Create service with mock dependencies."""
        return ConfigurationFloorEnforcementService(
            halt_trigger=mock_halt_trigger,
        )

    @pytest.mark.asyncio
    async def test_healthy_when_all_valid(self, service: ConfigurationFloorEnforcementService) -> None:
        """Health should be true when all thresholds valid."""
        health = await service.get_configuration_health()

        assert health.is_healthy is True
        assert len(health.threshold_statuses) == len(CONSTITUTIONAL_THRESHOLD_REGISTRY)

    @pytest.mark.asyncio
    async def test_includes_all_threshold_statuses(self, service: ConfigurationFloorEnforcementService) -> None:
        """Should include status for each threshold."""
        health = await service.get_configuration_health()
        names = {s.threshold_name for s in health.threshold_statuses}

        assert "cessation_breach_count" in names
        assert "recovery_waiting_hours" in names

    @pytest.mark.asyncio
    async def test_statuses_show_floor_values(self, service: ConfigurationFloorEnforcementService) -> None:
        """Each status should show floor value."""
        health = await service.get_configuration_health()

        for status in health.threshold_statuses:
            assert status.floor_value is not None
            assert status.current_value is not None
            assert status.is_valid == (status.current_value >= status.floor_value)

    @pytest.mark.asyncio
    async def test_health_includes_timestamp(self, service: ConfigurationFloorEnforcementService) -> None:
        """Health check should include timestamp."""
        before = datetime.now(timezone.utc)
        health = await service.get_configuration_health()
        after = datetime.now(timezone.utc)

        assert before <= health.checked_at <= after
