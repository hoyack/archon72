"""Complexity budget API response models (Story 8.6, AC5).

Pydantic models for complexity budget dashboard and metrics endpoints.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event.
- SC-3: Self-consistency finding - complexity budget dashboard required.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
)


class ComplexityMetricResponse(BaseModel):
    """Response model for a single complexity metric (AC1).

    Represents the current state of one complexity dimension.

    Attributes:
        dimension: Name of the complexity dimension.
        current_value: Current count/value.
        limit: Maximum allowed value.
        utilization: Percentage of limit used (0-100+).
        status: Current status (within_budget, warning, breached).
    """

    dimension: str = Field(description="Complexity dimension name")
    current_value: int = Field(description="Current metric value")
    limit: int = Field(description="Maximum allowed value")
    utilization: float = Field(description="Percentage of limit used")
    status: str = Field(description="Status: within_budget, warning, or breached")


class ComplexityDashboardResponse(BaseModel):
    """Response model for the complexity dashboard (AC1).

    Provides a comprehensive view of all complexity metrics.

    Attributes:
        adr_count: Current ADR count.
        adr_limit: ADR limit (15).
        adr_utilization: ADR utilization percentage.
        adr_status: ADR budget status.
        ceremony_types: Current ceremony type count.
        ceremony_type_limit: Ceremony type limit (10).
        ceremony_type_utilization: Ceremony type utilization percentage.
        ceremony_type_status: Ceremony type budget status.
        cross_component_deps: Current cross-component dependency count.
        cross_component_dep_limit: Cross-component dependency limit (20).
        cross_component_dep_utilization: Cross-component dependency utilization percentage.
        cross_component_dep_status: Cross-component dependency budget status.
        overall_status: Worst status across all dimensions.
        active_breaches: Number of unresolved breaches.
        pending_escalations: Number of breaches pending escalation.
        last_updated: Timestamp of last update.
    """

    adr_count: int = Field(description="Current ADR count")
    adr_limit: int = Field(default=ADR_LIMIT, description="ADR limit")
    adr_utilization: float = Field(description="ADR utilization percentage")
    adr_status: str = Field(description="ADR budget status")

    ceremony_types: int = Field(description="Current ceremony type count")
    ceremony_type_limit: int = Field(
        default=CEREMONY_TYPE_LIMIT, description="Ceremony type limit"
    )
    ceremony_type_utilization: float = Field(
        description="Ceremony type utilization percentage"
    )
    ceremony_type_status: str = Field(description="Ceremony type budget status")

    cross_component_deps: int = Field(
        description="Current cross-component dependency count"
    )
    cross_component_dep_limit: int = Field(
        default=CROSS_COMPONENT_DEP_LIMIT, description="Cross-component dependency limit"
    )
    cross_component_dep_utilization: float = Field(
        description="Cross-component dependency utilization percentage"
    )
    cross_component_dep_status: str = Field(
        description="Cross-component dependency budget status"
    )

    overall_status: str = Field(description="Worst status across all dimensions")
    active_breaches: int = Field(description="Number of unresolved breaches")
    pending_escalations: int = Field(
        default=0, description="Number of breaches pending escalation"
    )
    last_updated: datetime = Field(description="Timestamp of last update")


class ComplexityBreachResponse(BaseModel):
    """Response model for a complexity breach event (AC2, RT-6).

    Represents a recorded complexity budget breach.

    Attributes:
        breach_id: Unique identifier for the breach.
        dimension: Which dimension was breached.
        limit: The configured limit.
        actual_value: The actual value that triggered breach.
        overage: Amount over the limit.
        breached_at: When the breach occurred.
        requires_governance_ceremony: Whether governance approval is required.
        is_resolved: Whether the breach has been resolved.
    """

    breach_id: str = Field(description="Unique breach identifier")
    dimension: str = Field(description="Breached dimension")
    limit: int = Field(description="Configured limit")
    actual_value: int = Field(description="Actual value at breach")
    overage: int = Field(description="Amount over limit")
    breached_at: datetime = Field(description="Breach timestamp")
    requires_governance_ceremony: bool = Field(
        default=True, description="Whether governance ceremony required (RT-6)"
    )
    is_resolved: bool = Field(
        default=False, description="Whether breach is resolved"
    )


class ComplexityEscalationResponse(BaseModel):
    """Response model for a complexity escalation event (AC4).

    Represents an escalation created when a breach remains unresolved.

    Attributes:
        escalation_id: Unique identifier for the escalation.
        breach_id: ID of the associated breach.
        dimension: Which dimension was breached.
        escalation_level: Level of escalation (1, 2, etc.).
        days_without_resolution: Days since breach without resolution.
        escalated_at: When the escalation occurred.
        is_critical: Whether this is a critical escalation.
    """

    escalation_id: str = Field(description="Unique escalation identifier")
    breach_id: str = Field(description="Associated breach ID")
    dimension: str = Field(description="Breached dimension")
    escalation_level: int = Field(description="Escalation level")
    days_without_resolution: int = Field(
        description="Days since breach without resolution"
    )
    escalated_at: datetime = Field(description="Escalation timestamp")
    is_critical: bool = Field(description="Whether escalation is critical")


class ComplexityTrendDataPoint(BaseModel):
    """A single data point in complexity trend data (AC5).

    Attributes:
        timestamp: When the snapshot was taken.
        adr_count: ADR count at this time.
        ceremony_types: Ceremony types at this time.
        cross_component_deps: Cross-component dependencies at this time.
    """

    timestamp: datetime = Field(description="Snapshot timestamp")
    adr_count: int = Field(description="ADR count at this time")
    ceremony_types: int = Field(description="Ceremony types at this time")
    cross_component_deps: int = Field(
        description="Cross-component dependencies at this time"
    )


class ComplexityTrendResponse(BaseModel):
    """Response model for complexity trends (AC5).

    Provides historical complexity data for trend analysis.

    Attributes:
        start_date: Start of the trend period.
        end_date: End of the trend period.
        data_points: List of trend data points.
        total_breaches: Total breaches in the period.
        total_escalations: Total escalations in the period.
    """

    start_date: datetime = Field(description="Start of trend period")
    end_date: datetime = Field(description="End of trend period")
    data_points: list[ComplexityTrendDataPoint] = Field(
        default_factory=list, description="Trend data points"
    )
    total_breaches: int = Field(
        default=0, description="Total breaches in period"
    )
    total_escalations: int = Field(
        default=0, description="Total escalations in period"
    )


class ComplexityBreachListResponse(BaseModel):
    """Response model for listing breaches (AC5).

    Attributes:
        breaches: List of breach events.
        total_count: Total number of breaches.
        unresolved_count: Number of unresolved breaches.
    """

    breaches: list[ComplexityBreachResponse] = Field(
        default_factory=list, description="List of breach events"
    )
    total_count: int = Field(default=0, description="Total breach count")
    unresolved_count: int = Field(
        default=0, description="Number of unresolved breaches"
    )
