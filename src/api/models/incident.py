"""Incident Report API request/response models (Story 8.4, FR54, FR145, FR147).

Pydantic models for the incident reporting API endpoints.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
- CT-13: Reads during halt always allowed - incident queries work during halt
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(lambda v: v.isoformat() + "Z" if v else None, return_type=str),
]


class TimelineEntryResponse(BaseModel):
    """Response model for a timeline entry.

    Attributes:
        timestamp: When this event occurred (ISO 8601).
        description: Human-readable description.
        event_id: Link to constitutional event (if applicable).
        actor: Attribution for who/what triggered this event.
    """

    timestamp: DateTimeWithZ
    description: str
    event_id: UUID | None = None
    actor: str | None = None


class IncidentSummaryResponse(BaseModel):
    """Summary response for incident list endpoint (FR147, AC: 5).

    Attributes:
        incident_id: Unique identifier for this incident.
        incident_type: Type of incident (halt, fork, override_threshold).
        title: Human-readable title.
        status: Current status (draft, pending_publication, published, redacted).
        created_at: When the incident was created (ISO 8601).
        resolution_at: When the incident was resolved (if applicable).
    """

    incident_id: UUID
    incident_type: str
    title: str
    status: str
    created_at: DateTimeWithZ
    resolution_at: DateTimeWithZ | None = None


class IncidentDetailResponse(BaseModel):
    """Detailed incident report response (FR147).

    Constitutional Constraints:
    - FR147: Published incident reports are publicly available
    - AC: 5 - Query API with type, date filters

    Attributes:
        incident_id: Unique identifier for this incident.
        incident_type: Type of incident (halt, fork, override_threshold).
        title: Human-readable title.
        status: Current status (draft, pending_publication, published, redacted).
        timeline: Chronological list of events during the incident.
        cause: Root cause analysis.
        impact: Description of the impact.
        response: How the incident was resolved (empty until resolved).
        prevention_recommendations: Steps to prevent recurrence.
        related_event_ids: Links to constitutional events involved.
        created_at: When the incident was created (ISO 8601).
        resolution_at: When the incident was resolved (if applicable).
        published_at: When the incident was published (if applicable).
        redacted_fields: List of field names that have been redacted.
        content_hash: SHA-256 hash of incident content (for verification).
    """

    incident_id: UUID
    incident_type: str
    title: str
    status: str
    timeline: list[TimelineEntryResponse]
    cause: str
    impact: str
    response: str
    prevention_recommendations: list[str]
    related_event_ids: list[UUID]
    created_at: DateTimeWithZ
    resolution_at: DateTimeWithZ | None = None
    published_at: DateTimeWithZ | None = None
    redacted_fields: list[str] = Field(default_factory=list)
    content_hash: str


class ListIncidentsResponse(BaseModel):
    """Response for listing incidents with pagination (FR147, AC: 5).

    Attributes:
        incidents: List of incident summaries.
        total: Total number of matching incidents.
        limit: Maximum incidents per page.
        offset: Offset from start.
    """

    incidents: list[IncidentSummaryResponse]
    total: int
    limit: int
    offset: int


class PublishedIncidentsResponse(BaseModel):
    """Response for listing published incidents (FR147).

    Published incidents are publicly available for external verification.

    Attributes:
        incidents: List of published incident details.
        total: Total number of published incidents.
    """

    incidents: list[IncidentDetailResponse]
    total: int


class IncidentQueryParams(BaseModel):
    """Query parameters for incident filtering (AC: 5).

    Attributes:
        incident_type: Filter by incident type (optional).
        start_date: Filter by created_at >= start_date (optional).
        end_date: Filter by created_at <= end_date (optional).
        status: Filter by status (optional).
        limit: Maximum results to return (default 50, max 100).
        offset: Offset for pagination (default 0).
    """

    incident_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class IncidentErrorResponse(BaseModel):
    """Error response for incident operations (RFC 7807).

    Attributes:
        type: Error type URI.
        title: Human-readable error title.
        status: HTTP status code.
        detail: Detailed error message.
        instance: Request path that caused the error.
    """

    type: str
    title: str
    status: int
    detail: str
    instance: str


class PendingPublicationResponse(BaseModel):
    """Response for incidents pending publication (FR147).

    Lists incidents that are resolved and eligible for publication
    (7+ days since creation).

    Attributes:
        incidents: List of incidents pending publication.
        total: Total number of pending incidents.
    """

    incidents: list[IncidentSummaryResponse]
    total: int
