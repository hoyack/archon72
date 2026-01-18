"""Incident Report API routes (Story 8.4, FR54, FR145, FR147).

FastAPI router for incident report endpoints.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
- CT-11: HALT CHECK FIRST - Service handles halt for writes
- CT-13: Reads allowed during halt

Developer Golden Rules:
1. HALT CHECK FIRST - Service handles halt for writes
2. WITNESS EVERYTHING - Events written via EventWriterService
3. FAIL LOUD - Return meaningful error responses
4. READS DURING HALT - List/get/published endpoints work during halt (CT-13)
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.models.incident import (
    IncidentDetailResponse,
    IncidentErrorResponse,
    IncidentSummaryResponse,
    ListIncidentsResponse,
    PendingPublicationResponse,
    PublishedIncidentsResponse,
    TimelineEntryResponse,
)
from src.application.services.incident_reporting_service import (
    IncidentReportingService,
)
from src.domain.models.incident_report import IncidentStatus, IncidentType

router = APIRouter(prefix="/v1/incidents", tags=["incidents"])


# =============================================================================
# Dependency Injection Placeholder
# =============================================================================
# In production, this would be replaced with proper DI from the FastAPI app
# For now, we raise NotImplementedError as a placeholder


async def get_incident_service() -> IncidentReportingService:
    """Get incident reporting service instance.

    This is a placeholder dependency. In production, this would be
    configured via FastAPI dependency injection with proper service
    instantiation.

    Raises:
        NotImplementedError: Until proper DI is configured.
    """
    # TODO: Replace with actual service instantiation
    raise NotImplementedError(
        "IncidentReportingService dependency not configured. "
        "Configure this in src/api/dependencies/incident.py"
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _incident_to_summary(incident) -> IncidentSummaryResponse:
    """Convert domain IncidentReport to IncidentSummaryResponse."""
    return IncidentSummaryResponse(
        incident_id=incident.incident_id,
        incident_type=incident.incident_type.value,
        title=incident.title,
        status=incident.status.value,
        created_at=incident.created_at,
        resolution_at=incident.resolution_at,
    )


def _incident_to_detail(incident) -> IncidentDetailResponse:
    """Convert domain IncidentReport to IncidentDetailResponse."""
    return IncidentDetailResponse(
        incident_id=incident.incident_id,
        incident_type=incident.incident_type.value,
        title=incident.title,
        status=incident.status.value,
        timeline=[
            TimelineEntryResponse(
                timestamp=entry.timestamp,
                description=entry.description,
                event_id=entry.event_id,
                actor=entry.actor,
            )
            for entry in incident.timeline
        ],
        cause=incident.cause,
        impact=incident.impact,
        response=incident.response,
        prevention_recommendations=incident.prevention_recommendations,
        related_event_ids=incident.related_event_ids,
        created_at=incident.created_at,
        resolution_at=incident.resolution_at,
        published_at=incident.published_at,
        redacted_fields=incident.redacted_fields,
        content_hash=incident.content_hash(),
    )


def _parse_incident_type(type_str: str | None) -> IncidentType | None:
    """Parse incident type string to enum."""
    if type_str is None:
        return None
    try:
        return IncidentType(type_str)
    except ValueError:
        return None


def _parse_incident_status(status_str: str | None) -> IncidentStatus | None:
    """Parse incident status string to enum."""
    if status_str is None:
        return None
    try:
        return IncidentStatus(status_str)
    except ValueError:
        return None


# =============================================================================
# Incident Endpoints
# =============================================================================


@router.get(
    "/published",
    response_model=PublishedIncidentsResponse,
    summary="List published incidents",
    description=(
        "List all published incident reports. "
        "Published incidents are publicly available for external verification. "
        "Public access - no authentication required. "
        "Works during halt (read operation). "
        "FR147, CT-13."
    ),
)
async def list_published_incidents(
    request: Request,
    incident_service: IncidentReportingService = Depends(get_incident_service),
) -> PublishedIncidentsResponse:
    """List published incidents (FR147).

    Constitutional Constraints:
    - FR147: Incident reports publicly available within 7 days of resolution
    - CT-13: Read operations work during halt
    """
    incidents = await incident_service.get_published_incidents()

    return PublishedIncidentsResponse(
        incidents=[_incident_to_detail(i) for i in incidents],
        total=len(incidents),
    )


@router.get(
    "/pending",
    response_model=PendingPublicationResponse,
    summary="List incidents pending publication",
    description=(
        "List incident reports that are eligible for publication. "
        "These are resolved incidents where 7+ days have passed. "
        "Public access - no authentication required. "
        "Works during halt (read operation). "
        "FR147, CT-13."
    ),
)
async def list_pending_incidents(
    request: Request,
    incident_service: IncidentReportingService = Depends(get_incident_service),
) -> PendingPublicationResponse:
    """List incidents pending publication (FR147).

    Constitutional Constraints:
    - FR147: 7-day delay before publication
    - CT-13: Read operations work during halt
    """
    incidents = await incident_service.get_incidents_eligible_for_publication()

    return PendingPublicationResponse(
        incidents=[_incident_to_summary(i) for i in incidents],
        total=len(incidents),
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    responses={
        404: {"model": IncidentErrorResponse, "description": "Incident not found"},
    },
    summary="Get incident details",
    description=(
        "Get detailed information about a specific incident. "
        "Public access - no authentication required. "
        "Works during halt (read operation). "
        "FR147, CT-13."
    ),
)
async def get_incident(
    incident_id: UUID,
    request: Request,
    incident_service: IncidentReportingService = Depends(get_incident_service),
) -> IncidentDetailResponse:
    """Get incident details (FR147).

    Constitutional Constraints:
    - FR147: Incident reports publicly available
    - CT-13: Read operations work during halt
    """
    incident = await incident_service.get_incident_by_id(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://archon72.io/errors/incident-not-found",
                "title": "Incident Not Found",
                "status": 404,
                "detail": f"Incident {incident_id} not found",
                "instance": str(request.url),
            },
        )

    return _incident_to_detail(incident)


@router.get(
    "",
    response_model=ListIncidentsResponse,
    summary="Query incidents",
    description=(
        "Query incident reports with optional filters. "
        "Supports filtering by type, date range, and status. "
        "Public access - no authentication required. "
        "Works during halt (read operation). "
        "FR147, AC: 5, CT-13."
    ),
)
async def query_incidents(
    request: Request,
    incident_service: IncidentReportingService = Depends(get_incident_service),
    incident_type: Annotated[
        str | None,
        Query(description="Filter by incident type (halt, fork, override_threshold)"),
    ] = None,
    start_date: Annotated[
        datetime | None,
        Query(description="Filter by created_at >= start_date (ISO 8601)"),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(description="Filter by created_at <= end_date (ISO 8601)"),
    ] = None,
    status: Annotated[
        str | None,
        Query(
            description="Filter by status (draft, pending_publication, published, redacted)"
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListIncidentsResponse:
    """Query incidents with filters (AC: 5).

    Constitutional Constraints:
    - FR147: Public access to incident reports
    - AC: 5 - Query API with type, date filters
    - CT-13: Read operations work during halt
    """
    # Parse filter enums
    parsed_type = _parse_incident_type(incident_type)
    parsed_status = _parse_incident_status(status)

    # Query incidents
    incidents = await incident_service.query_incidents(
        incident_type=parsed_type,
        start_date=start_date,
        end_date=end_date,
        status=parsed_status,
    )

    # Apply pagination (service returns all matching)
    total = len(incidents)
    paginated = incidents[offset : offset + limit]

    return ListIncidentsResponse(
        incidents=[_incident_to_summary(i) for i in paginated],
        total=total,
        limit=limit,
        offset=offset,
    )
