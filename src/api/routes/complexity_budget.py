"""Complexity budget API endpoints (Story 8.6, AC5).

Provides endpoints for the complexity budget dashboard and metrics.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event.
- SC-3: Self-consistency finding - complexity budget dashboard required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Optional

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.models.complexity_budget import (
    ComplexityBreachListResponse,
    ComplexityBreachResponse,
    ComplexityDashboardResponse,
    ComplexityMetricResponse,
    ComplexityTrendDataPoint,
    ComplexityTrendResponse,
)
from src.application.ports.complexity_budget_repository import (
    ComplexityBudgetRepositoryPort,
)
from src.application.ports.complexity_calculator import ComplexityCalculatorPort
from src.application.ports.halt_checker import HaltChecker
from src.application.services.complexity_budget_escalation_service import (
    ComplexityBudgetEscalationService,
)
from src.application.services.complexity_budget_service import (
    ComplexityBudgetService,
)
from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
    ComplexityDimension,
)

router = APIRouter(prefix="/v1/complexity", tags=["complexity"])

# Placeholder for dependency injection
# In production, these would be injected via FastAPI dependencies
_complexity_service: Optional[ComplexityBudgetService] = None
_escalation_service: Optional[ComplexityBudgetEscalationService] = None


def get_complexity_service() -> ComplexityBudgetService:
    """Get the complexity budget service.

    Returns:
        The configured ComplexityBudgetService.

    Raises:
        HTTPException: If service is not configured.
    """
    if _complexity_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Complexity budget service not configured",
        )
    return _complexity_service


def get_escalation_service() -> ComplexityBudgetEscalationService:
    """Get the complexity budget escalation service.

    Returns:
        The configured ComplexityBudgetEscalationService.

    Raises:
        HTTPException: If service is not configured.
    """
    if _escalation_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Complexity escalation service not configured",
        )
    return _escalation_service


def configure_complexity_services(
    calculator: ComplexityCalculatorPort,
    repository: ComplexityBudgetRepositoryPort,
    event_writer: EventWriterService,
    halt_checker: HaltChecker,
) -> None:
    """Configure complexity budget services.

    Args:
        calculator: Port for calculating complexity metrics.
        repository: Repository for complexity data storage.
        event_writer: Service for writing witnessed events.
        halt_checker: Interface to check system halt state.
    """
    global _complexity_service, _escalation_service

    _complexity_service = ComplexityBudgetService(
        calculator=calculator,
        repository=repository,
        event_writer=event_writer,
        halt_checker=halt_checker,
    )

    _escalation_service = ComplexityBudgetEscalationService(
        repository=repository,
        event_writer=event_writer,
        halt_checker=halt_checker,
    )


def reset_complexity_services() -> None:
    """Reset complexity services (for testing)."""
    global _complexity_service, _escalation_service
    _complexity_service = None
    _escalation_service = None


@router.get(
    "/dashboard",
    response_model=ComplexityDashboardResponse,
    summary="Get complexity dashboard",
    description="Get the current complexity budget dashboard with all metrics (AC1).",
)
async def get_dashboard(
    service: ComplexityBudgetService = Depends(get_complexity_service),
    escalation_service: ComplexityBudgetEscalationService = Depends(
        get_escalation_service
    ),
) -> ComplexityDashboardResponse:
    """Get the complexity budget dashboard (AC1, SC-3).

    Returns current values, limits, utilization percentages, and status
    for all complexity dimensions.

    Returns:
        ComplexityDashboardResponse with full dashboard data.
    """
    data = await service.get_dashboard_data()
    pending_escalations = await escalation_service.get_pending_escalations_count()

    return ComplexityDashboardResponse(
        adr_count=data["adr_count"],
        adr_limit=data["adr_limit"],
        adr_utilization=data["adr_utilization"],
        adr_status=data["adr_status"],
        ceremony_types=data["ceremony_types"],
        ceremony_type_limit=data["ceremony_type_limit"],
        ceremony_type_utilization=data["ceremony_type_utilization"],
        ceremony_type_status=data["ceremony_type_status"],
        cross_component_deps=data["cross_component_deps"],
        cross_component_dep_limit=data["cross_component_dep_limit"],
        cross_component_dep_utilization=data["cross_component_dep_utilization"],
        cross_component_dep_status=data["cross_component_dep_status"],
        overall_status=data["overall_status"],
        active_breaches=data["active_breaches"],
        pending_escalations=pending_escalations,
        last_updated=datetime.fromisoformat(data["last_updated"]),
    )


@router.get(
    "/metrics",
    response_model=list[ComplexityMetricResponse],
    summary="Get all complexity metrics",
    description="Get current values for all complexity dimensions (AC1).",
)
async def get_metrics(
    service: ComplexityBudgetService = Depends(get_complexity_service),
) -> list[ComplexityMetricResponse]:
    """Get all complexity metrics (AC1).

    Returns current values, limits, utilization, and status for each dimension.

    Returns:
        List of ComplexityMetricResponse for each dimension.
    """
    snapshot = await service.check_all_budgets()

    # Use get_budget() method to access budget details for each dimension
    adr_budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
    ceremony_budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
    deps_budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)

    return [
        ComplexityMetricResponse(
            dimension=ComplexityDimension.ADR_COUNT.value,
            current_value=snapshot.adr_count,
            limit=ADR_LIMIT,
            utilization=adr_budget.utilization_percent,
            status=adr_budget.status.value,
        ),
        ComplexityMetricResponse(
            dimension=ComplexityDimension.CEREMONY_TYPES.value,
            current_value=snapshot.ceremony_types,
            limit=CEREMONY_TYPE_LIMIT,
            utilization=ceremony_budget.utilization_percent,
            status=ceremony_budget.status.value,
        ),
        ComplexityMetricResponse(
            dimension=ComplexityDimension.CROSS_COMPONENT_DEPS.value,
            current_value=snapshot.cross_component_deps,
            limit=CROSS_COMPONENT_DEP_LIMIT,
            utilization=deps_budget.utilization_percent,
            status=deps_budget.status.value,
        ),
    ]


@router.get(
    "/breaches",
    response_model=ComplexityBreachListResponse,
    summary="List complexity breaches",
    description="List all complexity budget breaches (AC2, AC5).",
)
async def list_breaches(
    resolved: Annotated[
        Optional[bool],
        Query(description="Filter by resolution status"),
    ] = None,
    service: ComplexityBudgetService = Depends(get_complexity_service),
) -> ComplexityBreachListResponse:
    """List all complexity breaches (AC2, AC5).

    Args:
        resolved: Optional filter by resolution status.

    Returns:
        ComplexityBreachListResponse with breach events.
    """
    all_breaches = await service.get_all_breaches()
    unresolved = await service.get_unresolved_breaches()
    unresolved_ids = {b.breach_id for b in unresolved}

    # Filter if requested
    if resolved is True:
        filtered = [b for b in all_breaches if b.breach_id not in unresolved_ids]
    elif resolved is False:
        filtered = unresolved
    else:
        filtered = all_breaches

    breach_responses = [
        ComplexityBreachResponse(
            breach_id=str(b.breach_id),
            dimension=b.dimension.value,
            limit=b.limit,
            actual_value=b.actual_value,
            overage=b.actual_value - b.limit,
            breached_at=b.breached_at,
            requires_governance_ceremony=b.requires_governance_ceremony,
            is_resolved=b.breach_id not in unresolved_ids,
        )
        for b in filtered
    ]

    return ComplexityBreachListResponse(
        breaches=breach_responses,
        total_count=len(all_breaches),
        unresolved_count=len(unresolved),
    )


@router.get(
    "/trends",
    response_model=ComplexityTrendResponse,
    summary="Get complexity trends",
    description="Get historical complexity data for trend analysis (AC5).",
)
async def get_trends(
    start_date: Annotated[
        datetime,
        Query(description="Start of trend period"),
    ],
    end_date: Annotated[
        datetime,
        Query(description="End of trend period"),
    ],
    service: ComplexityBudgetService = Depends(get_complexity_service),
    escalation_service: ComplexityBudgetEscalationService = Depends(
        get_escalation_service
    ),
) -> ComplexityTrendResponse:
    """Get historical complexity trends (AC5).

    Args:
        start_date: Start of the trend period.
        end_date: End of the trend period.

    Returns:
        ComplexityTrendResponse with trend data points.
    """
    snapshots = await service.get_snapshots_in_range(start_date, end_date)
    all_breaches = await service.get_all_breaches()
    all_escalations = await escalation_service.get_all_escalations()

    # Count breaches and escalations in the date range
    breaches_in_range = [
        b for b in all_breaches
        if start_date <= b.breached_at <= end_date
    ]
    escalations_in_range = [
        e for e in all_escalations
        if start_date <= e.escalated_at <= end_date
    ]

    data_points = [
        ComplexityTrendDataPoint(
            timestamp=s.timestamp,
            adr_count=s.adr_count,
            ceremony_types=s.ceremony_types,
            cross_component_deps=s.cross_component_deps,
        )
        for s in snapshots
    ]

    return ComplexityTrendResponse(
        start_date=start_date,
        end_date=end_date,
        data_points=data_points,
        total_breaches=len(breaches_in_range),
        total_escalations=len(escalations_in_range),
    )
