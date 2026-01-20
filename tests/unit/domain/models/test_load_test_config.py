"""Unit tests for LoadTestConfig domain model (Story 2B.7, NFR-10.5).

Tests:
- Default config creation
- Custom config creation
- Validation of all parameters
- Combined injection rate validation
- Serialization to dict
- Deserialization from dict
"""

from __future__ import annotations

import pytest

from src.domain.models.load_test_config import LoadTestConfig


class TestLoadTestConfigCreation:
    """Test LoadTestConfig creation and defaults."""

    def test_default_config_creation(self) -> None:
        """Default config has expected values."""
        config = LoadTestConfig()

        assert config.concurrent_sessions == 100
        assert config.total_petitions == 1000
        assert config.petition_batch_size == 100
        assert config.archon_response_latency_ms == 100
        assert config.failure_injection_rate == 0.0
        assert config.timeout_injection_rate == 0.0
        assert config.report_interval_seconds == 5

    def test_custom_config_creation(self) -> None:
        """Custom config retains provided values."""
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=500,
            petition_batch_size=50,
            archon_response_latency_ms=200,
            failure_injection_rate=0.1,
            timeout_injection_rate=0.05,
            report_interval_seconds=10,
        )

        assert config.concurrent_sessions == 50
        assert config.total_petitions == 500
        assert config.petition_batch_size == 50
        assert config.archon_response_latency_ms == 200
        assert config.failure_injection_rate == 0.1
        assert config.timeout_injection_rate == 0.05
        assert config.report_interval_seconds == 10

    def test_config_is_frozen(self) -> None:
        """Config is immutable after creation."""
        config = LoadTestConfig()

        with pytest.raises(AttributeError):
            config.concurrent_sessions = 200  # type: ignore[misc]


class TestLoadTestConfigValidation:
    """Test LoadTestConfig validation rules."""

    def test_concurrent_sessions_must_be_positive(self) -> None:
        """Concurrent sessions must be >= 1."""
        with pytest.raises(ValueError, match="concurrent_sessions must be >= 1"):
            LoadTestConfig(concurrent_sessions=0)

        with pytest.raises(ValueError, match="concurrent_sessions must be >= 1"):
            LoadTestConfig(concurrent_sessions=-1)

    def test_concurrent_sessions_max_limit(self) -> None:
        """Concurrent sessions must be <= 500."""
        with pytest.raises(ValueError, match="concurrent_sessions must be <= 500"):
            LoadTestConfig(concurrent_sessions=501)

        # 500 should work
        config = LoadTestConfig(concurrent_sessions=500)
        assert config.concurrent_sessions == 500

    def test_total_petitions_must_be_positive(self) -> None:
        """Total petitions must be >= 1."""
        with pytest.raises(ValueError, match="total_petitions must be >= 1"):
            LoadTestConfig(total_petitions=0)

    def test_petition_batch_size_must_be_positive(self) -> None:
        """Petition batch size must be >= 1."""
        with pytest.raises(ValueError, match="petition_batch_size must be >= 1"):
            LoadTestConfig(petition_batch_size=0)

    def test_archon_response_latency_must_be_non_negative(self) -> None:
        """Archon response latency must be >= 0."""
        with pytest.raises(ValueError, match="archon_response_latency_ms must be >= 0"):
            LoadTestConfig(archon_response_latency_ms=-1)

        # 0 should work
        config = LoadTestConfig(archon_response_latency_ms=0)
        assert config.archon_response_latency_ms == 0

    def test_failure_injection_rate_must_be_in_range(self) -> None:
        """Failure injection rate must be 0.0-1.0."""
        with pytest.raises(ValueError, match="failure_injection_rate must be 0.0-1.0"):
            LoadTestConfig(failure_injection_rate=-0.1)

        with pytest.raises(ValueError, match="failure_injection_rate must be 0.0-1.0"):
            LoadTestConfig(failure_injection_rate=1.1)

        # Boundaries should work
        config_zero = LoadTestConfig(failure_injection_rate=0.0)
        assert config_zero.failure_injection_rate == 0.0

        config_one = LoadTestConfig(failure_injection_rate=1.0)
        assert config_one.failure_injection_rate == 1.0

    def test_timeout_injection_rate_must_be_in_range(self) -> None:
        """Timeout injection rate must be 0.0-1.0."""
        with pytest.raises(ValueError, match="timeout_injection_rate must be 0.0-1.0"):
            LoadTestConfig(timeout_injection_rate=-0.1)

        with pytest.raises(ValueError, match="timeout_injection_rate must be 0.0-1.0"):
            LoadTestConfig(timeout_injection_rate=1.1)

    def test_combined_injection_rate_must_not_exceed_one(self) -> None:
        """Combined failure + timeout rate must be <= 1.0."""
        with pytest.raises(ValueError, match="Combined injection rates must be <= 1.0"):
            LoadTestConfig(failure_injection_rate=0.6, timeout_injection_rate=0.5)

        # 1.0 exactly should work
        config = LoadTestConfig(failure_injection_rate=0.5, timeout_injection_rate=0.5)
        assert config.failure_injection_rate + config.timeout_injection_rate == 1.0

    def test_report_interval_must_be_positive(self) -> None:
        """Report interval must be >= 1."""
        with pytest.raises(ValueError, match="report_interval_seconds must be >= 1"):
            LoadTestConfig(report_interval_seconds=0)


class TestLoadTestConfigSerialization:
    """Test LoadTestConfig serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all configuration fields."""
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=500,
            failure_injection_rate=0.1,
        )

        result = config.to_dict()

        assert result["concurrent_sessions"] == 50
        assert result["total_petitions"] == 500
        assert result["petition_batch_size"] == 100
        assert result["archon_response_latency_ms"] == 100
        assert result["failure_injection_rate"] == 0.1
        assert result["timeout_injection_rate"] == 0.0
        assert result["report_interval_seconds"] == 5
        assert result["schema_version"] == 1

    def test_from_dict_restores_config(self) -> None:
        """from_dict creates equivalent config."""
        original = LoadTestConfig(
            concurrent_sessions=75,
            total_petitions=750,
            failure_injection_rate=0.05,
        )

        data = original.to_dict()
        restored = LoadTestConfig.from_dict(data)

        assert restored == original

    def test_from_dict_uses_defaults_for_missing_keys(self) -> None:
        """from_dict uses defaults when keys are missing."""
        data = {"concurrent_sessions": 50}
        config = LoadTestConfig.from_dict(data)

        assert config.concurrent_sessions == 50
        assert config.total_petitions == 1000  # Default
        assert config.failure_injection_rate == 0.0  # Default


class TestLoadTestConfigEquality:
    """Test LoadTestConfig equality."""

    def test_equal_configs_are_equal(self) -> None:
        """Configs with same values are equal."""
        config1 = LoadTestConfig(concurrent_sessions=50, total_petitions=500)
        config2 = LoadTestConfig(concurrent_sessions=50, total_petitions=500)

        assert config1 == config2

    def test_different_configs_are_not_equal(self) -> None:
        """Configs with different values are not equal."""
        config1 = LoadTestConfig(concurrent_sessions=50)
        config2 = LoadTestConfig(concurrent_sessions=100)

        assert config1 != config2
