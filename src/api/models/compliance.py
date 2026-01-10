"""Compliance API request/response models (Story 9.9, NFR31-34).

Pydantic models for the compliance documentation API endpoints.

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
- FR44: Public read access without authentication
- CT-12: Witnessing creates accountability - all actions have attribution
"""

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field, PlainSerializer

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(lambda v: v.isoformat() + "Z" if v else None, return_type=str),
]


class ComplianceRequirementResponse(BaseModel):
    """Response model for a single compliance requirement (NFR31-34).

    Attributes:
        requirement_id: NFR ID (e.g., "NFR31").
        framework: Compliance framework (e.g., "EU_AI_ACT").
        description: Full description of the requirement.
        status: Current compliance status.
        implementation_reference: Where implemented in codebase.
        evidence: List of evidence supporting compliance status.
    """

    requirement_id: str = Field(
        ...,
        description="NFR ID (e.g., NFR31)",
        examples=["NFR31"],
    )
    framework: str = Field(
        ...,
        description="Compliance framework",
        examples=["EU_AI_ACT", "NIST_AI_RMF", "IEEE_7001", "GDPR", "MAESTRO"],
    )
    description: str = Field(
        ...,
        description="Full description of the requirement",
    )
    status: str = Field(
        ...,
        description="Current compliance status",
        examples=["COMPLIANT", "PARTIAL", "GAP_IDENTIFIED", "NOT_APPLICABLE"],
    )
    implementation_reference: Optional[str] = Field(
        default=None,
        description="Where implemented in codebase",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="List of evidence supporting compliance status",
    )


class ComplianceAssessmentResponse(BaseModel):
    """Response model for a compliance assessment (NFR31-34).

    Attributes:
        assessment_id: Unique assessment identifier.
        framework: Compliance framework being assessed.
        assessment_date: When assessment was performed (ISO 8601).
        requirements: Individual requirements with status.
        overall_status: Computed overall compliance status.
        gaps: List of identified gaps.
        remediation_plan: Plan for addressing gaps (if any).
    """

    assessment_id: str = Field(
        ...,
        description="Unique assessment identifier",
        examples=["EU_AI_ACT-ASSESSMENT-a1b2c3d4"],
    )
    framework: str = Field(
        ...,
        description="Compliance framework being assessed",
        examples=["EU_AI_ACT", "NIST_AI_RMF", "IEEE_7001", "GDPR", "MAESTRO"],
    )
    assessment_date: DateTimeWithZ = Field(
        ...,
        description="When assessment was performed (ISO 8601)",
    )
    requirements: list[ComplianceRequirementResponse] = Field(
        default_factory=list,
        description="Individual requirements with status",
    )
    overall_status: str = Field(
        ...,
        description="Computed overall compliance status",
        examples=["COMPLIANT", "PARTIAL", "GAP_IDENTIFIED", "NOT_APPLICABLE"],
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="List of identified gaps",
    )
    remediation_plan: Optional[str] = Field(
        default=None,
        description="Plan for addressing gaps",
    )


class CompliancePostureResponse(BaseModel):
    """Response model for overall compliance posture (NFR31-34).

    Returns framework -> status mapping for quick compliance overview.

    Attributes:
        posture: Dict mapping framework to its compliance status.
        total_frameworks: Number of frameworks assessed.
        compliant_count: Number of frameworks with COMPLIANT status.
        gaps_count: Number of frameworks with GAP_IDENTIFIED status.
    """

    posture: dict[str, str] = Field(
        default_factory=dict,
        description="Framework to status mapping",
        examples=[{"EU_AI_ACT": "COMPLIANT", "NIST_AI_RMF": "PARTIAL"}],
    )
    total_frameworks: int = Field(
        ...,
        ge=0,
        description="Total number of frameworks assessed",
    )
    compliant_count: int = Field(
        ...,
        ge=0,
        description="Number of frameworks with COMPLIANT status",
    )
    gaps_count: int = Field(
        ...,
        ge=0,
        description="Number of frameworks with GAP_IDENTIFIED status",
    )


class ComplianceGapsResponse(BaseModel):
    """Response model for compliance gaps (NFR31-34).

    Attributes:
        gaps: List of requirements with GAP_IDENTIFIED status.
        total_count: Total number of gaps identified.
    """

    gaps: list[ComplianceRequirementResponse] = Field(
        default_factory=list,
        description="List of requirements with gaps identified",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of gaps",
    )


class ComplianceFrameworksListResponse(BaseModel):
    """Response model for listing all framework assessments (NFR31-34).

    Attributes:
        assessments: List of latest assessment for each framework.
        total_count: Total number of frameworks assessed.
    """

    assessments: list[ComplianceAssessmentResponse] = Field(
        default_factory=list,
        description="List of latest framework assessments",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of frameworks assessed",
    )


class ComplianceErrorResponse(BaseModel):
    """RFC 7807 compliant error response for compliance endpoints.

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
        examples=["https://archon72.io/errors/framework-not-found"],
    )
    title: str = Field(
        ...,
        description="Short, human-readable summary",
        examples=["Framework Not Found"],
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
        examples=["Framework 'UNKNOWN' was not found"],
    )
    instance: str = Field(
        ...,
        description="URI reference identifying the specific occurrence",
        examples=["/v1/compliance/frameworks/UNKNOWN"],
    )
