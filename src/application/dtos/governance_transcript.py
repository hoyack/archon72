"""Governance transcript DTOs for application layer (Story 7.6, FR-7.4, Ruling-2).

These Pydantic models represent the full transcript data returned by the
application layer for elevated transcript access. The API layer may map
or re-export these models for responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TranscriptUtterance(BaseModel):
    """Single utterance in a deliberation transcript (Story 7.6, AC-1).

    ELEVATED ACCESS: Includes full Archon attribution per Ruling-2.
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
    """Detailed transcript for a single deliberation phase (Story 7.6, AC-1)."""

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
    """Complete transcript response for governance actors (Story 7.6, AC-1, AC-2)."""

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
