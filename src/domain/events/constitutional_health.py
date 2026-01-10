"""Constitutional health alert events (Story 8.10, ADR-10, AC2).

Domain events for constitutional health degradation alerts.
These alerts route to governance (not ops) and represent
potential threats to constitutional integrity.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- AC2: Alerts route to governance, not ops
- Alerts are distinct from operational alerts
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

# Event type constant (follows existing pattern in codebase)
CONSTITUTIONAL_HEALTH_ALERT_EVENT_TYPE: str = "constitutional_health_alert"


class ConstitutionalAlertType(str, Enum):
    """Types of constitutional health alerts (AC2).

    These represent different categories of constitutional
    health degradation that require governance attention.
    """

    BREACH_WARNING = "breach_warning"
    """Breach count reached warning threshold (8)."""

    BREACH_CRITICAL = "breach_critical"
    """Breach count exceeded critical threshold (>10)."""

    OVERRIDE_HIGH = "override_high"
    """Daily override rate exceeded incident threshold (3)."""

    OVERRIDE_CRITICAL = "override_critical"
    """Daily override rate exceeded critical threshold (6)."""

    DISSENT_LOW = "dissent_low"
    """Dissent health dropped below warning threshold (<10%)."""

    DISSENT_CRITICAL = "dissent_critical"
    """Dissent health dropped below critical threshold (<5%)."""

    WITNESS_DEGRADED = "witness_degraded"
    """Witness coverage below minimum threshold (<12)."""

    WITNESS_CRITICAL = "witness_critical"
    """Witness coverage critically low (<6)."""

    CEREMONIES_BLOCKED = "ceremonies_blocked"
    """Ceremonies blocked due to unhealthy constitutional status."""

    HEALTH_RECOVERED = "health_recovered"
    """Constitutional health returned to healthy status."""


class ConstitutionalAlertSeverity(str, Enum):
    """Severity levels for constitutional alerts.

    Maps to operational alert levels but routes to governance.
    """

    WARNING = "WARNING"
    """Requires attention but not blocking."""

    CRITICAL = "CRITICAL"
    """Blocking operations, immediate action required."""


@dataclass(frozen=True)
class ConstitutionalHealthAlertPayload:
    """Payload for constitutional health alert events (AC2).

    These alerts are witnessed events that record constitutional
    health degradation for governance review.

    Attributes:
        alert_type: Type of constitutional alert.
        severity: Alert severity (WARNING or CRITICAL).
        metric_name: Name of the metric that triggered alert.
        current_value: Current value of the metric.
        threshold_crossed: The threshold that was crossed.
        previous_status: Previous constitutional health status.
        new_status: New constitutional health status.
        message: Human-readable alert message.
        route_to: Alert routing destination (always "governance").
        raised_at: When the alert was raised.
        acknowledged_at: When governance acknowledged the alert (if any).
        acknowledged_by: Who acknowledged the alert (if any).
    """

    alert_type: ConstitutionalAlertType
    severity: ConstitutionalAlertSeverity
    metric_name: str
    current_value: float
    threshold_crossed: float
    previous_status: str
    new_status: str
    message: str
    route_to: str  # Always "governance" for constitutional alerts
    raised_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None

    @property
    def event_type(self) -> str:
        """Get the event type for this payload."""
        return CONSTITUTIONAL_HEALTH_ALERT_EVENT_TYPE

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        result: dict[str, object] = {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold_crossed": self.threshold_crossed,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "message": self.message,
            "route_to": self.route_to,
            "raised_at": self.raised_at.isoformat(),
        }
        if self.acknowledged_at:
            result["acknowledged_at"] = self.acknowledged_at.isoformat()
        if self.acknowledged_by:
            result["acknowledged_by"] = self.acknowledged_by
        return result


def create_breach_warning_alert(
    current_count: int,
    threshold: int,
    raised_at: datetime,
) -> ConstitutionalHealthAlertPayload:
    """Create a breach warning alert.

    Args:
        current_count: Current unacknowledged breach count.
        threshold: Warning threshold that was crossed (8).
        raised_at: When the alert was raised.

    Returns:
        ConstitutionalHealthAlertPayload for the warning.
    """
    return ConstitutionalHealthAlertPayload(
        alert_type=ConstitutionalAlertType.BREACH_WARNING,
        severity=ConstitutionalAlertSeverity.WARNING,
        metric_name="breach_count",
        current_value=current_count,
        threshold_crossed=threshold,
        previous_status="healthy",
        new_status="warning",
        message=(
            f"Constitutional warning: Unacknowledged breach count ({current_count}) "
            f"reached warning threshold ({threshold}). "
            f"Governance review recommended."
        ),
        route_to="governance",
        raised_at=raised_at,
    )


def create_breach_critical_alert(
    current_count: int,
    threshold: int,
    raised_at: datetime,
) -> ConstitutionalHealthAlertPayload:
    """Create a breach critical alert.

    Args:
        current_count: Current unacknowledged breach count.
        threshold: Critical threshold that was exceeded (10).
        raised_at: When the alert was raised.

    Returns:
        ConstitutionalHealthAlertPayload for the critical alert.
    """
    return ConstitutionalHealthAlertPayload(
        alert_type=ConstitutionalAlertType.BREACH_CRITICAL,
        severity=ConstitutionalAlertSeverity.CRITICAL,
        metric_name="breach_count",
        current_value=current_count,
        threshold_crossed=threshold,
        previous_status="warning",
        new_status="unhealthy",
        message=(
            f"CONSTITUTIONAL CRITICAL: Unacknowledged breach count ({current_count}) "
            f"exceeded critical threshold ({threshold}). "
            f"Ceremonies blocked. Cessation consideration required per FR32."
        ),
        route_to="governance",
        raised_at=raised_at,
    )


def create_ceremonies_blocked_alert(
    blocking_metrics: list[str],
    raised_at: datetime,
) -> ConstitutionalHealthAlertPayload:
    """Create an alert when ceremonies become blocked.

    Args:
        blocking_metrics: Names of metrics causing the block.
        raised_at: When the alert was raised.

    Returns:
        ConstitutionalHealthAlertPayload for the blocking alert.
    """
    metrics_str = ", ".join(blocking_metrics)
    return ConstitutionalHealthAlertPayload(
        alert_type=ConstitutionalAlertType.CEREMONIES_BLOCKED,
        severity=ConstitutionalAlertSeverity.CRITICAL,
        metric_name="overall_status",
        current_value=0,  # Not applicable for this alert type
        threshold_crossed=0,
        previous_status="warning",
        new_status="unhealthy",
        message=(
            f"CONSTITUTIONAL CRITICAL: Ceremonies blocked due to unhealthy status. "
            f"Blocking metrics: {metrics_str}. "
            f"Emergency override required to proceed per ADR-10."
        ),
        route_to="governance",
        raised_at=raised_at,
    )
