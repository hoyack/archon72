"""Failure prevention API response models (Story 8.8, FR106-FR107).

Pydantic models for failure prevention dashboard, early warnings, and health endpoints.

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load
"""

from datetime import datetime

from pydantic import BaseModel, Field


class FailureModeResponse(BaseModel):
    """Response model for a single failure mode.

    Represents a pre-mortem identified failure scenario.

    Attributes:
        id: Failure mode identifier (VAL-*, PV-*).
        description: Human-readable description of the failure.
        severity: Severity level (critical, high, medium, low).
        mitigation: The prevention measure in place.
        adr_reference: Optional ADR reference.
        owner: Team/role responsible.
        status: Current health status (healthy, warning, critical).
    """

    id: str = Field(description="Failure mode identifier (VAL-*, PV-*)")
    description: str = Field(description="Description of the failure mode")
    severity: str = Field(description="Severity: critical, high, medium, low")
    mitigation: str = Field(description="Prevention measure in place")
    adr_reference: str | None = Field(default=None, description="ADR reference")
    owner: str | None = Field(default=None, description="Responsible team/role")
    status: str = Field(description="Current status: healthy, warning, critical")


class ThresholdResponse(BaseModel):
    """Response model for a threshold configuration.

    Represents monitoring threshold for a failure mode metric.

    Attributes:
        mode_id: The failure mode this threshold monitors.
        metric_name: Name of the monitored metric.
        warning_value: Value at which WARNING status is triggered.
        critical_value: Value at which CRITICAL status is triggered.
        current_value: Current measured value.
        status: Current threshold status.
        last_updated: When the current value was last updated.
    """

    mode_id: str = Field(description="Failure mode identifier")
    metric_name: str = Field(description="Name of the monitored metric")
    warning_value: float = Field(description="WARNING threshold")
    critical_value: float = Field(description="CRITICAL threshold")
    current_value: float = Field(description="Current metric value")
    status: str = Field(description="Current status: healthy, warning, critical")
    last_updated: datetime = Field(description="Last update timestamp")


class EarlyWarningResponse(BaseModel):
    """Response model for an early warning alert (AC2).

    Represents an alert generated when indicators approach failure thresholds.

    Attributes:
        warning_id: Unique identifier for this warning.
        mode_id: The failure mode that triggered this warning.
        metric_name: Name of the metric that triggered the warning.
        current_value: The metric value that triggered the warning.
        threshold: The threshold value that was breached.
        threshold_type: Whether this is a "warning" or "critical" threshold.
        recommended_action: What action should be taken.
        timestamp: When this warning was generated.
        is_acknowledged: Whether this warning has been acknowledged.
    """

    warning_id: str = Field(description="Unique warning identifier")
    mode_id: str = Field(description="Failure mode identifier")
    metric_name: str = Field(description="Metric that triggered the warning")
    current_value: float = Field(description="Current metric value")
    threshold: float = Field(description="Threshold that was breached")
    threshold_type: str = Field(description="warning or critical")
    recommended_action: str = Field(description="Recommended action")
    timestamp: datetime = Field(description="Warning timestamp")
    is_acknowledged: bool = Field(default=False, description="Whether acknowledged")


class HealthSummaryResponse(BaseModel):
    """Response model for overall health summary (AC1).

    Provides system-wide health status across all failure modes.

    Attributes:
        overall_status: The worst status across all modes.
        warning_count: Number of modes in WARNING state.
        critical_count: Number of modes in CRITICAL state.
        healthy_count: Number of modes in HEALTHY state.
        active_warning_count: Number of unacknowledged warnings.
        timestamp: When this summary was generated.
    """

    overall_status: str = Field(description="Overall system health status")
    warning_count: int = Field(description="Modes in WARNING state")
    critical_count: int = Field(description="Modes in CRITICAL state")
    healthy_count: int = Field(description="Modes in HEALTHY state")
    active_warning_count: int = Field(description="Unacknowledged warnings")
    timestamp: datetime = Field(description="Summary generation timestamp")


class DashboardResponse(BaseModel):
    """Response model for the failure prevention dashboard (AC1, AC3).

    Comprehensive view of all failure modes and their health.

    Attributes:
        health_summary: Overall health summary.
        failure_modes: List of all failure modes with current status.
        active_warnings: List of unacknowledged early warnings.
        timestamp: Dashboard generation timestamp.
    """

    health_summary: HealthSummaryResponse = Field(description="Overall health summary")
    failure_modes: list[FailureModeResponse] = Field(
        default_factory=list, description="All failure modes"
    )
    active_warnings: list[EarlyWarningResponse] = Field(
        default_factory=list, description="Active early warnings"
    )
    timestamp: datetime = Field(description="Dashboard generation timestamp")


class MetricUpdateRequest(BaseModel):
    """Request model for updating a failure mode metric.

    Attributes:
        metric_name: Name of the metric to update.
        value: New metric value.
    """

    metric_name: str = Field(description="Metric name")
    value: float = Field(description="New metric value")


class MetricUpdateResponse(BaseModel):
    """Response model for metric update result.

    Attributes:
        mode_id: The failure mode that was updated.
        metric_name: Name of the updated metric.
        previous_status: Status before update.
        current_status: Status after update.
        warning_triggered: Whether a warning was triggered.
    """

    mode_id: str = Field(description="Updated failure mode")
    metric_name: str = Field(description="Updated metric name")
    previous_status: str = Field(description="Status before update")
    current_status: str = Field(description="Status after update")
    warning_triggered: bool = Field(description="Whether warning was triggered")


class AcknowledgeWarningRequest(BaseModel):
    """Request model for acknowledging a warning.

    Attributes:
        acknowledged_by: Who is acknowledging the warning.
    """

    acknowledged_by: str = Field(description="Who is acknowledging")


class AcknowledgeWarningResponse(BaseModel):
    """Response model for warning acknowledgment.

    Attributes:
        warning_id: The acknowledged warning ID.
        acknowledged_by: Who acknowledged it.
        acknowledged_at: When it was acknowledged.
        success: Whether acknowledgment succeeded.
    """

    warning_id: str = Field(description="Acknowledged warning ID")
    acknowledged_by: str = Field(description="Who acknowledged")
    acknowledged_at: datetime = Field(description="Acknowledgment timestamp")
    success: bool = Field(description="Whether acknowledgment succeeded")


class QueryPerformanceResponse(BaseModel):
    """Response model for query performance stats (AC4, FR106).

    Attributes:
        total_queries: Total queries tracked.
        compliant_queries: Queries within SLA.
        non_compliant_queries: Queries exceeding SLA.
        compliance_rate: Percentage of compliant queries.
        sla_threshold_events: Event count SLA threshold.
        sla_timeout_seconds: Timeout SLA threshold.
    """

    total_queries: int = Field(description="Total queries tracked")
    compliant_queries: int = Field(description="Queries within SLA")
    non_compliant_queries: int = Field(description="Queries exceeding SLA")
    compliance_rate: float = Field(description="Percentage compliant")
    sla_threshold_events: int = Field(description="Event count SLA threshold")
    sla_timeout_seconds: float = Field(description="Timeout SLA threshold")


class LoadSheddingResponse(BaseModel):
    """Response model for load shedding status (AC5, FR107).

    Attributes:
        current_load_level: Current load level (normal, elevated, high, critical).
        current_load_percent: Current load percentage.
        shedding_enabled: Whether shedding is active.
        events_shed: Total events shed in current session.
        constitutional_events_protected: Constitutional events that were protected.
    """

    current_load_level: str = Field(description="Current load level")
    current_load_percent: float = Field(description="Current load percentage")
    shedding_enabled: bool = Field(description="Whether shedding is active")
    events_shed: int = Field(description="Events shed this session")
    constitutional_events_protected: int = Field(
        description="Constitutional events protected (FR107)"
    )


class PatternViolationResponse(BaseModel):
    """Response model for a pattern violation (AC6).

    Attributes:
        violation_id: Unique violation identifier.
        violation_type: Type of violation (PV-001, PV-002, PV-003).
        location: File/line where violation was detected.
        description: Description of the violation.
        severity: Violation severity.
        is_resolved: Whether violation has been resolved.
        blocks_deployment: Whether this blocks deployment.
    """

    violation_id: str = Field(description="Unique violation ID")
    violation_type: str = Field(description="Violation type")
    location: str = Field(description="Location of violation")
    description: str = Field(description="Violation description")
    severity: str = Field(description="Violation severity")
    is_resolved: bool = Field(description="Whether resolved")
    blocks_deployment: bool = Field(description="Whether blocks deployment")


class PatternViolationScanResponse(BaseModel):
    """Response model for pattern violation scan results (AC6).

    Attributes:
        scan_id: Unique scan identifier.
        timestamp: When scan was performed.
        files_scanned: Number of files scanned.
        scan_duration_ms: Scan duration in milliseconds.
        violations: List of detected violations.
        critical_count: Number of critical violations.
        blocking_count: Number of blocking violations.
        blocks_deployment: Whether deployment is blocked.
    """

    scan_id: str = Field(description="Unique scan ID")
    timestamp: datetime = Field(description="Scan timestamp")
    files_scanned: int = Field(description="Files scanned")
    scan_duration_ms: int = Field(description="Scan duration in ms")
    violations: list[PatternViolationResponse] = Field(
        default_factory=list, description="Detected violations"
    )
    critical_count: int = Field(description="Critical violations")
    blocking_count: int = Field(description="Blocking violations")
    blocks_deployment: bool = Field(description="Whether deployment blocked")
