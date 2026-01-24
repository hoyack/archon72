"""Disposition emission stub for testing (Story 2A.8, FR-11.11).

This module provides a test stub implementation of DispositionEmissionProtocol
for unit and integration testing.

Usage:
    stub = DispositionEmissionStub()
    result = await stub.emit_disposition(session, consensus, petition)
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


# Required phases for complete witness chain
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
    DispositionOutcome.DEFER: PipelineType.DEFERRED_REVIEW,
    DispositionOutcome.NO_RESPONSE: PipelineType.NO_RESPONSE_ARCHIVE,
}


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class DispositionEmissionStub:
    """Test stub for DispositionEmissionProtocol (Story 2A.8).

    Provides configurable behavior for testing disposition emission
    and pipeline routing scenarios.

    Attributes:
        emit_calls: List of (session, consensus, petition) tuples from emit_disposition calls.
        route_calls: List of (petition, outcome, event_id) tuples from route_to_pipeline calls.
        pending_queries: List of (pipeline, limit) tuples from get_pending_dispositions calls.
        ack_calls: List of (petition_id, pipeline) tuples from acknowledge_routing calls.
        should_fail_validation: If True, emit_disposition raises IncompleteWitnessChainError.
        should_fail_routing: If True, route_to_pipeline raises PipelineRoutingError.
        should_fail_petition_state: If True, emit_disposition raises InvalidPetitionStateError.
        custom_result: If set, emit_disposition returns this instead of generating a result.
    """

    def __init__(self) -> None:
        """Initialize the stub with default behavior."""
        # Call tracking
        self.emit_calls: list[
            tuple[DeliberationSession, ConsensusResult, PetitionSubmission]
        ] = []
        self.route_calls: list[tuple[PetitionSubmission, DispositionOutcome, UUID]] = []
        self.pending_queries: list[tuple[PipelineType, int]] = []
        self.ack_calls: list[tuple[UUID, PipelineType]] = []

        # Configurable behavior
        self.should_fail_validation: bool = False
        self.should_fail_routing: bool = False
        self.should_fail_petition_state: bool = False
        self.custom_result: DispositionResult | None = None

        # In-memory queues for pending dispositions
        self._pending_queues: dict[PipelineType, list[PendingDisposition]] = (
            defaultdict(list)
        )
        self._emitted_sessions: dict[UUID, DispositionResult] = {}

    def reset(self) -> None:
        """Reset all call tracking and configurable state."""
        self.emit_calls.clear()
        self.route_calls.clear()
        self.pending_queries.clear()
        self.ack_calls.clear()
        self.should_fail_validation = False
        self.should_fail_routing = False
        self.should_fail_petition_state = False
        self.custom_result = None
        self._pending_queues.clear()
        self._emitted_sessions.clear()

    def add_pending_disposition(self, pending: PendingDisposition) -> None:
        """Add a pending disposition to a pipeline queue.

        Useful for setting up test scenarios.

        Args:
            pending: The pending disposition to add.
        """
        self._pending_queues[pending.pipeline].append(pending)
        self._pending_queues[pending.pipeline].sort(
            key=lambda p: (p.priority, p.queued_at)
        )

    async def emit_disposition(
        self,
        session: DeliberationSession,
        consensus: ConsensusResult,
        petition: PetitionSubmission,
    ) -> DispositionResult:
        """Emit disposition event and route to appropriate pipeline.

        Stub implementation that tracks calls and supports configurable behavior.

        Args:
            session: The completed deliberation session.
            consensus: The consensus result from ConsensusResolverService.
            petition: The petition being deliberated.

        Returns:
            DispositionResult with both events and routing details.

        Raises:
            IncompleteWitnessChainError: If should_fail_validation is True.
            InvalidPetitionStateError: If should_fail_petition_state is True.
            PipelineRoutingError: If should_fail_routing is True.
        """
        self.emit_calls.append((session, consensus, petition))

        # Return custom result if set
        if self.custom_result is not None:
            return self.custom_result

        # Idempotency check
        if session.session_id in self._emitted_sessions:
            return self._emitted_sessions[session.session_id]

        # Configurable failure scenarios
        if self.should_fail_validation:
            raise IncompleteWitnessChainError(
                session_id=session.session_id,
                missing_phases=[DeliberationPhase.VOTE],
            )

        if self.should_fail_petition_state:
            raise InvalidPetitionStateError(
                petition_id=str(petition.id),
                current_state=petition.state.value,
                expected_state="DELIBERATING",
            )

        if self.should_fail_routing:
            raise PipelineRoutingError(
                petition_id=petition.id,
                pipeline="UNKNOWN",
                reason="Stub configured to fail routing",
            )

        # Validate witness chain (unless bypassed)
        self._validate_witness_chain(session)

        # Validate petition state
        if petition.state != PetitionState.DELIBERATING:
            raise InvalidPetitionStateError(
                petition_id=str(petition.id),
                current_state=petition.state.value,
                expected_state="DELIBERATING",
            )

        # Map outcome
        outcome = self._map_outcome(consensus)

        # Get final witness hash
        final_witness_hash = session.phase_transcripts.get(
            DeliberationPhase.VOTE,
            b"\x00" * 32,  # Default for testing
        )

        # Build vote breakdown
        vote_breakdown = self._build_vote_breakdown(session)

        # Create events
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

        routing_event = await self.route_to_pipeline(
            petition=petition,
            outcome=outcome,
            deliberation_event_id=deliberation_event.event_id,
        )

        result = DispositionResult(
            deliberation_event=deliberation_event,
            routing_event=routing_event,
            success=True,
        )

        self._emitted_sessions[session.session_id] = result
        return result

    async def route_to_pipeline(
        self,
        petition: PetitionSubmission,
        outcome: DispositionOutcome,
        deliberation_event_id: UUID,
    ) -> PipelineRoutingEvent:
        """Route a petition to its target pipeline.

        Args:
            petition: The petition to route.
            outcome: The disposition outcome.
            deliberation_event_id: ID of the triggering event.

        Returns:
            PipelineRoutingEvent with routing details.
        """
        self.route_calls.append((petition, outcome, deliberation_event_id))

        pipeline = OUTCOME_TO_PIPELINE.get(outcome)
        if pipeline is None:
            raise PipelineRoutingError(
                petition_id=petition.id,
                pipeline="UNKNOWN",
                reason=f"No pipeline mapping for outcome {outcome.value}",
            )

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

        pending = PendingDisposition(
            petition_id=petition.id,
            outcome=outcome,
            pipeline=pipeline,
            deliberation_event_id=deliberation_event_id,
            routing_metadata=routing_event.routing_metadata,
        )

        self._pending_queues[pipeline].append(pending)
        return routing_event

    async def get_pending_dispositions(
        self,
        pipeline: PipelineType,
        limit: int = 100,
    ) -> list[PendingDisposition]:
        """Get pending dispositions for a pipeline.

        Args:
            pipeline: The pipeline type to query.
            limit: Maximum number to return.

        Returns:
            List of PendingDisposition in priority order.
        """
        self.pending_queries.append((pipeline, limit))
        queue = self._pending_queues.get(pipeline, [])
        return queue[:limit]

    async def acknowledge_routing(
        self,
        petition_id: UUID,
        pipeline: PipelineType,
    ) -> bool:
        """Acknowledge that a pipeline has picked up a petition.

        Args:
            petition_id: The petition ID.
            pipeline: The pipeline acknowledging.

        Returns:
            True if acknowledged, False if not found.
        """
        self.ack_calls.append((petition_id, pipeline))

        queue = self._pending_queues.get(pipeline, [])
        for i, pending in enumerate(queue):
            if pending.petition_id == petition_id:
                queue.pop(i)
                return True

        return False

    def _validate_witness_chain(self, session: DeliberationSession) -> None:
        """Validate that all 4 phase witnesses are recorded."""
        missing_phases: list[DeliberationPhase] = []

        for phase in REQUIRED_WITNESS_PHASES:
            if not session.has_transcript(phase):
                missing_phases.append(phase)

        if missing_phases:
            raise IncompleteWitnessChainError(
                session_id=session.session_id,
                missing_phases=missing_phases,
            )

    def _map_outcome(self, consensus: ConsensusResult) -> DispositionOutcome:
        """Map consensus winning outcome to DispositionOutcome."""
        if consensus.winning_outcome is None:
            raise PipelineRoutingError(
                petition_id=consensus.petition_id,
                pipeline="UNKNOWN",
                reason="Consensus has no winning outcome",
            )

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
        """Map dissenting archon's vote to DispositionOutcome."""
        if not consensus.has_dissent or consensus.dissent_archon_id is None:
            return None

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
    ) -> dict[UUID, tuple[DispositionOutcome, str]]:
        """Build vote breakdown from session."""
        vote_breakdown: dict[UUID, tuple[DispositionOutcome, str]] = {}

        for archon_id, vote in session.votes.items():
            outcome = DispositionOutcome(vote.value)
            rationale = f"Voted {vote.value} during deliberation"
            vote_breakdown[archon_id] = (outcome, rationale)

        return vote_breakdown
