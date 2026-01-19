"""Petition Submission API request/response models (Story 1.1, FR-1.1).

Pydantic models for the Three Fates petition submission API endpoints.

Constitutional Constraints:
- FR-1.1: Accept petition submissions via REST API
- FR-1.2: Generate UUIDv7 petition_id (using uuid4 for Python 3.11 compat)
- FR-1.3: Validate petition schema
- FR-1.6: Set initial state to RECEIVED
- FR-10.1: Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types
- CT-11: Silent failure destroys legitimacy - fail loud on errors
- CT-12: Witnessing creates accountability - all actions have attribution

Developer Golden Rules:
1. VALIDATE EARLY - Pydantic handles schema validation
2. FAIL LOUD - Invalid requests return 400 with RFC 7807
3. TYPE SAFETY - All fields typed, no Any
"""

from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, field_validator

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(lambda v: v.isoformat().replace("+00:00", "Z") if v else None, return_type=str),
]


class PetitionTypeEnum(str, Enum):
    """Petition type enumeration (FR-10.1).

    Types:
        GENERAL: General governance petition
        CESSATION: Request for system cessation review
        GRIEVANCE: Complaint about system behavior
        COLLABORATION: Request for inter-realm collaboration
    """

    GENERAL = "GENERAL"
    CESSATION = "CESSATION"
    GRIEVANCE = "GRIEVANCE"
    COLLABORATION = "COLLABORATION"


class SubmitPetitionSubmissionRequest(BaseModel):
    """Request to submit a new petition to the Three Fates system (FR-1.1, FR-1.3).

    Constitutional Constraints:
    - FR-1.3: Validate petition schema (type, text)
    - FR-10.1: Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types

    Attributes:
        type: Petition type (GENERAL, CESSATION, GRIEVANCE, COLLABORATION).
        text: Petition content (1-10,000 characters).
        realm: Optional routing realm identifier.
    """

    type: PetitionTypeEnum = Field(
        ...,
        description="Type of petition (GENERAL, CESSATION, GRIEVANCE, COLLABORATION)",
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Petition content (1-10,000 characters)",
    )
    realm: str | None = Field(
        default=None,
        max_length=100,
        description="Optional routing realm identifier",
    )

    @field_validator("text")
    @classmethod
    def validate_text_not_whitespace(cls, v: str) -> str:
        """Validate text is not only whitespace."""
        if not v.strip():
            raise ValueError("Petition text cannot be empty or whitespace only")
        return v


class SubmitPetitionSubmissionResponse(BaseModel):
    """Response after submitting a petition (FR-1.1, FR-1.2, FR-1.6).

    Constitutional Constraints:
    - FR-1.2: Returns generated petition_id
    - FR-1.6: State is always RECEIVED

    Attributes:
        petition_id: Unique identifier for the created petition.
        state: Initial state (always "RECEIVED").
        type: Petition type echoed back.
        content_hash: Base64-encoded Blake3 hash of content.
        realm: Assigned realm for petition routing.
        created_at: When the petition was created (ISO 8601).
    """

    petition_id: UUID
    state: str = "RECEIVED"
    type: PetitionTypeEnum
    content_hash: str = Field(..., description="Base64-encoded Blake3 hash")
    realm: str
    created_at: DateTimeWithZ


class PetitionSubmissionErrorResponse(BaseModel):
    """Error response for petition submission operations (RFC 7807).

    Implements RFC 7807 Problem Details for HTTP APIs.

    Attributes:
        type: Error type URI.
        title: Human-readable error title.
        status: HTTP status code.
        detail: Detailed error message.
        instance: Request path that caused the error.
    """

    type: str = Field(..., description="Error type URI")
    title: str = Field(..., description="Human-readable error title")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Detailed error message")
    instance: str = Field(..., description="Request path that caused the error")


class PetitionSubmissionStatusResponse(BaseModel):
    """Status response for a petition submission (FR-7.1, FR-7.4, Story 1.8).

    Constitutional Constraints:
    - FR-7.1: Observer SHALL be able to query petition status by petition_id
    - FR-7.4: System SHALL expose co_signer_count in status response
    - NFR-1.2: Status query latency p99 < 100ms

    Attributes:
        petition_id: Unique identifier for the petition.
        state: Current lifecycle state.
        type: Petition type.
        content_hash: Base64-encoded Blake3 hash.
        realm: Assigned realm.
        co_signer_count: Number of co-signers (FR-7.4).
        created_at: When the petition was created.
        updated_at: When the petition was last updated.
        fate_reason: Reason for fate assignment (only for terminal states).
    """

    petition_id: UUID
    state: str
    type: PetitionTypeEnum
    content_hash: str | None
    realm: str
    co_signer_count: int = Field(
        default=0,
        description="Number of co-signers for this petition (FR-7.4)",
    )
    created_at: DateTimeWithZ
    updated_at: DateTimeWithZ
    fate_reason: str | None = Field(
        default=None,
        description="Reason for fate assignment (only populated for terminal states)",
    )
