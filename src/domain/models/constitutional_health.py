"""Constitutional health domain models (Story 8.10, ADR-10).

This module provides domain models for tracking constitutional health
metrics distinct from operational metrics.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- System health = worst component health (conservative)
- FR32: Breach count thresholds
- NFR-023: Dissent health thresholds
- FR117: Witness coverage thresholds
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Threshold constants (from existing code per story Dev Notes)
# Breach count (Story 6.3, FR32)
BREACH_WARNING_THRESHOLD: int = 8
BREACH_CRITICAL_THRESHOLD: int = 10

# Override rate (Story 8.4)
OVERRIDE_INCIDENT_THRESHOLD: int = 3  # per day
OVERRIDE_CRITICAL_THRESHOLD: int = 6  # per day (double incident threshold)

# Dissent health (Story 2.4, NFR-023)
DISSENT_WARNING_THRESHOLD: float = 10.0  # percentage
DISSENT_CRITICAL_THRESHOLD: float = 5.0  # percentage

# Witness coverage (Story 6.6, FR117)
WITNESS_DEGRADED_THRESHOLD: int = 12  # minimum pool size
WITNESS_CRITICAL_THRESHOLD: int = 6  # critical minimum


class ConstitutionalHealthStatus(str, Enum):
    """Overall constitutional health status.

    Per ADR-10, system health = worst component health (conservative).
    """

    HEALTHY = "healthy"
    """All constitutional metrics within acceptable ranges."""

    WARNING = "warning"
    """One or more metrics at warning threshold but not critical."""

    UNHEALTHY = "unhealthy"
    """One or more metrics at critical threshold - ceremonies blocked."""


class MetricName(str, Enum):
    """Names for constitutional health metrics."""

    BREACH_COUNT = "breach_count"
    """Unacknowledged breaches in 90-day window (FR32)."""

    OVERRIDE_RATE = "override_rate"
    """Daily override rate (Story 8.4)."""

    DISSENT_HEALTH = "dissent_health"
    """Rolling average dissent percentage (NFR-023)."""

    WITNESS_COVERAGE = "witness_coverage"
    """Effective witness pool size (FR117)."""


@dataclass(frozen=True)
class ConstitutionalHealthMetric:
    """A single constitutional health metric with thresholds.

    Tracks a metric value against warning and critical thresholds.
    For some metrics (like dissent and witness coverage), lower values
    are worse, so comparison is inverted.

    Attributes:
        name: The metric identifier.
        value: Current metric value.
        warning_threshold: Threshold for WARNING status.
        critical_threshold: Threshold for UNHEALTHY status.
        invert_comparison: If True, lower values are worse (default False).
    """

    name: MetricName
    value: float
    warning_threshold: float
    critical_threshold: float
    invert_comparison: bool = False

    @property
    def status(self) -> ConstitutionalHealthStatus:
        """Calculate status based on value and thresholds.

        Returns:
            UNHEALTHY if at/past critical threshold,
            WARNING if at/past warning threshold,
            HEALTHY otherwise.
        """
        if self.invert_comparison:
            # Lower is worse (dissent, witness coverage)
            if self.value <= self.critical_threshold:
                return ConstitutionalHealthStatus.UNHEALTHY
            if self.value <= self.warning_threshold:
                return ConstitutionalHealthStatus.WARNING
        else:
            # Higher is worse (breach count, override rate)
            if self.value > self.critical_threshold:
                return ConstitutionalHealthStatus.UNHEALTHY
            if self.value >= self.warning_threshold:
                return ConstitutionalHealthStatus.WARNING
        return ConstitutionalHealthStatus.HEALTHY

    @property
    def is_healthy(self) -> bool:
        """True if metric is at HEALTHY status."""
        return self.status == ConstitutionalHealthStatus.HEALTHY

    @property
    def is_blocking(self) -> bool:
        """True if metric is at UNHEALTHY status (blocks ceremonies)."""
        return self.status == ConstitutionalHealthStatus.UNHEALTHY

    def to_dict(self) -> dict[str, object]:
        """Convert metric to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "name": self.name.value,
            "value": self.value,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "status": self.status.value,
            "is_blocking": self.is_blocking,
        }


@dataclass(frozen=True)
class ConstitutionalHealthSnapshot:
    """Snapshot of all constitutional health metrics at a point in time.

    Per ADR-10:
    - System health = worst component health (conservative)
    - UNHEALTHY status blocks ceremonies
    - Emergency override required to proceed when blocked

    Attributes:
        breach_count: Unacknowledged breaches in 90-day window.
        override_rate_daily: Number of overrides today.
        dissent_health_percent: Rolling 30-day average dissent percentage.
        witness_coverage: Effective witness pool size.
        calculated_at: When this snapshot was calculated.
    """

    breach_count: int
    override_rate_daily: int
    dissent_health_percent: float
    witness_coverage: int
    calculated_at: datetime

    # Calculated fields
    _metrics: list[ConstitutionalHealthMetric] | None = field(
        default=None, repr=False, compare=False
    )

    def get_all_metrics(self) -> list[ConstitutionalHealthMetric]:
        """Get all constitutional health metrics.

        Returns:
            List of ConstitutionalHealthMetric instances.
        """
        return [
            ConstitutionalHealthMetric(
                name=MetricName.BREACH_COUNT,
                value=self.breach_count,
                warning_threshold=BREACH_WARNING_THRESHOLD,
                critical_threshold=BREACH_CRITICAL_THRESHOLD,
                invert_comparison=False,
            ),
            ConstitutionalHealthMetric(
                name=MetricName.OVERRIDE_RATE,
                value=self.override_rate_daily,
                warning_threshold=OVERRIDE_INCIDENT_THRESHOLD,
                critical_threshold=OVERRIDE_CRITICAL_THRESHOLD,
                invert_comparison=False,
            ),
            ConstitutionalHealthMetric(
                name=MetricName.DISSENT_HEALTH,
                value=self.dissent_health_percent,
                warning_threshold=DISSENT_WARNING_THRESHOLD,
                critical_threshold=DISSENT_CRITICAL_THRESHOLD,
                invert_comparison=True,  # Lower is worse
            ),
            ConstitutionalHealthMetric(
                name=MetricName.WITNESS_COVERAGE,
                value=self.witness_coverage,
                warning_threshold=WITNESS_DEGRADED_THRESHOLD,
                critical_threshold=WITNESS_CRITICAL_THRESHOLD,
                invert_comparison=True,  # Lower is worse
            ),
        ]

    @property
    def overall_status(self) -> ConstitutionalHealthStatus:
        """Calculate overall status per ADR-10: worst component health.

        Returns:
            UNHEALTHY if any metric is UNHEALTHY,
            WARNING if any metric is WARNING,
            HEALTHY if all metrics are HEALTHY.
        """
        metrics = self.get_all_metrics()
        statuses = [m.status for m in metrics]

        # Conservative: worst component determines system health
        if ConstitutionalHealthStatus.UNHEALTHY in statuses:
            return ConstitutionalHealthStatus.UNHEALTHY
        if ConstitutionalHealthStatus.WARNING in statuses:
            return ConstitutionalHealthStatus.WARNING
        return ConstitutionalHealthStatus.HEALTHY

    @property
    def ceremonies_blocked(self) -> bool:
        """True if ceremonies are blocked due to unhealthy status (AC4).

        Per ADR-10, ceremonies are blocked when constitutional health
        is UNHEALTHY. Emergency override is required to proceed.
        """
        return self.overall_status == ConstitutionalHealthStatus.UNHEALTHY

    @property
    def blocking_reasons(self) -> list[str]:
        """Get list of reasons why ceremonies are blocked.

        Returns:
            List of human-readable blocking reason strings.
            Empty list if not blocked.
        """
        reasons: list[str] = []
        for metric in self.get_all_metrics():
            if metric.is_blocking:
                reasons.append(
                    f"{metric.name.value}: value {metric.value} "
                    f"exceeds critical threshold {metric.critical_threshold}"
                )
        return reasons

    def to_dict(self) -> dict[str, object]:
        """Convert snapshot to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "overall_status": self.overall_status.value,
            "ceremonies_blocked": self.ceremonies_blocked,
            "blocking_reasons": self.blocking_reasons,
            "metrics": [m.to_dict() for m in self.get_all_metrics()],
            "calculated_at": self.calculated_at.isoformat(),
        }
