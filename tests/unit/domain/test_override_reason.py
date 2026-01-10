"""Unit tests for OverrideReason enumeration (Story 5.2, FR28).

Tests verify that:
- All required override reasons exist (FR28)
- Description property returns human-readable text
- Serialization to string works correctly
"""

import pytest

from src.domain.models.override_reason import OverrideReason


class TestOverrideReasonEnum:
    """Tests for OverrideReason enum values."""

    def test_all_required_reasons_exist(self) -> None:
        """Test that all FR28-specified reasons are defined."""
        # FR28 requires these specific reasons
        assert hasattr(OverrideReason, "TECHNICAL_FAILURE")
        assert hasattr(OverrideReason, "CEREMONY_HEALTH")
        assert hasattr(OverrideReason, "EMERGENCY_HALT_CLEAR")
        assert hasattr(OverrideReason, "CONFIGURATION_ERROR")
        assert hasattr(OverrideReason, "WATCHDOG_INTERVENTION")
        assert hasattr(OverrideReason, "SECURITY_INCIDENT")

    def test_enum_value_is_string(self) -> None:
        """Test that enum values are strings (for serialization)."""
        assert OverrideReason.TECHNICAL_FAILURE.value == "TECHNICAL_FAILURE"
        assert OverrideReason.CEREMONY_HEALTH.value == "CEREMONY_HEALTH"
        assert OverrideReason.EMERGENCY_HALT_CLEAR.value == "EMERGENCY_HALT_CLEAR"
        assert OverrideReason.CONFIGURATION_ERROR.value == "CONFIGURATION_ERROR"
        assert OverrideReason.WATCHDOG_INTERVENTION.value == "WATCHDOG_INTERVENTION"
        assert OverrideReason.SECURITY_INCIDENT.value == "SECURITY_INCIDENT"

    def test_exactly_six_reasons_defined(self) -> None:
        """Test that exactly 6 reasons are defined (FR28 completeness)."""
        assert len(OverrideReason) == 6


class TestOverrideReasonDescription:
    """Tests for OverrideReason description property."""

    def test_technical_failure_description(self) -> None:
        """Test TECHNICAL_FAILURE has description."""
        assert OverrideReason.TECHNICAL_FAILURE.description
        assert isinstance(OverrideReason.TECHNICAL_FAILURE.description, str)
        assert "technical" in OverrideReason.TECHNICAL_FAILURE.description.lower()

    def test_ceremony_health_description(self) -> None:
        """Test CEREMONY_HEALTH has description."""
        assert OverrideReason.CEREMONY_HEALTH.description
        assert isinstance(OverrideReason.CEREMONY_HEALTH.description, str)
        assert "ceremony" in OverrideReason.CEREMONY_HEALTH.description.lower()

    def test_emergency_halt_clear_description(self) -> None:
        """Test EMERGENCY_HALT_CLEAR has description."""
        assert OverrideReason.EMERGENCY_HALT_CLEAR.description
        assert isinstance(OverrideReason.EMERGENCY_HALT_CLEAR.description, str)
        assert "halt" in OverrideReason.EMERGENCY_HALT_CLEAR.description.lower()

    def test_configuration_error_description(self) -> None:
        """Test CONFIGURATION_ERROR has description."""
        assert OverrideReason.CONFIGURATION_ERROR.description
        assert isinstance(OverrideReason.CONFIGURATION_ERROR.description, str)
        assert "configuration" in OverrideReason.CONFIGURATION_ERROR.description.lower()

    def test_watchdog_intervention_description(self) -> None:
        """Test WATCHDOG_INTERVENTION has description."""
        assert OverrideReason.WATCHDOG_INTERVENTION.description
        assert isinstance(OverrideReason.WATCHDOG_INTERVENTION.description, str)
        assert "watchdog" in OverrideReason.WATCHDOG_INTERVENTION.description.lower()

    def test_security_incident_description(self) -> None:
        """Test SECURITY_INCIDENT has description."""
        assert OverrideReason.SECURITY_INCIDENT.description
        assert isinstance(OverrideReason.SECURITY_INCIDENT.description, str)
        assert "security" in OverrideReason.SECURITY_INCIDENT.description.lower()

    def test_all_reasons_have_description(self) -> None:
        """Test that every reason has a non-empty description."""
        for reason in OverrideReason:
            assert reason.description, f"{reason.name} has no description"
            assert len(reason.description) > 10, f"{reason.name} description too short"


class TestOverrideReasonSerialization:
    """Tests for OverrideReason serialization."""

    def test_serialization_to_string(self) -> None:
        """Test reason can be serialized to string for JSON."""
        reason = OverrideReason.TECHNICAL_FAILURE
        serialized = reason.value
        assert serialized == "TECHNICAL_FAILURE"

    def test_deserialization_from_string(self) -> None:
        """Test reason can be created from string."""
        reason = OverrideReason("TECHNICAL_FAILURE")
        assert reason == OverrideReason.TECHNICAL_FAILURE

    def test_invalid_reason_raises_value_error(self) -> None:
        """Test that invalid reason string raises ValueError."""
        with pytest.raises(ValueError):
            OverrideReason("INVALID_REASON")

    def test_case_sensitive(self) -> None:
        """Test that reason lookup is case-sensitive."""
        with pytest.raises(ValueError):
            OverrideReason("technical_failure")
