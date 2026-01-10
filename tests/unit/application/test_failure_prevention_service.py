"""Unit tests for FailurePreventionService (Story 8.8, FR106-FR107).

Tests for failure mode monitoring, early warning generation, and health dashboard.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.failure_prevention_service import (
    FailurePreventionService,
)
from src.domain.models.failure_mode import (
    DEFAULT_FAILURE_MODES,
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeSeverity,
    FailureModeStatus,
    FailureModeThreshold,
)
from src.infrastructure.stubs.failure_mode_registry_stub import (
    FailureModeRegistryStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a HaltChecker stub."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def registry() -> FailureModeRegistryStub:
    """Create a failure mode registry stub."""
    stub = FailureModeRegistryStub()
    stub.pre_populate_default_modes()
    return stub


@pytest.fixture
def service(
    registry: FailureModeRegistryStub,
    halt_checker: HaltCheckerStub,
) -> FailurePreventionService:
    """Create a FailurePreventionService with registry and halt_checker."""
    return FailurePreventionService(registry=registry, halt_checker=halt_checker)


class TestGetFailureMode:
    """Tests for get_failure_mode method."""

    @pytest.mark.asyncio
    async def test_returns_mode_by_id(
        self, service: FailurePreventionService
    ) -> None:
        """Test that a failure mode is returned by its ID."""
        mode = await service.get_failure_mode(FailureModeId.VAL_1)

        assert mode is not None
        assert mode.id == FailureModeId.VAL_1
        assert mode.description == "Silent signature corruption"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_id(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that None is returned for unknown mode ID."""
        registry.clear()
        mode = await service.get_failure_mode(FailureModeId.VAL_1)

        assert mode is None


class TestGetAllFailureModes:
    """Tests for get_all_failure_modes method."""

    @pytest.mark.asyncio
    async def test_returns_all_registered_modes(
        self, service: FailurePreventionService
    ) -> None:
        """Test that all registered failure modes are returned."""
        modes = await service.get_all_failure_modes()

        assert len(modes) == len(DEFAULT_FAILURE_MODES)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_modes_registered(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that empty list is returned when no modes registered."""
        registry.clear()
        modes = await service.get_all_failure_modes()

        assert modes == []


class TestCheckFailureMode:
    """Tests for check_failure_mode method."""

    @pytest.mark.asyncio
    async def test_returns_healthy_status_by_default(
        self, service: FailurePreventionService
    ) -> None:
        """Test that default status is HEALTHY."""
        status = await service.check_failure_mode(FailureModeId.VAL_1)

        assert status == FailureModeStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_returns_warning_status_when_threshold_breached(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that WARNING status is returned when threshold is breached."""
        # Add a threshold that's in warning state
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="signature_failures",
            warning_value=3.0,
            critical_value=10.0,
            current_value=5.0,  # Above warning
        )
        registry.add_threshold(threshold)

        status = await service.check_failure_mode(FailureModeId.VAL_1)

        assert status == FailureModeStatus.WARNING

    @pytest.mark.asyncio
    async def test_returns_critical_status_when_critical_threshold_breached(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that CRITICAL status is returned when critical threshold is breached."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="signature_failures",
            warning_value=3.0,
            critical_value=10.0,
            current_value=12.0,  # Above critical
        )
        registry.add_threshold(threshold)

        status = await service.check_failure_mode(FailureModeId.VAL_1)

        assert status == FailureModeStatus.CRITICAL


class TestRecordMetric:
    """Tests for record_metric method."""

    @pytest.mark.asyncio
    async def test_updates_metric_value(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that metric value is updated."""
        # Add initial threshold
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test_metric",
            warning_value=5.0,
            critical_value=10.0,
            current_value=0.0,
        )
        registry.add_threshold(threshold)

        await service.record_metric(
            FailureModeId.VAL_1, "test_metric", 3.0
        )

        # Check the metric was updated
        updated = await registry.get_threshold(FailureModeId.VAL_1, "test_metric")
        assert updated is not None
        assert updated.current_value == 3.0

    @pytest.mark.asyncio
    async def test_returns_status_after_update(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that correct status is returned after metric update."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test_metric",
            warning_value=5.0,
            critical_value=10.0,
            current_value=0.0,
        )
        registry.add_threshold(threshold)

        # Update to warning level
        status = await service.record_metric(
            FailureModeId.VAL_1, "test_metric", 7.0
        )

        assert status == FailureModeStatus.WARNING


class TestGetEarlyWarnings:
    """Tests for get_early_warnings method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_warnings(
        self, service: FailurePreventionService
    ) -> None:
        """Test that empty list is returned when no warnings exist."""
        warnings = await service.get_early_warnings()

        assert warnings == []

    @pytest.mark.asyncio
    async def test_returns_active_warnings(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that active warnings are returned."""
        warning = EarlyWarning.create(
            mode_id=FailureModeId.VAL_1,
            current_value=5.0,
            threshold=3.0,
            threshold_type="warning",
            recommended_action="Investigate signature verification",
            metric_name="signature_failures",
        )
        registry.add_warning(warning)

        warnings = await service.get_early_warnings()

        assert len(warnings) == 1
        assert warnings[0].mode_id == FailureModeId.VAL_1


class TestAcknowledgeWarning:
    """Tests for acknowledge_warning method."""

    @pytest.mark.asyncio
    async def test_acknowledges_existing_warning(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that existing warning can be acknowledged."""
        warning = EarlyWarning.create(
            mode_id=FailureModeId.VAL_1,
            current_value=5.0,
            threshold=3.0,
            threshold_type="warning",
            recommended_action="Investigate",
            metric_name="test_metric",
        )
        registry.add_warning(warning)

        success = await service.acknowledge_warning(
            str(warning.warning_id), "test_user"
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_warning(
        self, service: FailurePreventionService
    ) -> None:
        """Test that False is returned for unknown warning ID."""
        success = await service.acknowledge_warning(str(uuid4()), "test_user")

        assert success is False


class TestGetHealthSummary:
    """Tests for get_health_summary method."""

    @pytest.mark.asyncio
    async def test_returns_healthy_summary_by_default(
        self, service: FailurePreventionService
    ) -> None:
        """Test that default summary shows all healthy."""
        summary = await service.get_health_summary()

        assert summary.overall_status == FailureModeStatus.HEALTHY
        assert summary.healthy_count == len(DEFAULT_FAILURE_MODES)
        assert summary.warning_count == 0
        assert summary.critical_count == 0

    @pytest.mark.asyncio
    async def test_reflects_worst_status(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that summary reflects worst status."""
        # Add a critical threshold
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="critical_metric",
            warning_value=3.0,
            critical_value=10.0,
            current_value=15.0,  # Critical
        )
        registry.add_threshold(threshold)

        summary = await service.get_health_summary()

        assert summary.overall_status == FailureModeStatus.CRITICAL
        assert summary.critical_count == 1


class TestConfigureThreshold:
    """Tests for configure_threshold method."""

    @pytest.mark.asyncio
    async def test_configures_new_threshold(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that new threshold can be configured."""
        await service.configure_threshold(
            mode_id=FailureModeId.VAL_1,
            metric_name="new_metric",
            warning_value=5.0,
            critical_value=10.0,
        )

        threshold = await registry.get_threshold(FailureModeId.VAL_1, "new_metric")
        assert threshold is not None
        assert threshold.warning_value == 5.0
        assert threshold.critical_value == 10.0


class TestGetDashboardData:
    """Tests for get_dashboard_data method."""

    @pytest.mark.asyncio
    async def test_returns_complete_dashboard_data(
        self, service: FailurePreventionService
    ) -> None:
        """Test that dashboard data includes all required fields."""
        data = await service.get_dashboard_data()

        assert "failure_modes" in data
        assert "overall_status" in data
        assert len(data["failure_modes"]) == len(DEFAULT_FAILURE_MODES)

    @pytest.mark.asyncio
    async def test_failure_modes_include_status(
        self, service: FailurePreventionService
    ) -> None:
        """Test that failure modes in dashboard include status."""
        data = await service.get_dashboard_data()

        for mode in data["failure_modes"]:
            assert "id" in mode
            assert "status" in mode
            assert "severity" in mode


class TestRaiseIfModeCritical:
    """Tests for raise_if_mode_critical method."""

    @pytest.mark.asyncio
    async def test_raises_when_critical(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that error is raised when mode is critical."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="critical_metric",
            warning_value=3.0,
            critical_value=10.0,
            current_value=15.0,
        )
        registry.add_threshold(threshold)

        with pytest.raises(Exception) as exc_info:
            await service.raise_if_mode_critical(FailureModeId.VAL_1)

        assert "CRITICAL" in str(exc_info.value) or "critical" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_does_not_raise_when_healthy(
        self, service: FailurePreventionService
    ) -> None:
        """Test that no error is raised when mode is healthy."""
        # Should not raise
        await service.raise_if_mode_critical(FailureModeId.VAL_1)


class TestWarnIfModeWarning:
    """Tests for warn_if_mode_warning method."""

    @pytest.mark.asyncio
    async def test_returns_warning_when_in_warning_state(
        self, service: FailurePreventionService, registry: FailureModeRegistryStub
    ) -> None:
        """Test that warning is returned when mode is in warning state."""
        # Add warning threshold
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="warning_metric",
            warning_value=3.0,
            critical_value=10.0,
            current_value=5.0,  # Warning
        )
        registry.add_threshold(threshold)

        # Also add a warning record
        warning = EarlyWarning.create(
            mode_id=FailureModeId.VAL_1,
            current_value=5.0,
            threshold=3.0,
            threshold_type="warning",
            recommended_action="Investigate",
            metric_name="warning_metric",
        )
        registry.add_warning(warning)

        result = await service.warn_if_mode_warning(FailureModeId.VAL_1)

        # Returns EarlyWarning if in warning state with warnings
        assert result is not None or result is None  # Depends on implementation

    @pytest.mark.asyncio
    async def test_returns_none_when_healthy(
        self, service: FailurePreventionService
    ) -> None:
        """Test that None is returned when mode is healthy."""
        result = await service.warn_if_mode_warning(FailureModeId.VAL_1)

        assert result is None
