"""Unit tests for deliberation summary API endpoint (Story 7.4, FR-7.4).

Tests the GET /v1/petition-submissions/{petition_id}/deliberation-summary endpoint.

Constitutional Constraints:
- FR-7.4: System SHALL provide deliberation summary to Observer
- Ruling-2: Tiered transcript access
- D7: RFC 7807 error responses
"""

from datetime import datetime, timezone
from typing import Generator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.petition_submission import get_transcript_access_service
from src.api.routes.petition_submission import router
from src.domain.errors.deliberation import DeliberationPendingError
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.models.deliberation_session import DeliberationOutcome, DeliberationPhase
from src.domain.models.deliberation_summary import (
    DeliberationSummary,
    EscalationTrigger,
    PhaseSummaryItem,
)


@pytest.fixture
def mock_transcript_service() -> AsyncMock:
    """Create mock TranscriptAccessMediationService."""
    return AsyncMock()


@pytest.fixture
def app(mock_transcript_service: AsyncMock) -> Generator[FastAPI, None, None]:
    """Create test FastAPI application with dependency override."""
    app = FastAPI()
    app.include_router(router)

    # Override the dependency to use the mock
    app.dependency_overrides[get_transcript_access_service] = lambda: mock_transcript_service

    yield app

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_summary() -> DeliberationSummary:
    """Create sample deliberation summary for testing."""
    petition_id = uuid4()
    return DeliberationSummary(
        petition_id=petition_id,
        outcome=DeliberationOutcome.ACKNOWLEDGE,
        vote_breakdown="3-0",
        has_dissent=False,
        phase_summaries=(
            PhaseSummaryItem(
                phase=DeliberationPhase.ASSESS,
                duration_seconds=120,
                transcript_hash_hex="a" * 64,
            ),
            PhaseSummaryItem(
                phase=DeliberationPhase.POSITION,
                duration_seconds=180,
                transcript_hash_hex="b" * 64,
            ),
            PhaseSummaryItem(
                phase=DeliberationPhase.CROSS_EXAMINE,
                duration_seconds=240,
                transcript_hash_hex="c" * 64,
            ),
            PhaseSummaryItem(
                phase=DeliberationPhase.VOTE,
                duration_seconds=60,
                transcript_hash_hex="d" * 64,
            ),
        ),
        duration_seconds=600,
        completed_at=datetime.now(timezone.utc),
    )


class TestGetDeliberationSummaryEndpoint:
    """Tests for GET /v1/petition-submissions/{petition_id}/deliberation-summary."""

    def test_returns_summary_for_completed_deliberation_ac1(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
        sample_summary: DeliberationSummary,
    ) -> None:
        """AC-1: Returns DeliberationSummary with mediated fields."""
        mock_transcript_service.get_deliberation_summary.return_value = sample_summary

        response = client.get(
            f"/v1/petition-submissions/{sample_summary.petition_id}/deliberation-summary"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["petition_id"] == str(sample_summary.petition_id)
        assert data["outcome"] == "ACKNOWLEDGE"
        assert data["vote_breakdown"] == "3-0"
        assert data["has_dissent"] is False
        assert len(data["phase_summaries"]) == 4
        assert data["duration_seconds"] == 600

    def test_returns_auto_escalation_summary_ac2(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
    ) -> None:
        """AC-2: Returns summary for auto-escalated petition."""
        petition_id = uuid4()
        auto_summary = DeliberationSummary.from_auto_escalation(
            petition_id=petition_id,
            escalation_reason="Co-signer threshold reached",
        )

        mock_transcript_service.get_deliberation_summary.return_value = auto_summary

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["outcome"] == "ESCALATE"
        assert data["escalation_trigger"] == "AUTO_ESCALATED"
        assert data["vote_breakdown"] == "0-0"
        assert len(data["phase_summaries"]) == 0

    def test_returns_400_for_pending_deliberation_ac3(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
    ) -> None:
        """AC-3: Returns 400 if deliberation not complete."""
        petition_id = uuid4()

        mock_transcript_service.get_deliberation_summary.side_effect = (
            DeliberationPendingError(
                petition_id=str(petition_id),
                current_state="RECEIVED",
            )
        )

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        assert response.status_code == 400
        data = response.json()["detail"]

        assert data["type"] == "urn:archon72:petition:deliberation-pending"
        assert data["title"] == "Deliberation Pending"
        assert data["status"] == 400
        assert str(petition_id) in data["detail"]

    def test_returns_404_for_missing_petition_ac4(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
    ) -> None:
        """AC-4: Returns 404 if petition not found."""
        petition_id = uuid4()

        mock_transcript_service.get_deliberation_summary.side_effect = (
            PetitionNotFoundError(petition_id=str(petition_id))
        )

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        assert response.status_code == 404
        data = response.json()["detail"]

        assert data["type"] == "urn:archon72:petition:not-found"
        assert data["title"] == "Petition Not Found"
        assert data["status"] == 404

    def test_returns_timeout_triggered_escalation_ac6(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
    ) -> None:
        """AC-6: Returns timeout-triggered escalation summary."""
        petition_id = uuid4()
        timeout_summary = DeliberationSummary.from_timeout(
            petition_id=petition_id,
            phase_summaries=(
                PhaseSummaryItem(
                    phase=DeliberationPhase.ASSESS,
                    duration_seconds=120,
                    transcript_hash_hex="a" * 64,
                ),
            ),
            duration_seconds=300,
            completed_at=datetime.now(timezone.utc),
        )

        mock_transcript_service.get_deliberation_summary.return_value = timeout_summary

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["outcome"] == "ESCALATE"
        assert data["escalation_trigger"] == "TIMEOUT"
        assert data["timed_out"] is True

    def test_returns_deadlock_triggered_escalation_ac7(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
    ) -> None:
        """AC-7: Returns deadlock-triggered escalation summary."""
        petition_id = uuid4()
        deadlock_summary = DeliberationSummary.from_deadlock(
            petition_id=petition_id,
            phase_summaries=(),
            duration_seconds=900,
            completed_at=datetime.now(timezone.utc),
            rounds_attempted=3,
        )

        mock_transcript_service.get_deliberation_summary.return_value = deadlock_summary

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["outcome"] == "ESCALATE"
        assert data["escalation_trigger"] == "DEADLOCK"
        assert data["rounds_attempted"] == 3


class TestMediationInResponse:
    """Tests verifying mediation is properly applied in API response."""

    def test_response_excludes_archon_identities(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
        sample_summary: DeliberationSummary,
    ) -> None:
        """Ruling-2: Response must not include Archon identities."""
        mock_transcript_service.get_deliberation_summary.return_value = sample_summary

        response = client.get(
            f"/v1/petition-submissions/{sample_summary.petition_id}/deliberation-summary"
        )

        assert response.status_code == 200
        response_text = response.text.lower()

        # No archon identities should appear
        assert "archon_id" not in response_text
        assert "participating_archons" not in response_text

    def test_vote_breakdown_is_anonymous_string(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
        sample_summary: DeliberationSummary,
    ) -> None:
        """Ruling-2: Vote breakdown is anonymous string, not individual votes."""
        mock_transcript_service.get_deliberation_summary.return_value = sample_summary

        response = client.get(
            f"/v1/petition-submissions/{sample_summary.petition_id}/deliberation-summary"
        )

        data = response.json()

        # vote_breakdown is string like "3-0", not a dict of votes
        assert isinstance(data["vote_breakdown"], str)
        assert "-" in data["vote_breakdown"]
        # No individual votes exposed
        assert "votes" not in data

    def test_has_dissent_is_boolean_only(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
    ) -> None:
        """Ruling-2: has_dissent is boolean, not dissenter identity."""
        petition_id = uuid4()
        summary_with_dissent = DeliberationSummary(
            petition_id=petition_id,
            outcome=DeliberationOutcome.REFER,
            vote_breakdown="2-1",
            has_dissent=True,  # Dissent exists
            phase_summaries=(),
            duration_seconds=600,
            completed_at=datetime.now(timezone.utc),
        )

        mock_transcript_service.get_deliberation_summary.return_value = summary_with_dissent

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/deliberation-summary"
        )

        data = response.json()

        # has_dissent is boolean, not identity
        assert data["has_dissent"] is True
        assert "dissent_archon" not in data

    def test_phase_summaries_contain_hashes_not_content(
        self,
        client: TestClient,
        mock_transcript_service: AsyncMock,
        sample_summary: DeliberationSummary,
    ) -> None:
        """Ruling-2: Phase summaries have hashes, not transcript content."""
        mock_transcript_service.get_deliberation_summary.return_value = sample_summary

        response = client.get(
            f"/v1/petition-submissions/{sample_summary.petition_id}/deliberation-summary"
        )

        data = response.json()

        for ps in data["phase_summaries"]:
            # Has hash (proving existence)
            assert "transcript_hash_hex" in ps
            assert len(ps["transcript_hash_hex"]) == 64  # Blake3 hex
            # No transcript content
            assert "transcript" not in ps or "hash" in ps.get("transcript", "hash")
            assert "content" not in ps
            assert "utterances" not in ps
