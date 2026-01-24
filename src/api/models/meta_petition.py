"""META petition API models (Story 8.5, FR-10.4).

Pydantic models for META petition queue API endpoints.

Constitutional Constraints:
- FR-10.4: META petitions SHALL route to High Archon [P2]
- CT-12: Witnessing creates accountability -> Resolution details required
- CT-13: Explicit consent -> Disposition is explicit action
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MetaDispositionEnum(str, Enum):
    """Disposition options for META petition resolution (AC4)."""

    ACKNOWLEDGE = "ACKNOWLEDGE"
    CREATE_ACTION = "CREATE_ACTION"
    FORWARD = "FORWARD"


class MetaPetitionStatusEnum(str, Enum):
    """Status of a META petition in the queue."""

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"


class MetaPetitionQueueItemResponse(BaseModel):
    """Response model for a META petition queue item."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                "submitter_id": "550e8400-e29b-41d4-a716-446655440001",
                "petition_text": "The petition deliberation timeout of 72 hours is too short for complex governance decisions.",
                "received_at": "2026-01-22T10:30:00Z",
                "status": "PENDING",
            }
        }
    )

    petition_id: UUID = Field(
        description="UUID of the META petition"
    )
    submitter_id: Optional[UUID] = Field(
        default=None,
        description="UUID of the petition submitter (may be None for anonymous)"
    )
    petition_text: str = Field(
        description="Full text of the META petition"
    )
    received_at: datetime = Field(
        description="When the petition was received in the queue (UTC)"
    )
    status: MetaPetitionStatusEnum = Field(
        description="Current status: PENDING or RESOLVED"
    )


class MetaPetitionQueueResponse(BaseModel):
    """Response model for listing pending META petitions (AC3)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                        "submitter_id": "550e8400-e29b-41d4-a716-446655440001",
                        "petition_text": "The petition system needs better error handling.",
                        "received_at": "2026-01-22T10:30:00Z",
                        "status": "PENDING",
                    }
                ],
                "total_count": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    items: list[MetaPetitionQueueItemResponse] = Field(
        description="List of pending META petitions (oldest first, FIFO)"
    )
    total_count: int = Field(
        ge=0,
        description="Total number of pending META petitions"
    )
    limit: int = Field(
        ge=1,
        le=100,
        description="Maximum items returned per page"
    )
    offset: int = Field(
        ge=0,
        description="Number of items skipped for pagination"
    )


class ResolveMetaPetitionRequest(BaseModel):
    """Request model for resolving a META petition (AC4)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "disposition": "ACKNOWLEDGE",
                "rationale": "Acknowledged the feedback regarding petition timeouts. Will monitor for patterns.",
            }
        }
    )

    disposition: MetaDispositionEnum = Field(
        description="Resolution disposition: ACKNOWLEDGE, CREATE_ACTION, or FORWARD"
    )
    rationale: str = Field(
        min_length=10,
        description="High Archon's rationale for the resolution (min 10 characters)"
    )
    forward_target: Optional[str] = Field(
        default=None,
        description="Target governance body (required if disposition is FORWARD)"
    )


class ResolveMetaPetitionResponse(BaseModel):
    """Response model for META petition resolution (AC4)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                "disposition": "ACKNOWLEDGE",
                "rationale": "Acknowledged the feedback regarding petition timeouts.",
                "high_archon_id": "550e8400-e29b-41d4-a716-446655440002",
                "resolved_at": "2026-01-22T11:00:00Z",
                "forward_target": None,
            }
        }
    )

    success: bool = Field(
        description="Whether the resolution was successful"
    )
    petition_id: UUID = Field(
        description="UUID of the resolved META petition"
    )
    disposition: MetaDispositionEnum = Field(
        description="Resolution disposition applied"
    )
    rationale: str = Field(
        description="High Archon's rationale"
    )
    high_archon_id: UUID = Field(
        description="UUID of the High Archon who resolved"
    )
    resolved_at: datetime = Field(
        description="When the resolution occurred (UTC)"
    )
    forward_target: Optional[str] = Field(
        default=None,
        description="Target governance body (if disposition is FORWARD)"
    )


class MetaPetitionErrorResponse(BaseModel):
    """Error response model for META petition operations."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "META petition not found in queue: 550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )

    detail: str = Field(
        description="Error message describing what went wrong"
    )
