"""Petition Submission API request/response models (Story 1.1, FR-1.1, Story 7.2/7.3).

Pydantic models for the Three Fates petition submission API endpoints.

Constitutional Constraints:
- FR-1.1: Accept petition submissions via REST API
- FR-1.2: Generate UUIDv7 petition_id (using uuid4 for Python 3.11 compat)
- FR-1.3: Validate petition schema
- FR-1.6: Set initial state to RECEIVED
- FR-7.3: System SHALL notify Observer on fate assignment (Story 7.2)
- FR-7.5: Petitioner SHALL be able to withdraw petition before fate assignment (Story 7.3)
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
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, field_validator, model_validator

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(
        lambda v: v.isoformat().replace("+00:00", "Z") if v else None, return_type=str
    ),
]


class PetitionTypeEnum(str, Enum):
    """Petition type enumeration (FR-10.1, FR-10.4).

    Types:
        GENERAL: General governance petition
        CESSATION: Request for system cessation review
        GRIEVANCE: Complaint about system behavior
        COLLABORATION: Request for inter-realm collaboration
        META: Petition about the petition system itself (FR-10.4)
              Routes directly to High Archon, bypassing deliberation.
    """

    GENERAL = "GENERAL"
    CESSATION = "CESSATION"
    GRIEVANCE = "GRIEVANCE"
    COLLABORATION = "COLLABORATION"
    META = "META"


class NotificationChannelEnum(str, Enum):
    """Notification channel enumeration (Story 7.2, FR-7.3).

    Channels:
        WEBHOOK: HTTP POST to configured URL (HTTPS required)
        IN_APP: Store in notification queue for retrieval (future)
    """

    WEBHOOK = "WEBHOOK"
    IN_APP = "IN_APP"


class NotificationPreferencesRequest(BaseModel):
    """Notification preferences for fate assignment notifications (Story 7.2, FR-7.3).

    Constitutional Constraints:
    - FR-7.3: System SHALL notify Observer on fate assignment
    - D7: RFC 7807 error responses for invalid preferences

    Attributes:
        channel: Notification delivery channel (WEBHOOK, IN_APP).
        webhook_url: URL for webhook delivery (HTTPS only, required for WEBHOOK).
        enabled: Whether notifications are enabled (default: True).
    """

    channel: NotificationChannelEnum = Field(
        ...,
        description="Notification delivery channel (WEBHOOK or IN_APP)",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=2048,
        description="HTTPS URL for webhook delivery (required for WEBHOOK channel)",
    )
    enabled: bool = Field(
        default=True,
        description="Whether notifications are enabled",
    )

    @model_validator(mode="after")
    def validate_webhook_requirements(self) -> "NotificationPreferencesRequest":
        """Validate webhook URL is provided and HTTPS for WEBHOOK channel."""
        if self.channel == NotificationChannelEnum.WEBHOOK:
            if not self.webhook_url:
                raise ValueError("webhook_url is required for WEBHOOK channel")
            if not self.webhook_url.strip():
                raise ValueError("webhook_url cannot be empty")
            try:
                parsed = urlparse(self.webhook_url)
                if parsed.scheme.lower() != "https":
                    raise ValueError(
                        f"webhook_url must use HTTPS (got {parsed.scheme})"
                    )
                if not parsed.netloc:
                    raise ValueError("webhook_url must include host")
            except Exception as e:
                if "HTTPS" in str(e) or "host" in str(e):
                    raise
                raise ValueError(f"Invalid webhook_url: {e}") from e
        return self


class SubmitPetitionSubmissionRequest(BaseModel):
    """Request to submit a new petition to the Three Fates system (FR-1.1, FR-1.3, Story 7.2).

    Constitutional Constraints:
    - FR-1.3: Validate petition schema (type, text)
    - FR-7.3: System SHALL notify Observer on fate assignment (Story 7.2)
    - FR-10.1: Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types

    Attributes:
        type: Petition type (GENERAL, CESSATION, GRIEVANCE, COLLABORATION).
        text: Petition content (1-10,000 characters).
        realm: Optional routing realm identifier.
        submitter_id: Optional submitter identity (UUID).
        notification_preferences: Optional notification preferences for fate assignment (Story 7.2).
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
    submitter_id: UUID | None = Field(
        default=None,
        description="Optional submitter identity (UUID)",
    )
    notification_preferences: NotificationPreferencesRequest | None = Field(
        default=None,
        description="Optional notification preferences for fate assignment notifications (Story 7.2, FR-7.3)",
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
    """Status response for a petition submission (FR-7.1, FR-7.2, FR-7.4, Story 1.8, Story 7.1).

    Constitutional Constraints:
    - FR-7.1: Observer SHALL be able to query petition status by petition_id
    - FR-7.2: System SHALL return status_token for efficient long-poll (Story 7.1)
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
        status_token: Opaque token for efficient long-polling (FR-7.2, Story 7.1).
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
    status_token: str | None = Field(
        default=None,
        description="Opaque token for efficient long-polling (FR-7.2, Story 7.1). "
        "Use with GET /v1/petition-submissions/{petition_id}/status?token={status_token}",
    )


class WithdrawPetitionRequest(BaseModel):
    """Request to withdraw a petition before fate assignment (Story 7.3, FR-7.5).

    Constitutional Constraints:
    - FR-7.5: Petitioner SHALL be able to withdraw petition before fate assignment
    - Authorization: Only the original submitter can withdraw

    Attributes:
        requester_id: UUID of the person requesting withdrawal (must match submitter_id).
        reason: Optional explanation for withdrawal.
    """

    requester_id: UUID = Field(
        ...,
        description="UUID of the person requesting withdrawal (must match petition submitter_id)",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional explanation for withdrawal",
    )


class WithdrawPetitionResponse(BaseModel):
    """Response after withdrawing a petition (Story 7.3, FR-7.5).

    Constitutional Constraints:
    - FR-7.5: Petition transitions to ACKNOWLEDGED with WITHDRAWN reason code

    Attributes:
        petition_id: Unique identifier for the withdrawn petition.
        state: Terminal state (always "ACKNOWLEDGED").
        fate_reason: Reason code with rationale (always starts with "WITHDRAWN:").
        updated_at: When the petition was withdrawn (ISO 8601).
    """

    petition_id: UUID
    state: str = "ACKNOWLEDGED"
    fate_reason: str = Field(
        ...,
        description="Reason code with rationale (e.g., 'WITHDRAWN: User changed mind')",
    )
    updated_at: DateTimeWithZ
