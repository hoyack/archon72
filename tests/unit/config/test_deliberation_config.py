"""Unit tests for DeliberationConfig (Story 2B.2, AC-5).

Tests timeout configuration with validation for bounds enforcement.
"""

from __future__ import annotations

import os
from datetime import timedelta
from unittest.mock import patch

import pytest

from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DEFAULT_DELIBERATION_TIMEOUT_SECONDS,
    EXTENDED_DELIBERATION_CONFIG,
    MAX_DELIBERATION_TIMEOUT_SECONDS,
    MIN_DELIBERATION_TIMEOUT_SECONDS,
    TEST_DELIBERATION_CONFIG,
    DeliberationConfig,
)


class TestDeliberationConfig:
    """Tests for DeliberationConfig dataclass."""

    def test_default_timeout_is_5_minutes(self) -> None:
        """Default timeout should be 300 seconds (5 minutes) per FR-11.9."""
        config = DeliberationConfig()
        assert config.timeout_seconds == 300
        assert config.timeout_seconds == DEFAULT_DELIBERATION_TIMEOUT_SECONDS

    def test_valid_timeout_at_minimum(self) -> None:
        """Timeout at minimum boundary (60 seconds) should be valid."""
        config = DeliberationConfig(timeout_seconds=MIN_DELIBERATION_TIMEOUT_SECONDS)
        assert config.timeout_seconds == 60

    def test_valid_timeout_at_maximum(self) -> None:
        """Timeout at maximum boundary (900 seconds) should be valid."""
        config = DeliberationConfig(timeout_seconds=MAX_DELIBERATION_TIMEOUT_SECONDS)
        assert config.timeout_seconds == 900

    def test_valid_timeout_within_range(self) -> None:
        """Timeout within valid range should be accepted."""
        config = DeliberationConfig(timeout_seconds=180)
        assert config.timeout_seconds == 180

    def test_invalid_timeout_below_minimum_raises(self) -> None:
        """Timeout below minimum (30 seconds) should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DeliberationConfig(timeout_seconds=30)

        assert "timeout_seconds must be between" in str(exc_info.value)
        assert "60" in str(exc_info.value)
        assert "900" in str(exc_info.value)

    def test_invalid_timeout_above_maximum_raises(self) -> None:
        """Timeout above maximum (1000 seconds) should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DeliberationConfig(timeout_seconds=1000)

        assert "timeout_seconds must be between" in str(exc_info.value)

    def test_invalid_timeout_zero_raises(self) -> None:
        """Timeout of zero should raise ValueError."""
        with pytest.raises(ValueError):
            DeliberationConfig(timeout_seconds=0)

    def test_invalid_timeout_negative_raises(self) -> None:
        """Negative timeout should raise ValueError."""
        with pytest.raises(ValueError):
            DeliberationConfig(timeout_seconds=-60)

    def test_timeout_timedelta_property(self) -> None:
        """timeout_timedelta should return correct timedelta."""
        config = DeliberationConfig(timeout_seconds=300)
        assert config.timeout_timedelta == timedelta(seconds=300)
        assert config.timeout_timedelta == timedelta(minutes=5)

    def test_config_is_frozen(self) -> None:
        """Config should be immutable (frozen dataclass)."""
        config = DeliberationConfig()
        with pytest.raises(AttributeError):
            config.timeout_seconds = 600  # type: ignore[misc]


class TestDeliberationConfigFromEnvironment:
    """Tests for from_environment factory method."""

    def test_from_environment_with_valid_env_var(self) -> None:
        """Should use environment variable when set."""
        with patch.dict(os.environ, {"DELIBERATION_TIMEOUT_SECONDS": "180"}):
            config = DeliberationConfig.from_environment()
            assert config.timeout_seconds == 180

    def test_from_environment_without_env_var(self) -> None:
        """Should use default when environment variable not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure the env var is not set
            if "DELIBERATION_TIMEOUT_SECONDS" in os.environ:
                del os.environ["DELIBERATION_TIMEOUT_SECONDS"]
            config = DeliberationConfig.from_environment()
            assert config.timeout_seconds == DEFAULT_DELIBERATION_TIMEOUT_SECONDS

    def test_from_environment_clamps_below_minimum(self) -> None:
        """Should clamp value below minimum to minimum."""
        with patch.dict(os.environ, {"DELIBERATION_TIMEOUT_SECONDS": "30"}):
            config = DeliberationConfig.from_environment()
            assert config.timeout_seconds == MIN_DELIBERATION_TIMEOUT_SECONDS

    def test_from_environment_clamps_above_maximum(self) -> None:
        """Should clamp value above maximum to maximum."""
        with patch.dict(os.environ, {"DELIBERATION_TIMEOUT_SECONDS": "2000"}):
            config = DeliberationConfig.from_environment()
            assert config.timeout_seconds == MAX_DELIBERATION_TIMEOUT_SECONDS

    def test_from_environment_handles_invalid_value(self) -> None:
        """Should use default for non-integer value."""
        with patch.dict(os.environ, {"DELIBERATION_TIMEOUT_SECONDS": "invalid"}):
            config = DeliberationConfig.from_environment()
            assert config.timeout_seconds == DEFAULT_DELIBERATION_TIMEOUT_SECONDS


class TestPredefinedConfigs:
    """Tests for pre-defined configuration instances."""

    def test_default_config_has_5_minute_timeout(self) -> None:
        """DEFAULT_DELIBERATION_CONFIG should have 5-minute timeout."""
        assert DEFAULT_DELIBERATION_CONFIG.timeout_seconds == 300

    def test_test_config_has_minimum_timeout(self) -> None:
        """TEST_DELIBERATION_CONFIG should have minimum timeout."""
        assert (
            TEST_DELIBERATION_CONFIG.timeout_seconds == MIN_DELIBERATION_TIMEOUT_SECONDS
        )

    def test_extended_config_has_maximum_timeout(self) -> None:
        """EXTENDED_DELIBERATION_CONFIG should have maximum timeout."""
        assert (
            EXTENDED_DELIBERATION_CONFIG.timeout_seconds
            == MAX_DELIBERATION_TIMEOUT_SECONDS
        )
