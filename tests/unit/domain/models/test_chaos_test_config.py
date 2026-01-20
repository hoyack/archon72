"""Unit tests for ChaosTestConfig domain model (Story 2B.8, NFR-9.5).

Tests:
- Default config creation
- Custom config creation
- Validation of all parameters
- Scenario enumeration completeness
- Serialization to dict
- Deserialization from dict
"""

from __future__ import annotations

import pytest

from src.domain.models.chaos_test_config import (
    CHAOS_CONFIG_SCHEMA_VERSION,
    MAX_INJECTION_DURATION_SECONDS,
    MIN_INJECTION_DURATION_SECONDS,
    ChaosScenario,
    ChaosTestConfig,
)


class TestChaosScenarioEnumeration:
    """Test ChaosScenario enumeration."""

    def test_all_scenarios_exist(self) -> None:
        """All expected chaos scenarios are defined."""
        assert ChaosScenario.ARCHON_TIMEOUT_MID_PHASE
        assert ChaosScenario.SERVICE_RESTART
        assert ChaosScenario.DATABASE_CONNECTION_FAILURE
        assert ChaosScenario.CREWAI_API_DEGRADATION
        assert ChaosScenario.WITNESS_WRITE_FAILURE
        assert ChaosScenario.NETWORK_PARTITION

    def test_scenario_count(self) -> None:
        """Six chaos scenarios are defined per AC-2."""
        assert len(ChaosScenario) == 6

    def test_scenario_values_are_snake_case(self) -> None:
        """Scenario values follow snake_case convention."""
        for scenario in ChaosScenario:
            assert scenario.value == scenario.value.lower()
            assert "_" in scenario.value or scenario.value.isalpha()

    def test_scenarios_can_be_created_from_string(self) -> None:
        """Scenarios can be instantiated from their string values."""
        for scenario in ChaosScenario:
            restored = ChaosScenario(scenario.value)
            assert restored == scenario


class TestChaosTestConfigCreation:
    """Test ChaosTestConfig creation and defaults."""

    def test_default_config_creation(self) -> None:
        """Config with only scenario uses defaults."""
        config = ChaosTestConfig(scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE)

        assert config.scenario == ChaosScenario.ARCHON_TIMEOUT_MID_PHASE
        assert config.injection_duration_seconds == 30
        assert config.injection_probability == 1.0
        assert config.affected_components == ()
        assert config.recovery_timeout_seconds == 60
        assert config.enable_audit_logging is True
        assert config.latency_injection_ms == 500

    def test_custom_config_creation(self) -> None:
        """Custom config retains provided values."""
        config = ChaosTestConfig(
            scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE,
            injection_duration_seconds=45,
            injection_probability=0.8,
            affected_components=("postgres", "connection_pool"),
            recovery_timeout_seconds=90,
            enable_audit_logging=False,
            latency_injection_ms=1000,
        )

        assert config.scenario == ChaosScenario.DATABASE_CONNECTION_FAILURE
        assert config.injection_duration_seconds == 45
        assert config.injection_probability == 0.8
        assert config.affected_components == ("postgres", "connection_pool")
        assert config.recovery_timeout_seconds == 90
        assert config.enable_audit_logging is False
        assert config.latency_injection_ms == 1000

    def test_config_is_frozen(self) -> None:
        """Config is immutable after creation."""
        config = ChaosTestConfig(scenario=ChaosScenario.SERVICE_RESTART)

        with pytest.raises(AttributeError):
            config.injection_duration_seconds = 100  # type: ignore[misc]


class TestChaosTestConfigValidation:
    """Test ChaosTestConfig validation rules."""

    def test_injection_duration_minimum(self) -> None:
        """Injection duration must be >= 1."""
        with pytest.raises(ValueError, match="injection_duration_seconds must be >= 1"):
            ChaosTestConfig(
                scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
                injection_duration_seconds=0,
            )

    def test_injection_duration_maximum(self) -> None:
        """Injection duration must be <= 300."""
        with pytest.raises(
            ValueError, match="injection_duration_seconds must be <= 300"
        ):
            ChaosTestConfig(
                scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
                injection_duration_seconds=301,
            )

        # 300 should work
        config = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
            injection_duration_seconds=MAX_INJECTION_DURATION_SECONDS,
        )
        assert config.injection_duration_seconds == 300

    def test_injection_duration_boundary_values(self) -> None:
        """Boundary values for injection duration work correctly."""
        config_min = ChaosTestConfig(
            scenario=ChaosScenario.SERVICE_RESTART,
            injection_duration_seconds=MIN_INJECTION_DURATION_SECONDS,
        )
        assert config_min.injection_duration_seconds == 1

        config_max = ChaosTestConfig(
            scenario=ChaosScenario.SERVICE_RESTART,
            injection_duration_seconds=MAX_INJECTION_DURATION_SECONDS,
        )
        assert config_max.injection_duration_seconds == 300

    def test_injection_probability_must_be_in_range(self) -> None:
        """Injection probability must be 0.0-1.0."""
        with pytest.raises(ValueError, match="injection_probability must be 0.0-1.0"):
            ChaosTestConfig(
                scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
                injection_probability=-0.1,
            )

        with pytest.raises(ValueError, match="injection_probability must be 0.0-1.0"):
            ChaosTestConfig(
                scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
                injection_probability=1.1,
            )

        # Boundaries should work
        config_zero = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
            injection_probability=0.0,
        )
        assert config_zero.injection_probability == 0.0

        config_one = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
            injection_probability=1.0,
        )
        assert config_one.injection_probability == 1.0

    def test_recovery_timeout_must_be_positive(self) -> None:
        """Recovery timeout must be >= 1."""
        with pytest.raises(ValueError, match="recovery_timeout_seconds must be >= 1"):
            ChaosTestConfig(
                scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
                recovery_timeout_seconds=0,
            )

    def test_latency_injection_must_be_non_negative(self) -> None:
        """Latency injection must be >= 0."""
        with pytest.raises(ValueError, match="latency_injection_ms must be >= 0"):
            ChaosTestConfig(
                scenario=ChaosScenario.CREWAI_API_DEGRADATION,
                latency_injection_ms=-1,
            )

        # 0 should work
        config = ChaosTestConfig(
            scenario=ChaosScenario.CREWAI_API_DEGRADATION,
            latency_injection_ms=0,
        )
        assert config.latency_injection_ms == 0


class TestChaosTestConfigSerialization:
    """Test ChaosTestConfig serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all configuration fields."""
        config = ChaosTestConfig(
            scenario=ChaosScenario.WITNESS_WRITE_FAILURE,
            injection_duration_seconds=20,
            injection_probability=0.75,
            affected_components=("event_writer",),
        )

        result = config.to_dict()

        assert result["scenario"] == "witness_write_failure"
        assert result["injection_duration_seconds"] == 20
        assert result["injection_probability"] == 0.75
        assert result["affected_components"] == ["event_writer"]
        assert result["recovery_timeout_seconds"] == 60
        assert result["enable_audit_logging"] is True
        assert result["latency_injection_ms"] == 500
        assert result["schema_version"] == CHAOS_CONFIG_SCHEMA_VERSION

    def test_from_dict_restores_config(self) -> None:
        """from_dict creates equivalent config."""
        original = ChaosTestConfig(
            scenario=ChaosScenario.NETWORK_PARTITION,
            injection_duration_seconds=45,
            injection_probability=0.9,
        )

        data = original.to_dict()
        restored = ChaosTestConfig.from_dict(data)

        assert restored.scenario == original.scenario
        assert (
            restored.injection_duration_seconds == original.injection_duration_seconds
        )
        assert restored.injection_probability == original.injection_probability

    def test_from_dict_uses_defaults_for_missing_keys(self) -> None:
        """from_dict uses defaults when optional keys are missing."""
        data = {"scenario": "service_restart"}
        config = ChaosTestConfig.from_dict(data)

        assert config.scenario == ChaosScenario.SERVICE_RESTART
        assert config.injection_duration_seconds == 30  # Default
        assert config.injection_probability == 1.0  # Default


class TestChaosTestConfigEquality:
    """Test ChaosTestConfig equality."""

    def test_equal_configs_are_equal(self) -> None:
        """Configs with same values are equal."""
        config1 = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
            injection_duration_seconds=30,
        )
        config2 = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
            injection_duration_seconds=30,
        )

        assert config1 == config2

    def test_different_configs_are_not_equal(self) -> None:
        """Configs with different values are not equal."""
        config1 = ChaosTestConfig(
            scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
        )
        config2 = ChaosTestConfig(
            scenario=ChaosScenario.SERVICE_RESTART,
        )

        assert config1 != config2

    def test_configs_with_different_durations_are_not_equal(self) -> None:
        """Configs with different durations are not equal."""
        config1 = ChaosTestConfig(
            scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE,
            injection_duration_seconds=30,
        )
        config2 = ChaosTestConfig(
            scenario=ChaosScenario.DATABASE_CONNECTION_FAILURE,
            injection_duration_seconds=60,
        )

        assert config1 != config2
