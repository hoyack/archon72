"""Transcript Access Mediation Service (Story 7.4, FR-7.4, Ruling-2).

This service provides mediated access to deliberation outcomes per Ruling-2
(Tiered Transcript Access). Observers receive summarized views that hide
sensitive details while proving immutability via hash references.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - mediated, not raw
- FR-7.4: System SHALL provide deliberation summary to Observer
- PRD Section 13A.8: Observer tier access definition
- CT-12: Witnessing creates accountability - hash references prove immutability

MEDIATION IS CRITICAL:
- Never expose raw Archon identities (UUIDs) to Observers
- Never expose individual vote choices (who voted for what)
- Vote breakdown is anonymous (e.g., "2-1", not "Archon A voted X")
- Dissent is boolean only (has_dissent: true/false)
- Phase summaries expose metadata, not transcript content
- Hash references prove transcripts exist without revealing content
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from src.application.ports.deliberation_summary import (
    DeliberationSummaryRepositoryProtocol,
)
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.services.base import LoggingMixin
from src.domain.errors.deliberation import DeliberationPendingError
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
)
from src.domain.models.deliberation_summary import (
    DeliberationSummary,
    EscalationTrigger,
    PhaseSummaryItem,
)
from src.domain.models.petition_submission import PetitionState

if TYPE_CHECKING:
    from src.domain.events.phase_witness import PhaseWitnessEvent
    from src.domain.models.deliberation_session import DeliberationSession


class TranscriptAccessMediationService(LoggingMixin):
    """Service for mediated access to deliberation summaries (Story 7.4, Ruling-2).

    Provides the Observer tier of transcript access per PRD Section 13A.8:
    - Phase summaries + final disposition rationale
    - Vote breakdown (anonymous)
    - Dissent presence indicator (boolean)
    - Hash references (proving immutability)

    Does NOT provide:
    - Raw transcript text
    - Individual Archon identities
    - Verbatim utterances
    - Who voted for what

    Constitutional Constraints:
    - Ruling-2: Tiered transcript access
    - FR-7.4: System SHALL provide deliberation summary
    - CT-12: Witnessing creates accountability
    - PRD Section 13A.8: Observer tier access

    Attributes:
        _summary_repo: Repository for deliberation session data.
        _petition_repo: Repository for petition data.
    """

    def __init__(
        self,
        summary_repo: DeliberationSummaryRepositoryProtocol,
        petition_repo: PetitionSubmissionRepositoryProtocol,
    ) -> None:
        """Initialize the transcript access mediation service.

        Args:
            summary_repo: Repository for deliberation data.
            petition_repo: Repository for petition data.
        """
        self._summary_repo = summary_repo
        self._petition_repo = petition_repo
        self._init_logger(component="petition")

    async def get_deliberation_summary(
        self,
        petition_id: UUID,
    ) -> DeliberationSummary:
        """Get mediated deliberation summary for a petition (FR-7.4).

        Returns a summary appropriate for Observer tier access per Ruling-2.
        All sensitive details (Archon identities, raw transcripts) are filtered.

        Constitutional Constraints:
        - Ruling-2: Mediated access only
        - FR-7.4: System SHALL provide deliberation summary
        - CT-12: Hash references prove witnessing
        - AC-5: Read operations permitted during halt (no halt check needed)

        Args:
            petition_id: UUID of the petition.

        Returns:
            DeliberationSummary with mediated view of deliberation outcome.

        Raises:
            PetitionNotFoundError: If petition does not exist (AC-4).
            DeliberationPendingError: If deliberation not yet complete (AC-3).
        """
        log = self._log_operation(
            "get_deliberation_summary",
            petition_id=str(petition_id),
        )
        log.info("summary_request_received")

        # 1. Check petition exists
        petition = await self._petition_repo.get(petition_id)
        if petition is None:
            log.warning("petition_not_found")
            raise PetitionNotFoundError(petition_id=str(petition_id))

        # 2. Check petition has completed deliberation
        if petition.state == PetitionState.RECEIVED:
            log.info("deliberation_pending", current_state=petition.state.value)
            raise DeliberationPendingError(
                petition_id=str(petition_id),
                current_state=petition.state.value,
            )

        # 3. Check for auto-escalation (no deliberation session)
        if petition.state == PetitionState.ESCALATED:
            # Check if there's a session - if not, was auto-escalated
            session = await self._summary_repo.get_session_by_petition_id(petition_id)
            if session is None:
                log.info("auto_escalation_detected")
                return self._build_auto_escalation_summary(petition_id, petition)

        # 4. Get deliberation session
        session = await self._summary_repo.get_session_by_petition_id(petition_id)
        if session is None:
            # Should not happen for non-auto-escalated petitions
            log.warning("session_not_found_unexpectedly")
            raise DeliberationPendingError(
                petition_id=str(petition_id),
                current_state=petition.state.value,
            )

        # 5. Check session is complete
        if session.phase != DeliberationPhase.COMPLETE:
            log.info(
                "deliberation_in_progress",
                session_phase=session.phase.value,
            )
            raise DeliberationPendingError(
                petition_id=str(petition_id),
                current_state=f"deliberation:{session.phase.value}",
            )

        # 6. Get phase witnesses for hash references
        witnesses = await self._summary_repo.get_phase_witnesses(session.session_id)

        # 7. Build mediated summary
        summary = self._build_mediated_summary(session, witnesses)
        log.info(
            "summary_generated",
            outcome=summary.outcome.value,
            has_dissent=summary.has_dissent,
        )

        return summary

    def _build_auto_escalation_summary(
        self,
        petition_id: UUID,
        petition: object,  # PetitionSubmission, avoiding circular import
    ) -> DeliberationSummary:
        """Build summary for auto-escalated petition (AC-2).

        Auto-escalation occurs when co-signer threshold is reached,
        bypassing the deliberation process entirely.

        Args:
            petition_id: UUID of the petition.
            petition: The petition object (for completed_at).

        Returns:
            DeliberationSummary indicating auto-escalation.
        """
        # Get completed_at from petition's updated_at or now
        completed_at: datetime
        if hasattr(petition, "updated_at") and petition.updated_at is not None:
            completed_at = petition.updated_at
        else:
            from datetime import timezone

            completed_at = datetime.now(timezone.utc)

        return DeliberationSummary.from_auto_escalation(
            petition_id=petition_id,
            escalation_reason="Co-signer threshold reached, automatic escalation",
            completed_at=completed_at,
        )

    def _build_mediated_summary(
        self,
        session: DeliberationSession,
        witnesses: list[PhaseWitnessEvent],
    ) -> DeliberationSummary:
        """Build mediated summary from session and witnesses (AC-1, AC-6, AC-7).

        This is the core mediation logic. It extracts only permitted fields
        and computes derived values without exposing Archon identities.

        MEDIATION RULES (Ruling-2):
        - vote_breakdown: Anonymous count (e.g., "2-1"), not who voted what
        - has_dissent: Boolean only, not dissenter identity
        - phase_summaries: Metadata and hashes, not transcript content
        - No Archon UUIDs exposed

        Args:
            session: The completed deliberation session.
            witnesses: Phase witness events for hash references.

        Returns:
            DeliberationSummary with mediated content.
        """
        # Handle special cases first
        if session.timed_out:
            return self._build_timeout_summary(session, witnesses)

        if session.is_deadlocked:
            return self._build_deadlock_summary(session, witnesses)

        # Normal completion - compute vote breakdown
        vote_breakdown = self._compute_vote_breakdown(session)
        has_dissent = session.dissent_archon_id is not None

        # Build phase summaries from witnesses (mediated)
        phase_summaries = self._build_phase_summaries(witnesses)

        # Compute duration
        duration_seconds = self._compute_duration_seconds(session)

        # Determine escalation trigger if outcome is ESCALATE
        escalation_trigger: EscalationTrigger | None = None
        if session.outcome == DeliberationOutcome.ESCALATE:
            escalation_trigger = EscalationTrigger.DELIBERATION

        assert session.completed_at is not None
        assert session.outcome is not None

        return DeliberationSummary(
            petition_id=session.petition_id,
            outcome=session.outcome,
            vote_breakdown=vote_breakdown,
            has_dissent=has_dissent,
            phase_summaries=tuple(phase_summaries),
            duration_seconds=duration_seconds,
            completed_at=session.completed_at,
            escalation_trigger=escalation_trigger,
            escalation_reason=None,
            timed_out=False,
            rounds_attempted=session.round_count,
        )

    def _build_timeout_summary(
        self,
        session: DeliberationSession,
        witnesses: list[PhaseWitnessEvent],
    ) -> DeliberationSummary:
        """Build summary for timeout-triggered escalation (AC-6).

        Args:
            session: The timed-out deliberation session.
            witnesses: Partial phase witness events.

        Returns:
            DeliberationSummary indicating timeout.
        """
        phase_summaries = self._build_phase_summaries(witnesses)
        duration_seconds = self._compute_duration_seconds(session)

        assert session.completed_at is not None

        return DeliberationSummary.from_timeout(
            petition_id=session.petition_id,
            phase_summaries=tuple(phase_summaries),
            duration_seconds=duration_seconds,
            completed_at=session.completed_at,
        )

    def _build_deadlock_summary(
        self,
        session: DeliberationSession,
        witnesses: list[PhaseWitnessEvent],
    ) -> DeliberationSummary:
        """Build summary for deadlock-triggered escalation (AC-7).

        Args:
            session: The deadlocked deliberation session.
            witnesses: Full phase witness events across all rounds.

        Returns:
            DeliberationSummary indicating deadlock.
        """
        phase_summaries = self._build_phase_summaries(witnesses)
        duration_seconds = self._compute_duration_seconds(session)

        assert session.completed_at is not None

        return DeliberationSummary.from_deadlock(
            petition_id=session.petition_id,
            phase_summaries=tuple(phase_summaries),
            duration_seconds=duration_seconds,
            completed_at=session.completed_at,
            rounds_attempted=session.round_count,
        )

    def _compute_vote_breakdown(self, session: DeliberationSession) -> str:
        """Compute anonymous vote breakdown string (Ruling-2).

        Returns format "X-Y" where X is majority count, Y is minority.
        Example: "2-1" for 2-1 consensus, "3-0" for unanimous.

        CRITICAL: This HIDES who voted for what - only counts revealed.

        Args:
            session: The deliberation session with votes.

        Returns:
            Vote breakdown string (e.g., "2-1", "3-0").
        """
        if not session.votes:
            return "0-0"

        # Count votes by outcome
        vote_counts: dict[DeliberationOutcome, int] = {}
        for vote in session.votes.values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        # Find majority and minority
        if not vote_counts:
            return "0-0"

        counts = sorted(vote_counts.values(), reverse=True)

        if len(counts) == 1:
            # Unanimous
            return f"{counts[0]}-0"
        elif len(counts) == 2:
            # 2-1 split
            return f"{counts[0]}-{counts[1]}"
        else:
            # 3-way split (shouldn't happen with consensus resolution)
            return f"{counts[0]}-{sum(counts[1:])}"

    def _build_phase_summaries(
        self,
        witnesses: list[PhaseWitnessEvent],
    ) -> list[PhaseSummaryItem]:
        """Build phase summaries from witness events (Ruling-2).

        Extracts metadata (duration, themes, hashes) without transcript content.
        Archon UUIDs from participating_archons are NOT exposed.

        Args:
            witnesses: Phase witness events.

        Returns:
            List of PhaseSummaryItem with mediated content.
        """
        summaries: list[PhaseSummaryItem] = []

        for witness in witnesses:
            # Compute phase duration
            duration_seconds = int(
                (witness.end_timestamp - witness.start_timestamp).total_seconds()
            )

            # Extract themes from metadata (if present)
            themes: tuple[str, ...] = tuple()
            if "themes" in witness.phase_metadata:
                themes = tuple(witness.phase_metadata["themes"])

            # Extract convergence indicator (if present)
            convergence: bool | None = witness.phase_metadata.get("convergence_reached")

            summaries.append(
                PhaseSummaryItem(
                    phase=witness.phase,
                    duration_seconds=duration_seconds,
                    transcript_hash_hex=witness.transcript_hash_hex,
                    themes=themes,
                    convergence_reached=convergence,
                )
            )

        return summaries

    def _compute_duration_seconds(self, session: DeliberationSession) -> int:
        """Compute total deliberation duration in seconds.

        Args:
            session: The deliberation session.

        Returns:
            Duration in seconds from created_at to completed_at.
        """
        if session.completed_at is None:
            return 0

        delta = session.completed_at - session.created_at
        return int(delta.total_seconds())
