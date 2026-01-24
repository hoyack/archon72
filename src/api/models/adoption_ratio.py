"""Adoption ratio API models (Story 8.6, PREVENT-7).

Pydantic models for adoption ratio monitoring API responses.

Constitutional Context:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
- FR-8.4: High Archon SHALL have access to legitimacy dashboard
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AdoptionRatioMetricsResponse(BaseModel):
    """Response model for adoption ratio metrics.

    Attributes:
        metrics_id: Unique identifier for this metrics record.
        realm_id: Realm identifier.
        cycle_id: Governance cycle identifier (e.g., "2026-W04").
        escalation_count: Petitions escalated to this realm this cycle.
        adoption_count: Petitions adopted by this realm's King this cycle.
        adoption_ratio: Ratio of adopted to escalated (0.0 to 1.0), None if no escalations.
        health_status: Health status based on ratio (NO_DATA, HEALTHY, WARN, CRITICAL).
        adopting_kings: List of King UUIDs who performed adoptions.
        computed_at: When these metrics were computed (UTC).
    """

    metrics_id: str = Field(
        ...,
        description="Unique identifier for this metrics record",
    )
    realm_id: str = Field(
        ...,
        description="Realm identifier",
    )
    cycle_id: str = Field(
        ...,
        description="Governance cycle identifier (e.g., '2026-W04')",
    )
    escalation_count: int = Field(
        ...,
        description="Petitions escalated to this realm this cycle",
        ge=0,
    )
    adoption_count: int = Field(
        ...,
        description="Petitions adopted by this realm's King this cycle",
        ge=0,
    )
    adoption_ratio: float | None = Field(
        ...,
        description="Ratio of adopted to escalated (0.0 to 1.0), None if no escalations",
        ge=0.0,
        le=1.0,
    )
    health_status: str = Field(
        ...,
        description="Health status based on ratio (NO_DATA, HEALTHY, WARN, CRITICAL)",
    )
    adopting_kings: list[str] = Field(
        default_factory=list,
        description="List of King UUIDs who performed adoptions",
    )
    computed_at: datetime = Field(
        ...,
        description="When these metrics were computed (UTC)",
    )


class AdoptionRatioAlertResponse(BaseModel):
    """Response model for an active adoption ratio alert.

    Attributes:
        alert_id: Unique alert identifier.
        realm_id: Realm with excessive adoption ratio.
        cycle_id: Governance cycle when detected.
        adoption_count: Number of adoptions in the cycle.
        escalation_count: Number of escalations in the cycle.
        adoption_ratio: The computed ratio (0.0 to 1.0).
        threshold: Threshold that was exceeded (0.50).
        severity: Alert severity (WARN or CRITICAL).
        trend_delta: Change from previous cycle (positive = increasing).
        adopting_kings: List of King UUIDs who performed adoptions.
        created_at: When alert was created (UTC).
        resolved_at: When alert was resolved (if applicable).
        status: Alert status (ACTIVE or RESOLVED).
    """

    alert_id: str = Field(
        ...,
        description="Unique alert identifier",
    )
    realm_id: str = Field(
        ...,
        description="Realm with excessive adoption ratio",
    )
    cycle_id: str = Field(
        ...,
        description="Governance cycle when detected",
    )
    adoption_count: int = Field(
        ...,
        description="Number of adoptions in the cycle",
        ge=0,
    )
    escalation_count: int = Field(
        ...,
        description="Number of escalations in the cycle",
        ge=1,
    )
    adoption_ratio: float = Field(
        ...,
        description="The computed ratio (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    threshold: float = Field(
        ...,
        description="Threshold that was exceeded",
        ge=0.0,
        le=1.0,
    )
    severity: str = Field(
        ...,
        description="Alert severity (WARN or CRITICAL)",
    )
    trend_delta: float | None = Field(
        None,
        description="Change from previous cycle (positive = increasing)",
    )
    adopting_kings: list[str] = Field(
        default_factory=list,
        description="List of King UUIDs who performed adoptions",
    )
    created_at: datetime = Field(
        ...,
        description="When alert was created (UTC)",
    )
    resolved_at: datetime | None = Field(
        None,
        description="When alert was resolved (if applicable)",
    )
    status: str = Field(
        ...,
        description="Alert status (ACTIVE or RESOLVED)",
    )


class RealmAdoptionRatioStatusResponse(BaseModel):
    """Response model for a single realm's adoption ratio status.

    Attributes:
        realm_id: Realm identifier.
        metrics: Current adoption ratio metrics (may be None if no data).
        active_alert: Active alert for this realm (may be None).
    """

    realm_id: str = Field(
        ...,
        description="Realm identifier",
    )
    metrics: AdoptionRatioMetricsResponse | None = Field(
        None,
        description="Current adoption ratio metrics (None if no data)",
    )
    active_alert: AdoptionRatioAlertResponse | None = Field(
        None,
        description="Active alert for this realm (None if no alert)",
    )


class AdoptionRatioDashboardResponse(BaseModel):
    """Response model for the adoption ratio dashboard.

    Provides High Archon with visibility into adoption patterns across realms.

    Attributes:
        cycle_id: Current governance cycle identifier.
        total_realms_with_data: Number of realms with adoption data.
        realms_exceeding_threshold: Number of realms exceeding 50% threshold.
        realms_critical: Number of realms at critical level (>70%).
        active_alerts_count: Total count of active alerts.
        realm_metrics: List of per-realm adoption ratio status.
        active_alerts: List of all active alerts.
        data_refreshed_at: When this dashboard data was computed.
    """

    cycle_id: str = Field(
        ...,
        description="Current governance cycle identifier",
    )
    total_realms_with_data: int = Field(
        ...,
        description="Number of realms with adoption data",
        ge=0,
    )
    realms_exceeding_threshold: int = Field(
        ...,
        description="Number of realms exceeding 50% threshold (PREVENT-7)",
        ge=0,
    )
    realms_critical: int = Field(
        ...,
        description="Number of realms at critical level (>70%)",
        ge=0,
    )
    active_alerts_count: int = Field(
        ...,
        description="Total count of active alerts",
        ge=0,
    )
    realm_metrics: list[RealmAdoptionRatioStatusResponse] = Field(
        default_factory=list,
        description="List of per-realm adoption ratio status",
    )
    active_alerts: list[AdoptionRatioAlertResponse] = Field(
        default_factory=list,
        description="List of all active alerts",
    )
    data_refreshed_at: datetime = Field(
        ...,
        description="When this dashboard data was computed",
    )


class AdoptionRatioErrorResponse(BaseModel):
    """Error response for adoption ratio endpoints.

    Attributes:
        detail: Error message describing what went wrong.
    """

    detail: str = Field(
        ...,
        description="Error message",
    )
