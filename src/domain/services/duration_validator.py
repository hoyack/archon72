"""Duration validation domain service (Story 5.2, FR24).

This module provides validation for override durations.
Indefinite overrides are prohibited - all overrides must have a bounded duration.

Constitutional Constraints:
- FR24: Override events SHALL include duration
- FR24: Duration must be within allowed bounds
- CT-11: Silent failure destroys legitimacy -> Validation failures must be explicit

Duration Constraints:
- Minimum: 60 seconds (1 minute) - Prevent accidental instant expirations
- Maximum: 604800 seconds (7 days) - Prevent long-term power consolidation
"""

from __future__ import annotations

from src.domain.errors.override import DurationValidationError

# Duration constraints (FR24)
MIN_DURATION_SECONDS: int = 60  # 1 minute minimum
MAX_DURATION_SECONDS: int = 604800  # 7 days maximum (7 * 24 * 60 * 60)


def validate_duration(duration_seconds: int) -> None:
    """Validate override duration is within allowed bounds.

    Constitutional Constraint (FR24):
    Override duration must be specified and within bounds.
    Indefinite overrides are prohibited.

    Args:
        duration_seconds: Duration in seconds to validate.

    Raises:
        DurationValidationError: If duration is invalid.
            - Zero or negative: "FR24: Duration required for all overrides"
            - Below minimum: "FR24: Duration below minimum of 60 seconds"
            - Above maximum: "FR24: Duration exceeds maximum of 7 days"
    """
    if duration_seconds <= 0:
        raise DurationValidationError(
            "FR24: Duration required for all overrides - "
            f"got {duration_seconds} seconds (must be > 0)"
        )

    if duration_seconds < MIN_DURATION_SECONDS:
        raise DurationValidationError(
            f"FR24: Duration below minimum of {MIN_DURATION_SECONDS} seconds - "
            f"got {duration_seconds} seconds"
        )

    if duration_seconds > MAX_DURATION_SECONDS:
        raise DurationValidationError(
            f"FR24: Duration exceeds maximum of 7 days ({MAX_DURATION_SECONDS} seconds) - "
            f"got {duration_seconds} seconds"
        )
