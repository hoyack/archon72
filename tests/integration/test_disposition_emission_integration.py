"""Integration tests for DispositionEmissionService (Story 2A.8, FR-11.11).

Tests verify end-to-end disposition emission flows including:
- Full deliberation-to-disposition pipeline
- Multi-pipeline routing scenarios
- Queue management across pipelines
- Error recovery scenarios
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.disposition_emission_service import (
    DispositionEmissionService,
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
from src.infrastructure.stubs.disposition_emission_stub import (
    DispositionEmissionStub,
)


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def _create_test_archons() -> tuple:
    """Create 3 test archon UUIDs."""
    return (uuid4(), uuid4(), uuid4())


def _create_complete_session(
    archons: tuple,
    petition_id: uuid4,
    outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
    dissent_archon_id: uuid4 | None = None,
) -> DeliberationSession:
    """Create a completed deliberation session with all phases witnessed."""
    session_id = uuid4()

    # Default votes: all vote for outcome
    votes = {archon: outcome for archon in archons}

    # If dissent, change one vote
    if dissent_archon_id is not None:
        # Determine dissent vote
        dissent_vote = (
            DeliberationOutcome.REFER
            if outcome != DeliberationOutcome.REFER
            else DeliberationOutcome.ESCALATE
        )
        votes[dissent_archon_id] = dissent_vote

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


def _create_consensus(
    session: DeliberationSession,
    winning_outcome: str,
    status: ConsensusStatus = ConsensusStatus.UNANIMOUS,
    dissent_archon_id: uuid4 | None = None,
) -> ConsensusResult:
    """Create a ConsensusResult matching the session."""
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
    petition_type: PetitionType = PetitionType.GENERAL,
    state: PetitionState = PetitionState.DELIBERATING,
    realm: str = "test-realm",
) -> PetitionSubmission:
    """Create a test petition."""
    return PetitionSubmission(
        id=petition_id,
        type=petition_type,
        text="Test petition for integration testing",
        state=state,
        realm=realm,
    )


class TestFullDispositionFlow:
    """Integration tests for complete disposition emission flow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = DispositionEmissionService()
        self.archons = _create_test_archons()

    @pytest.mark.asyncio
    async def test_complete_acknowledge_flow(self) -> None:
        """Test complete flow for ACKNOWLEDGE disposition."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Act - emit disposition
        result = await self.service.emit_disposition(session, consensus, petition)

        # Verify - result contains both events
        assert result.success is True
        assert result.deliberation_event.petition_id == petition_id
        assert result.deliberation_event.outcome == DispositionOutcome.ACKNOWLEDGE
        assert result.routing_event.pipeline == PipelineType.ACKNOWLEDGMENT

        # Verify - petition added to pending queue
        pending = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT
        )
        assert len(pending) == 1
        assert pending[0].petition_id == petition_id

        # Act - acknowledge routing (simulates downstream pipeline pickup)
        ack_result = await self.service.acknowledge_routing(
            petition_id, PipelineType.ACKNOWLEDGMENT
        )

        # Verify - petition removed from queue
        assert ack_result is True
        pending_after = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT
        )
        assert len(pending_after) == 0

    @pytest.mark.asyncio
    async def test_complete_refer_flow(self) -> None:
        """Test complete flow for REFER disposition."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
            outcome=DeliberationOutcome.REFER,
        )
        consensus = _create_consensus(session, "REFER")

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Verify
        assert result.success is True
        assert result.routing_event.pipeline == PipelineType.KNIGHT_REFERRAL

        pending = await self.service.get_pending_dispositions(
            PipelineType.KNIGHT_REFERRAL
        )
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_complete_escalate_flow(self) -> None:
        """Test complete flow for ESCALATE disposition."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
            outcome=DeliberationOutcome.ESCALATE,
        )
        consensus = _create_consensus(session, "ESCALATE")

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Verify
        assert result.success is True
        assert result.routing_event.pipeline == PipelineType.KING_ESCALATION

        pending = await self.service.get_pending_dispositions(
            PipelineType.KING_ESCALATION
        )
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_dissent_tracking_in_flow(self) -> None:
        """Test that dissent is properly tracked through the flow."""
        # Arrange - 2-1 vote with dissent
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        dissenter = self.archons[2]
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            dissent_archon_id=dissenter,
        )
        consensus = _create_consensus(
            session,
            "ACKNOWLEDGE",
            status=ConsensusStatus.ACHIEVED,
            dissent_archon_id=dissenter,
        )

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Verify - dissent captured in event
        assert result.success is True
        assert result.deliberation_event.dissent_present is True
        assert result.deliberation_event.dissent_archon_id == dissenter
        # Vote breakdown should show 3 votes
        assert len(result.deliberation_event.vote_breakdown) == 3


class TestMultiplePipelineScenarios:
    """Integration tests for multiple pipeline routing scenarios."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = DispositionEmissionService()

    @pytest.mark.asyncio
    async def test_multiple_petitions_to_same_pipeline(self) -> None:
        """Test multiple petitions routing to same pipeline."""
        # Arrange - create 3 petitions going to ACKNOWLEDGMENT
        petitions = []
        for i in range(3):
            archons = _create_test_archons()
            petition_id = uuid4()
            petition = _create_petition(petition_id)
            session = _create_complete_session(
                archons=archons,
                petition_id=petition_id,
                outcome=DeliberationOutcome.ACKNOWLEDGE,
            )
            consensus = _create_consensus(session, "ACKNOWLEDGE")
            petitions.append((session, consensus, petition))

        # Act - emit all dispositions
        for session, consensus, petition in petitions:
            await self.service.emit_disposition(session, consensus, petition)

        # Verify - all in queue
        pending = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT
        )
        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_petitions_to_different_pipelines(self) -> None:
        """Test petitions routing to different pipelines simultaneously."""
        # Arrange - one petition per pipeline
        outcomes = [
            (
                DeliberationOutcome.ACKNOWLEDGE,
                "ACKNOWLEDGE",
                PipelineType.ACKNOWLEDGMENT,
            ),
            (DeliberationOutcome.REFER, "REFER", PipelineType.KNIGHT_REFERRAL),
            (DeliberationOutcome.ESCALATE, "ESCALATE", PipelineType.KING_ESCALATION),
        ]

        for outcome, outcome_str, expected_pipeline in outcomes:
            archons = _create_test_archons()
            petition_id = uuid4()
            petition = _create_petition(petition_id)
            session = _create_complete_session(
                archons=archons,
                petition_id=petition_id,
                outcome=outcome,
            )
            consensus = _create_consensus(session, outcome_str)

            # Act
            result = await self.service.emit_disposition(session, consensus, petition)

            # Verify
            assert result.routing_event.pipeline == expected_pipeline

        # Verify - each pipeline has one petition
        for _, _, pipeline in outcomes:
            pending = await self.service.get_pending_dispositions(pipeline)
            assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_queue_limit_enforcement(self) -> None:
        """Test that get_pending_dispositions respects limit."""
        # Arrange - add 5 petitions
        for _ in range(5):
            archons = _create_test_archons()
            petition_id = uuid4()
            petition = _create_petition(petition_id)
            session = _create_complete_session(
                archons=archons,
                petition_id=petition_id,
                outcome=DeliberationOutcome.ACKNOWLEDGE,
            )
            consensus = _create_consensus(session, "ACKNOWLEDGE")
            await self.service.emit_disposition(session, consensus, petition)

        # Act - request only 3
        pending = await self.service.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT, limit=3
        )

        # Verify
        assert len(pending) == 3


class TestDispositionEmissionStubIntegration:
    """Integration tests using DispositionEmissionStub."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.stub = DispositionEmissionStub()
        self.archons = _create_test_archons()

    @pytest.mark.asyncio
    async def test_stub_tracks_emit_calls(self) -> None:
        """Test stub tracks all emit_disposition calls."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Act
        await self.stub.emit_disposition(session, consensus, petition)

        # Verify
        assert len(self.stub.emit_calls) == 1
        call_session, call_consensus, call_petition = self.stub.emit_calls[0]
        assert call_session.session_id == session.session_id
        assert call_petition.id == petition.id

    @pytest.mark.asyncio
    async def test_stub_configurable_failure(self) -> None:
        """Test stub can be configured to fail."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Configure failure
        self.stub.should_fail_validation = True

        # Act & Verify
        from src.domain.errors.deliberation import IncompleteWitnessChainError

        with pytest.raises(IncompleteWitnessChainError):
            await self.stub.emit_disposition(session, consensus, petition)

    @pytest.mark.asyncio
    async def test_stub_reset_clears_state(self) -> None:
        """Test stub reset clears all state."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Emit and verify state
        await self.stub.emit_disposition(session, consensus, petition)
        assert len(self.stub.emit_calls) == 1

        # Act
        self.stub.reset()

        # Verify
        assert len(self.stub.emit_calls) == 0
        assert len(self.stub.route_calls) == 0

    @pytest.mark.asyncio
    async def test_stub_pending_disposition_management(self) -> None:
        """Test stub manages pending dispositions correctly."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Act - emit and check queue
        await self.stub.emit_disposition(session, consensus, petition)
        pending = await self.stub.get_pending_dispositions(PipelineType.ACKNOWLEDGMENT)

        # Verify
        assert len(pending) == 1

        # Acknowledge
        result = await self.stub.acknowledge_routing(
            petition_id, PipelineType.ACKNOWLEDGMENT
        )
        assert result is True

        # Verify removed
        pending_after = await self.stub.get_pending_dispositions(
            PipelineType.ACKNOWLEDGMENT
        )
        assert len(pending_after) == 0


class TestEventContent:
    """Integration tests for event content verification."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = DispositionEmissionService()
        self.archons = _create_test_archons()

    @pytest.mark.asyncio
    async def test_deliberation_event_has_required_fields(self) -> None:
        """Test DeliberationCompleteEvent contains all required fields."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id, realm="finance-realm")
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Verify event fields
        event = result.deliberation_event
        assert event.event_id is not None
        assert event.petition_id == petition_id
        assert event.session_id == session.session_id
        assert event.outcome == DispositionOutcome.ACKNOWLEDGE
        assert len(event.vote_breakdown) == 3
        assert len(event.final_witness_hash) == 32
        assert event.completed_at is not None

    @pytest.mark.asyncio
    async def test_routing_event_has_required_fields(self) -> None:
        """Test PipelineRoutingEvent contains all required fields."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id, realm="finance-realm")
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Verify event fields
        event = result.routing_event
        assert event.event_id is not None
        assert event.petition_id == petition_id
        assert event.pipeline == PipelineType.ACKNOWLEDGMENT
        assert event.deliberation_event_id == result.deliberation_event.event_id
        assert event.routed_at is not None
        assert "petition_type" in event.routing_metadata
        assert "realm" in event.routing_metadata
        assert event.routing_metadata["realm"] == "finance-realm"

    @pytest.mark.asyncio
    async def test_event_serialization(self) -> None:
        """Test events can be serialized via to_dict."""
        # Arrange
        petition_id = uuid4()
        petition = _create_petition(petition_id)
        session = _create_complete_session(
            archons=self.archons,
            petition_id=petition_id,
        )
        consensus = _create_consensus(session, "ACKNOWLEDGE")

        # Act
        result = await self.service.emit_disposition(session, consensus, petition)

        # Verify serialization
        delib_dict = result.deliberation_event.to_dict()
        assert "event_id" in delib_dict
        assert "outcome" in delib_dict
        assert "schema_version" in delib_dict
        assert delib_dict["schema_version"] == 1

        routing_dict = result.routing_event.to_dict()
        assert "event_id" in routing_dict
        assert "pipeline" in routing_dict
        assert "schema_version" in routing_dict
