"""API models for escalation queue and decision package endpoints (Stories 6.1-6.2, FR-5.4).

Pydantic models for request/response payloads of the King escalation API:
- Story 6.1: Escalation queue listing
- Story 6.2: Escalation decision package (full context for adoption/acknowledgment)

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- D8: Keyset pagination compliance
- RULING-3: Realm-scoped data access
- RULING-2: Tiered transcript access (mediated summaries for Kings)
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


# Story 6.2: Escalation Decision Package Models


class SubmitterMetadataResponse(BaseModel):
    """Anonymized submitter metadata for decision package (Story 6.2).

    Attributes:
        public_key_hash: SHA-256 hash of submitter's public key (anonymized)
        submitted_at: When the petition was originally submitted (ISO 8601 UTC)
    """

    public_key_hash: str = Field(
        ...,
        description="SHA-256 hash of submitter's public key (anonymized)",
        min_length=64,
        max_length=64,
    )
    submitted_at: datetime = Field(
        ...,
        description="When the petition was originally submitted (ISO 8601 UTC)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "public_key_hash": "a3c4f7b2e1d9c8a5f6b3e2d1c9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1",
                "submitted_at": "2026-01-15T08:30:00Z",
            }
        }


class CoSignerResponse(BaseModel):
    """Co-signer information for decision package (Story 6.2).

    Attributes:
        public_key_hash: SHA-256 hash of co-signer's public key (anonymized)
        signed_at: When the co-signature was added (ISO 8601 UTC)
        sequence: Order of this co-signer (1-based)
    """

    public_key_hash: str = Field(
        ...,
        description="SHA-256 hash of co-signer's public key (anonymized)",
        min_length=64,
        max_length=64,
    )
    signed_at: datetime = Field(
        ...,
        description="When the co-signature was added (ISO 8601 UTC)",
    )
    sequence: int = Field(
        ...,
        description="Order of this co-signer (1-based)",
        ge=1,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "public_key_hash": "b4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
                "signed_at": "2026-01-15T09:15:00Z",
                "sequence": 1,
            }
        }


class CoSignerListResponse(BaseModel):
    """Paginated co-signer list for decision package (Story 6.2, D8).

    Uses keyset pagination for efficient navigation with large co-signer counts.

    Attributes:
        items: List of co-signers in sequence order
        total_count: Total number of co-signers (all pages)
        next_cursor: Cursor for next page (null if no more items)
        has_more: Whether there are more items after this page
    """

    items: list[CoSignerResponse] = Field(
        ...,
        description="List of co-signers in sequence order",
    )
    total_count: int = Field(
        ...,
        description="Total number of co-signers (all pages)",
        ge=0,
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
                        "public_key_hash": "b4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
                        "signed_at": "2026-01-15T09:15:00Z",
                        "sequence": 1,
                    }
                ],
                "total_count": 150,
                "next_cursor": "c2VxdWVuY2U6Mg==",
                "has_more": True,
            }
        }


class DeliberationSummaryResponse(BaseModel):
    """Mediated deliberation summary for decision package (Story 6.2, RULING-2).

    Per RULING-2: Kings receive mediated summaries, not raw transcripts.
    Full transcripts are reserved for HIGH_ARCHON/AUDITOR roles only.

    Attributes:
        vote_breakdown: Vote distribution (e.g., "2-1 split", "unanimous")
        has_dissent: Whether the decision was not unanimous
        decision_outcome: Final deliberation outcome
        transcript_hash: Hash reference to full transcript (for auditors)
    """

    vote_breakdown: str = Field(
        ...,
        description='Vote distribution (e.g., "2-1 split", "unanimous")',
    )
    has_dissent: bool = Field(
        ...,
        description="Whether the decision was not unanimous",
    )
    decision_outcome: str = Field(
        ...,
        description="Final deliberation outcome (e.g., ESCALATE, APPROVE, REJECT)",
    )
    transcript_hash: str = Field(
        ...,
        description="Hash reference to full transcript (for auditors)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "vote_breakdown": "2-1 split",
                "has_dissent": True,
                "decision_outcome": "ESCALATE",
                "transcript_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            }
        }


class KnightRecommendationResponse(BaseModel):
    """Knight recommendation details for decision package (Story 6.2).

    Included when escalation source is KNIGHT_RECOMMENDATION.

    Attributes:
        knight_id: UUID of the Knight who made the recommendation
        recommendation_text: Knight's rationale for escalation
        recommended_at: When the recommendation was made (ISO 8601 UTC)
    """

    knight_id: UUID = Field(
        ...,
        description="UUID of the Knight who made the recommendation",
    )
    recommendation_text: str = Field(
        ...,
        description="Knight's rationale for escalation",
    )
    recommended_at: datetime = Field(
        ...,
        description="When the recommendation was made (ISO 8601 UTC)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "knight_id": "660e9500-f39c-52e5-b827-557766551111",
                "recommendation_text": "This petition raises critical governance concerns requiring King's attention.",
                "recommended_at": "2026-01-18T14:30:00Z",
            }
        }


class EscalationHistoryResponse(BaseModel):
    """Escalation history context for decision package (Story 6.2).

    Provides context-dependent information based on escalation source:
    - DELIBERATION: Includes deliberation summary
    - KNIGHT_RECOMMENDATION: Includes Knight recommendation
    - CO_SIGNER_THRESHOLD: Only includes co-signer count

    Attributes:
        escalation_source: What triggered the escalation
        escalated_at: When the petition was escalated (ISO 8601 UTC)
        co_signer_count_at_escalation: Number of co-signers when escalated
        deliberation_summary: Mediated deliberation summary (if applicable)
        knight_recommendation: Knight recommendation details (if applicable)
    """

    escalation_source: EscalationSourceEnum = Field(
        ...,
        description="What triggered the escalation",
    )
    escalated_at: datetime = Field(
        ...,
        description="When the petition was escalated (ISO 8601 UTC)",
    )
    co_signer_count_at_escalation: int = Field(
        ...,
        description="Number of co-signers when escalated",
        ge=0,
    )
    deliberation_summary: DeliberationSummaryResponse | None = Field(
        None,
        description="Mediated deliberation summary (if escalation source is DELIBERATION)",
    )
    knight_recommendation: KnightRecommendationResponse | None = Field(
        None,
        description="Knight recommendation details (if escalation source is KNIGHT_RECOMMENDATION)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "escalation_source": "DELIBERATION",
                "escalated_at": "2026-01-20T12:00:00Z",
                "co_signer_count_at_escalation": 85,
                "deliberation_summary": {
                    "vote_breakdown": "2-1 split",
                    "has_dissent": True,
                    "decision_outcome": "ESCALATE",
                    "transcript_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                },
                "knight_recommendation": None,
            }
        }


class EscalationDecisionPackageResponse(BaseModel):
    """Complete decision package for King adoption/acknowledgment decision (Story 6.2).

    Provides comprehensive context for Kings to make informed decisions about
    petition adoption or acknowledgment.

    Constitutional Constraints:
    - FR-5.4: King receives distinct escalation context
    - RULING-2: Tiered transcript access (mediated summaries only)
    - RULING-3: Realm-scoped data access

    Attributes:
        petition_id: UUID of the escalated petition
        petition_type: Type of petition
        petition_content: Full petition text
        submitter_metadata: Anonymized submitter information
        co_signers: Paginated co-signer list
        escalation_history: Context about why/how petition was escalated
    """

    petition_id: UUID = Field(
        ...,
        description="UUID of the escalated petition",
    )
    petition_type: PetitionTypeEnum = Field(
        ...,
        description="Type of petition (CESSATION, GRIEVANCE, etc.)",
    )
    petition_content: str = Field(
        ...,
        description="Full petition text",
    )
    submitter_metadata: SubmitterMetadataResponse = Field(
        ...,
        description="Anonymized submitter information",
    )
    co_signers: CoSignerListResponse = Field(
        ...,
        description="Paginated co-signer list with total count",
    )
    escalation_history: EscalationHistoryResponse = Field(
        ...,
        description="Context about why/how petition was escalated",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                "petition_type": "CESSATION",
                "petition_content": "Request for cessation review due to concerns about...",
                "submitter_metadata": {
                    "public_key_hash": "a3c4f7b2e1d9c8a5f6b3e2d1c9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1",
                    "submitted_at": "2026-01-15T08:30:00Z",
                },
                "co_signers": {
                    "items": [
                        {
                            "public_key_hash": "b4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
                            "signed_at": "2026-01-15T09:15:00Z",
                            "sequence": 1,
                        }
                    ],
                    "total_count": 150,
                    "next_cursor": "c2VxdWVuY2U6Mg==",
                    "has_more": True,
                },
                "escalation_history": {
                    "escalation_source": "CO_SIGNER_THRESHOLD",
                    "escalated_at": "2026-01-20T12:00:00Z",
                    "co_signer_count_at_escalation": 150,
                    "deliberation_summary": None,
                    "knight_recommendation": None,
                },
            }
        }


# Story 6.3: Petition Adoption Models


class PetitionAdoptionRequest(BaseModel):
    """Request to adopt an escalated petition and create a Motion (Story 6.3, FR-5.5).

    Constitutional Constraints:
    - FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
    - FR-5.6: Adoption SHALL consume promotion budget (H1 compliance) [P0]
    - FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]

    Attributes:
        motion_title: Title for the new Motion (3-200 chars)
        motion_body: Intent/body text for the Motion (10-5000 chars)
        adoption_rationale: King's rationale for adoption (50-2000 chars, required for governance)
    """

    motion_title: str = Field(
        ...,
        description="Title for the new Motion",
        min_length=3,
        max_length=200,
    )
    motion_body: str = Field(
        ...,
        description="Intent/body text for the Motion (becomes normative intent)",
        min_length=10,
        max_length=5000,
    )
    adoption_rationale: str = Field(
        ...,
        description="King's rationale for adopting this petition (required, min 50 chars)",
        min_length=50,
        max_length=2000,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "motion_title": "Address Data Retention Policy Concerns",
                "motion_body": "The petitioners have raised valid concerns about data retention policies. This motion directs the system to review and update retention policies to balance privacy and operational needs.",
                "adoption_rationale": "The 150+ co-signers demonstrate strong community concern. The petition text aligns with governance priorities for data privacy and discretion. This issue merits formal governance consideration.",
            }
        }


class ProvenanceResponse(BaseModel):
    """Provenance information for adopted petition (Story 6.3, FR-5.7).

    Attributes:
        source_petition_ref: UUID of the source petition (immutable)
        adoption_rationale: King's rationale for adoption
        budget_consumed: Budget consumed for this adoption (always 1)
    """

    source_petition_ref: UUID = Field(
        ...,
        description="UUID of the source petition (immutable provenance)",
    )
    adoption_rationale: str = Field(
        ...,
        description="King's rationale for adoption",
    )
    budget_consumed: int = Field(
        ...,
        description="Budget consumed for this adoption",
        ge=1,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "source_petition_ref": "550e8400-e29b-41d4-a716-446655440000",
                "adoption_rationale": "The 150+ co-signers demonstrate strong community concern...",
                "budget_consumed": 1,
            }
        }


class PetitionAdoptionResponse(BaseModel):
    """Response for successful petition adoption (Story 6.3, FR-5.5).

    Constitutional Constraints:
    - FR-5.7: Motion includes immutable source_petition_ref
    - NFR-6.2: Provenance immutability enforced at database level

    Attributes:
        motion_id: UUID of the created Motion
        petition_id: UUID of the adopted petition
        sponsor_id: UUID of the King who adopted
        created_at: When the Motion was created (ISO 8601 UTC)
        provenance: Immutable provenance information
    """

    motion_id: UUID = Field(
        ...,
        description="UUID of the created Motion",
    )
    petition_id: UUID = Field(
        ...,
        description="UUID of the adopted petition",
    )
    sponsor_id: UUID = Field(
        ...,
        description="UUID of the King who adopted (sponsor)",
    )
    created_at: datetime = Field(
        ...,
        description="When the Motion was created (ISO 8601 UTC)",
    )
    provenance: ProvenanceResponse = Field(
        ...,
        description="Immutable provenance information linking Motion to Petition",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "motion_id": "770e9600-f49d-63f6-c938-668877662222",
                "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                "sponsor_id": "880ea700-g5ae-74g7-d049-779988773333",
                "created_at": "2026-01-22T14:30:00Z",
                "provenance": {
                    "source_petition_ref": "550e8400-e29b-41d4-a716-446655440000",
                    "adoption_rationale": "The 150+ co-signers demonstrate strong community concern...",
                    "budget_consumed": 1,
                },
            }
        }


# Story 6.5: King Escalation Acknowledgment Models


class KingAcknowledgmentRequest(BaseModel):
    """Request for King to acknowledge an escalated petition (Story 6.5, FR-5.8).

    Constitutional Constraints:
    - FR-5.8: King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]
    - Story 6.5: Rationale minimum 100 characters (higher bar for Kings)

    Attributes:
        reason_code: Reason from AcknowledgmentReasonCode enum
        rationale: King's explanation (min 100 chars to respect petitioners)
    """

    reason_code: str = Field(
        ...,
        description="Reason code from AcknowledgmentReasonCode enum",
        min_length=1,
        max_length=50,
    )
    rationale: str = Field(
        ...,
        description="King's explanation for declining adoption (min 100 chars)",
        min_length=100,
        max_length=2000,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "reason_code": "NOTED",
                "rationale": "I have carefully reviewed this petition and the concerns raised by 150+ co-signers. While I appreciate their dedication to system governance, the specific concerns outlined have been addressed in recent policy updates. The new safeguards already provide the protections requested in this petition.",
            }
        }


class KingAcknowledgmentResponse(BaseModel):
    """Response for successful King acknowledgment (Story 6.5, FR-5.8).

    Constitutional Constraints:
    - FR-5.8: King acknowledgments provide formal response to petitioners
    - CT-12: Acknowledgments are witnessed and immutable

    Attributes:
        acknowledgment_id: UUID of the created acknowledgment
        petition_id: UUID of the acknowledged petition
        king_id: UUID of the King who acknowledged
        reason_code: Reason code for the acknowledgment
        acknowledged_at: When the acknowledgment occurred (ISO 8601 UTC)
        realm_id: Realm where acknowledgment occurred
    """

    acknowledgment_id: UUID = Field(
        ...,
        description="UUID of the created acknowledgment",
    )
    petition_id: UUID = Field(
        ...,
        description="UUID of the acknowledged escalated petition",
    )
    king_id: UUID = Field(
        ...,
        description="UUID of the King who acknowledged",
    )
    reason_code: str = Field(
        ...,
        description="Reason code for the acknowledgment",
    )
    acknowledged_at: datetime = Field(
        ...,
        description="When the acknowledgment occurred (ISO 8601 UTC)",
    )
    realm_id: str = Field(
        ...,
        description="Realm where acknowledgment occurred",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "acknowledgment_id": "990eb800-h6bf-85h8-e15a-880099884444",
                "petition_id": "550e8400-e29b-41d4-a716-446655440000",
                "king_id": "880ea700-g5ae-74g7-d049-779988773333",
                "reason_code": "NOTED",
                "acknowledged_at": "2026-01-22T14:30:00Z",
                "realm_id": "governance",
            }
        }
