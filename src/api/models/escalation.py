"""API models for escalation queue endpoints (Story 6.1, FR-5.4).

Pydantic models for request/response payloads of the King escalation queue API.

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- D8: Keyset pagination compliance
- RULING-3: Realm-scoped data access
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class EscalationSourceEnum(str, Enum):
    """Source that triggered the escalation (FR-5.4).

    Values:
        DELIBERATION: Three Fates deliberation decided ESCALATE
        CO_SIGNER_THRESHOLD: Auto-escalation from co-signer count
        KNIGHT_RECOMMENDATION: Knight recommended escalation
    """

    DELIBERATION = "DELIBERATION"
    CO_SIGNER_THRESHOLD = "CO_SIGNER_THRESHOLD"
    KNIGHT_RECOMMENDATION = "KNIGHT_RECOMMENDATION"


class PetitionTypeEnum(str, Enum):
    """Type of petition (FR-10.1).

    Values:
        GENERAL: General governance petition
        CESSATION: Request for system cessation review
        GRIEVANCE: Complaint about system behavior
        COLLABORATION: Request for inter-realm collaboration
    """

    GENERAL = "GENERAL"
    CESSATION = "CESSATION"
    GRIEVANCE = "GRIEVANCE"
    COLLABORATION = "COLLABORATION"


class EscalationQueueItemResponse(BaseModel):
    """A single item in the King's escalation queue response (FR-5.4).

    Attributes:
        petition_id: UUID of the escalated petition
        petition_type: Type of petition
        escalation_source: What triggered the escalation
        co_signer_count: Number of co-signers (for visibility)
        escalated_at: When the petition was escalated (ISO 8601 UTC)
    """

    petition_id: UUID = Field(
        ...,
        description="UUID of the escalated petition",
    )
    petition_type: PetitionTypeEnum = Field(
        ...,
        description="Type of petition (CESSATION, GRIEVANCE, etc.)",
    )
    escalation_source: EscalationSourceEnum = Field(
        ...,
        description="What triggered the escalation",
    )
    co_signer_count: int = Field(
        ...,
        description="Number of co-signers",
        ge=0,
    )
    escalated_at: datetime = Field(
        ...,
        description="When the petition was escalated (ISO 8601 UTC)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                "petition_type": "CESSATION",
                "escalation_source": "CO_SIGNER_THRESHOLD",
                "co_signer_count": 150,
                "escalated_at": "2026-01-20T12:00:00Z",
            }
        }


class EscalationQueueResponse(BaseModel):
    """Response for King's escalation queue query (FR-5.4, D8).

    Uses keyset pagination for efficient cursor-based navigation.

    Attributes:
        items: List of escalated petitions in FIFO order
        next_cursor: Cursor for next page (null if no more items)
        has_more: Whether there are more items after this page
    """

    items: list[EscalationQueueItemResponse] = Field(
        ...,
        description="List of escalated petitions in FIFO order (oldest first)",
    )
    next_cursor: str | None = Field(
        None,
        description="Cursor for next page (null if no more items)",
    )
    has_more: bool = Field(
        ...,
        description="Whether there are more items after this page",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                        "petition_type": "CESSATION",
                        "escalation_source": "CO_SIGNER_THRESHOLD",
                        "co_signer_count": 150,
                        "escalated_at": "2026-01-20T12:00:00Z",
                    }
                ],
                "next_cursor": "ZXhhbXBsZS1jdXJzb3I=",
                "has_more": True,
            }
        }


class EscalationQueueErrorResponse(BaseModel):
    """RFC 7807 error response with governance extensions.

    Attributes:
        type: URI identifying the problem type
        title: Short human-readable summary
        status: HTTP status code
        detail: Human-readable explanation
        instance: URI reference identifying the specific occurrence
    """

    type: str = Field(
        ...,
        description="URI identifying the problem type",
    )
    title: str = Field(
        ...,
        description="Short human-readable summary",
    )
    status: int = Field(
        ...,
        description="HTTP status code",
        ge=100,
        le=599,
    )
    detail: str = Field(
        ...,
        description="Human-readable explanation",
    )
    instance: str = Field(
        ...,
        description="URI reference identifying the specific occurrence",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "https://archon.example.com/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "Escalation queue access is not permitted during system halt",
                "instance": "/api/v1/kings/550e8400-e29b-41d4-a716-446655440000/escalations",
            }
        }
