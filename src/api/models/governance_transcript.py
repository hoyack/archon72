"""Governance transcript API models (Story 7.6, FR-7.4, Ruling-2).

This module defines Pydantic models for the elevated transcript access
endpoint. These models expose full transcript details including Archon
attributions - unlike the mediated models in Story 7.4.

Constitutional Constraints:
- Ruling-2: Elevated tier access - full details
- FR-7.4: System SHALL provide full transcript to governance actors
- CT-12: Witnessing creates accountability
- PRD Section 13A.8: HIGH_ARCHON/AUDITOR tier access definition
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TranscriptUtterance(BaseModel):
    """Single utterance in a deliberation transcript (Story 7.6, AC-1).

    ELEVATED ACCESS: Unlike mediated summaries, this includes full
    Archon attribution per Ruling-2 elevated tier.

    Constitutional Constraints:
    - Ruling-2: Elevated tier exposes archon_id
    - FR-7.4: Full utterance content
    - CT-12: Timestamps enable audit
    """

    model_config = ConfigDict(frozen=True)

    archon_id: Annotated[
        UUID,
        Field(description="UUID of the Archon who made this utterance"),
    ]
    timestamp: Annotated[
        datetime,
        Field(description="When utterance was made (ISO 8601 UTC)"),
    ]
    content: Annotated[
        str,
        Field(description="Full text content of the utterance"),
    ]
    sequence: Annotated[
        int,
        Field(ge=0, description="Order of utterance within the phase (0-indexed)"),
    ]


class PhaseTranscriptDetail(BaseModel):
    """Detailed transcript for a single deliberation phase (Story 7.6, AC-1).

    ELEVATED ACCESS: Contains all utterances with Archon attribution.
    This is the full content, not a summary.

    Constitutional Constraints:
    - Ruling-2: Elevated tier exposes all utterances
    - FR-11.4: Phase protocol (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
    - CT-12: Hash proves integrity
    """

    model_config = ConfigDict(frozen=True)

    phase: Annotated[
        str,
        Field(description="Phase name (ASSESS, POSITION, CROSS_EXAMINE, VOTE)"),
    ]
    start_timestamp: Annotated[
        datetime,
        Field(description="When phase started (ISO 8601 UTC)"),
    ]
    end_timestamp: Annotated[
        datetime,
        Field(description="When phase ended (ISO 8601 UTC)"),
    ]
    utterances: Annotated[
        list[TranscriptUtterance],
        Field(description="All utterances in this phase with Archon attribution"),
    ]
    transcript_hash_hex: Annotated[
        str,
        Field(description="Blake3 hash of transcript content (hex, 64 chars)"),
    ]


class FullTranscriptResponse(BaseModel):
    """Complete transcript response for governance actors (Story 7.6, AC-1, AC-2).

    ELEVATED ACCESS: Full deliberation transcript with all Archon
    attributions and raw content. This is NOT mediated.

    Accessible to:
    - HIGH_ARCHON role (AC-1)
    - AUDITOR role (AC-2)

    NOT accessible to:
    - OBSERVER role (AC-3)
    - SEEKER role (AC-4)

    Constitutional Constraints:
    - Ruling-2: Elevated tier for governance actors only
    - FR-7.4: Full transcript access
    - CT-12: Access logged for audit trail
    """

    model_config = ConfigDict(frozen=True)

    session_id: Annotated[
        UUID,
        Field(description="UUID of the deliberation session"),
    ]
    petition_id: Annotated[
        UUID,
        Field(description="UUID of the petition being deliberated"),
    ]
    phases: Annotated[
        list[PhaseTranscriptDetail],
        Field(description="Detailed transcripts for each phase"),
    ]
    outcome: Annotated[
        str,
        Field(description="Final outcome (ACKNOWLEDGE, REFER, ESCALATE)"),
    ]
    has_dissent: Annotated[
        bool,
        Field(description="Whether there was a dissenting vote (2-1)"),
    ]
    dissent_text: Annotated[
        str | None,
        Field(description="Raw dissent text if present, None otherwise"),
    ]
    completed_at: Annotated[
        datetime,
        Field(description="When deliberation completed (ISO 8601 UTC)"),
    ]


class TranscriptAccessError(BaseModel):
    """Error response for transcript access failures (Story 7.6, AC-3, AC-4, AC-5).

    Follows RFC 7807 Problem Details with governance extensions.

    Constitutional Constraints:
    - RFC 7807: Standard error format
    - Governance extensions: trace_id, actor, cycle_id, as_of_seq
    """

    model_config = ConfigDict(frozen=True)

    type: Annotated[
        str,
        Field(description="Error type URI"),
    ]
    title: Annotated[
        str,
        Field(description="Short, human-readable title"),
    ]
    status: Annotated[
        int,
        Field(description="HTTP status code"),
    ]
    detail: Annotated[
        str,
        Field(description="Detailed error message"),
    ]
    instance: Annotated[
        str | None,
        Field(description="URI of the request that caused the error"),
    ] = None
    redirect_hint: Annotated[
        str | None,
        Field(
            description="Suggested alternative endpoint for denied users (AC-3, AC-4)"
        ),
    ] = None
    # Governance extensions
    trace_id: Annotated[
        str | None,
        Field(description="Request trace ID for debugging"),
    ] = None
    actor: Annotated[
        str | None,
        Field(description="Actor who made the request"),
    ] = None
