"""Governance transcript access protocol (Story 7.6, FR-7.4, Ruling-2).

This module defines the protocol for elevated transcript access for
governance actors (HIGH_ARCHON and AUDITOR roles). This is the elevated
tier of access - full transcripts with Archon attribution, unlike the
mediated access in Story 7.4.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - elevated tier for governance
- FR-7.4: System SHALL provide full transcript to governance actors
- CT-12: Witnessing creates accountability - access must be logged
- PRD Section 13A.8: HIGH_ARCHON/AUDITOR tier access definition
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from src.application.dtos.governance_transcript import FullTranscriptResponse


class GovernanceTranscriptAccessProtocol(Protocol):
    """Protocol for elevated transcript access (Story 7.6, FR-7.4).

    Implementations provide full transcript access for governance actors
    including HIGH_ARCHON and AUDITOR roles. This is the elevated tier
    per Ruling-2, providing:
    - All utterances with Archon attribution (archon_id for each)
    - Timestamps for each utterance (ISO 8601 UTC)
    - Phase boundaries (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
    - Raw dissent text (if present)

    Unlike TranscriptAccessMediationService (Story 7.4), this service
    does NOT filter out Archon identities or transcript content.

    Constitutional Constraints:
    - Ruling-2: Elevated tier access for governance
    - FR-7.4: Full transcript access
    - CT-12: Access must be logged for audit
    """

    async def get_full_transcript(
        self,
        session_id: UUID,
        accessor_archon_id: UUID,
        accessor_role: str,
    ) -> FullTranscriptResponse:
        """Get full transcript for a deliberation session (FR-7.4).

        Returns complete transcript with all Archon attributions.
        This is elevated access - no filtering of sensitive details.

        Constitutional Constraints:
        - Ruling-2: Elevated tier access
        - CT-12: Access is logged for audit trail
        - AC-5: Read operations permitted during halt

        Args:
            session_id: UUID of the deliberation session.
            accessor_archon_id: UUID of the accessor (for audit logging).
            accessor_role: Role of the accessor (HIGH_ARCHON or AUDITOR).

        Returns:
            FullTranscriptResponse with complete transcript data.

        Raises:
            SessionNotFoundError: If session does not exist (AC-5).
        """
        ...
