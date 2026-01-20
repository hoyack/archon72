"""Failure prevention API endpoints (Story 8.8, FR106-FR107).

Provides endpoints for failure mode monitoring, early warnings, and health dashboard.

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.api.models.failure_prevention import (
    AcknowledgeWarningRequest,
    AcknowledgeWarningResponse,
    DashboardResponse,
    EarlyWarningResponse,
    FailureModeResponse,
    HealthSummaryResponse,
    LoadSheddingResponse,
    MetricUpdateRequest,
    MetricUpdateResponse,
    PatternViolationResponse,
    PatternViolationScanResponse,
    QueryPerformanceResponse,
)
from src.application.ports.failure_mode_registry import FailureModeRegistryPort
from src.application.services.failure_prevention_service import FailurePreventionService
from src.application.services.load_shedding_service import LoadSheddingService
from src.application.services.pattern_violation_service import PatternViolationService
from src.application.services.query_performance_service import QueryPerformanceService
from src.domain.models.failure_mode import FailureModeId

router = APIRouter(prefix="/v1/failure-prevention", tags=["failure-prevention"])

# Placeholder for dependency injection
_failure_prevention_service: FailurePreventionService | None = None
_query_performance_service: QueryPerformanceService | None = None
_load_shedding_service: LoadSheddingService | None = None
_pattern_violation_service: PatternViolationService | None = None


def get_failure_prevention_service() -> FailurePreventionService:
    """Get the failure prevention service.

    Returns:
        The configured FailurePreventionService.

    Raises:
        HTTPException: If service is not configured.
    """
    if _failure_prevention_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failure prevention service not configured",
        )
    return _failure_prevention_service


def get_query_performance_service() -> QueryPerformanceService:
    """Get the query performance service.

    Returns:
        The configured QueryPerformanceService.

    Raises:
        HTTPException: If service is not configured.
    """
    if _query_performance_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Query performance service not configured",
        )
    return _query_performance_service


def get_load_shedding_service() -> LoadSheddingService:
    """Get the load shedding service.

    Returns:
        The configured LoadSheddingService.

    Raises:
        HTTPException: If service is not configured.
    """
    if _load_shedding_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Load shedding service not configured",
        )
    return _load_shedding_service


def get_pattern_violation_service() -> PatternViolationService:
    """Get the pattern violation service.

    Returns:
        The configured PatternViolationService.

    Raises:
        HTTPException: If service is not configured.
    """
    if _pattern_violation_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pattern violation service not configured",
        )
    return _pattern_violation_service


def configure_failure_prevention_services(
    registry: FailureModeRegistryPort,
) -> None:
    """Configure failure prevention services.

    Args:
        registry: Port for failure mode storage.
    """
    global _failure_prevention_service, _query_performance_service
    global _load_shedding_service, _pattern_violation_service

    _failure_prevention_service = FailurePreventionService(registry=registry)
    _query_performance_service = QueryPerformanceService()
    _load_shedding_service = LoadSheddingService()
    _pattern_violation_service = PatternViolationService()


def reset_failure_prevention_services() -> None:
    """Reset failure prevention services (for testing)."""
    global _failure_prevention_service, _query_performance_service
    global _load_shedding_service, _pattern_violation_service
    _failure_prevention_service = None
    _query_performance_service = None
    _load_shedding_service = None
    _pattern_violation_service = None


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get failure prevention dashboard",
    description="Get the comprehensive failure prevention dashboard (AC1, AC3).",
)
async def get_dashboard(
    service: FailurePreventionService = Depends(get_failure_prevention_service),
) -> DashboardResponse:
    """Get the failure prevention dashboard (AC1, AC3).

    Returns current health status for all failure modes and active warnings.

    Returns:
        DashboardResponse with full dashboard data.
    """
    data = await service.get_dashboard_data()
    summary = await service.get_health_summary()
    warnings = await service.get_early_warnings()

    # Build failure mode responses
    mode_responses = []
    for mode_data in data["failure_modes"]:
        mode_responses.append(
            FailureModeResponse(
                id=mode_data["id"],
                description=mode_data["description"],
                severity=mode_data["severity"],
                mitigation=mode_data["mitigation"],
                adr_reference=mode_data.get("adr_reference"),
                owner=mode_data.get("owner"),
                status=mode_data["status"],
            )
        )

    # Build warning responses
    warning_responses = []
    for warning in warnings:
        warning_responses.append(
            EarlyWarningResponse(
                warning_id=str(warning.warning_id),
                mode_id=warning.mode_id.value,
                metric_name=warning.metric_name,
                current_value=warning.current_value,
                threshold=warning.threshold,
                threshold_type=warning.threshold_type,
                recommended_action=warning.recommended_action,
                timestamp=warning.timestamp,
                is_acknowledged=False,  # These are active warnings
            )
        )

    return DashboardResponse(
        health_summary=HealthSummaryResponse(
            overall_status=summary.overall_status.value,
            warning_count=summary.warning_count,
            critical_count=summary.critical_count,
            healthy_count=summary.healthy_count,
            active_warning_count=len(warnings),
            timestamp=summary.timestamp,
        ),
        failure_modes=mode_responses,
        active_warnings=warning_responses,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/health",
    response_model=HealthSummaryResponse,
    summary="Get health summary",
    description="Get overall health summary across all failure modes (AC1).",
)
async def get_health_summary(
    service: FailurePreventionService = Depends(get_failure_prevention_service),
) -> HealthSummaryResponse:
    """Get overall health summary (AC1).

    Returns the aggregated health status across all failure modes.

    Returns:
        HealthSummaryResponse with overall status.
    """
    summary = await service.get_health_summary()
    warnings = await service.get_early_warnings()

    return HealthSummaryResponse(
        overall_status=summary.overall_status.value,
        warning_count=summary.warning_count,
        critical_count=summary.critical_count,
        healthy_count=summary.healthy_count,
        active_warning_count=len(warnings),
        timestamp=summary.timestamp,
    )


@router.get(
    "/modes",
    response_model=list[FailureModeResponse],
    summary="List all failure modes",
    description="Get all registered failure modes with current status.",
)
async def list_failure_modes(
    service: FailurePreventionService = Depends(get_failure_prevention_service),
) -> list[FailureModeResponse]:
    """List all failure modes.

    Returns all registered failure modes with their current health status.

    Returns:
        List of FailureModeResponse for each mode.
    """
    modes = await service.get_all_failure_modes()
    responses = []

    for mode in modes:
        mode_status = await service.check_failure_mode(mode.id)
        responses.append(
            FailureModeResponse(
                id=mode.id.value,
                description=mode.description,
                severity=mode.severity.value,
                mitigation=mode.mitigation,
                adr_reference=mode.adr_reference,
                owner=mode.owner,
                status=mode_status.value,
            )
        )

    return responses


@router.get(
    "/modes/{mode_id}",
    response_model=FailureModeResponse,
    summary="Get a specific failure mode",
    description="Get details for a specific failure mode.",
)
async def get_failure_mode(
    mode_id: str = Path(description="Failure mode ID (e.g., VAL-1, PV-001)"),
    service: FailurePreventionService = Depends(get_failure_prevention_service),
) -> FailureModeResponse:
    """Get a specific failure mode.

    Args:
        mode_id: The failure mode identifier.

    Returns:
        FailureModeResponse with mode details.

    Raises:
        HTTPException: If mode is not found.
    """
    try:
        fm_id = FailureModeId(mode_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown failure mode: {mode_id}",
        )

    mode = await service.get_failure_mode(fm_id)
    if mode is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failure mode not found: {mode_id}",
        )

    mode_status = await service.check_failure_mode(fm_id)

    return FailureModeResponse(
        id=mode.id.value,
        description=mode.description,
        severity=mode.severity.value,
        mitigation=mode.mitigation,
        adr_reference=mode.adr_reference,
        owner=mode.owner,
        status=mode_status.value,
    )


@router.post(
    "/modes/{mode_id}/metrics",
    response_model=MetricUpdateResponse,
    summary="Update failure mode metric",
    description="Record a new metric value for a failure mode.",
)
async def update_metric(
    request: MetricUpdateRequest,
    mode_id: str = Path(description="Failure mode ID"),
    service: FailurePreventionService = Depends(get_failure_prevention_service),
) -> MetricUpdateResponse:
    """Update a failure mode metric.

    Args:
        request: The metric update request.
        mode_id: The failure mode identifier.

    Returns:
        MetricUpdateResponse with update result.

    Raises:
        HTTPException: If mode is not found.
    """
    try:
        fm_id = FailureModeId(mode_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown failure mode: {mode_id}",
        )

    previous_status = await service.check_failure_mode(fm_id)
    new_status = await service.record_metric(fm_id, request.metric_name, request.value)

    # Check if warning was triggered
    warning_triggered = previous_status.value == "healthy" and new_status.value in (
        "warning",
        "critical",
    )

    return MetricUpdateResponse(
        mode_id=mode_id,
        metric_name=request.metric_name,
        previous_status=previous_status.value,
        current_status=new_status.value,
        warning_triggered=warning_triggered,
    )


@router.get(
    "/warnings",
    response_model=list[EarlyWarningResponse],
    summary="List active warnings",
    description="Get all active (unacknowledged) early warnings (AC2).",
)
async def list_warnings(
    service: FailurePreventionService = Depends(get_failure_prevention_service),
) -> list[EarlyWarningResponse]:
    """List all active warnings (AC2).

    Returns all unacknowledged early warning alerts.

    Returns:
        List of EarlyWarningResponse for active warnings.
    """
    warnings = await service.get_early_warnings()

    return [
        EarlyWarningResponse(
            warning_id=str(w.warning_id),
            mode_id=w.mode_id.value,
            metric_name=w.metric_name,
            current_value=w.current_value,
            threshold=w.threshold,
            threshold_type=w.threshold_type,
            recommended_action=w.recommended_action,
            timestamp=w.timestamp,
            is_acknowledged=False,
        )
        for w in warnings
    ]


@router.post(
    "/warnings/{warning_id}/acknowledge",
    response_model=AcknowledgeWarningResponse,
    summary="Acknowledge a warning",
    description="Acknowledge that a warning has been addressed.",
)
async def acknowledge_warning(
    request: AcknowledgeWarningRequest,
    warning_id: str = Path(description="Warning ID to acknowledge"),
    service: FailurePreventionService = Depends(get_failure_prevention_service),
) -> AcknowledgeWarningResponse:
    """Acknowledge a warning.

    Args:
        request: The acknowledgment request.
        warning_id: The warning ID to acknowledge.

    Returns:
        AcknowledgeWarningResponse with result.

    Raises:
        HTTPException: If warning is not found.
    """
    success = await service.acknowledge_warning(warning_id, request.acknowledged_by)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warning not found: {warning_id}",
        )

    return AcknowledgeWarningResponse(
        warning_id=warning_id,
        acknowledged_by=request.acknowledged_by,
        acknowledged_at=datetime.now(timezone.utc),
        success=True,
    )


@router.get(
    "/query-performance",
    response_model=QueryPerformanceResponse,
    summary="Get query performance stats",
    description="Get query performance compliance statistics (AC4, FR106).",
)
async def get_query_performance(
    service: QueryPerformanceService = Depends(get_query_performance_service),
) -> QueryPerformanceResponse:
    """Get query performance stats (AC4, FR106).

    Returns compliance statistics for query SLA monitoring.

    Returns:
        QueryPerformanceResponse with compliance stats.
    """
    stats = await service.get_compliance_stats()

    return QueryPerformanceResponse(
        total_queries=stats["total_queries"],
        compliant_queries=stats["compliant_queries"],
        non_compliant_queries=stats["non_compliant_queries"],
        compliance_rate=stats["compliance_rate"],
        sla_threshold_events=stats["sla_threshold_events"],
        sla_timeout_seconds=stats["sla_timeout_seconds"],
    )


@router.get(
    "/load-shedding",
    response_model=LoadSheddingResponse,
    summary="Get load shedding status",
    description="Get current load shedding status (AC5, FR107).",
)
async def get_load_shedding(
    service: LoadSheddingService = Depends(get_load_shedding_service),
) -> LoadSheddingResponse:
    """Get load shedding status (AC5, FR107).

    Returns current load level and shedding statistics.

    Returns:
        LoadSheddingResponse with load status.
    """
    stats = await service.get_shedding_stats()
    load_status = await service.get_load_status()

    return LoadSheddingResponse(
        current_load_level=load_status.level.value,
        current_load_percent=load_status.current_load,
        shedding_enabled=stats["shedding_enabled"],
        events_shed=stats["total_shed"],
        constitutional_events_protected=stats["constitutional_protected"],
    )


@router.get(
    "/pattern-violations",
    response_model=PatternViolationScanResponse,
    summary="Get pattern violations",
    description="Get detected pattern violations from FMEA analysis (AC6).",
)
async def get_pattern_violations(
    service: PatternViolationService = Depends(get_pattern_violation_service),
) -> PatternViolationScanResponse:
    """Get pattern violations (AC6).

    Returns all detected pattern violations from FMEA risk matrix.

    Returns:
        PatternViolationScanResponse with violations.
    """
    violations = service.detect_violations()
    stats = service.get_violation_stats()

    violation_responses = [
        PatternViolationResponse(
            violation_id=str(v.violation_id),
            violation_type=v.violation_type.value,
            location=v.location,
            description=v.description,
            severity=v.severity.value,
            is_resolved=v.is_resolved,
            blocks_deployment=v.blocks_deployment,
        )
        for v in violations
    ]

    return PatternViolationScanResponse(
        scan_id="current",
        timestamp=datetime.now(timezone.utc),
        files_scanned=0,  # Would be populated by actual scan
        scan_duration_ms=0,
        violations=violation_responses,
        critical_count=stats.get("by_severity", {}).get("critical", 0),
        blocking_count=stats["blocking_count"],
        blocks_deployment=stats["blocks_deployment"],
    )
