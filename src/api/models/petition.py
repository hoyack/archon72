"""Petition API request/response models (Story 7.2, FR39).

Pydantic models for the external observer petition API endpoints.

Constitutional Constraints:
- FR39: External observers can petition with 100+ co-signers
- FR44: Public read access without authentication
- AC4: Ed25519 signature algorithm
- AC8: Public petition listing without authentication
- CT-12: Witnessing creates accountability - all actions have attribution
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


class SubmitPetitionRequest(BaseModel):
    """Request to submit a new petition (FR39, AC1).

    Constitutional Constraints:
    - AC1: Petition created with submitter's Ed25519 signature
    - AC4: Ed25519 signature over petition content

    Attributes:
        petition_content: Reason for cessation concern.
        submitter_public_key: Hex-encoded Ed25519 public key.
        submitter_signature: Hex-encoded Ed25519 signature over petition_content.
    """

    petition_content: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Reason for cessation concern",
    )
    submitter_public_key: str = Field(
        ...,
        min_length=64,
        max_length=128,
        description="Hex-encoded Ed25519 public key",
    )
    submitter_signature: str = Field(
        ...,
        min_length=128,
        max_length=256,
        description="Hex-encoded Ed25519 signature over petition_content",
    )


class SubmitPetitionResponse(BaseModel):
    """Response after submitting a petition (FR39, AC1).

    Attributes:
        petition_id: Unique identifier for the created petition.
        created_at: When the petition was created (ISO 8601).
        status: Initial status (always "open").
    """

    petition_id: UUID
    created_at: DateTimeWithZ
    status: str = "open"


class CosignPetitionRequest(BaseModel):
    """Request to co-sign an existing petition (FR39, AC2).

    Constitutional Constraints:
    - AC2: Duplicate co-signatures from same public key are rejected
    - AC4: Ed25519 signature over original petition content

    Attributes:
        cosigner_public_key: Hex-encoded Ed25519 public key.
        cosigner_signature: Hex-encoded Ed25519 signature over petition content.
    """

    cosigner_public_key: str = Field(
        ...,
        min_length=64,
        max_length=128,
        description="Hex-encoded Ed25519 public key",
    )
    cosigner_signature: str = Field(
        ...,
        min_length=128,
        max_length=256,
        description="Hex-encoded Ed25519 signature over original petition content",
    )


class CosignPetitionResponse(BaseModel):
    """Response after co-signing a petition (FR39, AC2, AC3).

    Attributes:
        petition_id: The petition that was co-signed.
        cosigner_sequence: Order of this co-signer (1-based).
        cosigner_count: Total co-signers after this signature.
        threshold_met: Whether 100 co-signers was reached.
        agenda_placement_id: ID of cessation agenda placement (if threshold met).
    """

    petition_id: UUID
    cosigner_sequence: int
    cosigner_count: int
    threshold_met: bool
    agenda_placement_id: UUID | None = None


class CoSignerResponse(BaseModel):
    """Response model for a single co-signer.

    Attributes:
        public_key: Hex-encoded Ed25519 public key.
        signed_at: When the co-signature was added (ISO 8601).
        sequence: Order of this co-signer (1-based).
    """

    public_key: str
    signed_at: DateTimeWithZ
    sequence: int


class PetitionDetailResponse(BaseModel):
    """Detailed petition response (FR39, AC8).

    Constitutional Constraints:
    - AC8: Public access without authentication
    - FR44: No registration required

    Attributes:
        petition_id: Unique identifier for this petition.
        submitter_public_key: Hex-encoded public key of submitter.
        petition_content: Reason for cessation concern.
        created_at: When the petition was submitted (ISO 8601).
        status: Current status (open, threshold_met, closed).
        cosigner_count: Number of co-signers.
        threshold: Required co-signers for agenda placement (100).
        threshold_met_at: When threshold was reached, if applicable.
        cosigners: List of co-signers (may be paginated in future).
    """

    petition_id: UUID
    submitter_public_key: str
    petition_content: str
    created_at: DateTimeWithZ
    status: str
    cosigner_count: int
    threshold: int = 100
    threshold_met_at: DateTimeWithZ | None = None
    cosigners: list[CoSignerResponse] = Field(default_factory=list)


class PetitionSummaryResponse(BaseModel):
    """Summary petition response for list endpoint (FR39, AC8).

    Attributes:
        petition_id: Unique identifier for this petition.
        submitter_public_key: Hex-encoded public key of submitter (truncated).
        petition_content_preview: First 200 chars of petition content.
        created_at: When the petition was submitted (ISO 8601).
        status: Current status (open, threshold_met, closed).
        cosigner_count: Number of co-signers.
        threshold: Required co-signers for agenda placement (100).
    """

    petition_id: UUID
    submitter_public_key: str
    petition_content_preview: str
    created_at: DateTimeWithZ
    status: str
    cosigner_count: int
    threshold: int = 100


class ListPetitionsResponse(BaseModel):
    """Response for listing petitions with pagination (FR39, AC8).

    Attributes:
        petitions: List of petition summaries.
        total: Total number of matching petitions.
        limit: Maximum petitions per page.
        offset: Offset from start.
    """

    petitions: list[PetitionSummaryResponse]
    total: int
    limit: int
    offset: int


class PetitionErrorResponse(BaseModel):
    """Error response for petition operations (RFC 7807).

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
