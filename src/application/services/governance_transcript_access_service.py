"""Governance Transcript Access Service (Story 7.6, FR-7.4, Ruling-2).

This service provides elevated transcript access for governance actors
(HIGH_ARCHON and AUDITOR roles). This is the elevated tier of Ruling-2,
providing full transcripts with Archon attribution.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - elevated tier for governance
- FR-7.4: System SHALL provide full transcript to governance actors
- CT-12: Witnessing creates accountability - access must be logged
- PRD Section 13A.8: HIGH_ARCHON/AUDITOR tier access definition
- AC-5: Read operations permitted during halt

ELEVATED ACCESS - FULL DETAILS EXPOSED:
- All utterances with Archon attribution (archon_id for each)
- Timestamps for each utterance (ISO 8601 UTC)
- Phase boundaries (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
- Raw dissent text (if present)

Unlike TranscriptAccessMediationService (Story 7.4), this service does NOT
filter out Archon identities or transcript content.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

from src.application.dtos.governance_transcript import (
    FullTranscriptResponse,
    PhaseTranscriptDetail,
    TranscriptUtterance,
)
from src.application.ports.deliberation_summary import (
    DeliberationSummaryRepositoryProtocol,
)
from src.application.ports.governance_transcript_access import (
    GovernanceTranscriptAccessProtocol,
)
from src.application.ports.transcript_store import TranscriptStoreProtocol
from src.application.services.base import LoggingMixin
from src.domain.errors.deliberation import SessionNotFoundError
from src.domain.models.deliberation_session import (
    DeliberationPhase,
)

if TYPE_CHECKING:
    from src.domain.events.phase_witness import PhaseWitnessEvent
    from src.domain.models.deliberation_session import DeliberationSession


class GovernanceTranscriptAccessService(LoggingMixin, GovernanceTranscriptAccessProtocol):
    """Service for elevated transcript access (Story 7.6, FR-7.4, Ruling-2).

    Provides full transcript access for governance actors including
    HIGH_ARCHON and AUDITOR roles. This is the elevated tier per Ruling-2.

    Unlike TranscriptAccessMediationService (Story 7.4):
    - DOES expose raw Archon identities (UUIDs)
    - DOES expose individual utterances
    - DOES expose raw dissent text
    - DOES NOT filter any sensitive details

    Constitutional Constraints:
    - Ruling-2: Elevated tier access for governance
    - FR-7.4: Full transcript access
    - CT-12: Access logged for audit trail
    - AC-5: Read operations permitted during halt

    Attributes:
        _summary_repo: Repository for deliberation session data.
        _transcript_store: Store for raw transcript content.
    """

    def __init__(
        self,
        summary_repo: DeliberationSummaryRepositoryProtocol,
        transcript_store: TranscriptStoreProtocol,
    ) -> None:
        """Initialize the governance transcript access service.

        Args:
            summary_repo: Repository for deliberation data.
            transcript_store: Store for raw transcript content.
        """
        self._summary_repo = summary_repo
        self._transcript_store = transcript_store
        self._init_logger(component="petition")

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
        - CT-12: Access is logged for audit trail (AC-7)
        - AC-5: Read operations permitted during halt
        - AC-6: Read operations succeed even during halt

        Args:
            session_id: UUID of the deliberation session.
            accessor_archon_id: UUID of the accessor (for audit logging).
            accessor_role: Role of the accessor (HIGH_ARCHON or AUDITOR).

        Returns:
            FullTranscriptResponse with complete transcript data.

        Raises:
            SessionNotFoundError: If session does not exist (AC-5).
        """
        log = self._log_operation(
            "get_full_transcript",
            session_id=str(session_id),
            accessor_archon_id=str(accessor_archon_id),
            accessor_role=accessor_role,
        )

        # Log access for audit trail (CT-12, AC-7)
        log.info(
            "transcript_access_requested",
            accessor_archon_id=str(accessor_archon_id),
            accessor_role=accessor_role,
            session_id=str(session_id),
        )

        # 1. Get session by session_id
        session = await self._summary_repo.get_session_by_session_id(session_id)
        if session is None:
            log.warning("session_not_found", session_id=str(session_id))
            raise SessionNotFoundError(
                session_id=str(session_id),
                message="Deliberation session not found",
            )

        # 2. Get phase witnesses for session
        witnesses = await self._summary_repo.get_phase_witnesses(session_id)

        # 3. Build full transcript response
        transcript = await self._build_full_transcript(session, witnesses)

        # Log successful access (CT-12, AC-7)
        log.info(
            "transcript_access_granted",
            accessor_archon_id=str(accessor_archon_id),
            accessor_role=accessor_role,
            session_id=str(session_id),
            outcome=transcript.outcome,
            has_dissent=transcript.has_dissent,
        )

        return transcript

    async def _build_full_transcript(
        self,
        session: DeliberationSession,
        witnesses: list[PhaseWitnessEvent],
    ) -> FullTranscriptResponse:
        """Build full transcript response from session and witnesses.

        ELEVATED ACCESS: Includes all Archon attributions and raw content.
        This is NOT mediated - full details exposed.

        Args:
            session: The completed deliberation session.
            witnesses: Phase witness events for hash references.

        Returns:
            FullTranscriptResponse with all details.
        """
        # Build phase transcripts from witnesses
        phases: list[PhaseTranscriptDetail] = []
        for witness in witnesses:
            phase_detail = await self._build_phase_detail(witness)
            phases.append(phase_detail)

        # Get dissent text if there was dissent
        dissent_text: str | None = None
        if session.dissent_archon_id is not None:
            dissent_text = await self._extract_dissent_text(session, witnesses)

        # Determine outcome string
        outcome_str = session.outcome.value if session.outcome else "UNKNOWN"

        assert session.completed_at is not None

        return FullTranscriptResponse(
            session_id=session.session_id,
            petition_id=session.petition_id,
            phases=phases,
            outcome=outcome_str,
            has_dissent=session.dissent_archon_id is not None,
            dissent_text=dissent_text,
            completed_at=session.completed_at,
        )

    async def _build_phase_detail(
        self,
        witness: PhaseWitnessEvent,
    ) -> PhaseTranscriptDetail:
        """Build phase transcript detail from witness event.

        Retrieves actual transcript content from store and parses
        utterances with Archon attribution.

        Args:
            witness: Phase witness event with hash reference.

        Returns:
            PhaseTranscriptDetail with full utterances.
        """
        # Get raw transcript content from store
        transcript_content = await self._transcript_store.retrieve(
            witness.transcript_hash
        )

        # Parse utterances from transcript content
        utterances: list[TranscriptUtterance] = []
        if transcript_content:
            utterances = self._parse_transcript_content(
                transcript_content,
                witness.participating_archons,
            )

        return PhaseTranscriptDetail(
            phase=witness.phase.value,
            start_timestamp=witness.start_timestamp,
            end_timestamp=witness.end_timestamp,
            utterances=utterances,
            transcript_hash_hex=witness.transcript_hash_hex,
        )

    def _parse_transcript_content(
        self,
        content: str,
        participating_archons: tuple[UUID, UUID, UUID],
    ) -> list[TranscriptUtterance]:
        """Parse transcript content into utterances with Archon attribution.

        The transcript content is expected to be JSON-formatted with
        utterance records containing archon_id, timestamp, content, sequence.

        Args:
            content: Raw transcript content (JSON).
            participating_archons: Tuple of participating Archon UUIDs.

        Returns:
            List of TranscriptUtterance objects.
        """
        try:
            # Attempt to parse as JSON
            data = json.loads(content)

            if isinstance(data, list):
                # List of utterances
                return [
                    TranscriptUtterance(
                        archon_id=UUID(item.get("archon_id", str(participating_archons[0]))),
                        timestamp=item.get("timestamp", "1970-01-01T00:00:00Z"),
                        content=item.get("content", ""),
                        sequence=item.get("sequence", i),
                    )
                    for i, item in enumerate(data)
                ]
            elif isinstance(data, dict):
                # Single utterance or structured format
                utterances_data = data.get("utterances", [data])
                return [
                    TranscriptUtterance(
                        archon_id=UUID(item.get("archon_id", str(participating_archons[0]))),
                        timestamp=item.get("timestamp", "1970-01-01T00:00:00Z"),
                        content=item.get("content", ""),
                        sequence=item.get("sequence", i),
                    )
                    for i, item in enumerate(utterances_data)
                ]

        except (json.JSONDecodeError, KeyError, ValueError):
            # If parsing fails, treat as plain text
            pass

        # Fallback: treat content as single utterance from first archon
        return [
            TranscriptUtterance(
                archon_id=participating_archons[0],
                timestamp="1970-01-01T00:00:00Z",  # Unknown timestamp
                content=content,
                sequence=0,
            )
        ]

    async def _extract_dissent_text(
        self,
        session: DeliberationSession,
        witnesses: list[PhaseWitnessEvent],
    ) -> str | None:
        """Extract dissent text from VOTE phase transcript.

        Dissent is recorded in the VOTE phase by the dissenting Archon.
        This extracts the raw dissent text for elevated access.

        Args:
            session: The deliberation session with dissent.
            witnesses: Phase witness events.

        Returns:
            Dissent text if found, None otherwise.
        """
        # Find VOTE phase witness
        vote_witness = next(
            (w for w in witnesses if w.phase == DeliberationPhase.VOTE),
            None,
        )

        if vote_witness is None:
            return None

        # Check phase metadata for dissent
        if "dissent_text" in vote_witness.phase_metadata:
            return vote_witness.phase_metadata["dissent_text"]

        # Try to extract from transcript content
        transcript_content = await self._transcript_store.retrieve(
            vote_witness.transcript_hash
        )

        if not transcript_content:
            return None

        try:
            data = json.loads(transcript_content)
            if isinstance(data, dict):
                return data.get("dissent_text")
        except json.JSONDecodeError:
            pass

        return None
