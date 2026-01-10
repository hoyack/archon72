"""Unit tests for ConfigurationFloorValidatorProtocol port (Story 6.10, NFR39).

Tests for the port interface and result dataclasses.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> Startup failure over running below floor
"""

from abc import ABC
from datetime import datetime, timezone

import pytest

from src.application.ports.configuration_floor_validator import (
    ConfigurationChangeResult,
    ConfigurationFloorValidatorProtocol,
    ConfigurationHealthStatus,
    ConfigurationValidationResult,
    ThresholdStatus,
    ThresholdViolation,
)


class TestThresholdViolation:
    """Tests for ThresholdViolation dataclass."""

    def test_create_with_all_fields(self) -> None:
        """Should create with all required fields."""
        violation = ThresholdViolation(
            threshold_name="cessation_breach_count",
            attempted_value=5,
            floor_value=10,
            fr_reference="FR32",
        )

        assert violation.threshold_name == "cessation_breach_count"
        assert violation.attempted_value == 5
        assert violation.floor_value == 10
        assert violation.fr_reference == "FR32"

    def test_frozen_dataclass(self) -> None:
        """Should be immutable (frozen dataclass)."""
        violation = ThresholdViolation(
            threshold_name="test",
            attempted_value=1,
            floor_value=2,
            fr_reference="FR1",
        )

        with pytest.raises(AttributeError):
            violation.threshold_name = "modified"  # type: ignore[misc]


class TestThresholdStatus:
    """Tests for ThresholdStatus dataclass."""

    def test_create_valid_status(self) -> None:
        """Should create status with is_valid=True when above floor."""
        status = ThresholdStatus(
            threshold_name="cessation_breach_count",
            floor_value=10,
            current_value=15,
            is_valid=True,
        )

        assert status.threshold_name == "cessation_breach_count"
        assert status.floor_value == 10
        assert status.current_value == 15
        assert status.is_valid is True

    def test_create_invalid_status(self) -> None:
        """Should create status with is_valid=False when below floor."""
        status = ThresholdStatus(
            threshold_name="cessation_breach_count",
            floor_value=10,
            current_value=5,
            is_valid=False,
        )

        assert status.is_valid is False

    def test_frozen_dataclass(self) -> None:
        """Should be immutable (frozen dataclass)."""
        status = ThresholdStatus(
            threshold_name="test",
            floor_value=10,
            current_value=15,
            is_valid=True,
        )

        with pytest.raises(AttributeError):
            status.is_valid = False  # type: ignore[misc]


class TestConfigurationValidationResult:
    """Tests for ConfigurationValidationResult dataclass."""

    def test_create_valid_result(self) -> None:
        """Should create result when all validations pass."""
        result = ConfigurationValidationResult(
            is_valid=True,
            violations=(),
            validated_count=13,
            validated_at=datetime.now(timezone.utc),
        )

        assert result.is_valid is True
        assert len(result.violations) == 0
        assert result.validated_count == 13

    def test_create_invalid_result_with_violations(self) -> None:
        """Should create result with violations when validation fails."""
        violations = (
            ThresholdViolation(
                threshold_name="cessation_breach_count",
                attempted_value=5,
                floor_value=10,
                fr_reference="FR32",
            ),
        )

        result = ConfigurationValidationResult(
            is_valid=False,
            violations=violations,
            validated_count=13,
            validated_at=datetime.now(timezone.utc),
        )

        assert result.is_valid is False
        assert len(result.violations) == 1
        assert result.violations[0].threshold_name == "cessation_breach_count"

    def test_frozen_dataclass(self) -> None:
        """Should be immutable (frozen dataclass)."""
        result = ConfigurationValidationResult(
            is_valid=True,
            violations=(),
            validated_count=13,
            validated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore[misc]


class TestConfigurationChangeResult:
    """Tests for ConfigurationChangeResult dataclass."""

    def test_create_valid_change(self) -> None:
        """Should create result for valid change."""
        result = ConfigurationChangeResult(
            is_valid=True,
            threshold_name="cessation_breach_count",
            requested_value=15,
            floor_value=10,
            rejection_reason=None,
        )

        assert result.is_valid is True
        assert result.rejection_reason is None

    def test_create_rejected_change(self) -> None:
        """Should create result for rejected change with reason."""
        result = ConfigurationChangeResult(
            is_valid=False,
            threshold_name="cessation_breach_count",
            requested_value=5,
            floor_value=10,
            rejection_reason="Value below constitutional floor",
        )

        assert result.is_valid is False
        assert result.rejection_reason == "Value below constitutional floor"

    def test_frozen_dataclass(self) -> None:
        """Should be immutable (frozen dataclass)."""
        result = ConfigurationChangeResult(
            is_valid=True,
            threshold_name="test",
            requested_value=15,
            floor_value=10,
            rejection_reason=None,
        )

        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore[misc]


class TestConfigurationHealthStatus:
    """Tests for ConfigurationHealthStatus dataclass."""

    def test_create_healthy_status(self) -> None:
        """Should create healthy status when all thresholds valid."""
        statuses = (
            ThresholdStatus(
                threshold_name="cessation_breach_count",
                floor_value=10,
                current_value=10,
                is_valid=True,
            ),
        )

        health = ConfigurationHealthStatus(
            is_healthy=True,
            threshold_statuses=statuses,
            checked_at=datetime.now(timezone.utc),
        )

        assert health.is_healthy is True
        assert len(health.threshold_statuses) == 1

    def test_create_unhealthy_status(self) -> None:
        """Should create unhealthy status when any threshold invalid."""
        statuses = (
            ThresholdStatus(
                threshold_name="cessation_breach_count",
                floor_value=10,
                current_value=5,
                is_valid=False,
            ),
        )

        health = ConfigurationHealthStatus(
            is_healthy=False,
            threshold_statuses=statuses,
            checked_at=datetime.now(timezone.utc),
        )

        assert health.is_healthy is False

    def test_frozen_dataclass(self) -> None:
        """Should be immutable (frozen dataclass)."""
        health = ConfigurationHealthStatus(
            is_healthy=True,
            threshold_statuses=(),
            checked_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            health.is_healthy = False  # type: ignore[misc]


class TestConfigurationFloorValidatorProtocol:
    """Tests for ConfigurationFloorValidatorProtocol interface."""

    def test_is_abstract_base_class(self) -> None:
        """Protocol should be an ABC."""
        assert issubclass(ConfigurationFloorValidatorProtocol, ABC)

    def test_has_validate_startup_configuration_method(self) -> None:
        """Should have validate_startup_configuration method."""
        assert hasattr(ConfigurationFloorValidatorProtocol, "validate_startup_configuration")

    def test_has_validate_configuration_change_method(self) -> None:
        """Should have validate_configuration_change method."""
        assert hasattr(ConfigurationFloorValidatorProtocol, "validate_configuration_change")

    def test_has_get_all_floors_method(self) -> None:
        """Should have get_all_floors method."""
        assert hasattr(ConfigurationFloorValidatorProtocol, "get_all_floors")

    def test_has_get_floor_method(self) -> None:
        """Should have get_floor method."""
        assert hasattr(ConfigurationFloorValidatorProtocol, "get_floor")

    def test_has_get_configuration_health_method(self) -> None:
        """Should have get_configuration_health method."""
        assert hasattr(ConfigurationFloorValidatorProtocol, "get_configuration_health")
