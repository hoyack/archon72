"""Constitutional health errors (Story 8.10, ADR-10).

Domain errors for constitutional health constraint violations.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- AC4: Ceremonies blocked when unhealthy
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.errors.constitutional import ConstitutionalViolationError

if TYPE_CHECKING:
    from src.domain.models.constitutional_health import (
        ConstitutionalHealthSnapshot,
        ConstitutionalHealthStatus,
    )


class ConstitutionalHealthError(ConstitutionalViolationError):
    """Base error for constitutional health violations.

    All constitutional health errors inherit from this class
    and from ConstitutionalViolationError to indicate they
    represent constitutional (not just operational) failures.
    """

    pass


class ConstitutionalHealthDegradedError(ConstitutionalHealthError):
    """Raised when constitutional health is degraded (AC2).

    This error indicates that one or more constitutional health
    metrics have crossed warning or critical thresholds.

    Attributes:
        status: Current constitutional health status.
        degraded_metrics: List of metric names that are degraded.
        message: Human-readable error message.
    """

    def __init__(
        self,
        status: str,
        degraded_metrics: list[str],
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            status: Current constitutional health status (warning/unhealthy).
            degraded_metrics: List of metric names that are degraded.
            message: Optional custom message.
        """
        self.status = status
        self.degraded_metrics = degraded_metrics

        if message is None:
            metrics_str = ", ".join(degraded_metrics)
            message = (
                f"Constitutional health degraded to {status}. "
                f"Affected metrics: {metrics_str}"
            )

        super().__init__(message)


class CeremonyBlockedByConstitutionalHealthError(ConstitutionalHealthError):
    """Raised when a ceremony cannot proceed due to unhealthy status (AC4).

    Per ADR-10, ceremonies are blocked when constitutional health
    is UNHEALTHY. Emergency override is required to proceed.

    Attributes:
        blocking_reasons: List of reasons why ceremonies are blocked.
        requires_override: Always True - emergency override required.
    """

    def __init__(
        self,
        blocking_reasons: list[str],
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            blocking_reasons: List of reasons from blocking metrics.
            message: Optional custom message.
        """
        self.blocking_reasons = blocking_reasons
        self.requires_override = True

        if message is None:
            reasons_str = "; ".join(blocking_reasons) if blocking_reasons else "Unknown"
            message = (
                f"Ceremony blocked due to unhealthy constitutional status. "
                f"Blocking reasons: {reasons_str}. "
                f"Emergency override required to proceed per ADR-10."
            )

        super().__init__(message)


class ConstitutionalHealthCheckFailedError(ConstitutionalHealthError):
    """Raised when the constitutional health check itself fails.

    This indicates an infrastructure failure in checking health,
    not a health degradation. The system should fail loudly per CT-11.

    Attributes:
        source_error: The underlying error that caused the failure.
    """

    def __init__(
        self,
        source_error: Exception,
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            source_error: The underlying error.
            message: Optional custom message.
        """
        self.source_error = source_error

        if message is None:
            message = (
                f"Constitutional health check failed: {source_error}. "
                f"System should halt per CT-11 (silent failure destroys legitimacy)."
            )

        super().__init__(message)
