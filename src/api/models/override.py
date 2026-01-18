"""Override API response models (Story 5.3, FR25).

Pydantic models for the public override visibility API endpoints.
These models expose all override data for public transparency.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: Public read access without registration
- FR48: Rate limits identical for anonymous and authenticated
- CT-12: Witnessing creates accountability - witness attribution visible
- CT-11: Silent failure destroys legitimacy - errors must be visible

CRITICAL: Keeper identity is NOT anonymized per FR25.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer

from src.api.models.observer import PaginationMetadata

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(lambda v: v.isoformat() + "Z" if v else None, return_type=str),
]


class OverrideEventResponse(BaseModel):
    """Single override event response for public transparency (FR25).

    CRITICAL: Keeper identity is NOT anonymized per FR25 requirement.
    All override data is fully visible to support public accountability.

    Constitutional Constraints:
    - FR25: All overrides SHALL be publicly visible
    - FR44: No authentication required
    - CT-12: Witnessing creates accountability

    Attributes:
        override_id: Unique identifier for this override event.
        keeper_id: Keeper identity (VISIBLE per FR25 - NOT anonymized).
        scope: What is being overridden.
        duration: Duration in seconds.
        reason: Human-readable override reason.
        action_type: Type of override action.
        initiated_at: When the override was initiated (UTC).
        expires_at: When the override expires (calculated).
        event_hash: Content hash for verification.
        sequence: Event sequence number.
        witness_id: Witness attribution (CT-12 compliance).
    """

    override_id: UUID = Field(description="Unique override event identifier")
    keeper_id: str = Field(
        description="Keeper identity - VISIBLE per FR25 (NOT anonymized)"
    )
    scope: str = Field(description="What is being overridden")
    duration: int = Field(description="Duration in seconds", ge=1)
    reason: str = Field(description="Override reason (FR28 enumerated)")
    action_type: str = Field(description="Type of override action")
    initiated_at: DateTimeWithZ = Field(description="When initiated (UTC)")
    expires_at: DateTimeWithZ = Field(description="When expires (calculated)")
    event_hash: str = Field(description="Content hash for verification")
    sequence: int = Field(description="Event sequence number", ge=1)
    witness_id: str | None = Field(
        default=None, description="Witness attribution (CT-12)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "override_id": "550e8400-e29b-41d4-a716-446655440000",
                "keeper_id": "keeper-alpha-001",
                "scope": "agent_pool_size",
                "duration": 3600,
                "reason": "EMERGENCY_RESPONSE",
                "action_type": "CONFIG_CHANGE",
                "initiated_at": "2026-01-07T10:30:00Z",
                "expires_at": "2026-01-07T11:30:00Z",
                "event_hash": "a" * 64,
                "sequence": 42,
                "witness_id": "witness-001",
            }
        },
    }


class OverrideEventsListResponse(BaseModel):
    """List response for override events query (FR25).

    Provides paginated list of all public overrides with full visibility.

    Constitutional Constraints:
    - FR25: All overrides publicly visible
    - FR44: No authentication required

    Attributes:
        overrides: List of override event responses.
        pagination: Pagination metadata (reused from observer API).
    """

    overrides: list[OverrideEventResponse]
    pagination: PaginationMetadata

    model_config = {
        "json_schema_extra": {
            "example": {
                "overrides": [
                    {
                        "override_id": "550e8400-e29b-41d4-a716-446655440000",
                        "keeper_id": "keeper-alpha-001",
                        "scope": "agent_pool_size",
                        "duration": 3600,
                        "reason": "EMERGENCY_RESPONSE",
                        "action_type": "CONFIG_CHANGE",
                        "initiated_at": "2026-01-07T10:30:00Z",
                        "expires_at": "2026-01-07T11:30:00Z",
                        "event_hash": "a" * 64,
                        "sequence": 42,
                        "witness_id": "witness-001",
                    }
                ],
                "pagination": {
                    "total_count": 100,
                    "offset": 0,
                    "limit": 100,
                    "has_more": False,
                },
            }
        },
    }
