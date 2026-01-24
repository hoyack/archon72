"""Integration tests for deliberation summary endpoint (Story 7.4, FR-7.4).

Tests the full flow from API endpoint through service to repository stubs.

Constitutional Constraints:
- FR-7.4: System SHALL provide deliberation summary to Observer
- Ruling-2: Tiered transcript access
- CT-13: Reads allowed during halt (AC-5)
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.petition_submission import (
    get_deliberation_summary_repository,
    get_petition_submission_repository,
    reset_petition_submission_dependencies,
    set_deliberation_summary_repository,
    set_petition_submission_repository,
)
from src.api.routes.petition_submission import router
from src.domain.events.phase_witness import PhaseWitnessEvent
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
from src.infrastructure.stubs.deliberation_summary_repository_stub import (
    DeliberationSummaryRepositoryStub,
)
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI application."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_dependencies() -> None:
    """Reset dependencies before each test."""
    reset_petition_submission_dependencies()


@pytest.fixture
def petition_repo() -> PetitionSubmissionRepositoryStub:
    """Create and set petition repository stub."""
    repo = PetitionSubmissionRepositoryStub()
    set_petition_submission_repository(repo)
    return repo


@pytest.fixture
def summary_repo() -> DeliberationSummaryRepositoryStub:
    """Create and set deliberation summary repository stub."""
    repo = DeliberationSummaryRepositoryStub()
    set_deliberation_summary_repository(repo)
    return repo


def _create_test_petition(
    petition_id: uuid4,
    state: PetitionState,
) -> PetitionSubmission:
    """Create a test petition with all required fields."""
    return PetitionSubmission(
        id=petition_id,
        type=PetitionType.GENERAL,
        text="Test petition content for deliberation summary integration test",
        state=state,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestDeliberationSummaryIntegration:
    """Integration tests for deliberation summary endpoint."""

    def test_full_flow_completed_deliberation_ac1(
        self,
        client: TestClient,
        petition_repo: PetitionSubmissionRepositoryStub,
        summary_repo: DeliberationSummaryRepositoryStub,
    ) -> None:
        """AC-1: Full flow for completed deliberation returns summary."""
        # Setup: Create petition in ACKNOWLEDGED state
        petition_id = uuid4()
        petition = _create_test_petition(petition_id, PetitionState.ACKNOWLEDGED)
        petition_repo._submissions[petition_id] = petition

        # Setup: Create completed deliberation session
        session = _create_completed_session(petition_id)
        summary_repo.add_session(session)

        # Setup: Create phase witnesses
        witnesses = _create_phase_witnesses(session.session_id)
        summary_repo.add_witnesses(session.session_id, witnesses)

        # Act: Call endpoint
        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert data["petition_id"] == str(petition_id)
        assert data["outcome"] == "ACKNOWLEDGE"
        assert "vote_breakdown" in data
        assert "has_dissent" in data
        assert len(data["phase_summaries"]) == 4

    def test_auto_escalation_returns_summary_ac2(
        self,
        client: TestClient,
        petition_repo: PetitionSubmissionRepositoryStub,
        summary_repo: DeliberationSummaryRepositoryStub,
    ) -> None:
        """AC-2: Auto-escalated petition returns summary without session."""
        # Setup: Create petition in ESCALATED state (no session = auto-escalated)
        petition_id = uuid4()
        petition = _create_test_petition(petition_id, PetitionState.ESCALATED)
        petition_repo._submissions[petition_id] = petition
        # NO session added = auto-escalation

        # Act
        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert data["outcome"] == "ESCALATE"
        assert data["escalation_trigger"] == "AUTO_ESCALATED"
        assert data["vote_breakdown"] == "0-0"

    def test_pending_deliberation_returns_400_ac3(
        self,
        client: TestClient,
        petition_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """AC-3: Petition still in RECEIVED state returns 400."""
        # Setup: Create petition in RECEIVED state (no deliberation yet)
        petition_id = uuid4()
        petition = _create_test_petition(petition_id, PetitionState.RECEIVED)
        petition_repo._submissions[petition_id] = petition

        # Act
        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        # Assert
        assert response.status_code == 400
        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:petition:deliberation-pending"

    def test_missing_petition_returns_404_ac4(
        self,
        client: TestClient,
        petition_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """AC-4: Non-existent petition returns 404."""
        petition_id = uuid4()
        # NO petition added

        # Act
        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        # Assert
        assert response.status_code == 404
        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:petition:not-found"

    def test_incomplete_session_returns_400_ac3(
        self,
        client: TestClient,
        petition_repo: PetitionSubmissionRepositoryStub,
        summary_repo: DeliberationSummaryRepositoryStub,
    ) -> None:
        """AC-3: Session in progress (not COMPLETE) returns 400."""
        # Setup: Create petition in ACKNOWLEDGED state
        petition_id = uuid4()
        petition = _create_test_petition(petition_id, PetitionState.ACKNOWLEDGED)
        petition_repo._submissions[petition_id] = petition

        # Setup: Create session still in VOTE phase
        session = _create_incomplete_session(petition_id, DeliberationPhase.VOTE)
        summary_repo.add_session(session)

        # Act
        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        # Assert
        assert response.status_code == 400
        assert "VOTE" in response.json()["detail"]["detail"]


class TestMediationEnforcement:
    """Tests verifying mediation is enforced in integration."""

    def test_response_contains_no_archon_ids(
        self,
        client: TestClient,
        petition_repo: PetitionSubmissionRepositoryStub,
        summary_repo: DeliberationSummaryRepositoryStub,
    ) -> None:
        """Ruling-2: Full response must not expose Archon identities."""
        # Setup
        petition_id = uuid4()
        petition = _create_test_petition(petition_id, PetitionState.ACKNOWLEDGED)
        petition_repo._submissions[petition_id] = petition

        session = _create_completed_session(petition_id)
        summary_repo.add_session(session)

        witnesses = _create_phase_witnesses(session.session_id)
        summary_repo.add_witnesses(session.session_id, witnesses)

        # Act
        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        # Assert
        response_text = response.text.lower()
        # Check the archon UUIDs from witnesses are NOT in response
        for witness in witnesses:
            for archon_id in witness.participating_archons:
                assert str(archon_id).lower() not in response_text


# =============================================================================
# Test Helpers
# =============================================================================


def _create_completed_session(petition_id: uuid4) -> DeliberationSession:
    """Create a completed deliberation session for testing."""
    archons = (uuid4(), uuid4(), uuid4())

    return DeliberationSession(
        session_id=uuid4(),
        petition_id=petition_id,
        assigned_archons=archons,
        phase=DeliberationPhase.COMPLETE,
        outcome=DeliberationOutcome.ACKNOWLEDGE,
        votes={
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: DeliberationOutcome.ACKNOWLEDGE,
        },
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )


def _create_incomplete_session(
    petition_id: uuid4, phase: DeliberationPhase
) -> DeliberationSession:
    """Create an incomplete deliberation session for testing."""
    archons = (uuid4(), uuid4(), uuid4())

    return DeliberationSession(
        session_id=uuid4(),
        petition_id=petition_id,
        assigned_archons=archons,
        phase=phase,  # Not COMPLETE
        outcome=None,
        votes={},
        created_at=datetime.now(timezone.utc),
        completed_at=None,
    )


def _create_phase_witnesses(session_id: uuid4) -> list[PhaseWitnessEvent]:
    """Create phase witness events for testing."""
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

    for phase in phases:
        witness = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=session_id,
            phase=phase,
            transcript_hash=b"a" * 32,
            participating_archons=archons,
            start_timestamp=now,
            end_timestamp=now,
            phase_metadata={},
            previous_witness_hash=prev_hash,
        )
        prev_hash = witness.event_hash
        witnesses.append(witness)

    return witnesses
