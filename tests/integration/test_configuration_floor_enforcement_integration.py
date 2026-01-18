"""Integration tests for configuration floor enforcement (Story 6.10, NFR39).

Tests the complete flow of configuration floor enforcement including
startup validation, runtime change rejection, and halt triggering.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT on runtime violations
- CT-13: Integrity outranks availability -> Startup failure over running below floor
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.configuration_floor_validator import (
    ConfigurationFloorValidatorProtocol,
)
from src.application.services.configuration_floor_enforcement_service import (
    ConfigurationFloorEnforcementService,
)
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
)
from src.infrastructure.stubs.configuration_floor_validator_stub import (
    ConfigurationFloorValidatorStub,
)
from src.infrastructure.stubs.halt_state import HaltState
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub


class TestStartupValidationIntegration:
    """Integration tests for startup configuration validation (AC1)."""

    @pytest.fixture
    def halt_state(self) -> HaltState:
        """Create fresh halt state for tests."""
        state = HaltState.get_instance("test_startup")
        state.reset()
        return state

    @pytest.fixture
    def halt_trigger(self, halt_state: HaltState) -> HaltTriggerStub:
        """Create halt trigger with shared state."""
        return HaltTriggerStub(halt_state=halt_state)

    @pytest.fixture
    def service(
        self, halt_trigger: HaltTriggerStub
    ) -> ConfigurationFloorEnforcementService:
        """Create service with halt trigger."""
        return ConfigurationFloorEnforcementService(halt_trigger=halt_trigger)

    @pytest.mark.asyncio
    async def test_startup_validates_all_constitutional_thresholds(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC1: Startup should validate all constitutional thresholds."""
        result = await service.validate_startup_configuration()

        # Should validate all thresholds in registry
        assert result.validated_count == len(CONSTITUTIONAL_THRESHOLD_REGISTRY)

    @pytest.mark.asyncio
    async def test_startup_validation_passes_with_defaults(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC1: Startup should pass with default (valid) configuration."""
        result = await service.validate_startup_configuration()

        assert result.is_valid is True
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_startup_validation_includes_timestamp(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """Startup validation should include timestamp for audit."""
        before = datetime.now(timezone.utc)
        result = await service.validate_startup_configuration()
        after = datetime.now(timezone.utc)

        assert before <= result.validated_at <= after


class TestRuntimeChangeValidationIntegration:
    """Integration tests for runtime configuration change validation (AC2)."""

    @pytest.fixture
    def halt_state(self) -> HaltState:
        """Create fresh halt state for tests."""
        state = HaltState.get_instance("test_runtime")
        state.reset()
        return state

    @pytest.fixture
    def halt_trigger(self, halt_state: HaltState) -> HaltTriggerStub:
        """Create halt trigger with shared state."""
        return HaltTriggerStub(halt_state=halt_state)

    @pytest.fixture
    def service(
        self, halt_trigger: HaltTriggerStub
    ) -> ConfigurationFloorEnforcementService:
        """Create service with halt trigger."""
        return ConfigurationFloorEnforcementService(halt_trigger=halt_trigger)

    @pytest.mark.asyncio
    async def test_valid_change_is_accepted(
        self, service: ConfigurationFloorEnforcementService, halt_state: HaltState
    ) -> None:
        """AC2: Valid configuration changes should be accepted."""
        # cessation_breach_count has floor of 10, so 15 is valid
        result = await service.validate_configuration_change(
            "cessation_breach_count", 15
        )

        assert result.is_valid is True
        assert result.rejection_reason is None
        # Should NOT trigger halt
        assert halt_state.is_halted is False

    @pytest.mark.asyncio
    async def test_value_at_floor_is_accepted(
        self, service: ConfigurationFloorEnforcementService, halt_state: HaltState
    ) -> None:
        """AC2: Value exactly at floor should be accepted."""
        # cessation_breach_count has floor of 10
        result = await service.validate_configuration_change(
            "cessation_breach_count", 10
        )

        assert result.is_valid is True
        assert halt_state.is_halted is False

    @pytest.mark.asyncio
    async def test_value_below_floor_triggers_halt(
        self, service: ConfigurationFloorEnforcementService, halt_state: HaltState
    ) -> None:
        """AC2, CT-11: Value below floor should trigger system halt."""
        # cessation_breach_count has floor of 10, so 5 is invalid
        result = await service.validate_configuration_change(
            "cessation_breach_count", 5
        )

        assert result.is_valid is False
        assert result.rejection_reason is not None
        # Should trigger halt per CT-11
        assert halt_state.is_halted is True

    @pytest.mark.asyncio
    async def test_halt_reason_includes_nfr39_reference(
        self, service: ConfigurationFloorEnforcementService, halt_state: HaltState
    ) -> None:
        """Halt reason should reference NFR39 for traceability."""
        await service.validate_configuration_change("cessation_breach_count", 5)

        reason = halt_state.halt_reason
        assert reason is not None
        assert "NFR39" in reason


class TestThresholdRegistryIntegration:
    """Integration tests for threshold registry access."""

    @pytest.fixture
    def service(self) -> ConfigurationFloorEnforcementService:
        """Create service with mock halt trigger."""
        return ConfigurationFloorEnforcementService(halt_trigger=AsyncMock())

    def test_get_all_floors_matches_registry(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC3: get_all_floors should return all constitutional thresholds."""
        floors = service.get_all_floors()

        assert len(floors) == len(CONSTITUTIONAL_THRESHOLD_REGISTRY)
        # Verify specific known thresholds
        names = {t.threshold_name for t in floors}
        assert "cessation_breach_count" in names
        assert "recovery_waiting_hours" in names
        assert "minimum_keeper_quorum" in names

    def test_get_floor_returns_correct_values(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC3: get_floor should return correct threshold values."""
        threshold = service.get_floor("cessation_breach_count")

        assert threshold.threshold_name == "cessation_breach_count"
        assert threshold.constitutional_floor == 10
        assert threshold.fr_reference == "FR32"

    def test_get_floor_raises_for_unknown(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC3: get_floor should raise KeyError for unknown threshold."""
        with pytest.raises(KeyError):
            service.get_floor("unknown_threshold")


class TestHealthCheckIntegration:
    """Integration tests for configuration health check (AC6)."""

    @pytest.fixture
    def service(self) -> ConfigurationFloorEnforcementService:
        """Create service with mock halt trigger."""
        return ConfigurationFloorEnforcementService(halt_trigger=AsyncMock())

    @pytest.mark.asyncio
    async def test_health_includes_all_thresholds(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC6: Health check should include all threshold statuses."""
        health = await service.get_configuration_health()

        assert len(health.threshold_statuses) == len(CONSTITUTIONAL_THRESHOLD_REGISTRY)

    @pytest.mark.asyncio
    async def test_health_shows_floor_and_current_values(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC6: Health check should show floor and current values."""
        health = await service.get_configuration_health()

        for status in health.threshold_statuses:
            assert status.floor_value is not None
            assert status.current_value is not None
            assert status.is_valid == (status.current_value >= status.floor_value)

    @pytest.mark.asyncio
    async def test_health_is_healthy_with_valid_config(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC6: Health should be healthy with valid configuration."""
        health = await service.get_configuration_health()

        assert health.is_healthy is True

    @pytest.mark.asyncio
    async def test_health_includes_timestamp(
        self, service: ConfigurationFloorEnforcementService
    ) -> None:
        """AC6: Health check should include timestamp."""
        before = datetime.now(timezone.utc)
        health = await service.get_configuration_health()
        after = datetime.now(timezone.utc)

        assert before <= health.checked_at <= after


class TestStubIntegration:
    """Integration tests for stub implementation."""

    @pytest.fixture
    def halt_state(self) -> HaltState:
        """Create fresh halt state for tests."""
        state = HaltState.get_instance("test_stub")
        state.reset()
        return state

    @pytest.fixture
    def halt_trigger(self, halt_state: HaltState) -> HaltTriggerStub:
        """Create halt trigger with shared state."""
        return HaltTriggerStub(halt_state=halt_state)

    @pytest.fixture
    def stub(self, halt_trigger: HaltTriggerStub) -> ConfigurationFloorValidatorStub:
        """Create stub with halt trigger."""
        return ConfigurationFloorValidatorStub(halt_trigger=halt_trigger)

    def test_stub_implements_protocol(
        self, stub: ConfigurationFloorValidatorStub
    ) -> None:
        """Stub should implement ConfigurationFloorValidatorProtocol."""
        assert isinstance(stub, ConfigurationFloorValidatorProtocol)

    @pytest.mark.asyncio
    async def test_stub_validation_count_tracking(
        self, stub: ConfigurationFloorValidatorStub
    ) -> None:
        """Stub should track validation count for testing."""
        assert stub.get_validation_count() == 0

        await stub.validate_startup_configuration()
        assert stub.get_validation_count() == 1

        await stub.validate_configuration_change("cessation_breach_count", 15)
        assert stub.get_validation_count() == 2

    def test_stub_reset_clears_count(
        self, stub: ConfigurationFloorValidatorStub
    ) -> None:
        """Stub reset should clear validation count."""
        stub.reset()
        assert stub.get_validation_count() == 0


class TestConstitutionalFloorImmutability:
    """Tests verifying constitutional floors cannot be modified (AC3)."""

    def test_floor_values_are_immutable(self) -> None:
        """Constitutional floor values should be immutable."""
        # Get a threshold
        threshold = CONSTITUTIONAL_THRESHOLD_REGISTRY.get_threshold(
            "cessation_breach_count"
        )

        # Verify it's frozen (dataclass)
        with pytest.raises(AttributeError):
            threshold.constitutional_floor = 5  # type: ignore[misc]

    def test_registry_returns_same_values(self) -> None:
        """Registry should return consistent floor values."""
        threshold1 = CONSTITUTIONAL_THRESHOLD_REGISTRY.get_threshold(
            "cessation_breach_count"
        )
        threshold2 = CONSTITUTIONAL_THRESHOLD_REGISTRY.get_threshold(
            "cessation_breach_count"
        )

        assert threshold1.constitutional_floor == threshold2.constitutional_floor
        assert threshold1.constitutional_floor == 10
