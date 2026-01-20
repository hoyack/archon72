"""Disposition emission service (Story 2A.8, FR-11.11).

This module implements the DispositionEmissionProtocol for emitting
deliberation outcomes and routing petitions to downstream pipelines.

Constitutional Constraints:
- CT-14: Every claim terminates in witnessed fate
- CT-12: Outcome witnessed by participating archons
- FR-11.11: Route to appropriate pipeline

Pipeline Routing:
- ACKNOWLEDGE → Acknowledgment Execution (Epic 3)
- REFER → Knight Referral Workflow (Epic 4)
- ESCALATE → King Escalation Queue (Epic 6)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.domain.errors.deliberation import (
    IncompleteWitnessChainError,
    InvalidPetitionStateError,
    PipelineRoutingError,
)
from src.domain.events.disposition import (
    DeliberationCompleteEvent,
    DispositionOutcome,
    PipelineRoutingEvent,
    PipelineType,
)
from src.domain.models.consensus_result import ConsensusResult
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.disposition_result import (
    DispositionResult,
    PendingDisposition,
)
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Required phases for complete witness chain (4 phases before COMPLETE)
REQUIRED_WITNESS_PHASES: tuple[DeliberationPhase, ...] = (
    DeliberationPhase.ASSESS,
    DeliberationPhase.POSITION,
    DeliberationPhase.CROSS_EXAMINE,
    DeliberationPhase.VOTE,
)


# Mapping from DispositionOutcome to PipelineType
OUTCOME_TO_PIPELINE: dict[DispositionOutcome, PipelineType] = {
    DispositionOutcome.ACKNOWLEDGE: PipelineType.ACKNOWLEDGMENT,
    DispositionOutcome.REFER: PipelineType.KNIGHT_REFERRAL,
    DispositionOutcome.ESCALATE: PipelineType.KING_ESCALATION,
}


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class DispositionEmissionService:
    """Service for disposition emission and pipeline routing (Story 2A.8, FR-11.11).

    Emits the deliberation outcome as an event and routes the petition
    to the appropriate downstream pipeline based on the Three Fates disposition.

    Constitutional Constraints:
    - CT-14: Every claim terminates in witnessed fate
    - CT-12: Outcome witnessed by participating archons
    - FR-11.11: Route to appropriate pipeline

    Pipeline Routing:
    - ACKNOWLEDGE → Acknowledgment Execution (Epic 3)
    - REFER → Knight Referral Workflow (Epic 4)
    - ESCALATE → King Escalation Queue (Epic 6)
    """

    def __init__(self) -> None:
        """Initialize disposition emission service."""
        # In-memory queue for pending dispositions (keyed by pipeline)
        self._pending_queues: dict[PipelineType, list[PendingDisposition]] = (
            defaultdict(list)
        )
        # Track emitted dispositions for idempotency
        self._emitted_sessions: dict[UUID, DispositionResult] = {}

    async def emit_disposition(
        self,
        session: DeliberationSession,
        consensus: ConsensusResult,
        petition: PetitionSubmission,
    ) -> DispositionResult:
        """Emit disposition event and route to appropriate pipeline.

        This is the main entry point for completing a deliberation.
        It performs the following atomically:
        1. Validates witness chain is complete (4 phases)
        2. Creates DeliberationCompleteEvent
        3. Validates petition state
        4. Routes to appropriate pipeline
        5. Creates PipelineRoutingEvent

        Args:
            session: The completed deliberation session.
            consensus: The consensus result from ConsensusResolverService.
            petition: The petition being deliberated.

        Returns:
            DispositionResult with both events and routing details.

        Raises:
            IncompleteWitnessChainError: If witness chain has < 4 phases.
            InvalidPetitionStateError: If petition not in DELIBERATING state.
            PipelineRoutingError: If routing fails.
        """
        logger.info(
            "Emitting disposition for session %s, petition %s",
            session.session_id,
            petition.id,
        )

        # Idempotency check - return existing result if already emitted
        if session.session_id in self._emitted_sessions:
            logger.info(
                "Session %s already emitted, returning cached result",
                session.session_id,
            )
            return self._emitted_sessions[session.session_id]

        # Step 1: Validate witness chain completeness (CT-14, NFR-10.4)
        self._validate_witness_chain(session)

        # Step 2: Validate petition state (must be DELIBERATING)
        self._validate_petition_state(petition)

        # Step 3: Convert consensus outcome to disposition outcome
        outcome = self._map_outcome(consensus)

        # Step 4: Get the final witness hash from VOTE phase
        final_witness_hash = session.phase_transcripts[DeliberationPhase.VOTE]

        # Step 5: Build vote breakdown from consensus
        vote_breakdown = self._build_vote_breakdown(session, consensus)

        # Step 6: Create DeliberationCompleteEvent
        deliberation_event = DeliberationCompleteEvent(
            event_id=uuid4(),
            petition_id=petition.id,
            session_id=session.session_id,
            outcome=outcome,
            vote_breakdown=vote_breakdown,
            dissent_present=consensus.has_dissent,
            final_witness_hash=final_witness_hash,
            dissent_archon_id=consensus.dissent_archon_id,
            dissent_disposition=self._map_dissent_outcome(consensus),
        )

        # Step 7: Route to pipeline
        routing_event = await self.route_to_pipeline(
            petition=petition,
            outcome=outcome,
            deliberation_event_id=deliberation_event.event_id,
        )

        # Step 8: Create and cache result
        result = DispositionResult(
            deliberation_event=deliberation_event,
            routing_event=routing_event,
            success=True,
        )

        self._emitted_sessions[session.session_id] = result

        logger.info(
            "Disposition emitted for session %s: outcome=%s, pipeline=%s",
            session.session_id,
            outcome.value,
            routing_event.pipeline.value,
        )

        return result

    async def route_to_pipeline(
        self,
        petition: PetitionSubmission,
        outcome: DispositionOutcome,
        deliberation_event_id: UUID,
    ) -> PipelineRoutingEvent:
        """Route a petition to its target pipeline.

        Called internally by emit_disposition, but also available
        for re-routing scenarios.

        Args:
            petition: The petition to route.
            outcome: The disposition outcome.
            deliberation_event_id: ID of the triggering event.

        Returns:
            PipelineRoutingEvent with routing details.

        Raises:
            PipelineRoutingError: If routing fails.
        """
        # Determine target pipeline from outcome
        pipeline = OUTCOME_TO_PIPELINE.get(outcome)
        if pipeline is None:
            raise PipelineRoutingError(
                petition_id=petition.id,
                pipeline="UNKNOWN",
                reason=f"No pipeline mapping for outcome {outcome.value}",
            )

        # Create routing event
        routing_event = PipelineRoutingEvent(
            event_id=uuid4(),
            petition_id=petition.id,
            pipeline=pipeline,
            deliberation_event_id=deliberation_event_id,
            routing_metadata={
                "petition_type": petition.type.value,
                "realm": petition.realm,
            },
        )

        # Create pending disposition for pipeline queue
        pending = PendingDisposition(
            petition_id=petition.id,
            outcome=outcome,
            pipeline=pipeline,
            deliberation_event_id=deliberation_event_id,
            routing_metadata=routing_event.routing_metadata,
        )

        # Add to pending queue
        self._pending_queues[pipeline].append(pending)
        self._pending_queues[pipeline].sort(key=lambda p: (p.priority, p.queued_at))

        logger.info(
            "Petition %s routed to pipeline %s",
            petition.id,
            pipeline.value,
        )

        return routing_event

    async def get_pending_dispositions(
        self,
        pipeline: PipelineType,
        limit: int = 100,
    ) -> list[PendingDisposition]:
        """Get pending dispositions for a pipeline.

        Used by downstream pipelines to retrieve their queued work.

        Args:
            pipeline: The pipeline type to query.
            limit: Maximum number to return.

        Returns:
            List of PendingDisposition in priority order.
        """
        queue = self._pending_queues.get(pipeline, [])
        return queue[:limit]

    async def acknowledge_routing(
        self,
        petition_id: UUID,
        pipeline: PipelineType,
    ) -> bool:
        """Acknowledge that a pipeline has picked up a petition.

        Removes the petition from pending queue.

        Args:
            petition_id: The petition ID.
            pipeline: The pipeline acknowledging.

        Returns:
            True if acknowledged, False if not found.
        """
        queue = self._pending_queues.get(pipeline, [])

        for i, pending in enumerate(queue):
            if pending.petition_id == petition_id:
                queue.pop(i)
                logger.info(
                    "Petition %s acknowledged by pipeline %s",
                    petition_id,
                    pipeline.value,
                )
                return True

        logger.warning(
            "Petition %s not found in pipeline %s queue",
            petition_id,
            pipeline.value,
        )
        return False

    def _validate_witness_chain(self, session: DeliberationSession) -> None:
        """Validate that all 4 phase witnesses are recorded.

        Args:
            session: The deliberation session to validate.

        Raises:
            IncompleteWitnessChainError: If any required phases are missing.
        """
        missing_phases: list[DeliberationPhase] = []

        for phase in REQUIRED_WITNESS_PHASES:
            if not session.has_transcript(phase):
                missing_phases.append(phase)

        if missing_phases:
            raise IncompleteWitnessChainError(
                session_id=session.session_id,
                missing_phases=missing_phases,
            )

    def _validate_petition_state(self, petition: PetitionSubmission) -> None:
        """Validate petition is in DELIBERATING state.

        Args:
            petition: The petition to validate.

        Raises:
            InvalidPetitionStateError: If not in DELIBERATING state.
        """
        if petition.state != PetitionState.DELIBERATING:
            raise InvalidPetitionStateError(
                petition_id=str(petition.id),
                current_state=petition.state.value,
                expected_state="DELIBERATING",
            )

    def _map_outcome(self, consensus: ConsensusResult) -> DispositionOutcome:
        """Map consensus winning outcome to DispositionOutcome.

        Args:
            consensus: The consensus result.

        Returns:
            The corresponding DispositionOutcome.

        Raises:
            PipelineRoutingError: If outcome cannot be mapped.
        """
        if consensus.winning_outcome is None:
            raise PipelineRoutingError(
                petition_id=consensus.petition_id,
                pipeline="UNKNOWN",
                reason="Consensus has no winning outcome",
            )

        # Map string outcome to DispositionOutcome enum
        try:
            return DispositionOutcome(consensus.winning_outcome)
        except ValueError:
            raise PipelineRoutingError(
                petition_id=consensus.petition_id,
                pipeline="UNKNOWN",
                reason=f"Invalid outcome value: {consensus.winning_outcome}",
            )

    def _map_dissent_outcome(
        self, consensus: ConsensusResult
    ) -> DispositionOutcome | None:
        """Map dissenting archon's vote to DispositionOutcome.

        Args:
            consensus: The consensus result.

        Returns:
            The dissenter's outcome, or None if unanimous.
        """
        if not consensus.has_dissent or consensus.dissent_archon_id is None:
            return None

        # Find what the dissenter voted for from vote_distribution
        # Note: ConsensusResult stores vote_distribution as dict[str, int]
        # which counts votes per outcome, not individual votes
        # We need to find the outcome that isn't the winning one with count 1
        for outcome_str, count in consensus.vote_distribution.items():
            if outcome_str != consensus.winning_outcome and count == 1:
                try:
                    return DispositionOutcome(outcome_str)
                except ValueError:
                    return None

        return None

    def _build_vote_breakdown(
        self,
        session: DeliberationSession,
        consensus: ConsensusResult,
    ) -> dict[UUID, tuple[DispositionOutcome, str]]:
        """Build vote breakdown from session and consensus.

        Args:
            session: The deliberation session with votes.
            consensus: The consensus result.

        Returns:
            Dict mapping archon_id to (outcome, rationale).
        """
        vote_breakdown: dict[UUID, tuple[DispositionOutcome, str]] = {}

        for archon_id, vote in session.votes.items():
            # Map DeliberationOutcome to DispositionOutcome
            outcome = DispositionOutcome(vote.value)
            # Use a default rationale since session doesn't store rationales
            rationale = f"Voted {vote.value} during deliberation"
            vote_breakdown[archon_id] = (outcome, rationale)

        return vote_breakdown
