"""Deliberation timeout configuration (Story 2B.2, FR-11.9, HC-7).

This module defines configuration for deliberation timeout enforcement
with environment variable overrides for production tuning.

Constitutional Constraints:
- FR-11.9: System SHALL enforce deliberation timeout (5 minutes default) with auto-ESCALATE on expiry
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-3.4: Timeout reliability - 100% timeouts fire
- HP-1: Job queue for reliable deadline execution
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - timeout MUST fire
- CT-14: Silence must be expensive - every petition terminates in witnessed fate

Environment Variables:
- DELIBERATION_TIMEOUT_SECONDS: Timeout duration (default: 300, min: 60, max: 900)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta


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


# Default deliberation timeout (FR-11.9: 5 minutes default)
DEFAULT_DELIBERATION_TIMEOUT_SECONDS = 300

# Minimum timeout floor (1 minute)
MIN_DELIBERATION_TIMEOUT_SECONDS = 60

# Maximum timeout ceiling (15 minutes)
MAX_DELIBERATION_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class DeliberationConfig:
    """Configuration for deliberation timeout enforcement (FR-11.9, HC-7).

    All values can be overridden via environment variables for production tuning.

    Constitutional Constraints:
    - FR-11.9: 5-minute default with auto-ESCALATE on expiry
    - HC-7: Prevent stuck petitions via timeout
    - CT-11: Silent failure destroys legitimacy - timeout MUST fire
    - CT-14: Silence is expensive - every petition terminates in witnessed fate

    Attributes:
        timeout_seconds: Timeout duration in seconds.
                        Default: 300 (5 minutes).
                        Minimum: 60 (1 minute).
                        Maximum: 900 (15 minutes).
    """

    timeout_seconds: int = DEFAULT_DELIBERATION_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not MIN_DELIBERATION_TIMEOUT_SECONDS <= self.timeout_seconds <= MAX_DELIBERATION_TIMEOUT_SECONDS:
            raise ValueError(
                f"timeout_seconds must be between {MIN_DELIBERATION_TIMEOUT_SECONDS} "
                f"and {MAX_DELIBERATION_TIMEOUT_SECONDS}, got {self.timeout_seconds}"
            )

    @property
    def timeout_timedelta(self) -> timedelta:
        """Get timeout as a timedelta for datetime operations.

        Returns:
            Timeout duration as timedelta.
        """
        return timedelta(seconds=self.timeout_seconds)

    @classmethod
    def from_environment(cls) -> DeliberationConfig:
        """Create config from environment variables with defaults (AC-5).

        Environment Variables:
            DELIBERATION_TIMEOUT_SECONDS: Timeout in seconds (default: 300)

        Returns:
            DeliberationConfig with values from environment or defaults.
        """
        timeout = _get_int_env(
            "DELIBERATION_TIMEOUT_SECONDS",
            DEFAULT_DELIBERATION_TIMEOUT_SECONDS,
        )
        # Clamp to valid range
        timeout = max(
            MIN_DELIBERATION_TIMEOUT_SECONDS,
            min(timeout, MAX_DELIBERATION_TIMEOUT_SECONDS),
        )
        return cls(timeout_seconds=timeout)


# Pre-defined configurations for common use cases

# Default production config (FR-11.9 compliant: 5 minutes)
DEFAULT_DELIBERATION_CONFIG = DeliberationConfig()

# Testing config with short timeout for unit tests
TEST_DELIBERATION_CONFIG = DeliberationConfig(
    timeout_seconds=MIN_DELIBERATION_TIMEOUT_SECONDS,  # 60 seconds
)

# Maximum timeout config for extended deliberations
EXTENDED_DELIBERATION_CONFIG = DeliberationConfig(
    timeout_seconds=MAX_DELIBERATION_TIMEOUT_SECONDS,  # 15 minutes
)
