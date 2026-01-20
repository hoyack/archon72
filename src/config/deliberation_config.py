"""Deliberation timeout and deadlock configuration (Story 2B.2, 2B.3, FR-11.9, FR-11.10, HC-7).

This module defines configuration for deliberation timeout and deadlock enforcement
with environment variable overrides for production tuning.

Constitutional Constraints:
- FR-11.9: System SHALL enforce deliberation timeout (5 minutes default) with auto-ESCALATE on expiry
- FR-11.10: System SHALL auto-ESCALATE after 3 deliberation rounds without supermajority (deadlock)
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-3.4: Timeout reliability - 100% timeouts fire
- HP-1: Job queue for reliable deadline execution
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - timeout/deadlock MUST fire
- CT-14: Silence must be expensive - every petition terminates in witnessed fate
- AT-1: Every petition terminates in exactly one of Three Fates

Environment Variables:
- DELIBERATION_TIMEOUT_SECONDS: Timeout duration (default: 300, min: 60, max: 900)
- MAX_DELIBERATION_ROUNDS: Maximum voting rounds before deadlock (default: 3, min: 1, max: 10)
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

# =============================================================================
# Deadlock Configuration (FR-11.10, Story 2B.3)
# =============================================================================

# Default maximum deliberation rounds before deadlock (FR-11.10: 3 rounds)
DEFAULT_MAX_DELIBERATION_ROUNDS = 3

# Minimum rounds floor (at least 1 vote attempt)
MIN_DELIBERATION_ROUNDS = 1

# Maximum rounds ceiling (prevent infinite deliberation)
MAX_DELIBERATION_ROUNDS = 10


@dataclass(frozen=True)
class DeliberationConfig:
    """Configuration for deliberation timeout and deadlock enforcement (FR-11.9, FR-11.10, HC-7).

    All values can be overridden via environment variables for production tuning.

    Constitutional Constraints:
    - FR-11.9: 5-minute default with auto-ESCALATE on expiry
    - FR-11.10: Auto-ESCALATE after 3 rounds without supermajority (deadlock)
    - HC-7: Prevent stuck petitions via timeout/deadlock
    - CT-11: Silent failure destroys legitimacy - timeout/deadlock MUST fire
    - CT-14: Silence is expensive - every petition terminates in witnessed fate
    - AT-1: Every petition terminates in exactly one of Three Fates

    Attributes:
        timeout_seconds: Timeout duration in seconds.
                        Default: 300 (5 minutes).
                        Minimum: 60 (1 minute).
                        Maximum: 900 (15 minutes).
        max_rounds: Maximum voting rounds before deadlock (FR-11.10).
                   Default: 3 rounds.
                   Minimum: 1 round.
                   Maximum: 10 rounds.
    """

    timeout_seconds: int = DEFAULT_DELIBERATION_TIMEOUT_SECONDS
    max_rounds: int = DEFAULT_MAX_DELIBERATION_ROUNDS

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if (
            not MIN_DELIBERATION_TIMEOUT_SECONDS
            <= self.timeout_seconds
            <= MAX_DELIBERATION_TIMEOUT_SECONDS
        ):
            raise ValueError(
                f"timeout_seconds must be between {MIN_DELIBERATION_TIMEOUT_SECONDS} "
                f"and {MAX_DELIBERATION_TIMEOUT_SECONDS}, got {self.timeout_seconds}"
            )
        if not MIN_DELIBERATION_ROUNDS <= self.max_rounds <= MAX_DELIBERATION_ROUNDS:
            raise ValueError(
                f"max_rounds must be between {MIN_DELIBERATION_ROUNDS} "
                f"and {MAX_DELIBERATION_ROUNDS}, got {self.max_rounds}"
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
            MAX_DELIBERATION_ROUNDS: Max voting rounds before deadlock (default: 3)

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

        max_rounds = _get_int_env(
            "MAX_DELIBERATION_ROUNDS",
            DEFAULT_MAX_DELIBERATION_ROUNDS,
        )
        # Clamp to valid range
        max_rounds = max(
            MIN_DELIBERATION_ROUNDS,
            min(max_rounds, MAX_DELIBERATION_ROUNDS),
        )

        return cls(timeout_seconds=timeout, max_rounds=max_rounds)


# Pre-defined configurations for common use cases

# Default production config (FR-11.9, FR-11.10 compliant: 5 minutes timeout, 3 rounds max)
DEFAULT_DELIBERATION_CONFIG = DeliberationConfig()

# Testing config with short timeout for unit tests
TEST_DELIBERATION_CONFIG = DeliberationConfig(
    timeout_seconds=MIN_DELIBERATION_TIMEOUT_SECONDS,  # 60 seconds
    max_rounds=DEFAULT_MAX_DELIBERATION_ROUNDS,  # 3 rounds
)

# Maximum timeout config for extended deliberations
EXTENDED_DELIBERATION_CONFIG = DeliberationConfig(
    timeout_seconds=MAX_DELIBERATION_TIMEOUT_SECONDS,  # 15 minutes
    max_rounds=DEFAULT_MAX_DELIBERATION_ROUNDS,  # 3 rounds
)

# Single round config for fast-fail testing
SINGLE_ROUND_DELIBERATION_CONFIG = DeliberationConfig(
    timeout_seconds=MIN_DELIBERATION_TIMEOUT_SECONDS,  # 60 seconds
    max_rounds=MIN_DELIBERATION_ROUNDS,  # 1 round (immediate deadlock on split)
)
