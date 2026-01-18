"""Unit tests for review session domain model.

Story: consent-gov-6-4: Prince Panel Domain Model

Tests for artifact review mechanism (AC3/FR37):
- Panel receives witness statements
- Panel can access related events
- Review session recorded
- All evidence preserved

References:
    - FR37: Prince Panel can review witness artifacts
    - AC3: Panel can review witness artifacts
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.governance.panel.review_session import ReviewedArtifact, ReviewSession


class TestReviewedArtifact:
    """Tests for ReviewedArtifact model."""

    def test_create_reviewed_artifact(self) -> None:
        """Can create a reviewed artifact record."""
        artifact = ReviewedArtifact(
            artifact_id=uuid4(),
            artifact_type="witness_statement",
            reviewed_at=datetime.now(timezone.utc),
        )

        assert artifact.artifact_type == "witness_statement"

    def test_reviewed_artifact_is_immutable(self) -> None:
        """ReviewedArtifact is frozen dataclass."""
        artifact = ReviewedArtifact(
            artifact_id=uuid4(),
            artifact_type="witness_statement",
            reviewed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            artifact.artifact_type = "event"  # type: ignore

    def test_can_record_event_artifact(self) -> None:
        """Can record review of event artifacts."""
        artifact = ReviewedArtifact(
            artifact_id=uuid4(),
            artifact_type="governance_event",
            reviewed_at=datetime.now(timezone.utc),
        )

        assert artifact.artifact_type == "governance_event"


class TestReviewSession:
    """Tests for ReviewSession model."""

    def test_create_review_session(self) -> None:
        """Can create a review session."""
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            reviewed_artifacts=[],
            notes=None,
        )

        assert session.is_active is True

    def test_session_with_artifacts(self) -> None:
        """Can create session with reviewed artifacts."""
        statement_id = uuid4()
        artifact = ReviewedArtifact(
            artifact_id=statement_id,
            artifact_type="witness_statement",
            reviewed_at=datetime.now(timezone.utc),
        )

        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=statement_id,
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            reviewed_artifacts=[artifact],
            notes=None,
        )

        assert session.artifact_count == 1

    def test_session_with_multiple_artifacts(self) -> None:
        """Session can track multiple reviewed artifacts."""
        statement_id = uuid4()
        event_id = uuid4()
        now = datetime.now(timezone.utc)

        artifacts = [
            ReviewedArtifact(
                artifact_id=statement_id,
                artifact_type="witness_statement",
                reviewed_at=now,
            ),
            ReviewedArtifact(
                artifact_id=event_id,
                artifact_type="governance_event",
                reviewed_at=now + timedelta(minutes=5),
            ),
        ]

        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=statement_id,
            started_at=now,
            ended_at=None,
            reviewed_artifacts=artifacts,
            notes=None,
        )

        assert session.artifact_count == 2

    def test_session_is_active_when_no_end_time(self) -> None:
        """Session is active when ended_at is None."""
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            reviewed_artifacts=[],
            notes=None,
        )

        assert session.is_active is True

    def test_session_is_not_active_when_ended(self) -> None:
        """Session is not active when ended_at is set."""
        now = datetime.now(timezone.utc)
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            started_at=now,
            ended_at=now + timedelta(hours=1),
            reviewed_artifacts=[],
            notes=None,
        )

        assert session.is_active is False

    def test_session_with_notes(self) -> None:
        """Session can include panel notes."""
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            reviewed_artifacts=[],
            notes="Panel noted potential timing discrepancy in events.",
        )

        assert session.notes is not None
        assert "timing" in session.notes

    def test_session_is_immutable(self) -> None:
        """ReviewSession is frozen dataclass."""
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            reviewed_artifacts=[],
            notes=None,
        )

        with pytest.raises(AttributeError):
            session.notes = "New notes"  # type: ignore

    def test_session_preserves_all_evidence(self) -> None:
        """Session preserves all reviewed evidence (AC3)."""
        statement_id = uuid4()
        event1_id = uuid4()
        event2_id = uuid4()
        now = datetime.now(timezone.utc)

        artifacts = [
            ReviewedArtifact(
                artifact_id=statement_id,
                artifact_type="witness_statement",
                reviewed_at=now,
            ),
            ReviewedArtifact(
                artifact_id=event1_id,
                artifact_type="governance_event",
                reviewed_at=now + timedelta(minutes=2),
            ),
            ReviewedArtifact(
                artifact_id=event2_id,
                artifact_type="governance_event",
                reviewed_at=now + timedelta(minutes=5),
            ),
        ]

        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=statement_id,
            started_at=now,
            ended_at=now + timedelta(hours=1),
            reviewed_artifacts=artifacts,
            notes="All evidence examined.",
        )

        # Evidence is preserved
        assert session.artifact_count == 3
        artifact_ids = [a.artifact_id for a in session.reviewed_artifacts]
        assert statement_id in artifact_ids
        assert event1_id in artifact_ids
        assert event2_id in artifact_ids


class TestReviewSessionIntegration:
    """Integration-style tests for review session workflow."""

    def test_complete_review_workflow(self) -> None:
        """Test complete review session workflow."""
        panel_id = uuid4()
        statement_id = uuid4()
        start_time = datetime.now(timezone.utc)

        # 1. Start review session
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=panel_id,
            statement_id=statement_id,
            started_at=start_time,
            ended_at=None,
            reviewed_artifacts=[
                ReviewedArtifact(
                    artifact_id=statement_id,
                    artifact_type="witness_statement",
                    reviewed_at=start_time,
                ),
            ],
            notes=None,
        )

        assert session.is_active is True
        assert session.artifact_count == 1

        # 2. Add more artifacts during review (immutably)
        additional_event = uuid4()
        updated_artifacts = list(session.reviewed_artifacts)
        updated_artifacts.append(
            ReviewedArtifact(
                artifact_id=additional_event,
                artifact_type="governance_event",
                reviewed_at=start_time + timedelta(minutes=10),
            )
        )

        session_with_more = ReviewSession(
            session_id=session.session_id,
            panel_id=session.panel_id,
            statement_id=session.statement_id,
            started_at=session.started_at,
            ended_at=None,
            reviewed_artifacts=updated_artifacts,
            notes="Additional context event reviewed.",
        )

        assert session_with_more.artifact_count == 2

        # 3. End review session
        end_time = start_time + timedelta(hours=1)
        completed_session = ReviewSession(
            session_id=session_with_more.session_id,
            panel_id=session_with_more.panel_id,
            statement_id=session_with_more.statement_id,
            started_at=session_with_more.started_at,
            ended_at=end_time,
            reviewed_artifacts=session_with_more.reviewed_artifacts,
            notes=session_with_more.notes,
        )

        assert completed_session.is_active is False
        assert completed_session.artifact_count == 2
