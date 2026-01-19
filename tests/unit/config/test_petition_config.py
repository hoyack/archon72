"""Unit tests for PetitionQueueConfig and PetitionRateLimitConfig (Story 1.3, 1.4).

Tests for petition configuration including:
- Default value validation
- Environment variable loading
- Input validation

Constitutional Constraints Tested:
- FR-1.4: Configurable queue threshold
- FR-1.5: Configurable rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- AC2: Environment variable configuration
- AC5: Rate limit environment variable configuration
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.config.petition_config import (
    DEFAULT_PETITION_QUEUE_CONFIG,
    DEFAULT_PETITION_RATE_LIMIT_CONFIG,
    HIGH_CAPACITY_PETITION_QUEUE_CONFIG,
    RELAXED_PETITION_RATE_LIMIT_CONFIG,
    TEST_PETITION_QUEUE_CONFIG,
    TEST_PETITION_RATE_LIMIT_CONFIG,
    PetitionQueueConfig,
    PetitionRateLimitConfig,
)


class TestPetitionQueueConfig:
    """Tests for PetitionQueueConfig dataclass."""

    class TestDefaults:
        """Tests for default configuration values."""

        def test_default_threshold(self) -> None:
            """Default threshold should be 10,000."""
            config = PetitionQueueConfig()
            assert config.threshold == 10_000

        def test_default_hysteresis(self) -> None:
            """Default hysteresis should be 500."""
            config = PetitionQueueConfig()
            assert config.hysteresis == 500

        def test_default_cache_ttl(self) -> None:
            """Default cache TTL should be 5.0 seconds."""
            config = PetitionQueueConfig()
            assert config.cache_ttl_seconds == 5.0

        def test_default_retry_after(self) -> None:
            """Default Retry-After should be 60 seconds."""
            config = PetitionQueueConfig()
            assert config.retry_after_seconds == 60

    class TestValidation:
        """Tests for configuration validation."""

        def test_threshold_must_be_positive(self) -> None:
            """Threshold must be >= 1."""
            with pytest.raises(ValueError, match="threshold must be positive"):
                PetitionQueueConfig(threshold=0)

            with pytest.raises(ValueError, match="threshold must be positive"):
                PetitionQueueConfig(threshold=-1)

        def test_hysteresis_must_be_non_negative(self) -> None:
            """Hysteresis must be >= 0."""
            with pytest.raises(ValueError, match="hysteresis must be non-negative"):
                PetitionQueueConfig(hysteresis=-1)

        def test_hysteresis_must_be_less_than_threshold(self) -> None:
            """Hysteresis must be < threshold."""
            with pytest.raises(ValueError, match="hysteresis.*must be less than"):
                PetitionQueueConfig(threshold=100, hysteresis=100)

            with pytest.raises(ValueError, match="hysteresis.*must be less than"):
                PetitionQueueConfig(threshold=100, hysteresis=150)

        def test_cache_ttl_must_be_positive(self) -> None:
            """Cache TTL must be > 0."""
            with pytest.raises(ValueError, match="cache_ttl_seconds must be positive"):
                PetitionQueueConfig(cache_ttl_seconds=0)

            with pytest.raises(ValueError, match="cache_ttl_seconds must be positive"):
                PetitionQueueConfig(cache_ttl_seconds=-1.0)

        def test_retry_after_must_be_at_least_one(self) -> None:
            """Retry-After must be >= 1."""
            with pytest.raises(ValueError, match="retry_after_seconds must be at least 1"):
                PetitionQueueConfig(retry_after_seconds=0)

        def test_valid_custom_config(self) -> None:
            """Valid custom configuration should work."""
            config = PetitionQueueConfig(
                threshold=5000,
                hysteresis=250,
                cache_ttl_seconds=2.5,
                retry_after_seconds=45,
            )
            assert config.threshold == 5000
            assert config.hysteresis == 250
            assert config.cache_ttl_seconds == 2.5
            assert config.retry_after_seconds == 45

        def test_zero_hysteresis_is_valid(self) -> None:
            """Zero hysteresis should be valid (immediate resume)."""
            config = PetitionQueueConfig(threshold=100, hysteresis=0)
            assert config.hysteresis == 0

    class TestFromEnvironment:
        """Tests for environment variable configuration (AC2)."""

        def test_uses_defaults_when_no_env_vars(self) -> None:
            """Should use defaults when environment variables not set."""
            with patch.dict(os.environ, {}, clear=True):
                # Clear any existing env vars
                for key in [
                    "PETITION_QUEUE_THRESHOLD",
                    "PETITION_QUEUE_HYSTERESIS",
                    "PETITION_QUEUE_CACHE_TTL",
                    "PETITION_QUEUE_RETRY_AFTER",
                ]:
                    os.environ.pop(key, None)

                config = PetitionQueueConfig.from_environment()

                assert config.threshold == 10_000
                assert config.hysteresis == 500
                assert config.cache_ttl_seconds == 5.0
                assert config.retry_after_seconds == 60

        def test_loads_threshold_from_env(self) -> None:
            """Should load threshold from PETITION_QUEUE_THRESHOLD."""
            with patch.dict(os.environ, {"PETITION_QUEUE_THRESHOLD": "50000"}):
                config = PetitionQueueConfig.from_environment()
                assert config.threshold == 50000

        def test_loads_hysteresis_from_env(self) -> None:
            """Should load hysteresis from PETITION_QUEUE_HYSTERESIS."""
            with patch.dict(os.environ, {"PETITION_QUEUE_HYSTERESIS": "1000"}):
                config = PetitionQueueConfig.from_environment()
                assert config.hysteresis == 1000

        def test_loads_cache_ttl_from_env(self) -> None:
            """Should load cache TTL from PETITION_QUEUE_CACHE_TTL."""
            with patch.dict(os.environ, {"PETITION_QUEUE_CACHE_TTL": "2.5"}):
                config = PetitionQueueConfig.from_environment()
                assert config.cache_ttl_seconds == 2.5

        def test_loads_retry_after_from_env(self) -> None:
            """Should load Retry-After from PETITION_QUEUE_RETRY_AFTER."""
            with patch.dict(os.environ, {"PETITION_QUEUE_RETRY_AFTER": "120"}):
                config = PetitionQueueConfig.from_environment()
                assert config.retry_after_seconds == 120

        def test_invalid_env_var_uses_default(self) -> None:
            """Invalid environment variable values should use defaults."""
            with patch.dict(os.environ, {"PETITION_QUEUE_THRESHOLD": "not_a_number"}):
                config = PetitionQueueConfig.from_environment()
                assert config.threshold == 10_000  # Default

        def test_loads_all_env_vars_together(self) -> None:
            """Should load all values from environment together."""
            env_vars = {
                "PETITION_QUEUE_THRESHOLD": "20000",
                "PETITION_QUEUE_HYSTERESIS": "1500",
                "PETITION_QUEUE_CACHE_TTL": "3.0",
                "PETITION_QUEUE_RETRY_AFTER": "90",
            }
            with patch.dict(os.environ, env_vars):
                config = PetitionQueueConfig.from_environment()

                assert config.threshold == 20000
                assert config.hysteresis == 1500
                assert config.cache_ttl_seconds == 3.0
                assert config.retry_after_seconds == 90


class TestPreDefinedConfigs:
    """Tests for pre-defined configuration instances."""

    def test_default_config_values(self) -> None:
        """DEFAULT_PETITION_QUEUE_CONFIG should have standard values."""
        config = DEFAULT_PETITION_QUEUE_CONFIG
        assert config.threshold == 10_000
        assert config.hysteresis == 500
        assert config.cache_ttl_seconds == 5.0
        assert config.retry_after_seconds == 60

    def test_test_config_has_low_threshold(self) -> None:
        """TEST_PETITION_QUEUE_CONFIG should have low thresholds for testing."""
        config = TEST_PETITION_QUEUE_CONFIG
        assert config.threshold == 100
        assert config.hysteresis == 10
        assert config.cache_ttl_seconds == 0.1
        assert config.retry_after_seconds == 5

    def test_high_capacity_config(self) -> None:
        """HIGH_CAPACITY_PETITION_QUEUE_CONFIG should have higher limits."""
        config = HIGH_CAPACITY_PETITION_QUEUE_CONFIG
        assert config.threshold == 50_000
        assert config.hysteresis == 2_500
        assert config.cache_ttl_seconds == 2.0
        assert config.retry_after_seconds == 30

    def test_configs_are_frozen(self) -> None:
        """Pre-defined configs should be immutable (frozen dataclass)."""
        with pytest.raises(Exception):  # FrozenInstanceError
            DEFAULT_PETITION_QUEUE_CONFIG.threshold = 99999  # type: ignore[misc]


class TestPetitionRateLimitConfig:
    """Tests for PetitionRateLimitConfig dataclass (Story 1.4, HC-4)."""

    class TestDefaults:
        """Tests for default configuration values."""

        def test_default_limit_per_hour(self) -> None:
            """Default limit should be 10 (HC-4)."""
            config = PetitionRateLimitConfig()
            assert config.limit_per_hour == 10

        def test_default_window_minutes(self) -> None:
            """Default window should be 60 minutes."""
            config = PetitionRateLimitConfig()
            assert config.window_minutes == 60

        def test_default_bucket_ttl_hours(self) -> None:
            """Default bucket TTL should be 2 hours."""
            config = PetitionRateLimitConfig()
            assert config.bucket_ttl_hours == 2

    class TestValidation:
        """Tests for configuration validation."""

        def test_limit_per_hour_must_be_positive(self) -> None:
            """Limit must be >= 1."""
            with pytest.raises(ValueError, match="limit_per_hour must be positive"):
                PetitionRateLimitConfig(limit_per_hour=0)

            with pytest.raises(ValueError, match="limit_per_hour must be positive"):
                PetitionRateLimitConfig(limit_per_hour=-1)

        def test_window_minutes_must_be_positive(self) -> None:
            """Window must be >= 1."""
            with pytest.raises(ValueError, match="window_minutes must be positive"):
                PetitionRateLimitConfig(window_minutes=0)

            with pytest.raises(ValueError, match="window_minutes must be positive"):
                PetitionRateLimitConfig(window_minutes=-1)

        def test_bucket_ttl_must_be_positive(self) -> None:
            """Bucket TTL must be >= 1."""
            with pytest.raises(ValueError, match="bucket_ttl_hours must be positive"):
                PetitionRateLimitConfig(bucket_ttl_hours=0)

        def test_bucket_ttl_must_be_greater_than_window(self) -> None:
            """Bucket TTL must be > window_minutes."""
            with pytest.raises(ValueError, match="bucket_ttl_hours.*must be greater than"):
                # 1 hour = 60 min, window = 60 min -> TTL not greater
                PetitionRateLimitConfig(window_minutes=60, bucket_ttl_hours=1)

        def test_valid_custom_config(self) -> None:
            """Valid custom configuration should work."""
            config = PetitionRateLimitConfig(
                limit_per_hour=50,
                window_minutes=30,
                bucket_ttl_hours=2,
            )
            assert config.limit_per_hour == 50
            assert config.window_minutes == 30
            assert config.bucket_ttl_hours == 2

    class TestFromEnvironment:
        """Tests for environment variable configuration (AC5)."""

        def test_uses_defaults_when_no_env_vars(self) -> None:
            """Should use defaults when environment variables not set."""
            with patch.dict(os.environ, {}, clear=True):
                # Clear any existing env vars
                for key in [
                    "PETITION_RATE_LIMIT_PER_HOUR",
                    "PETITION_RATE_LIMIT_WINDOW_MINUTES",
                    "PETITION_RATE_LIMIT_TTL_HOURS",
                ]:
                    os.environ.pop(key, None)

                config = PetitionRateLimitConfig.from_environment()

                assert config.limit_per_hour == 10
                assert config.window_minutes == 60
                assert config.bucket_ttl_hours == 2

        def test_loads_limit_from_env(self) -> None:
            """Should load limit from PETITION_RATE_LIMIT_PER_HOUR."""
            with patch.dict(os.environ, {"PETITION_RATE_LIMIT_PER_HOUR": "25"}):
                config = PetitionRateLimitConfig.from_environment()
                assert config.limit_per_hour == 25

        def test_loads_window_from_env(self) -> None:
            """Should load window from PETITION_RATE_LIMIT_WINDOW_MINUTES."""
            with patch.dict(os.environ, {"PETITION_RATE_LIMIT_WINDOW_MINUTES": "30"}):
                config = PetitionRateLimitConfig.from_environment()
                assert config.window_minutes == 30

        def test_loads_ttl_from_env(self) -> None:
            """Should load TTL from PETITION_RATE_LIMIT_TTL_HOURS."""
            with patch.dict(os.environ, {"PETITION_RATE_LIMIT_TTL_HOURS": "4"}):
                config = PetitionRateLimitConfig.from_environment()
                assert config.bucket_ttl_hours == 4

        def test_invalid_env_var_uses_default(self) -> None:
            """Invalid environment variable values should use defaults."""
            with patch.dict(os.environ, {"PETITION_RATE_LIMIT_PER_HOUR": "not_a_number"}):
                config = PetitionRateLimitConfig.from_environment()
                assert config.limit_per_hour == 10  # Default

        def test_loads_all_env_vars_together(self) -> None:
            """Should load all values from environment together."""
            env_vars = {
                "PETITION_RATE_LIMIT_PER_HOUR": "100",
                "PETITION_RATE_LIMIT_WINDOW_MINUTES": "120",
                "PETITION_RATE_LIMIT_TTL_HOURS": "4",
            }
            with patch.dict(os.environ, env_vars):
                config = PetitionRateLimitConfig.from_environment()

                assert config.limit_per_hour == 100
                assert config.window_minutes == 120
                assert config.bucket_ttl_hours == 4


class TestRateLimitPreDefinedConfigs:
    """Tests for pre-defined rate limit configuration instances."""

    def test_default_config_values(self) -> None:
        """DEFAULT_PETITION_RATE_LIMIT_CONFIG should have HC-4 compliant values."""
        config = DEFAULT_PETITION_RATE_LIMIT_CONFIG
        assert config.limit_per_hour == 10
        assert config.window_minutes == 60
        assert config.bucket_ttl_hours == 2

    def test_test_config_has_low_limits(self) -> None:
        """TEST_PETITION_RATE_LIMIT_CONFIG should have low limits for testing."""
        config = TEST_PETITION_RATE_LIMIT_CONFIG
        assert config.limit_per_hour == 3
        assert config.window_minutes == 5
        assert config.bucket_ttl_hours == 1

    def test_relaxed_config(self) -> None:
        """RELAXED_PETITION_RATE_LIMIT_CONFIG should have higher limits."""
        config = RELAXED_PETITION_RATE_LIMIT_CONFIG
        assert config.limit_per_hour == 50
        assert config.window_minutes == 60
        assert config.bucket_ttl_hours == 2

    def test_configs_are_frozen(self) -> None:
        """Pre-defined rate limit configs should be immutable."""
        with pytest.raises(Exception):  # FrozenInstanceError
            DEFAULT_PETITION_RATE_LIMIT_CONFIG.limit_per_hour = 99999  # type: ignore[misc]
