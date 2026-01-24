"""Deliberation Summary API models (Story 7.4, FR-7.4, Ruling-2).

Pydantic models for the mediated deliberation summary endpoint.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - mediated view for Observers
- FR-7.4: System SHALL provide deliberation summary to Observer
- D7: RFC 7807 error responses with governance extensions
- PRD Section 13A.8: Observer tier access definition

What Observers CAN see:
- Outcome (ACKNOWLEDGE, REFER, ESCALATE)
- Vote breakdown string (e.g., "2-1", "3-0")
- Dissent presence (boolean only)
- Phase summaries (metadata, not content)
- Duration and timestamps
- Hash references (proving immutability)

What Observers CANNOT see:
- Raw transcript text
- Individual Archon identities
- Verbatim utterances
- Who voted for what
"""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer

# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(
        lambda v: v.isoformat().replace("+00:00", "Z") if v else None, return_type=str
    ),
]


class DeliberationOutcomeEnum(str, Enum):
    """Deliberation outcome enumeration (Three Fates).

    Outcomes:
        ACKNOWLEDGE: Petition acknowledged, no further action needed.
        REFER: Referred to Knight for review.
        ESCALATE: Escalated to King for adoption consideration.
    """

    ACKNOWLEDGE = "ACKNOWLEDGE"
    REFER = "REFER"
    ESCALATE = "ESCALATE"


class EscalationTriggerEnum(str, Enum):
    """Escalation trigger enumeration (Story 7.4, AC-2, AC-6, AC-7).

    Triggers:
        DELIBERATION: Normal 2-of-3 vote resulted in ESCALATE.
        AUTO_ESCALATED: Co-signer threshold triggered automatic escalation.
        TIMEOUT: Deliberation timed out (HC-7).
        DEADLOCK: Maximum rounds exceeded without consensus (FR-11.10).
    """

    DELIBERATION = "DELIBERATION"
    AUTO_ESCALATED = "AUTO_ESCALATED"
    TIMEOUT = "TIMEOUT"
    DEADLOCK = "DEADLOCK"


class DeliberationPhaseEnum(str, Enum):
    """Deliberation phase enumeration.

    Phases:
        ASSESS: Phase 1 - Independent assessment.
        POSITION: Phase 2 - State preferred disposition.
        CROSS_EXAMINE: Phase 3 - Challenge positions.
        VOTE: Phase 4 - Cast final votes.
    """

    ASSESS = "ASSESS"
    POSITION = "POSITION"
    CROSS_EXAMINE = "CROSS_EXAMINE"
    VOTE = "VOTE"


class PhaseSummaryModel(BaseModel):
    """Summary of a single deliberation phase (Story 7.4, AC-1).

    Provides high-level phase information without exposing transcript content.
    Hash references prove transcript immutability without revealing content.

    Constitutional Constraints:
    - Ruling-2: No raw transcript exposure
    - CT-12: Hash proves witnessing occurred

    Attributes:
        phase: The deliberation phase (ASSESS, POSITION, CROSS_EXAMINE, VOTE).
        duration_seconds: How long the phase took.
        transcript_hash_hex: Hex-encoded Blake3 hash (proves existence).
        themes: Optional list of high-level themes discussed.
        convergence_reached: Optional indicator if archons converged.
    """

    phase: DeliberationPhaseEnum = Field(..., description="Deliberation phase")
    duration_seconds: int = Field(
        ...,
        ge=0,
        description="Phase duration in seconds",
    )
    transcript_hash_hex: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Blake3 hash of transcript (hex-encoded, proves immutability)",
    )
    themes: list[str] | None = Field(
        default=None,
        description="High-level themes discussed (metadata only)",
    )
    convergence_reached: bool | None = Field(
        default=None,
        description="Whether archons converged on position",
    )


class DeliberationSummaryResponse(BaseModel):
    """Mediated deliberation summary for Observer access (Story 7.4, FR-7.4, AC-1).

    This response provides the Observer tier of transcript access per Ruling-2.
    It reveals deliberation outcomes without exposing sensitive details like
    individual Archon identities or raw transcript content.

    Constitutional Constraints:
    - Ruling-2: Tiered transcript access - mediated view
    - FR-7.4: System SHALL provide deliberation summary
    - CT-12: Hash references prove witnessing occurred

    Attributes:
        petition_id: UUID of the deliberated petition.
        outcome: Deliberation outcome (ACKNOWLEDGE, REFER, ESCALATE).
        vote_breakdown: Anonymous vote breakdown (e.g., "2-1", "3-0").
        has_dissent: Whether there was a dissenting vote (boolean, not identity).
        phase_summaries: List of phase summaries with metadata.
        duration_seconds: Total deliberation duration in seconds.
        completed_at: When deliberation completed (ISO 8601 UTC).
        escalation_trigger: Why escalated (if outcome is ESCALATE).
        escalation_reason: Additional escalation context.
        timed_out: True if terminated by timeout.
        rounds_attempted: Number of voting rounds attempted.
    """

    petition_id: str = Field(..., description="UUID of the petition")
    outcome: DeliberationOutcomeEnum = Field(
        ...,
        description="Deliberation outcome (ACKNOWLEDGE, REFER, ESCALATE)",
    )
    vote_breakdown: str = Field(
        ...,
        description="Anonymous vote breakdown (e.g., '2-1' or '3-0')",
    )
    has_dissent: bool = Field(
        ...,
        description="Whether there was a dissenting vote (boolean, not identity)",
    )
    phase_summaries: list[PhaseSummaryModel] = Field(
        ...,
        description="High-level phase summaries (metadata and hashes, not content)",
    )
    duration_seconds: int = Field(
        ...,
        ge=0,
        description="Total deliberation duration in seconds",
    )
    completed_at: DateTimeWithZ = Field(
        ...,
        description="When deliberation completed (ISO 8601 UTC)",
    )
    escalation_trigger: EscalationTriggerEnum | None = Field(
        default=None,
        description="Why escalated (only if outcome is ESCALATE)",
    )
    escalation_reason: str | None = Field(
        default=None,
        description="Additional context for escalation",
    )
    timed_out: bool = Field(
        default=False,
        description="True if terminated by timeout",
    )
    rounds_attempted: int = Field(
        default=1,
        ge=0,
        description="Number of voting rounds attempted",
    )


class DeliberationPendingErrorResponse(BaseModel):
    """Error response when deliberation has not completed (Story 7.4, AC-3).

    Implements RFC 7807 Problem Details with governance extensions.

    Constitutional Constraints:
    - D7: RFC 7807 error responses with governance extensions

    Attributes:
        type: Error type URN (always "urn:archon72:petition:deliberation-pending").
        title: Human-readable error title.
        status: HTTP status code (always 400).
        detail: Detailed error message.
        instance: Request path.
    """

    type: str = Field(
        default="urn:archon72:petition:deliberation-pending",
        description="Error type URN",
    )
    title: str = Field(
        default="Deliberation Pending",
        description="Human-readable error title",
    )
    status: int = Field(default=400, description="HTTP status code")
    detail: str = Field(
        ...,
        description="Detailed error message including petition_id",
    )
    instance: str = Field(..., description="Request path that caused the error")


class PetitionNotFoundErrorResponse(BaseModel):
    """Error response when petition does not exist (Story 7.4, AC-4).

    Implements RFC 7807 Problem Details with governance extensions.

    Constitutional Constraints:
    - D7: RFC 7807 error responses with governance extensions

    Attributes:
        type: Error type URN (always "urn:archon72:petition:not-found").
        title: Human-readable error title.
        status: HTTP status code (always 404).
        detail: Detailed error message.
        instance: Request path.
    """

    type: str = Field(
        default="urn:archon72:petition:not-found",
        description="Error type URN",
    )
    title: str = Field(
        default="Petition Not Found",
        description="Human-readable error title",
    )
    status: int = Field(default=404, description="HTTP status code")
    detail: str = Field(
        ...,
        description="Detailed error message including petition_id",
    )
    instance: str = Field(..., description="Request path that caused the error")
