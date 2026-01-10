"""Waiver API request/response models (Story 9.8, SC-4, SR-10).

Pydantic models for the constitutional waiver API endpoints.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- FR44: Public read access without authentication
- CT-12: Witnessing creates accountability - all actions have attribution
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(lambda v: v.isoformat() + "Z" if v else None, return_type=str),
]


class WaiverResponse(BaseModel):
    """Response model for a single waiver (SC-4, SR-10).

    Constitutional Constraints:
    - SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
    - SR-10: CT-15 waiver documentation -> Must be explicit
    - FR44: Public read access without authentication

    Attributes:
        waiver_id: Unique identifier for this waiver.
        constitutional_truth_id: The CT being waived (e.g., "CT-15").
        constitutional_truth_statement: Full text of the CT being waived.
        what_is_waived: Description of waived requirement.
        rationale: Detailed reason for the waiver.
        target_phase: When the requirement will be addressed.
        status: Current status (ACTIVE, IMPLEMENTED, CANCELLED).
        documented_at: When the waiver was created (ISO 8601).
        documented_by: Agent/system that documented the waiver.
    """

    waiver_id: str = Field(
        ...,
        description="Unique identifier for this waiver",
        examples=["CT-15-MVP-WAIVER"],
    )
    constitutional_truth_id: str = Field(
        ...,
        description="The Constitutional Truth being waived",
        examples=["CT-15"],
    )
    constitutional_truth_statement: str = Field(
        ...,
        description="Full text of the CT being waived",
        examples=["Legitimacy requires consent"],
    )
    what_is_waived: str = Field(
        ...,
        description="Description of what requirement is waived",
    )
    rationale: str = Field(
        ...,
        description="Detailed reason for the waiver",
    )
    target_phase: str = Field(
        ...,
        description="When the requirement will be addressed",
        examples=["Phase 2 - Seeker Journey"],
    )
    status: str = Field(
        ...,
        description="Current status of the waiver",
        examples=["ACTIVE", "IMPLEMENTED", "CANCELLED"],
    )
    documented_at: DateTimeWithZ = Field(
        ...,
        description="When the waiver was created (ISO 8601)",
    )
    documented_by: str = Field(
        ...,
        description="Agent/system that documented the waiver",
    )


class WaiversListResponse(BaseModel):
    """Response model for listing waivers (SC-4, SR-10, FR44).

    Constitutional Constraints:
    - FR44: Public read access without authentication
    - AC3: Waiver accessible via API

    Attributes:
        waivers: List of waiver records.
        total_count: Total number of waivers returned.
    """

    waivers: list[WaiverResponse] = Field(
        default_factory=list,
        description="List of waiver records",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of waivers",
    )


class WaiverErrorResponse(BaseModel):
    """RFC 7807 compliant error response for waiver endpoints.

    Attributes:
        type: URI reference identifying the problem type.
        title: Short, human-readable summary.
        status: HTTP status code.
        detail: Human-readable explanation.
        instance: URI reference identifying the specific occurrence.
    """

    type: str = Field(
        ...,
        description="URI reference identifying the problem type",
        examples=["https://archon72.io/errors/waiver-not-found"],
    )
    title: str = Field(
        ...,
        description="Short, human-readable summary",
        examples=["Waiver Not Found"],
    )
    status: int = Field(
        ...,
        ge=400,
        le=599,
        description="HTTP status code",
    )
    detail: str = Field(
        ...,
        description="Human-readable explanation",
        examples=["Waiver with ID 'CT-15-MVP-WAIVER' was not found"],
    )
    instance: str = Field(
        ...,
        description="URI reference identifying the specific occurrence",
        examples=["/v1/waivers/CT-15-MVP-WAIVER"],
    )
