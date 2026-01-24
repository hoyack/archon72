"""Unit tests for TranscriptAccessMediationService (Story 7.4, FR-7.4).

Tests the service that provides mediated access to deliberation summaries
per Ruling-2 (Tiered Transcript Access).

Constitutional Constraints:
- Ruling-2: Tiered transcript access - mediated view
- FR-7.4: System SHALL provide deliberation summary
- CT-12: Hash references prove witnessing
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from src.application.ports.deliberation_summary import (
    DeliberationSummaryRepositoryProtocol,
)
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.services.transcript_access_mediation_service import (
    TranscriptAccessMediationService,
)
from src.domain.errors.deliberation import DeliberationPendingError
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.events.phase_witness import PhaseWitnessEvent
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.deliberation_summary import EscalationTrigger
from src.domain.models.petition_submission import PetitionState, PetitionSubmission


class TestTranscriptAccessMediationServiceInit:
    """Tests for service initialization."""

    def test_service_initializes_with_dependencies(self) -> None:
        """Test service initializes with required dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        petition_repo = AsyncMock(spec=PetitionSubmissionRepositoryProtocol)

        service = TranscriptAccessMediationService(
            summary_repo=summary_repo,
            petition_repo=petition_repo,
        )

        assert service._summary_repo is summary_repo
        assert service._petition_repo is petition_repo


class TestGetDeliberationSummary:
    """Tests for get_deliberation_summary method."""

    @pytest_asyncio.fixture
    async def service(self) -> TranscriptAccessMediationService:
        """Create service with mock dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        petition_repo = AsyncMock(spec=PetitionSubmissionRepositoryProtocol)
        return TranscriptAccessMediationService(
            summary_repo=summary_repo,
            petition_repo=petition_repo,
        )

    @pytest_asyncio.fixture
    def mock_petition_received(self) -> PetitionSubmission:
        """Create mock petition in RECEIVED state."""
        return _create_mock_petition(PetitionState.RECEIVED)

    @pytest_asyncio.fixture
    def mock_petition_acknowledged(self) -> PetitionSubmission:
        """Create mock petition in ACKNOWLEDGED state."""
        return _create_mock_petition(PetitionState.ACKNOWLEDGED)

    @pytest_asyncio.fixture
    def mock_petition_escalated(self) -> PetitionSubmission:
        """Create mock petition in ESCALATED state."""
        return _create_mock_petition(PetitionState.ESCALATED)

    @pytest.mark.asyncio
    async def test_returns_summary_for_completed_deliberation_ac1(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """AC-1: Returns DeliberationSummary with mediated fields."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ACKNOWLEDGED, petition_id)
        session = _create_mock_session(petition_id, DeliberationPhase.COMPLETE)
        witnesses = _create_mock_witnesses(session.session_id)

        service._petition_repo.get.return_value = petition
        service._summary_repo.get_session_by_petition_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses

        summary = await service.get_deliberation_summary(petition_id)

        assert summary.petition_id == petition_id
        assert summary.outcome == session.outcome
        # Verify mediation: vote breakdown is string, not individual votes
        assert isinstance(summary.vote_breakdown, str)
        # Verify mediation: has_dissent is boolean only
        assert isinstance(summary.has_dissent, bool)

    @pytest.mark.asyncio
    async def test_handles_auto_escalation_ac2(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """AC-2: Handles auto-escalation (no deliberation session)."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ESCALATED, petition_id)

        service._petition_repo.get.return_value = petition
        # No session - auto-escalated
        service._summary_repo.get_session_by_petition_id.return_value = None

        summary = await service.get_deliberation_summary(petition_id)

        assert summary.outcome == DeliberationOutcome.ESCALATE
        assert summary.escalation_trigger == EscalationTrigger.AUTO_ESCALATED
        assert summary.vote_breakdown == "0-0"  # No votes occurred
        assert len(summary.phase_summaries) == 0  # No phases

    @pytest.mark.asyncio
    async def test_raises_pending_for_received_state_ac3(
        self,
        service: TranscriptAccessMediationService,
        mock_petition_received: PetitionSubmission,
    ) -> None:
        """AC-3: Returns 400 if deliberation not complete (RECEIVED state)."""
        service._petition_repo.get.return_value = mock_petition_received

        with pytest.raises(DeliberationPendingError) as exc_info:
            await service.get_deliberation_summary(mock_petition_received.id)

        assert str(mock_petition_received.id) in str(exc_info.value)
        assert "RECEIVED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_pending_for_incomplete_session_ac3(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """AC-3: Returns pending if session not in COMPLETE phase."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ACKNOWLEDGED, petition_id)
        # Session still in VOTE phase (not COMPLETE)
        session = _create_mock_session(petition_id, DeliberationPhase.VOTE)

        service._petition_repo.get.return_value = petition
        service._summary_repo.get_session_by_petition_id.return_value = session

        with pytest.raises(DeliberationPendingError) as exc_info:
            await service.get_deliberation_summary(petition_id)

        assert "VOTE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_petition_ac4(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """AC-4: Returns 404 if petition not found."""
        petition_id = uuid4()
        service._petition_repo.get.return_value = None

        with pytest.raises(PetitionNotFoundError):
            await service.get_deliberation_summary(petition_id)

    @pytest.mark.asyncio
    async def test_handles_timeout_triggered_escalation_ac6(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """AC-6: Handles timeout-triggered escalation."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ESCALATED, petition_id)
        session = _create_mock_session(
            petition_id, DeliberationPhase.COMPLETE, timed_out=True
        )
        witnesses = _create_mock_witnesses(session.session_id)

        service._petition_repo.get.return_value = petition
        service._summary_repo.get_session_by_petition_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses

        summary = await service.get_deliberation_summary(petition_id)

        assert summary.timed_out is True
        assert summary.escalation_trigger == EscalationTrigger.TIMEOUT

    @pytest.mark.asyncio
    async def test_handles_deadlock_triggered_escalation_ac7(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """AC-7: Handles deadlock-triggered escalation."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ESCALATED, petition_id)
        session = _create_mock_session(
            petition_id, DeliberationPhase.COMPLETE, is_deadlocked=True, round_count=3
        )
        witnesses = _create_mock_witnesses(session.session_id)

        service._petition_repo.get.return_value = petition
        service._summary_repo.get_session_by_petition_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses

        summary = await service.get_deliberation_summary(petition_id)

        assert summary.escalation_trigger == EscalationTrigger.DEADLOCK
        assert summary.rounds_attempted == 3


class TestMediationRules:
    """Tests verifying mediation hides sensitive data per Ruling-2."""

    @pytest_asyncio.fixture
    async def service(self) -> TranscriptAccessMediationService:
        """Create service with mock dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        petition_repo = AsyncMock(spec=PetitionSubmissionRepositoryProtocol)
        return TranscriptAccessMediationService(
            summary_repo=summary_repo,
            petition_repo=petition_repo,
        )

    @pytest.mark.asyncio
    async def test_vote_breakdown_is_anonymous_string(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """Ruling-2: Vote breakdown hides who voted what."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ACKNOWLEDGED, petition_id)
        session = _create_mock_session(petition_id, DeliberationPhase.COMPLETE)
        witnesses = _create_mock_witnesses(session.session_id)

        service._petition_repo.get.return_value = petition
        service._summary_repo.get_session_by_petition_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses

        summary = await service.get_deliberation_summary(petition_id)

        # Vote breakdown should be string like "2-1" or "3-0"
        assert isinstance(summary.vote_breakdown, str)
        assert "-" in summary.vote_breakdown
        # Verify individual votes are NOT exposed
        summary_dict = summary.to_dict()
        assert "votes" not in summary_dict
        assert "archon" not in str(summary_dict).lower()

    @pytest.mark.asyncio
    async def test_dissent_is_boolean_only(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """Ruling-2: Dissent presence is boolean, not identity."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ACKNOWLEDGED, petition_id)
        session = _create_mock_session(petition_id, DeliberationPhase.COMPLETE)
        session.dissent_archon_id = uuid4()  # Has dissenter
        witnesses = _create_mock_witnesses(session.session_id)

        service._petition_repo.get.return_value = petition
        service._summary_repo.get_session_by_petition_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses

        summary = await service.get_deliberation_summary(petition_id)

        # has_dissent should be True but identity hidden
        assert summary.has_dissent is True
        summary_dict = summary.to_dict()
        assert "dissent_archon" not in str(summary_dict).lower()

    @pytest.mark.asyncio
    async def test_phase_summaries_have_metadata_only(
        self, service: TranscriptAccessMediationService
    ) -> None:
        """Ruling-2: Phase summaries have metadata, not content."""
        petition_id = uuid4()
        petition = _create_mock_petition(PetitionState.ACKNOWLEDGED, petition_id)
        session = _create_mock_session(petition_id, DeliberationPhase.COMPLETE)
        witnesses = _create_mock_witnesses(session.session_id)

        service._petition_repo.get.return_value = petition
        service._summary_repo.get_session_by_petition_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses

        summary = await service.get_deliberation_summary(petition_id)

        # Phase summaries should have metadata fields
        for ps in summary.phase_summaries:
            assert ps.phase is not None
            assert ps.duration_seconds >= 0
            assert ps.transcript_hash_hex  # Hash present
            # Verify NO transcript content
            ps_dict = ps.to_dict()
            assert "transcript_content" not in ps_dict
            assert "utterances" not in ps_dict


# =============================================================================
# Test Helpers
# =============================================================================


def _create_mock_petition(
    state: PetitionState, petition_id: UUID | None = None
) -> PetitionSubmission:
    """Create a mock petition in the given state."""
    if petition_id is None:
        petition_id = uuid4()

    # Create a minimal mock that has required attributes
    mock = AsyncMock(spec=PetitionSubmission)
    mock.id = petition_id
    mock.state = state
    mock.updated_at = datetime.now(timezone.utc)
    return mock


def _create_mock_session(
    petition_id: UUID,
    phase: DeliberationPhase,
    timed_out: bool = False,
    is_deadlocked: bool = False,
    round_count: int = 1,
) -> DeliberationSession:
    """Create a mock deliberation session."""
    session = AsyncMock(spec=DeliberationSession)
    session.session_id = uuid4()
    session.petition_id = petition_id
    session.phase = phase
    session.timed_out = timed_out
    session.is_deadlocked = is_deadlocked
    session.round_count = round_count
    session.dissent_archon_id = None

    # Set outcome based on state
    if phase == DeliberationPhase.COMPLETE:
        if is_deadlocked or timed_out:
            session.outcome = DeliberationOutcome.ESCALATE
        else:
            session.outcome = DeliberationOutcome.ACKNOWLEDGE
    else:
        session.outcome = None

    session.completed_at = datetime.now(timezone.utc) if phase == DeliberationPhase.COMPLETE else None
    session.created_at = datetime.now(timezone.utc)

    # Mock votes (will be converted to anonymous breakdown)
    archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
    session.assigned_archons = (archon1, archon2, archon3)
    session.votes = {
        archon1: DeliberationOutcome.ACKNOWLEDGE,
        archon2: DeliberationOutcome.ACKNOWLEDGE,
        archon3: DeliberationOutcome.ACKNOWLEDGE,
    }

    return session


def _create_mock_witnesses(session_id: UUID) -> list[PhaseWitnessEvent]:
    """Create mock phase witness events."""
    witnesses: list[PhaseWitnessEvent] = []
    phases = [
        DeliberationPhase.ASSESS,
        DeliberationPhase.POSITION,
        DeliberationPhase.CROSS_EXAMINE,
        DeliberationPhase.VOTE,
    ]

    prev_hash: bytes | None = None
    archons = (uuid4(), uuid4(), uuid4())
    now = datetime.now(timezone.utc)

    for i, phase in enumerate(phases):
        start = now
        end = now

        witness = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=session_id,
            phase=phase,
            transcript_hash=b"a" * 32,  # 32-byte Blake3 hash
            participating_archons=archons,
            start_timestamp=start,
            end_timestamp=end,
            phase_metadata={"themes": ["constitutional"]},
            previous_witness_hash=prev_hash,
        )

        prev_hash = witness.event_hash
        witnesses.append(witness)

    return witnesses
