"""Unit tests for failure mode domain models (Story 8.8, FR106-FR107).

Tests for FailureMode, FailureModeThreshold, and EarlyWarning models.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.failure_mode import (
    DEFAULT_FAILURE_MODES,
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeSeverity,
    FailureModeStatus,
    FailureModeThreshold,
)


class TestFailureModeId:
    """Tests for FailureModeId enum."""

    def test_val_modes_defined(self) -> None:
        """Test that VAL-* modes are defined."""
        assert FailureModeId.VAL_1 == "VAL-1"
        assert FailureModeId.VAL_2 == "VAL-2"
        assert FailureModeId.VAL_3 == "VAL-3"
        assert FailureModeId.VAL_4 == "VAL-4"
        assert FailureModeId.VAL_5 == "VAL-5"

    def test_pv_modes_defined(self) -> None:
        """Test that PV-* modes are defined."""
        assert FailureModeId.PV_001 == "PV-001"
        assert FailureModeId.PV_002 == "PV-002"
        assert FailureModeId.PV_003 == "PV-003"


class TestFailureModeStatus:
    """Tests for FailureModeStatus enum."""

    def test_status_values(self) -> None:
        """Test that status values are defined."""
        assert FailureModeStatus.HEALTHY == "healthy"
        assert FailureModeStatus.WARNING == "warning"
        assert FailureModeStatus.CRITICAL == "critical"


class TestFailureModeSeverity:
    """Tests for FailureModeSeverity enum."""

    def test_severity_values(self) -> None:
        """Test that severity values are defined."""
        assert FailureModeSeverity.CRITICAL == "critical"
        assert FailureModeSeverity.HIGH == "high"
        assert FailureModeSeverity.MEDIUM == "medium"
        assert FailureModeSeverity.LOW == "low"


class TestFailureModeThreshold:
    """Tests for FailureModeThreshold dataclass."""

    def test_create_threshold(self) -> None:
        """Test creating a threshold with factory method."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test_metric",
            warning_value=5.0,
            critical_value=10.0,
        )

        assert threshold.mode_id == FailureModeId.VAL_1
        assert threshold.metric_name == "test_metric"
        assert threshold.warning_value == 5.0
        assert threshold.critical_value == 10.0
        assert threshold.current_value == 0.0

    def test_status_healthy_below_warning(self) -> None:
        """Test that status is HEALTHY when below warning threshold."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=5.0,
            critical_value=10.0,
            current_value=3.0,
        )

        assert threshold.status == FailureModeStatus.HEALTHY

    def test_status_warning_at_warning_threshold(self) -> None:
        """Test that status is WARNING at warning threshold."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=5.0,
            critical_value=10.0,
            current_value=5.0,
        )

        assert threshold.status == FailureModeStatus.WARNING

    def test_status_warning_between_thresholds(self) -> None:
        """Test that status is WARNING between thresholds."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=5.0,
            critical_value=10.0,
            current_value=7.5,
        )

        assert threshold.status == FailureModeStatus.WARNING

    def test_status_critical_at_critical_threshold(self) -> None:
        """Test that status is CRITICAL at critical threshold."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=5.0,
            critical_value=10.0,
            current_value=10.0,
        )

        assert threshold.status == FailureModeStatus.CRITICAL

    def test_status_critical_above_critical_threshold(self) -> None:
        """Test that status is CRITICAL above critical threshold."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=5.0,
            critical_value=10.0,
            current_value=15.0,
        )

        assert threshold.status == FailureModeStatus.CRITICAL

    def test_less_comparison_mode(self) -> None:
        """Test 'less' comparison mode for thresholds."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="uptime",
            warning_value=95.0,
            critical_value=90.0,  # Lower is worse
            current_value=92.0,
            comparison="less",
        )

        assert threshold.status == FailureModeStatus.WARNING

    def test_is_critical_property(self) -> None:
        """Test is_critical property."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=5.0,
            critical_value=10.0,
            current_value=15.0,
        )

        assert threshold.is_critical is True

    def test_is_warning_property(self) -> None:
        """Test is_warning property."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test",
            warning_value=5.0,
            critical_value=10.0,
            current_value=7.0,
        )

        assert threshold.is_warning is True

    def test_invalid_comparison_value(self) -> None:
        """Test that invalid comparison value raises error."""
        with pytest.raises(ValueError) as exc_info:
            FailureModeThreshold.create(
                mode_id=FailureModeId.VAL_1,
                metric_name="test",
                warning_value=5.0,
                critical_value=10.0,
                comparison="invalid",
            )

        assert "comparison must be" in str(exc_info.value)

    def test_invalid_threshold_order_greater(self) -> None:
        """Test that warning > critical is invalid for 'greater' comparison."""
        with pytest.raises(ValueError) as exc_info:
            FailureModeThreshold.create(
                mode_id=FailureModeId.VAL_1,
                metric_name="test",
                warning_value=10.0,  # Warning > Critical is invalid
                critical_value=5.0,
                comparison="greater",
            )

        assert "warning_value" in str(exc_info.value)

    def test_to_summary(self) -> None:
        """Test that to_summary returns readable string."""
        threshold = FailureModeThreshold.create(
            mode_id=FailureModeId.VAL_1,
            metric_name="test_metric",
            warning_value=5.0,
            critical_value=10.0,
            current_value=3.0,
        )

        summary = threshold.to_summary()

        assert "test_metric" in summary
        assert "3.0" in summary


class TestFailureMode:
    """Tests for FailureMode dataclass."""

    def test_create_failure_mode(self) -> None:
        """Test creating a failure mode."""
        mode = FailureMode(
            id=FailureModeId.VAL_1,
            description="Test failure mode",
            severity=FailureModeSeverity.HIGH,
            mitigation="Test mitigation",
        )

        assert mode.id == FailureModeId.VAL_1
        assert mode.description == "Test failure mode"
        assert mode.severity == FailureModeSeverity.HIGH
        assert mode.mitigation == "Test mitigation"

    def test_empty_description_raises(self) -> None:
        """Test that empty description raises error."""
        with pytest.raises(ValueError) as exc_info:
            FailureMode(
                id=FailureModeId.VAL_1,
                description="",
                severity=FailureModeSeverity.HIGH,
                mitigation="Test mitigation",
            )

        assert "description cannot be empty" in str(exc_info.value)

    def test_empty_mitigation_raises(self) -> None:
        """Test that empty mitigation raises error."""
        with pytest.raises(ValueError) as exc_info:
            FailureMode(
                id=FailureModeId.VAL_1,
                description="Test",
                severity=FailureModeSeverity.HIGH,
                mitigation="",
            )

        assert "mitigation cannot be empty" in str(exc_info.value)

    def test_optional_adr_reference(self) -> None:
        """Test that ADR reference is optional."""
        mode = FailureMode(
            id=FailureModeId.VAL_1,
            description="Test",
            severity=FailureModeSeverity.HIGH,
            mitigation="Mitigation",
            adr_reference="ADR-1",
        )

        assert mode.adr_reference == "ADR-1"

    def test_to_summary(self) -> None:
        """Test that to_summary returns readable string."""
        mode = FailureMode(
            id=FailureModeId.VAL_1,
            description="Test failure",
            severity=FailureModeSeverity.CRITICAL,
            mitigation="Fix it",
        )

        summary = mode.to_summary()

        assert "VAL-1" in summary
        assert "Test failure" in summary
        assert "critical" in summary


class TestEarlyWarning:
    """Tests for EarlyWarning dataclass."""

    def test_create_early_warning(self) -> None:
        """Test creating an early warning."""
        warning = EarlyWarning.create(
            mode_id=FailureModeId.VAL_1,
            current_value=7.5,
            threshold=5.0,
            threshold_type="warning",
            recommended_action="Investigate immediately",
            metric_name="test_metric",
        )

        assert warning.mode_id == FailureModeId.VAL_1
        assert warning.current_value == 7.5
        assert warning.threshold == 5.0
        assert warning.threshold_type == "warning"
        assert warning.recommended_action == "Investigate immediately"
        assert warning.metric_name == "test_metric"

    def test_invalid_threshold_type_raises(self) -> None:
        """Test that invalid threshold type raises error."""
        with pytest.raises(ValueError) as exc_info:
            EarlyWarning.create(
                mode_id=FailureModeId.VAL_1,
                current_value=7.5,
                threshold=5.0,
                threshold_type="invalid",  # Invalid
                recommended_action="Test",
                metric_name="test",
            )

        assert "threshold_type must be" in str(exc_info.value)

    def test_empty_recommended_action_raises(self) -> None:
        """Test that empty recommended action raises error."""
        with pytest.raises(ValueError) as exc_info:
            EarlyWarning.create(
                mode_id=FailureModeId.VAL_1,
                current_value=7.5,
                threshold=5.0,
                threshold_type="warning",
                recommended_action="",  # Empty
                metric_name="test",
            )

        assert "recommended_action cannot be empty" in str(exc_info.value)

    def test_to_summary(self) -> None:
        """Test that to_summary returns readable string."""
        warning = EarlyWarning.create(
            mode_id=FailureModeId.VAL_1,
            current_value=7.5,
            threshold=5.0,
            threshold_type="warning",
            recommended_action="Investigate",
            metric_name="test_metric",
        )

        summary = warning.to_summary()

        assert "VAL-1" in summary
        assert "WARNING" in summary
        assert "7.5" in summary


class TestDefaultFailureModes:
    """Tests for DEFAULT_FAILURE_MODES dictionary."""

    def test_all_val_modes_defined(self) -> None:
        """Test that all VAL-* modes are defined."""
        assert FailureModeId.VAL_1 in DEFAULT_FAILURE_MODES
        assert FailureModeId.VAL_2 in DEFAULT_FAILURE_MODES
        assert FailureModeId.VAL_3 in DEFAULT_FAILURE_MODES
        assert FailureModeId.VAL_4 in DEFAULT_FAILURE_MODES
        assert FailureModeId.VAL_5 in DEFAULT_FAILURE_MODES

    def test_all_pv_modes_defined(self) -> None:
        """Test that all PV-* modes are defined."""
        assert FailureModeId.PV_001 in DEFAULT_FAILURE_MODES
        assert FailureModeId.PV_002 in DEFAULT_FAILURE_MODES
        assert FailureModeId.PV_003 in DEFAULT_FAILURE_MODES

    def test_val1_is_signature_corruption(self) -> None:
        """Test that VAL-1 is silent signature corruption."""
        mode = DEFAULT_FAILURE_MODES[FailureModeId.VAL_1]

        assert "signature" in mode.description.lower()
        assert mode.severity == FailureModeSeverity.CRITICAL

    def test_pv001_is_raw_string_event_type(self) -> None:
        """Test that PV-001 is raw string event type."""
        mode = DEFAULT_FAILURE_MODES[FailureModeId.PV_001]

        assert "string" in mode.description.lower() or "event" in mode.description.lower()
        assert mode.severity == FailureModeSeverity.HIGH

    def test_pv003_is_missing_halt_guard(self) -> None:
        """Test that PV-003 is missing HaltGuard."""
        mode = DEFAULT_FAILURE_MODES[FailureModeId.PV_003]

        assert "halt" in mode.description.lower() or "guard" in mode.description.lower()
        assert mode.severity == FailureModeSeverity.CRITICAL

    def test_all_modes_have_mitigation(self) -> None:
        """Test that all modes have mitigation defined."""
        for mode_id, mode in DEFAULT_FAILURE_MODES.items():
            assert mode.mitigation, f"Mode {mode_id} has no mitigation"
