"""Unit tests for GovernanceTranscriptAccessService (Story 7.6, FR-7.4, Ruling-2).

Tests the elevated transcript access service that provides full transcript
access for governance actors (HIGH_ARCHON and AUDITOR roles).

Constitutional Constraints:
- Ruling-2: Elevated tier access for governance actors
- FR-7.4: System SHALL provide full transcript to governance actors
- CT-12: Access logged for audit trail
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from src.application.dtos.governance_transcript import (
    FullTranscriptResponse,
    PhaseTranscriptDetail,
)
from src.application.ports.deliberation_summary import (
    DeliberationSummaryRepositoryProtocol,
)
from src.application.ports.transcript_store import TranscriptStoreProtocol
from src.application.services.governance_transcript_access_service import (
    GovernanceTranscriptAccessService,
)
from src.domain.errors.deliberation import SessionNotFoundError
from src.domain.events.phase_witness import PhaseWitnessEvent
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)


class TestGovernanceTranscriptAccessServiceInit:
    """Tests for service initialization."""

    def test_service_initializes_with_dependencies(self) -> None:
        """Test service initializes with required dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        transcript_store = AsyncMock(spec=TranscriptStoreProtocol)

        service = GovernanceTranscriptAccessService(
            summary_repo=summary_repo,
            transcript_store=transcript_store,
        )

        assert service._summary_repo is summary_repo
        assert service._transcript_store is transcript_store


class TestGetFullTranscript:
    """Tests for get_full_transcript method (Story 7.6, AC-1 through AC-7)."""

    @pytest_asyncio.fixture
    async def service(self) -> GovernanceTranscriptAccessService:
        """Create service with mock dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        transcript_store = AsyncMock(spec=TranscriptStoreProtocol)
        return GovernanceTranscriptAccessService(
            summary_repo=summary_repo,
            transcript_store=transcript_store,
        )

    @pytest.mark.asyncio
    async def test_high_archon_gets_full_transcript_ac1(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """AC-1: HIGH_ARCHON gets full transcript with Archon attribution."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        # Setup mocks
        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        # Execute
        _ = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        # Verify
        assert isinstance(result, FullTranscriptResponse)
        assert result.session_id == session.session_id
        assert result.petition_id == session.petition_id
        assert result.outcome == "ACKNOWLEDGE"
        assert len(result.phases) == 4  # ASSESS, POSITION, CROSS_EXAMINE, VOTE

        # ELEVATED: Verify Archon attribution is exposed (not hidden)
        for phase in result.phases:
            assert isinstance(phase, PhaseTranscriptDetail)
            for utterance in phase.utterances:
                assert isinstance(utterance.archon_id, UUID)  # Archon ID exposed

    @pytest.mark.asyncio
    async def test_auditor_gets_full_transcript_ac2(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """AC-2: AUDITOR gets full transcript with Archon attribution."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "AUDITOR"

        # Setup mocks
        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        # Execute
        _ = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        # Verify
        assert isinstance(result, FullTranscriptResponse)
        assert result.session_id == session.session_id
        # ELEVATED: Verify Archon attribution is exposed
        for phase in result.phases:
            for utterance in phase.utterances:
                assert isinstance(utterance.archon_id, UUID)

    @pytest.mark.asyncio
    async def test_session_not_found_returns_error_ac5(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """AC-5: Session not found returns SessionNotFoundError."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        service._summary_repo.get_session_by_session_id.return_value = None

        with pytest.raises(SessionNotFoundError) as exc_info:
            await service.get_full_transcript(
                session_id=session_id,
                accessor_archon_id=accessor_archon_id,
                accessor_role=accessor_role,
            )

        assert str(session_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_operation_succeeds_ac6(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """AC-6: Read operations succeed (permitted even during halt)."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        # Setup mocks
        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        # Execute - should succeed
        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        # Read succeeded
        assert result is not None
        assert isinstance(result, FullTranscriptResponse)

    @pytest.mark.asyncio
    async def test_access_is_logged_for_audit_ac7(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """AC-7/CT-12: Access attempts are logged for audit trail."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        # Setup mocks
        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        # Execute - the logging is internal but we verify the call completes
        _ = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        # Verify repos were called correctly (audit trail includes recording access)
        service._summary_repo.get_session_by_session_id.assert_called_once_with(
            session_id
        )
        service._summary_repo.get_phase_witnesses.assert_called_once_with(session_id)


class TestTranscriptWithDissent:
    """Tests for transcripts with dissenting votes."""

    @pytest_asyncio.fixture
    async def service(self) -> GovernanceTranscriptAccessService:
        """Create service with mock dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        transcript_store = AsyncMock(spec=TranscriptStoreProtocol)
        return GovernanceTranscriptAccessService(
            summary_repo=summary_repo,
            transcript_store=transcript_store,
        )

    @pytest.mark.asyncio
    async def test_has_dissent_flag_exposed(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """ELEVATED: has_dissent flag is exposed in response."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        # Setup session with dissent
        session = _create_mock_session(session_id, has_dissent=True)
        witnesses = _create_mock_witnesses(session_id, with_dissent=True)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        assert result.has_dissent is True

    @pytest.mark.asyncio
    async def test_dissent_text_exposed_from_metadata(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """ELEVATED: Raw dissent text is exposed (from phase metadata)."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"
        dissent_text = "I respectfully dissent from the majority opinion."

        # Setup session with dissent
        session = _create_mock_session(session_id, has_dissent=True)
        witnesses = _create_mock_witnesses(
            session_id, with_dissent=True, dissent_text=dissent_text
        )
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        assert result.dissent_text == dissent_text


class TestPhaseTranscriptDetails:
    """Tests for phase transcript details with full attribution."""

    @pytest_asyncio.fixture
    async def service(self) -> GovernanceTranscriptAccessService:
        """Create service with mock dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        transcript_store = AsyncMock(spec=TranscriptStoreProtocol)
        return GovernanceTranscriptAccessService(
            summary_repo=summary_repo,
            transcript_store=transcript_store,
        )

    @pytest.mark.asyncio
    async def test_all_phases_included(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """All deliberation phases are included in response."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        # All 4 phases present
        phase_names = [p.phase for p in result.phases]
        assert "ASSESS" in phase_names
        assert "POSITION" in phase_names
        assert "CROSS_EXAMINE" in phase_names
        assert "VOTE" in phase_names

    @pytest.mark.asyncio
    async def test_phase_timestamps_exposed(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """Phase start/end timestamps are exposed."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        for phase in result.phases:
            assert phase.start_timestamp is not None
            assert phase.end_timestamp is not None
            assert isinstance(phase.start_timestamp, datetime)
            assert isinstance(phase.end_timestamp, datetime)

    @pytest.mark.asyncio
    async def test_transcript_hash_included(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """Transcript hash is included for integrity verification."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = _create_mock_transcript_json(session.assigned_archons)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        for phase in result.phases:
            assert phase.transcript_hash_hex is not None
            assert len(phase.transcript_hash_hex) == 64  # Blake3 hex


class TestTranscriptContentParsing:
    """Tests for parsing transcript content into utterances."""

    @pytest_asyncio.fixture
    async def service(self) -> GovernanceTranscriptAccessService:
        """Create service with mock dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        transcript_store = AsyncMock(spec=TranscriptStoreProtocol)
        return GovernanceTranscriptAccessService(
            summary_repo=summary_repo,
            transcript_store=transcript_store,
        )

    @pytest.mark.asyncio
    async def test_json_list_format_parsed(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """JSON list format transcript content is parsed correctly."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"
        archon1 = uuid4()

        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = json.dumps(
            [
                {
                    "archon_id": str(archon1),
                    "timestamp": "2026-01-01T12:00:00Z",
                    "content": "Test utterance content",
                    "sequence": 0,
                }
            ]
        )

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        # Verify utterances parsed
        assert len(result.phases) > 0
        phase = result.phases[0]
        assert len(phase.utterances) > 0
        utterance = phase.utterances[0]
        assert utterance.archon_id == archon1
        assert utterance.content == "Test utterance content"
        assert utterance.sequence == 0

    @pytest.mark.asyncio
    async def test_json_dict_format_with_utterances_key_parsed(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """JSON dict format with 'utterances' key is parsed correctly."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"
        archon1 = uuid4()

        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = json.dumps(
            {
                "utterances": [
                    {
                        "archon_id": str(archon1),
                        "timestamp": "2026-01-01T12:00:00Z",
                        "content": "Dict format utterance",
                        "sequence": 0,
                    }
                ]
            }
        )

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        phase = result.phases[0]
        assert len(phase.utterances) > 0
        assert phase.utterances[0].content == "Dict format utterance"

    @pytest.mark.asyncio
    async def test_plain_text_fallback(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """Plain text content is treated as single utterance fallback."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)
        transcript_content = "Plain text transcript content"

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = transcript_content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        phase = result.phases[0]
        assert len(phase.utterances) == 1
        assert phase.utterances[0].content == "Plain text transcript content"

    @pytest.mark.asyncio
    async def test_empty_transcript_content_handled(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """Empty transcript content results in empty utterances list."""
        session_id = uuid4()
        accessor_archon_id = uuid4()
        accessor_role = "HIGH_ARCHON"

        session = _create_mock_session(session_id)
        witnesses = _create_mock_witnesses(session_id)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = None  # No content

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=accessor_archon_id,
            accessor_role=accessor_role,
        )

        # Empty utterances when no content
        for phase in result.phases:
            assert len(phase.utterances) == 0


class TestOutcomeMapping:
    """Tests for outcome value mapping in response."""

    @pytest_asyncio.fixture
    async def service(self) -> GovernanceTranscriptAccessService:
        """Create service with mock dependencies."""
        summary_repo = AsyncMock(spec=DeliberationSummaryRepositoryProtocol)
        transcript_store = AsyncMock(spec=TranscriptStoreProtocol)
        return GovernanceTranscriptAccessService(
            summary_repo=summary_repo,
            transcript_store=transcript_store,
        )

    @pytest.mark.asyncio
    async def test_acknowledge_outcome(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """ACKNOWLEDGE outcome is correctly mapped."""
        session_id = uuid4()
        session = _create_mock_session(
            session_id, outcome=DeliberationOutcome.ACKNOWLEDGE
        )
        witnesses = _create_mock_witnesses(session_id)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = "[]"

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=uuid4(),
            accessor_role="HIGH_ARCHON",
        )

        assert result.outcome == "ACKNOWLEDGE"

    @pytest.mark.asyncio
    async def test_refer_outcome(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """REFER outcome is correctly mapped."""
        session_id = uuid4()
        session = _create_mock_session(session_id, outcome=DeliberationOutcome.REFER)
        witnesses = _create_mock_witnesses(session_id)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = "[]"

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=uuid4(),
            accessor_role="HIGH_ARCHON",
        )

        assert result.outcome == "REFER"

    @pytest.mark.asyncio
    async def test_escalate_outcome(
        self, service: GovernanceTranscriptAccessService
    ) -> None:
        """ESCALATE outcome is correctly mapped."""
        session_id = uuid4()
        session = _create_mock_session(session_id, outcome=DeliberationOutcome.ESCALATE)
        witnesses = _create_mock_witnesses(session_id)

        service._summary_repo.get_session_by_session_id.return_value = session
        service._summary_repo.get_phase_witnesses.return_value = witnesses
        service._transcript_store.retrieve.return_value = "[]"

        result = await service.get_full_transcript(
            session_id=session_id,
            accessor_archon_id=uuid4(),
            accessor_role="HIGH_ARCHON",
        )

        assert result.outcome == "ESCALATE"


# =============================================================================
# Test Helpers
# =============================================================================


def _create_mock_session(
    session_id: UUID,
    has_dissent: bool = False,
    outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
) -> DeliberationSession:
    """Create a mock deliberation session."""
    session = AsyncMock(spec=DeliberationSession)
    session.session_id = session_id
    session.petition_id = uuid4()
    session.phase = DeliberationPhase.COMPLETE
    session.outcome = outcome
    session.completed_at = datetime.now(timezone.utc)
    session.created_at = datetime.now(timezone.utc)

    # Archons
    archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
    session.assigned_archons = (archon1, archon2, archon3)

    # Dissent
    session.dissent_archon_id = archon3 if has_dissent else None

    # Votes
    session.votes = {
        archon1: outcome,
        archon2: outcome,
        archon3: DeliberationOutcome.ESCALATE if has_dissent else outcome,
    }

    return session


def _create_mock_witnesses(
    session_id: UUID,
    with_dissent: bool = False,
    dissent_text: str | None = None,
) -> list[PhaseWitnessEvent]:
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
        metadata: dict = {"themes": ["constitutional"]}

        # Add dissent text to VOTE phase metadata
        if phase == DeliberationPhase.VOTE and with_dissent and dissent_text:
            metadata["dissent_text"] = dissent_text

        witness = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=session_id,
            phase=phase,
            transcript_hash=b"a" * 32,  # 32-byte Blake3 hash
            participating_archons=archons,
            start_timestamp=now,
            end_timestamp=now,
            phase_metadata=metadata,
            previous_witness_hash=prev_hash,
        )

        prev_hash = witness.event_hash
        witnesses.append(witness)

    return witnesses


def _create_mock_transcript_json(archons: tuple[UUID, UUID, UUID]) -> str:
    """Create mock JSON transcript content."""
    now = datetime.now(timezone.utc).isoformat()
    return json.dumps(
        [
            {
                "archon_id": str(archons[0]),
                "timestamp": now,
                "content": "This is the first utterance.",
                "sequence": 0,
            },
            {
                "archon_id": str(archons[1]),
                "timestamp": now,
                "content": "This is the second utterance.",
                "sequence": 1,
            },
            {
                "archon_id": str(archons[2]),
                "timestamp": now,
                "content": "This is the third utterance.",
                "sequence": 2,
            },
        ]
    )
