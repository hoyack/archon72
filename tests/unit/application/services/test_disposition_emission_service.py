"""Unit tests for DispositionEmissionService (Story 2A.8, FR-11.11).

Tests verify:
- AC1: Service emits DeliberationCompleteEvent with outcome
- AC2: Event includes vote breakdown and dissent info
- AC3: Service routes to correct pipeline based on outcome
- AC4: ACKNOWLEDGE -> Acknowledgment pipeline
- AC5: REFER -> Knight Referral pipeline
- AC6: ESCALATE -> King Escalation pipeline
- AC7: Error handling for incomplete witness chain
- AC8: Unit tests pass (this file)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.disposition_emission_service import (
    DispositionEmissionService,
    OUTCOME_TO_PIPELINE,
    REQUIRED_WITNESS_PHASES,
)
from src.domain.errors.deliberation import (
    IncompleteWitnessChainError,
    InvalidPetitionStateError,
    PipelineRoutingError,
)
from src.domain.events.disposition import (
    DispositionOutcome,
    PipelineType,
)
from src.domain.models.consensus_result import (
    ConsensusResult,
    ConsensusStatus,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def _create_test_archons() -> tuple[uuid4, uuid4, uuid4]:
    """Create 3 test archon UUIDs."""
    return (uuid4(), uuid4(), uuid4())


def _create_complete_session(
    archons: tuple,
    votes: dict | None = None,
    outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
    dissent_archon_id: uuid4 | None = None,
) -> DeliberationSession:
    """Create a completed deliberation session with all phases witnessed.

    Args:
        archons: Tuple of 3 archon UUIDs.
        votes: Optional votes dict. Defaults to all voting for outcome.
        outcome: The deliberation outcome.
        dissent_archon_id: Optional dissenter ID.

    Returns:
        A completed DeliberationSession.
    """
    session_id = uuid4()
    petition_id = uuid4()

    # Default votes: all vote for outcome
    if votes is None:
        votes = {
            archons[0]: outcome,
            archons[1]: outcome,
            archons[2]: outcome,
        }

    # Create phase transcripts (32-byte Blake3 hashes)
    phase_transcripts = {
        DeliberationPhase.ASSESS: b"\x01" * 32,
        DeliberationPhase.POSITION: b"\x02" * 32,
        DeliberationPhase.CROSS_EXAMINE: b"\x03" * 32,
        DeliberationPhase.VOTE: b"\x04" * 32,
    }

    return DeliberationSession(
        session_id=session_id,
        petition_id=petition_id,
        assigned_archons=archons,
        phase=DeliberationPhase.COMPLETE,
        phase_transcripts=phase_transcripts,
        votes=votes,
        outcome=outcome,
        dissent_archon_id=dissent_archon_id,
        completed_at=_utc_now(),
    )


def _create_incomplete_session(
    archons: tuple,
    missing_phase: DeliberationPhase,
) -> DeliberationSession:
    """Create a session missing a phase transcript.

    Args:
        archons: Tuple of 3 archon UUIDs.
        missing_phase: The phase to omit from transcripts.

    Returns:
        A DeliberationSession missing the specified phase transcript.
    """
    session_id = uuid4()
    petition_id = uuid4()

    outcome = DeliberationOutcome.ACKNOWLEDGE
    votes = {archon: outcome for archon in archons}

    # Create phase transcripts but omit missing_phase
    phase_transcripts = {}
    for phase in [
        DeliberationPhase.ASSESS,
        DeliberationPhase.POSITION,
        DeliberationPhase.CROSS_EXAMINE,
        DeliberationPhase.VOTE,
    ]:
        if phase != missing_phase:
            phase_transcripts[phase] = bytes([phase.value[0].encode()[0]] * 32)

    return DeliberationSession(
        session_id=session_id,
        petition_id=petition_id,
        assigned_archons=archons,
        phase=DeliberationPhase.COMPLETE,
        phase_transcripts=phase_transcripts,
        votes=votes,
        outcome=outcome,
        completed_at=_utc_now(),
    )


def _create_consensus(
    session: DeliberationSession,
    winning_outcome: str,
    status: ConsensusStatus = ConsensusStatus.UNANIMOUS,
    dissent_archon_id: uuid4 | None = None,
) -> ConsensusResult:
    """Create a ConsensusResult matching the session.

    Args:
        session: The deliberation session.
        winning_outcome: String value of winning outcome.
        status: Consensus status (UNANIMOUS or ACHIEVED).
        dissent_archon_id: Optional dissenter ID.

    Returns:
        A ConsensusResult.
    """
    # Count votes by outcome
    vote_distribution: dict[str, int] = {}
    for vote in session.votes.values():
        vote_distribution[vote.value] = vote_distribution.get(vote.value, 0) + 1

    majority_archons = [
        aid for aid, vote in session.votes.items() if vote.value == winning_outcome
    ]

    return ConsensusResult(
        session_id=session.session_id,
        petition_id=session.petition_id,
        status=status,
        winning_outcome=winning_outcome,
        vote_distribution=vote_distribution,
        majority_archon_ids=tuple(majority_archons),
        dissent_archon_id=dissent_archon_id,
    )


def _create_petition(
    petition_id: uuid4,
    state: PetitionState = PetitionState.DELIBERATING,
) -> PetitionSubmission:
    """Create a test petition.

    Args:
        petition_id: The petition ID.
        state: Petition state.

    Returns:
        A PetitionSubmission.
    """
    return PetitionSubmission(
        id=petition_id,
        type=PetitionType.GENERAL,
        text="Test petition for disposition emission",
        state=state,
        realm="test-realm",
    )


class TestDispositionEmissionService:
    """Tests for DispositionEmissionService."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = DispositionEmissionService()
        self.archons = _create_test_archons()

    @pytest.mark.asyncio
    async def test_emit_disposition_success_acknowledge(self) -> None:
        """Test AC1, AC4: emit_disposition creates events and routes to ACKNOWLEDGMENT pipeline."""
        # Arrange
        session = _create_complete_session(
            archons=self.archons,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")
        petition = _create_petition(session.petition_id)

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Assert
        assert result.success is True
        assert result.outcome == DispositionOutcome.ACKNOWLEDGE
        assert result.target_pipeline == PipelineType.ACKNOWLEDGMENT
        assert result.deliberation_event.session_id == session.session_id
        assert result.routing_event.pipeline == PipelineType.ACKNOWLEDGMENT

    @pytest.mark.asyncio
    async def test_emit_disposition_success_refer(self) -> None:
        """Test AC5: REFER outcome routes to KNIGHT_REFERRAL pipeline."""
        # Arrange
        session = _create_complete_session(
            archons=self.archons,
            outcome=DeliberationOutcome.REFER,
        )
        consensus = _create_consensus(session, "REFER")
        petition = _create_petition(session.petition_id)

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Assert
        assert result.success is True
        assert result.outcome == DispositionOutcome.REFER
        assert result.target_pipeline == PipelineType.KNIGHT_REFERRAL

    @pytest.mark.asyncio
    async def test_emit_disposition_success_escalate(self) -> None:
        """Test AC6: ESCALATE outcome routes to KING_ESCALATION pipeline."""
        # Arrange
        session = _create_complete_session(
            archons=self.archons,
            outcome=DeliberationOutcome.ESCALATE,
        )
        consensus = _create_consensus(session, "ESCALATE")
        petition = _create_petition(session.petition_id)

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Assert
        assert result.success is True
        assert result.outcome == DispositionOutcome.ESCALATE
        assert result.target_pipeline == PipelineType.KING_ESCALATION

    @pytest.mark.asyncio
    async def test_emit_disposition_with_dissent(self) -> None:
        """Test AC2: Event includes vote breakdown and dissent info."""
        # Arrange - create 2-1 vote
        votes = {
            self.archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            self.archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            self.archons[2]: DeliberationOutcome.REFER,  # Dissenter
        }
        session = _create_complete_session(
            archons=self.archons,
            votes=votes,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            dissent_archon_id=self.archons[2],
        )
        consensus = _create_consensus(
            session,
            "ACKNOWLEDGE",
            status=ConsensusStatus.ACHIEVED,
            dissent_archon_id=self.archons[2],
        )
        petition = _create_petition(session.petition_id)

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Assert
        assert result.success is True
        assert result.deliberation_event.dissent_present is True
        assert result.deliberation_event.dissent_archon_id == self.archons[2]
        assert result.deliberation_event.dissent_disposition == DispositionOutcome.REFER
        assert len(result.deliberation_event.vote_breakdown) == 3

    @pytest.mark.asyncio
    async def test_emit_disposition_idempotent(self) -> None:
        """Test idempotency: calling twice returns same result."""
        # Arrange
        session = _create_complete_session(
            archons=self.archons,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")
        petition = _create_petition(session.petition_id)

        # Act
        result1 = await self.service.emit_disposition(session, consensus, petition)
        result2 = await self.service.emit_disposition(session, consensus, petition)

        # Assert
        assert result1.deliberation_event.event_id == result2.deliberation_event.event_id
        assert result1.routing_event.event_id == result2.routing_event.event_id

    @pytest.mark.asyncio
    async def test_emit_disposition_incomplete_witness_chain(self) -> None:
        """Test AC7: Error when witness chain is incomplete."""
        # Arrange - missing VOTE phase transcript
        session = _create_incomplete_session(
            archons=self.archons,
            missing_phase=DeliberationPhase.VOTE,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")
        petition = _create_petition(session.petition_id)

        # Act & Assert
        with pytest.raises(IncompleteWitnessChainError) as exc_info:
            await self.service.emit_disposition(session, consensus, petition)

        assert DeliberationPhase.VOTE in exc_info.value.missing_phases

    @pytest.mark.asyncio
    async def test_emit_disposition_wrong_petition_state(self) -> None:
        """Test AC7: Error when petition not in DELIBERATING state."""
        # Arrange
        session = _create_complete_session(
            archons=self.archons,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")
        # Petition in wrong state
        petition = _create_petition(session.petition_id, state=PetitionState.RECEIVED)

        # Act & Assert
        with pytest.raises(InvalidPetitionStateError) as exc_info:
            await self.service.emit_disposition(session, consensus, petition)

        assert exc_info.value.current_state == "RECEIVED"
        assert exc_info.value.expected_state == "DELIBERATING"

    @pytest.mark.asyncio
    async def test_emit_disposition_invalid_outcome(self) -> None:
        """Test AC7: Error when consensus has no winning outcome."""
        # Arrange
        session = _create_complete_session(
            archons=self.archons,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
        )
        # Consensus with no winning outcome
        consensus = ConsensusResult(
            session_id=session.session_id,
            petition_id=session.petition_id,
            status=ConsensusStatus.NOT_REACHED,
            winning_outcome=None,
            vote_distribution={"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1},
        )
        petition = _create_petition(session.petition_id)

        # Act & Assert
        with pytest.raises(PipelineRoutingError):
            await self.service.emit_disposition(session, consensus, petition)


class TestRouteToBasePipeline:
    """Tests for route_to_pipeline method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = DispositionEmissionService()

    @pytest.mark.asyncio
    async def test_route_to_acknowledgment_pipeline(self) -> None:
        """Test routing to ACKNOWLEDGMENT pipeline."""
        # Arrange
        petition = _create_petition(uuid4())
        event_id = uuid4()

        # Act
        result = await self.service.route_to_pipeline(
            petition=petition,
            outcome=DispositionOutcome.ACKNOWLEDGE,
            deliberation_event_id=event_id,
        )

        # Assert
        assert result.pipeline == PipelineType.ACKNOWLEDGMENT
        assert result.petition_id == petition.id
        assert result.deliberation_event_id == event_id

    @pytest.mark.asyncio
    async def test_route_to_knight_referral_pipeline(self) -> None:
        """Test routing to KNIGHT_REFERRAL pipeline."""
        # Arrange
        petition = _create_petition(uuid4())
        event_id = uuid4()

        # Act
        result = await self.service.route_to_pipeline(
            petition=petition,
            outcome=DispositionOutcome.REFER,
            deliberation_event_id=event_id,
        )

        # Assert
        assert result.pipeline == PipelineType.KNIGHT_REFERRAL

    @pytest.mark.asyncio
    async def test_route_to_king_escalation_pipeline(self) -> None:
        """Test routing to KING_ESCALATION pipeline."""
        # Arrange
        petition = _create_petition(uuid4())
        event_id = uuid4()

        # Act
        result = await self.service.route_to_pipeline(
            petition=petition,
            outcome=DispositionOutcome.ESCALATE,
            deliberation_event_id=event_id,
        )

        # Assert
        assert result.pipeline == PipelineType.KING_ESCALATION

    @pytest.mark.asyncio
    async def test_route_adds_to_pending_queue(self) -> None:
        """Test that routing adds petition to pending queue."""
        # Arrange
        petition = _create_petition(uuid4())
        event_id = uuid4()

        # Act
        await self.service.route_to_pipeline(
            petition=petition,
            outcome=DispositionOutcome.ACKNOWLEDGE,
            deliberation_event_id=event_id,
        )

        # Assert
        pending = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT
        )
        assert len(pending) == 1
        assert pending[0].petition_id == petition.id


class TestPendingDispositions:
    """Tests for pending disposition queue management."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = DispositionEmissionService()

    @pytest.mark.asyncio
    async def test_get_pending_dispositions_empty(self) -> None:
        """Test empty queue returns empty list."""
        # Act
        pending = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT
        )

        # Assert
        assert pending == []

    @pytest.mark.asyncio
    async def test_get_pending_dispositions_with_limit(self) -> None:
        """Test limit parameter restricts returned items."""
        # Arrange - add 3 petitions
        for _ in range(3):
            petition = _create_petition(uuid4())
            await self.service.route_to_pipeline(
                petition=petition,
                outcome=DispositionOutcome.ACKNOWLEDGE,
                deliberation_event_id=uuid4(),
            )

        # Act
        pending = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT, limit=2
        )

        # Assert
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_acknowledge_routing_removes_from_queue(self) -> None:
        """Test acknowledging routing removes petition from queue."""
        # Arrange
        petition = _create_petition(uuid4())
        await self.service.route_to_pipeline(
            petition=petition,
            outcome=DispositionOutcome.ACKNOWLEDGE,
            deliberation_event_id=uuid4(),
        )

        # Act
        result = await self.service.acknowledge_routing(
            petition.id, PipelineType.ACKNOWLEDGMENT
        )

        # Assert
        assert result is True
        pending = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT
        )
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_acknowledge_routing_not_found(self) -> None:
        """Test acknowledging non-existent petition returns False."""
        # Act
        result = await self.service.acknowledge_routing(
            uuid4(), PipelineType.ACKNOWLEDGMENT
        )

        # Assert
        assert result is False


class TestOutcomeToPipelineMapping:
    """Tests for outcome to pipeline mapping."""

    def test_all_outcomes_have_pipeline_mapping(self) -> None:
        """Test all DispositionOutcome values have pipeline mappings."""
        for outcome in DispositionOutcome:
            assert outcome in OUTCOME_TO_PIPELINE

    def test_acknowledge_maps_to_acknowledgment(self) -> None:
        """Test ACKNOWLEDGE -> ACKNOWLEDGMENT."""
        assert OUTCOME_TO_PIPELINE[DispositionOutcome.ACKNOWLEDGE] == PipelineType.ACKNOWLEDGMENT

    def test_refer_maps_to_knight_referral(self) -> None:
        """Test REFER -> KNIGHT_REFERRAL."""
        assert OUTCOME_TO_PIPELINE[DispositionOutcome.REFER] == PipelineType.KNIGHT_REFERRAL

    def test_escalate_maps_to_king_escalation(self) -> None:
        """Test ESCALATE -> KING_ESCALATION."""
        assert OUTCOME_TO_PIPELINE[DispositionOutcome.ESCALATE] == PipelineType.KING_ESCALATION


class TestRequiredWitnessPhases:
    """Tests for required witness phases constant."""

    def test_four_phases_required(self) -> None:
        """Test exactly 4 phases are required."""
        assert len(REQUIRED_WITNESS_PHASES) == 4

    def test_complete_phase_not_required(self) -> None:
        """Test COMPLETE phase is not in required phases."""
        assert DeliberationPhase.COMPLETE not in REQUIRED_WITNESS_PHASES

    def test_all_deliberation_phases_except_complete(self) -> None:
        """Test all non-terminal phases are required."""
        expected = {
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        }
        assert set(REQUIRED_WITNESS_PHASES) == expected
