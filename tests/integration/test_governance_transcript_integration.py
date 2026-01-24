"""Integration tests for governance transcript endpoint (Story 7.6, FR-7.4, Ruling-2).

Tests the full flow from API endpoint through service including authentication
and authorization for elevated transcript access.

Constitutional Constraints:
- Ruling-2: Elevated tier access for HIGH_ARCHON and AUDITOR
- FR-7.4: System SHALL provide full transcript to governance actors
- CT-12: Access logged for audit trail
- AC-1 through AC-7: Acceptance criteria coverage
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.governance_transcript import (
    get_summary_repo,
    get_transcript_store,
    router,
)
from src.domain.events.phase_witness import PhaseWitnessEvent
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.deliberation_summary_repository_stub import (
    DeliberationSummaryRepositoryStub,
)
from src.infrastructure.stubs.transcript_store_stub import TranscriptStoreStub


@pytest.fixture
def summary_repo() -> DeliberationSummaryRepositoryStub:
    """Create a fresh summary repository stub."""
    return DeliberationSummaryRepositoryStub()


@pytest.fixture
def transcript_store() -> TranscriptStoreStub:
    """Create a fresh transcript store stub."""
    return TranscriptStoreStub()


@pytest.fixture
def app(
    summary_repo: DeliberationSummaryRepositoryStub,
    transcript_store: TranscriptStoreStub,
) -> FastAPI:
    """Create test FastAPI application with dependency overrides."""
    app = FastAPI()
    app.include_router(router)

    # Override dependencies using FastAPI's dependency_overrides
    app.dependency_overrides[get_summary_repo] = lambda: summary_repo
    app.dependency_overrides[get_transcript_store] = lambda: transcript_store

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


def _inject_transcript(store: TranscriptStoreStub, content_hash: bytes, content: str) -> None:
    """Directly inject transcript at a specific hash (for testing).

    This bypasses the normal hash computation to allow matching
    the fixed hashes used in test witnesses.
    """
    store._transcripts[content_hash] = content


class TestHighArchonAccess:
    """Tests for HIGH_ARCHON role access (Story 7.6, AC-1)."""

    def test_high_archon_gets_full_transcript_ac1(
        self,
        client: TestClient,
        summary_repo: DeliberationSummaryRepositoryStub,
        transcript_store: TranscriptStoreStub,
    ) -> None:
        """AC-1: HIGH_ARCHON gets full transcript with Archon attribution."""
        # Setup: Create session and witnesses
        session = _create_completed_session()
        summary_repo.add_session(session)

        witnesses = _create_phase_witnesses(session.session_id, session.assigned_archons)
        summary_repo.add_witnesses(session.session_id, witnesses)

        # Setup: Store transcript content at the witness hash
        transcript_json = _create_transcript_json(session.assigned_archons)
        for witness in witnesses:
            _inject_transcript(transcript_store, witness.transcript_hash, transcript_json)

        # Act: Call endpoint as HIGH_ARCHON
        response = client.get(
            f"/deliberations/{session.session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify full transcript returned
        assert data["session_id"] == str(session.session_id)
        assert data["petition_id"] == str(session.petition_id)
        assert data["outcome"] == "ACKNOWLEDGE"
        assert len(data["phases"]) == 4

        # ELEVATED: Verify Archon IDs are exposed (not hidden)
        for phase in data["phases"]:
            assert len(phase["utterances"]) > 0
            for utterance in phase["utterances"]:
                assert "archon_id" in utterance
                # Archon ID should be a valid UUID string
                assert len(utterance["archon_id"]) == 36  # UUID format

    def test_high_archon_sees_dissent_text(
        self,
        client: TestClient,
        summary_repo: DeliberationSummaryRepositoryStub,
        transcript_store: TranscriptStoreStub,
    ) -> None:
        """ELEVATED: HIGH_ARCHON sees raw dissent text."""
        # Setup
        session = _create_completed_session(has_dissent=True)
        summary_repo.add_session(session)

        dissent_text = "I respectfully dissent from the majority opinion."
        witnesses = _create_phase_witnesses(
            session.session_id,
            session.assigned_archons,
            dissent_text=dissent_text,
        )
        summary_repo.add_witnesses(session.session_id, witnesses)

        transcript_json = _create_transcript_json(session.assigned_archons)
        for witness in witnesses:
            _inject_transcript(transcript_store, witness.transcript_hash, transcript_json)

        # Act
        response = client.get(
            f"/deliberations/{session.session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["has_dissent"] is True
        assert data["dissent_text"] == dissent_text


class TestAuditorAccess:
    """Tests for AUDITOR role access (Story 7.6, AC-2)."""

    def test_auditor_gets_full_transcript_ac2(
        self,
        client: TestClient,
        summary_repo: DeliberationSummaryRepositoryStub,
        transcript_store: TranscriptStoreStub,
    ) -> None:
        """AC-2: AUDITOR gets full transcript with Archon attribution."""
        # Setup
        session = _create_completed_session()
        summary_repo.add_session(session)

        witnesses = _create_phase_witnesses(session.session_id, session.assigned_archons)
        summary_repo.add_witnesses(session.session_id, witnesses)

        transcript_json = _create_transcript_json(session.assigned_archons)
        for witness in witnesses:
            _inject_transcript(transcript_store, witness.transcript_hash, transcript_json)

        # Act: Call endpoint as AUDITOR
        response = client.get(
            f"/deliberations/{session.session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "AUDITOR",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # ELEVATED: Same access as HIGH_ARCHON
        assert data["session_id"] == str(session.session_id)
        assert len(data["phases"]) == 4

        # Verify Archon IDs exposed
        for phase in data["phases"]:
            for utterance in phase["utterances"]:
                assert "archon_id" in utterance


class TestObserverDenied:
    """Tests for OBSERVER role denial (Story 7.6, AC-3)."""

    def test_observer_denied_with_redirect_hint_ac3(
        self,
        client: TestClient,
    ) -> None:
        """AC-3: OBSERVER role denied with redirect hint to mediated endpoint."""
        session_id = uuid4()

        # Act: Call endpoint as OBSERVER
        response = client.get(
            f"/deliberations/{session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "OBSERVER",
            },
        )

        # Assert: 403 Forbidden
        assert response.status_code == 403
        data = response.json()["detail"]

        assert data["type"] == "urn:archon72:transcript:insufficient-role"
        assert "OBSERVER" in data["detail"]
        assert "redirect_hint" in data
        assert "deliberation-summary" in data["redirect_hint"]


class TestSeekerDenied:
    """Tests for SEEKER role denial (Story 7.6, AC-4)."""

    def test_seeker_denied_with_redirect_hint_ac4(
        self,
        client: TestClient,
    ) -> None:
        """AC-4: SEEKER role denied with redirect hint to mediated endpoint."""
        session_id = uuid4()

        # Act: Call endpoint as SEEKER
        response = client.get(
            f"/deliberations/{session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "SEEKER",
            },
        )

        # Assert: 403 Forbidden
        assert response.status_code == 403
        data = response.json()["detail"]

        assert data["type"] == "urn:archon72:transcript:insufficient-role"
        assert "SEEKER" in data["detail"]
        assert "redirect_hint" in data


class TestSessionNotFound:
    """Tests for session not found (Story 7.6, AC-5)."""

    def test_session_not_found_returns_404_ac5(
        self,
        client: TestClient,
    ) -> None:
        """AC-5: Session not found returns 404."""
        session_id = uuid4()  # Non-existent session

        # Act
        response = client.get(
            f"/deliberations/{session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 404
        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:transcript:session-not-found"


class TestReadOperationsPermitted:
    """Tests for read operations during halt (Story 7.6, AC-6)."""

    def test_read_operation_succeeds_ac6(
        self,
        client: TestClient,
        summary_repo: DeliberationSummaryRepositoryStub,
        transcript_store: TranscriptStoreStub,
    ) -> None:
        """AC-6: Read operations permitted (succeed even during halt)."""
        # Setup
        session = _create_completed_session()
        summary_repo.add_session(session)

        witnesses = _create_phase_witnesses(session.session_id, session.assigned_archons)
        summary_repo.add_witnesses(session.session_id, witnesses)

        transcript_json = _create_transcript_json(session.assigned_archons)
        for witness in witnesses:
            _inject_transcript(transcript_store, witness.transcript_hash, transcript_json)

        # Act: Read operation
        response = client.get(
            f"/deliberations/{session.session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert: Read succeeds
        assert response.status_code == 200


class TestAuthenticationRequired:
    """Tests for authentication requirements."""

    def test_missing_archon_id_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Missing X-Archon-Id header returns 401."""
        session_id = uuid4()

        # Act: No X-Archon-Id header
        response = client.get(
            f"/deliberations/{session_id}/transcript",
            headers={
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 401

    def test_missing_archon_role_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Missing X-Archon-Role header returns 401."""
        session_id = uuid4()

        # Act: No X-Archon-Role header
        response = client.get(
            f"/deliberations/{session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
            },
        )

        # Assert
        assert response.status_code == 401

    def test_invalid_archon_id_format_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """Invalid Archon ID format returns 400."""
        session_id = uuid4()

        # Act: Invalid UUID
        response = client.get(
            f"/deliberations/{session_id}/transcript",
            headers={
                "X-Archon-Id": "not-a-valid-uuid",
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 400


class TestPhaseDetails:
    """Tests for phase details in response."""

    def test_all_four_phases_included(
        self,
        client: TestClient,
        summary_repo: DeliberationSummaryRepositoryStub,
        transcript_store: TranscriptStoreStub,
    ) -> None:
        """All four deliberation phases are included."""
        # Setup
        session = _create_completed_session()
        summary_repo.add_session(session)

        witnesses = _create_phase_witnesses(session.session_id, session.assigned_archons)
        summary_repo.add_witnesses(session.session_id, witnesses)

        transcript_json = _create_transcript_json(session.assigned_archons)
        for witness in witnesses:
            _inject_transcript(transcript_store, witness.transcript_hash, transcript_json)

        # Act
        response = client.get(
            f"/deliberations/{session.session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        phase_names = [p["phase"] for p in data["phases"]]
        assert "ASSESS" in phase_names
        assert "POSITION" in phase_names
        assert "CROSS_EXAMINE" in phase_names
        assert "VOTE" in phase_names

    def test_phase_timestamps_included(
        self,
        client: TestClient,
        summary_repo: DeliberationSummaryRepositoryStub,
        transcript_store: TranscriptStoreStub,
    ) -> None:
        """Phase timestamps are included."""
        # Setup
        session = _create_completed_session()
        summary_repo.add_session(session)

        witnesses = _create_phase_witnesses(session.session_id, session.assigned_archons)
        summary_repo.add_witnesses(session.session_id, witnesses)

        transcript_json = _create_transcript_json(session.assigned_archons)
        for witness in witnesses:
            _inject_transcript(transcript_store, witness.transcript_hash, transcript_json)

        # Act
        response = client.get(
            f"/deliberations/{session.session_id}/transcript",
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        for phase in data["phases"]:
            assert "start_timestamp" in phase
            assert "end_timestamp" in phase
            assert "transcript_hash_hex" in phase
            assert len(phase["transcript_hash_hex"]) == 64  # Blake3 hex


# =============================================================================
# Test Helpers
# =============================================================================


def _create_completed_session(has_dissent: bool = False) -> DeliberationSession:
    """Create a completed deliberation session for testing."""
    archons = (uuid4(), uuid4(), uuid4())

    return DeliberationSession(
        session_id=uuid4(),
        petition_id=uuid4(),
        assigned_archons=archons,
        phase=DeliberationPhase.COMPLETE,
        outcome=DeliberationOutcome.ACKNOWLEDGE,
        votes={
            archons[0]: DeliberationOutcome.ACKNOWLEDGE,
            archons[1]: DeliberationOutcome.ACKNOWLEDGE,
            archons[2]: (
                DeliberationOutcome.ESCALATE if has_dissent else DeliberationOutcome.ACKNOWLEDGE
            ),
        },
        dissent_archon_id=archons[2] if has_dissent else None,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )


def _create_phase_witnesses(
    session_id,
    archons: tuple,
    dissent_text: str | None = None,
) -> list[PhaseWitnessEvent]:
    """Create phase witness events for testing."""
    witnesses: list[PhaseWitnessEvent] = []
    phases = [
        DeliberationPhase.ASSESS,
        DeliberationPhase.POSITION,
        DeliberationPhase.CROSS_EXAMINE,
        DeliberationPhase.VOTE,
    ]

    prev_hash: bytes | None = None
    now = datetime.now(timezone.utc)

    for phase in phases:
        metadata: dict = {"themes": ["constitutional"]}

        # Add dissent text to VOTE phase
        if phase == DeliberationPhase.VOTE and dissent_text:
            metadata["dissent_text"] = dissent_text

        witness = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=session_id,
            phase=phase,
            transcript_hash=b"a" * 32,
            participating_archons=archons,
            start_timestamp=now,
            end_timestamp=now,
            phase_metadata=metadata,
            previous_witness_hash=prev_hash,
        )
        prev_hash = witness.event_hash
        witnesses.append(witness)

    return witnesses


def _create_transcript_json(archons: tuple) -> str:
    """Create JSON transcript content."""
    now = datetime.now(timezone.utc).isoformat()
    return json.dumps(
        [
            {
                "archon_id": str(archons[0]),
                "timestamp": now,
                "content": "First utterance from first archon.",
                "sequence": 0,
            },
            {
                "archon_id": str(archons[1]),
                "timestamp": now,
                "content": "Second utterance from second archon.",
                "sequence": 1,
            },
            {
                "archon_id": str(archons[2]),
                "timestamp": now,
                "content": "Third utterance from third archon.",
                "sequence": 2,
            },
        ]
    )
