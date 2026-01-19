"""Petition system configuration (Story 1.3, 1.4).

This module defines configuration for petition queue management and rate limiting
with environment variable overrides for production tuning.

Constitutional Constraints:
- FR-1.4: Configurable queue threshold (default: 10,000)
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- NFR-3.1: No silent petition loss
- NFR-5.1: Rate limiting per identity: Configurable per type
- NFR-7.4: Queue depth monitoring with backpressure
- D4: PostgreSQL time-bucket counters

Environment Variables (Queue):
- PETITION_QUEUE_THRESHOLD: Max pending petitions before 503 (default: 10000)
- PETITION_QUEUE_HYSTERESIS: Buffer before resuming accepts (default: 500)
- PETITION_QUEUE_CACHE_TTL: Cache TTL in seconds (default: 5.0)
- PETITION_QUEUE_RETRY_AFTER: Retry-After header value in seconds (default: 60)

Environment Variables (Rate Limit):
- PETITION_RATE_LIMIT_PER_HOUR: Max submissions per submitter per hour (default: 10)
- PETITION_RATE_LIMIT_WINDOW_MINUTES: Sliding window size in minutes (default: 60)
- PETITION_RATE_LIMIT_TTL_HOURS: Bucket TTL for cleanup in hours (default: 2)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int_env(key: str, default: int) -> int:
    """Get integer environment variable with default.

    Args:
        key: Environment variable name.
        default: Default value if not set or invalid.

    Returns:
        Parsed integer value or default.
    """
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float_env(key: str, default: float) -> float:
    """Get float environment variable with default.

    Args:
        key: Environment variable name.
        default: Default value if not set or invalid.

    Returns:
        Parsed float value or default.
    """
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class PetitionQueueConfig:
    """Configuration for petition queue overflow protection (Story 1.3, AC2).

    All values can be overridden via environment variables for production tuning.

    Attributes:
        threshold: Maximum queue depth before 503 responses (FR-1.4).
                  Default: 10,000 pending petitions.
        hysteresis: Buffer below threshold to resume accepting (AC1).
                   Default: 500. Prevents rapid state oscillation.
        cache_ttl_seconds: How long to cache queue depth queries (NFR-1.1).
                          Default: 5.0 seconds. Balances accuracy vs latency.
        retry_after_seconds: Retry-After header value for 503 responses (AC3).
                            Default: 60 seconds.
    """

    threshold: int = 10_000
    hysteresis: int = 500
    cache_ttl_seconds: float = 5.0
    retry_after_seconds: int = 60

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.threshold < 1:
            raise ValueError(f"threshold must be positive, got {self.threshold}")
        if self.hysteresis < 0:
            raise ValueError(f"hysteresis must be non-negative, got {self.hysteresis}")
        if self.hysteresis >= self.threshold:
            raise ValueError(
                f"hysteresis ({self.hysteresis}) must be less than "
                f"threshold ({self.threshold})"
            )
        if self.cache_ttl_seconds <= 0:
            raise ValueError(
                f"cache_ttl_seconds must be positive, got {self.cache_ttl_seconds}"
            )
        if self.retry_after_seconds < 1:
            raise ValueError(
                f"retry_after_seconds must be at least 1, got {self.retry_after_seconds}"
            )

    @classmethod
    def from_environment(cls) -> "PetitionQueueConfig":
        """Create config from environment variables with defaults (AC2).

        Environment Variables:
            PETITION_QUEUE_THRESHOLD: Max pending petitions (default: 10000)
            PETITION_QUEUE_HYSTERESIS: Resume buffer (default: 500)
            PETITION_QUEUE_CACHE_TTL: Cache TTL seconds (default: 5.0)
            PETITION_QUEUE_RETRY_AFTER: Retry-After seconds (default: 60)

        Returns:
            PetitionQueueConfig with values from environment or defaults.
        """
        return cls(
            threshold=_get_int_env("PETITION_QUEUE_THRESHOLD", 10_000),
            hysteresis=_get_int_env("PETITION_QUEUE_HYSTERESIS", 500),
            cache_ttl_seconds=_get_float_env("PETITION_QUEUE_CACHE_TTL", 5.0),
            retry_after_seconds=_get_int_env("PETITION_QUEUE_RETRY_AFTER", 60),
        )


# Pre-defined configurations for common use cases

# Default production config (loaded from environment)
DEFAULT_PETITION_QUEUE_CONFIG = PetitionQueueConfig()

# Testing config with low thresholds for unit tests
TEST_PETITION_QUEUE_CONFIG = PetitionQueueConfig(
    threshold=100,
    hysteresis=10,
    cache_ttl_seconds=0.1,
    retry_after_seconds=5,
)

# High-capacity production config for scaling
HIGH_CAPACITY_PETITION_QUEUE_CONFIG = PetitionQueueConfig(
    threshold=50_000,
    hysteresis=2_500,
    cache_ttl_seconds=2.0,
    retry_after_seconds=30,
)


@dataclass(frozen=True)
class PetitionRateLimitConfig:
    """Configuration for submitter rate limiting (Story 1.4, HC-4, D4).

    All values can be overridden via environment variables for production tuning.

    Attributes:
        limit_per_hour: Maximum submissions per submitter per window (HC-4).
                       Default: 10 petitions per hour.
        window_minutes: Sliding window size in minutes (D4).
                       Default: 60 minutes.
        bucket_ttl_hours: How long to keep expired buckets before cleanup.
                         Default: 2 hours. Provides buffer beyond window.
    """

    limit_per_hour: int = 10
    window_minutes: int = 60
    bucket_ttl_hours: int = 2

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.limit_per_hour < 1:
            raise ValueError(
                f"limit_per_hour must be positive, got {self.limit_per_hour}"
            )
        if self.window_minutes < 1:
            raise ValueError(
                f"window_minutes must be positive, got {self.window_minutes}"
            )
        if self.bucket_ttl_hours < 1:
            raise ValueError(
                f"bucket_ttl_hours must be positive, got {self.bucket_ttl_hours}"
            )
        if self.bucket_ttl_hours * 60 <= self.window_minutes:
            raise ValueError(
                f"bucket_ttl_hours ({self.bucket_ttl_hours}h = {self.bucket_ttl_hours * 60}min) "
                f"must be greater than window_minutes ({self.window_minutes}min)"
            )

    @classmethod
    def from_environment(cls) -> "PetitionRateLimitConfig":
        """Create config from environment variables with defaults (AC5).

        Environment Variables:
            PETITION_RATE_LIMIT_PER_HOUR: Max per submitter per hour (default: 10)
            PETITION_RATE_LIMIT_WINDOW_MINUTES: Window size in minutes (default: 60)
            PETITION_RATE_LIMIT_TTL_HOURS: Bucket TTL in hours (default: 2)

        Returns:
            PetitionRateLimitConfig with values from environment or defaults.
        """
        return cls(
            limit_per_hour=_get_int_env("PETITION_RATE_LIMIT_PER_HOUR", 10),
            window_minutes=_get_int_env("PETITION_RATE_LIMIT_WINDOW_MINUTES", 60),
            bucket_ttl_hours=_get_int_env("PETITION_RATE_LIMIT_TTL_HOURS", 2),
        )


# Pre-defined rate limit configurations

# Default production config (HC-4 compliant)
DEFAULT_PETITION_RATE_LIMIT_CONFIG = PetitionRateLimitConfig()

# Testing config with low thresholds for unit tests
TEST_PETITION_RATE_LIMIT_CONFIG = PetitionRateLimitConfig(
    limit_per_hour=3,
    window_minutes=5,
    bucket_ttl_hours=1,
)

# Relaxed config for high-throughput scenarios
RELAXED_PETITION_RATE_LIMIT_CONFIG = PetitionRateLimitConfig(
    limit_per_hour=50,
    window_minutes=60,
    bucket_ttl_hours=2,
)
