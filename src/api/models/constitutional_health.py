"""Constitutional health API response models (Story 8.10, ADR-10).

Pydantic models for constitutional health endpoint responses.
These models provide visibility into constitutional integrity
distinct from operational health metrics.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- AC3: Constitutional vs operational health distinction
- AC5: Response includes all constitutional metrics
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ConstitutionalHealthStatusResponse(str, Enum):
    """Constitutional health status for API responses.

    Maps to domain ConstitutionalHealthStatus.
    """

    HEALTHY = "healthy"
    """All constitutional metrics within acceptable ranges."""

    WARNING = "warning"
    """One or more metrics at warning threshold but not critical."""

    UNHEALTHY = "unhealthy"
    """One or more metrics at critical threshold - ceremonies blocked."""


class ConstitutionalMetricResponse(BaseModel):
    """Single constitutional health metric in API response.

    Attributes:
        name: Metric identifier (e.g., "breach_count").
        value: Current metric value.
        warning_threshold: Threshold for WARNING status.
        critical_threshold: Threshold for UNHEALTHY status.
        status: Current status based on value vs thresholds.
        is_blocking: True if this metric is blocking ceremonies.
    """

    name: str = Field(description="Metric identifier")
    value: float = Field(description="Current metric value")
    warning_threshold: float = Field(description="Warning threshold")
    critical_threshold: float = Field(description="Critical threshold")
    status: ConstitutionalHealthStatusResponse = Field(
        description="Current status: healthy/warning/unhealthy"
    )
    is_blocking: bool = Field(default=False, description="True if blocking ceremonies")
    description: str | None = Field(
        default=None, description="Human-readable description of metric"
    )


class ConstitutionalHealthResponse(BaseModel):
    """Constitutional health endpoint response (AC5).

    Returns all constitutional health metrics with overall status.
    This is distinct from operational health (/health).

    Attributes:
        status: Overall constitutional health status.
        ceremonies_blocked: True if ceremonies cannot proceed.
        blocking_reasons: List of reasons blocking ceremonies.
        metrics: Dictionary of metric name to metric details.
        checked_at: UTC timestamp when health was checked.
        health_type: Always "constitutional" to distinguish from operational.
    """

    status: ConstitutionalHealthStatusResponse = Field(
        description="Overall constitutional health status"
    )
    ceremonies_blocked: bool = Field(
        description="True if ceremonies are blocked due to unhealthy status"
    )
    blocking_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons why ceremonies are blocked (empty if not blocked)",
    )
    metrics: dict[str, ConstitutionalMetricResponse] = Field(
        description="All constitutional health metrics keyed by name"
    )
    checked_at: datetime = Field(description="UTC timestamp when health was checked")
    health_type: str = Field(
        default="constitutional",
        description="Health type: always 'constitutional' for this endpoint",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "warning",
                "ceremonies_blocked": False,
                "blocking_reasons": [],
                "metrics": {
                    "breach_count": {
                        "name": "breach_count",
                        "value": 8,
                        "warning_threshold": 8,
                        "critical_threshold": 10,
                        "status": "warning",
                        "is_blocking": False,
                        "description": "Unacknowledged breaches in 90-day window",
                    },
                    "override_rate": {
                        "name": "override_rate",
                        "value": 1,
                        "warning_threshold": 3,
                        "critical_threshold": 6,
                        "status": "healthy",
                        "is_blocking": False,
                        "description": "Daily override rate",
                    },
                    "dissent_health": {
                        "name": "dissent_health",
                        "value": 25.5,
                        "warning_threshold": 10.0,
                        "critical_threshold": 5.0,
                        "status": "healthy",
                        "is_blocking": False,
                        "description": "30-day rolling average dissent percentage",
                    },
                    "witness_coverage": {
                        "name": "witness_coverage",
                        "value": 20,
                        "warning_threshold": 12,
                        "critical_threshold": 6,
                        "status": "healthy",
                        "is_blocking": False,
                        "description": "Effective witness pool size",
                    },
                },
                "checked_at": "2025-01-08T10:30:00Z",
                "health_type": "constitutional",
            }
        }
    }


class ConstitutionalHealthAlertResponse(BaseModel):
    """Alert raised when constitutional health degrades (AC2).

    Constitutional alerts route to governance, not ops.

    Attributes:
        alert_type: Type of constitutional alert.
        severity: Alert severity (WARNING or CRITICAL).
        metric_name: Which metric triggered the alert.
        current_value: Current metric value.
        threshold_crossed: Which threshold was crossed.
        message: Human-readable alert message.
        route_to: Alert routing destination (always "governance").
        raised_at: UTC timestamp when alert was raised.
    """

    alert_type: str = Field(
        description="Alert type (e.g., BREACH_WARNING, DISSENT_LOW)"
    )
    severity: str = Field(description="Alert severity: WARNING or CRITICAL")
    metric_name: str = Field(description="Metric that triggered the alert")
    current_value: float = Field(description="Current metric value")
    threshold_crossed: float = Field(description="Threshold that was crossed")
    message: str = Field(description="Human-readable alert message")
    route_to: str = Field(
        default="governance",
        description="Alert routing: always 'governance' for constitutional alerts",
    )
    raised_at: datetime = Field(description="UTC timestamp when alert was raised")
