"""Co-Sign API request/response models (Story 5.2, Story 5.3, Story 5.4, Story 5.5, Story 5.6, FR-6.1, FR-6.5, FR-6.6, FR-5.1, FR-5.3).

Pydantic models for the Three Fates petition co-signing API endpoints.

Constitutional Constraints:
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.2: System SHALL reject duplicate co-signature (NFR-3.5)
- FR-6.3: System SHALL reject co-sign after fate assignment
- FR-6.4: System SHALL increment co-signer count atomically
- FR-6.5: System SHALL check escalation threshold on each co-sign
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- NFR-5.1: Rate limiting per identity: Configurable per type
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- CT-11: Silent failure destroys legitimacy - fail loud on errors, return 429 never silently drop
- CT-12: Witnessing creates accountability - all actions have attribution
- CT-14: Silence must be expensive - auto-escalation ensures collective petitions get King attention
- SYBIL-1: Identity verification + rate limiting per verified identity

Developer Golden Rules:
1. VALIDATE EARLY - Pydantic handles schema validation
2. FAIL LOUD - Invalid requests return 400/409/422/429 with RFC 7807
3. TYPE SAFETY - All fields typed, no Any
4. VERIFY IDENTITY - Check signer identity before accepting co-sign (NFR-5.2)
5. RATE LIMIT INFO - Include rate_limit_remaining and rate_limit_reset_at in success response (AC6)
6. THRESHOLD INFO - Include threshold_reached, threshold_value, petition_type in success response (Story 5.5)
7. ESCALATION INFO - Include escalation_triggered and escalation_id in success response (Story 5.6)
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(
        lambda v: v.isoformat().replace("+00:00", "Z") if v else None, return_type=str
    ),
]


class CoSignRequest(BaseModel):
    """Request to co-sign a petition (FR-6.1).

    Constitutional Constraints:
    - FR-6.1: Seeker SHALL be able to co-sign active petition

    Attributes:
        signer_id: UUID of the Seeker adding their support.
    """

    signer_id: UUID = Field(
        ...,
        description="UUID of the Seeker adding their support",
    )


class CoSignResponse(BaseModel):
    """Response after successfully co-signing a petition (FR-6.1, FR-6.4, FR-6.5, FR-6.6, FR-5.1, FR-5.3, CT-12, NFR-5.2).

    Constitutional Constraints:
    - FR-6.1: Co-sign successful
    - FR-6.4: co_signer_count is incremented atomically
    - FR-6.5: Escalation threshold checked on each co-sign
    - FR-6.6: Rate limit info included in response (AC6)
    - FR-5.1: Auto-escalation when threshold reached
    - FR-5.3: Escalation event emitted with co_signer_count
    - NFR-5.1: Rate limit configurable per identity type
    - NFR-5.2: Identity verification for co-sign
    - CT-12: cosign_id enables witnessing accountability
    - CT-14: Silence must be expensive - auto-escalation ensures King attention
    - SYBIL-1: Rate limiting per verified identity

    Attributes:
        cosign_id: Unique identifier for this co-signature (UUIDv7).
        petition_id: Reference to the petition that was co-signed.
        signer_id: UUID of the Seeker who co-signed.
        signed_at: When the co-signature was recorded (ISO 8601).
        content_hash: BLAKE3 hex-encoded hash for witness integrity.
        co_signer_count: Updated total co-signer count after this signature.
        identity_verified: Whether signer identity was verified (NFR-5.2, LEGIT-1).
        rate_limit_remaining: Number of co-signs remaining before rate limit (Story 5.4, AC6).
        rate_limit_reset_at: UTC datetime when rate limit window resets (Story 5.4, AC6).
        threshold_reached: Whether escalation threshold was reached (Story 5.5, FR-6.5).
        threshold_value: The escalation threshold for this petition type (Story 5.5, FR-5.2).
        petition_type: The type of petition (CESSATION, GRIEVANCE, etc.).
        escalation_triggered: Whether auto-escalation was triggered (Story 5.6, FR-5.1).
        escalation_id: UUID of the escalation event if triggered (Story 5.6, FR-5.3).
    """

    cosign_id: UUID = Field(
        ...,
        description="Unique identifier for this co-signature",
    )
    petition_id: UUID = Field(
        ...,
        description="Reference to the petition that was co-signed",
    )
    signer_id: UUID = Field(
        ...,
        description="UUID of the Seeker who co-signed",
    )
    signed_at: DateTimeWithZ = Field(
        ...,
        description="When the co-signature was recorded",
    )
    content_hash: str = Field(
        ...,
        description="BLAKE3 hex-encoded hash for witness integrity",
    )
    co_signer_count: int = Field(
        ...,
        ge=1,
        description="Updated total co-signer count after this signature",
    )
    identity_verified: bool = Field(
        ...,
        description="Whether signer identity was verified (NFR-5.2, LEGIT-1)",
    )
    rate_limit_remaining: int | None = Field(
        default=None,
        ge=0,
        description="Number of co-signs remaining before rate limit (FR-6.6, AC6)",
    )
    rate_limit_reset_at: DateTimeWithZ | None = Field(
        default=None,
        description="UTC datetime when rate limit window resets (FR-6.6, AC6)",
    )
    threshold_reached: bool = Field(
        default=False,
        description="Whether escalation threshold was reached (FR-6.5, Story 5.5)",
    )
    threshold_value: int | None = Field(
        default=None,
        ge=1,
        description="The escalation threshold for this petition type (FR-5.2, Story 5.5)",
    )
    petition_type: str | None = Field(
        default=None,
        description="The type of petition (CESSATION, GRIEVANCE, GENERAL, COLLABORATION)",
    )
    escalation_triggered: bool = Field(
        default=False,
        description="Whether auto-escalation was triggered (FR-5.1, Story 5.6)",
    )
    escalation_id: UUID | None = Field(
        default=None,
        description="UUID of the escalation event if triggered (FR-5.3, Story 5.6)",
    )


class CoSignErrorResponse(BaseModel):
    """Error response for co-sign operations (RFC 7807).

    Implements RFC 7807 Problem Details for HTTP APIs with
    governance extensions (D7).

    Attributes:
        type: Error type URI.
        title: Human-readable error title.
        status: HTTP status code.
        detail: Detailed error message.
        instance: Request path that caused the error.
        petition_id: Optional petition_id for context.
        signer_id: Optional signer_id for context.
        nfr_reference: Optional NFR constraint reference (NFR-5.2 for identity).
        hardening_control: Optional hardening control reference (LEGIT-1, SYBIL-1).
        retry_after: Optional seconds to wait before retrying (for 503/429).
        current_count: Optional current rate limit count (for 429).
        limit: Optional rate limit maximum (for 429).
        rate_limit_remaining: Optional remaining co-signs (for 429, always 0).
        rate_limit_reset_at: Optional reset time (for 429).
    """

    type: str = Field(..., description="Error type URI")
    title: str = Field(..., description="Human-readable error title")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Detailed error message")
    instance: str = Field(..., description="Request path that caused the error")
    petition_id: UUID | None = Field(
        default=None,
        description="Petition ID that caused the error (if applicable)",
    )
    signer_id: UUID | None = Field(
        default=None,
        description="Signer ID that caused the error (if applicable)",
    )
    nfr_reference: str | None = Field(
        default=None,
        description="NFR constraint reference (e.g., NFR-5.2 for identity verification)",
    )
    hardening_control: str | None = Field(
        default=None,
        description="Hardening control reference (e.g., LEGIT-1, SYBIL-1)",
    )
    retry_after: int | None = Field(
        default=None,
        description="Seconds to wait before retrying (for 503/429 responses)",
    )
    current_count: int | None = Field(
        default=None,
        description="Current count in rate limit window (for 429 responses)",
    )
    limit: int | None = Field(
        default=None,
        description="Maximum allowed in rate limit window (for 429 responses)",
    )
    rate_limit_remaining: int | None = Field(
        default=None,
        description="Remaining co-signs before rate limit (0 for 429)",
    )
    rate_limit_reset_at: str | None = Field(
        default=None,
        description="ISO 8601 datetime when rate limit window resets (for 429)",
    )


class CountVerificationRequest(BaseModel):
    """Request to verify co-signer count consistency (Story 5.8, AC5).

    Constitutional Constraints:
    - NFR-2.2: 100k+ co-signers support - counter enables O(1) reads at scale
    - AC5: Any discrepancy triggers MEDIUM alert
    - CT-11: Silent failure destroys legitimacy - discrepancies must be visible

    Attributes:
        petition_id: UUID of the petition to verify count for.
    """

    petition_id: UUID = Field(
        ...,
        description="UUID of the petition to verify count for",
    )


class CountVerificationResponse(BaseModel):
    """Response from count verification (Story 5.8, AC5).

    Constitutional Constraints:
    - NFR-2.2: Counter vs COUNT(*) comparison
    - AC5: Reports discrepancy with severity indicator
    - CT-11: All verification results are logged

    Attributes:
        petition_id: UUID of the verified petition.
        counter_value: Value from co_signer_count column (O(1) read).
        actual_count: Value from SELECT COUNT(*) (O(n) verification).
        is_consistent: True if counter matches actual count.
        discrepancy: Difference between counter and actual (0 if consistent).
    """

    petition_id: UUID = Field(
        ...,
        description="UUID of the verified petition",
    )
    counter_value: int = Field(
        ...,
        ge=0,
        description="Value from co_signer_count column (O(1) read)",
    )
    actual_count: int = Field(
        ...,
        ge=0,
        description="Value from SELECT COUNT(*) (O(n) verification)",
    )
    is_consistent: bool = Field(
        ...,
        description="True if counter matches actual count",
    )
    discrepancy: int = Field(
        ...,
        description="Difference between counter and actual (0 if consistent)",
    )


class BatchCountVerificationRequest(BaseModel):
    """Request to verify co-signer count for multiple petitions (Story 5.8, AC5).

    Attributes:
        petition_ids: List of petition UUIDs to verify.
    """

    petition_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,  # Reasonable batch limit
        description="List of petition UUIDs to verify (max 100)",
    )


class BatchCountVerificationResponse(BaseModel):
    """Response from batch count verification (Story 5.8, AC5).

    Attributes:
        total: Total number of petitions verified.
        consistent: Number of petitions with consistent counts.
        inconsistent: Number of petitions with discrepancies.
        results: Individual verification results.
    """

    total: int = Field(..., ge=0, description="Total petitions verified")
    consistent: int = Field(..., ge=0, description="Petitions with consistent counts")
    inconsistent: int = Field(..., ge=0, description="Petitions with discrepancies")
    results: list[CountVerificationResponse] = Field(
        ..., description="Individual verification results"
    )
