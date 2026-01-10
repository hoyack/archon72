"""Unit tests for Incident Report domain models (Story 8.4, FR54, FR145, FR147).

Tests the IncidentReport, IncidentType, IncidentStatus, and TimelineEntry models.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable by external parties
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.models.incident_report import (
    DAILY_OVERRIDE_THRESHOLD,
    PUBLICATION_DELAY_DAYS,
    IncidentReport,
    IncidentStatus,
    IncidentType,
    TimelineEntry,
)


class TestIncidentType:
    """Test IncidentType enum values (AC: 1,2,3)."""

    def test_halt_type_exists(self) -> None:
        """Halt incident type should exist per FR145."""
        assert IncidentType.HALT.value == "halt"

    def test_fork_type_exists(self) -> None:
        """Fork incident type should exist per FR145."""
        assert IncidentType.FORK.value == "fork"

    def test_override_threshold_type_exists(self) -> None:
        """Override threshold incident type should exist per FR145."""
        assert IncidentType.OVERRIDE_THRESHOLD.value == "override_threshold"


class TestIncidentStatus:
    """Test IncidentStatus enum values (AC: 4)."""

    def test_draft_status_exists(self) -> None:
        """Draft status should exist for new incidents."""
        assert IncidentStatus.DRAFT.value == "draft"

    def test_pending_publication_status_exists(self) -> None:
        """Pending publication status should exist for resolved incidents."""
        assert IncidentStatus.PENDING_PUBLICATION.value == "pending_publication"

    def test_published_status_exists(self) -> None:
        """Published status should exist for publicly available incidents."""
        assert IncidentStatus.PUBLISHED.value == "published"

    def test_redacted_status_exists(self) -> None:
        """Redacted status should exist for security-sensitive incidents."""
        assert IncidentStatus.REDACTED.value == "redacted"


class TestTimelineEntry:
    """Test TimelineEntry dataclass (AC: 1,2,3)."""

    def test_create_timeline_entry_minimal(self) -> None:
        """Create timeline entry with required fields only."""
        timestamp = datetime.now(timezone.utc)
        entry = TimelineEntry(
            timestamp=timestamp,
            description="System halt triggered",
        )
        assert entry.timestamp == timestamp
        assert entry.description == "System halt triggered"
        assert entry.event_id is None
        assert entry.actor is None

    def test_create_timeline_entry_full(self) -> None:
        """Create timeline entry with all fields."""
        timestamp = datetime.now(timezone.utc)
        event_id = uuid4()
        entry = TimelineEntry(
            timestamp=timestamp,
            description="Fork detected by continuous monitor",
            event_id=event_id,
            actor="system.fork_monitor",
        )
        assert entry.timestamp == timestamp
        assert entry.description == "Fork detected by continuous monitor"
        assert entry.event_id == event_id
        assert entry.actor == "system.fork_monitor"

    def test_timeline_entry_is_frozen(self) -> None:
        """Timeline entry should be immutable."""
        entry = TimelineEntry(
            timestamp=datetime.now(timezone.utc),
            description="Test",
        )
        with pytest.raises(AttributeError):
            entry.description = "Modified"  # type: ignore


class TestIncidentReport:
    """Test IncidentReport domain model (AC: 1,2,3,4)."""

    def test_create_incident_report_halt(self) -> None:
        """Create a halt incident report per FR145."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)
        related_event_id = uuid4()

        report = IncidentReport(
            incident_id=incident_id,
            incident_type=IncidentType.HALT,
            title="System Halt - Fork Detected",
            timeline=[
                TimelineEntry(
                    timestamp=now,
                    description="Fork detected",
                    event_id=related_event_id,
                    actor="system.fork_monitor",
                ),
            ],
            cause="Conflicting hash chains detected from partition",
            impact="System writes halted, read-only access maintained",
            response="",
            prevention_recommendations=[],
            related_event_ids=[related_event_id],
            created_at=now,
        )

        assert report.incident_id == incident_id
        assert report.incident_type == IncidentType.HALT
        assert report.title == "System Halt - Fork Detected"
        assert len(report.timeline) == 1
        assert report.cause == "Conflicting hash chains detected from partition"
        assert report.status == IncidentStatus.DRAFT

    def test_create_incident_report_fork(self) -> None:
        """Create a fork incident report per FR145."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)

        report = IncidentReport(
            incident_id=incident_id,
            incident_type=IncidentType.FORK,
            title="Fork Detection - Hash Chain Conflict",
            timeline=[],
            cause="Two events claimed same prev_hash with different content",
            impact="Constitutional crisis detected",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=now,
        )

        assert report.incident_type == IncidentType.FORK
        assert report.status == IncidentStatus.DRAFT

    def test_create_incident_report_override_threshold(self) -> None:
        """Create an override threshold incident report per FR145."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)
        override_ids = [uuid4() for _ in range(4)]

        report = IncidentReport(
            incident_id=incident_id,
            incident_type=IncidentType.OVERRIDE_THRESHOLD,
            title="Override Threshold Exceeded - 4 Overrides Today",
            timeline=[],
            cause=">3 Keeper overrides in a single day",
            impact="Potential keeper abuse pattern detected",
            response="",
            prevention_recommendations=[],
            related_event_ids=override_ids,
            created_at=now,
        )

        assert report.incident_type == IncidentType.OVERRIDE_THRESHOLD
        assert len(report.related_event_ids) == 4
        assert report.status == IncidentStatus.DRAFT

    def test_default_status_is_draft(self) -> None:
        """New incidents should default to DRAFT status."""
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        assert report.status == IncidentStatus.DRAFT

    def test_resolution_at_none_by_default(self) -> None:
        """resolution_at should be None for new incidents."""
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        assert report.resolution_at is None

    def test_publish_eligible_at_calculated_from_creation(self) -> None:
        """publish_eligible_at should be 7 days from creation per FR147."""
        now = datetime.now(timezone.utc)
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=now,
        )
        expected = now + timedelta(days=PUBLICATION_DELAY_DAYS)
        assert report.publish_eligible_at == expected

    def test_is_publish_eligible_before_7_days(self) -> None:
        """Incident should NOT be eligible for publication before 7 days."""
        now = datetime.now(timezone.utc)
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="Investigation complete",
            prevention_recommendations=["Monitor partitions"],
            related_event_ids=[],
            created_at=now,
            resolution_at=now,  # Resolved immediately
        )
        assert not report.is_publish_eligible()

    def test_is_publish_eligible_after_7_days(self) -> None:
        """Incident should be eligible for publication after 7 days."""
        created = datetime.now(timezone.utc) - timedelta(days=8)
        resolved = created + timedelta(hours=1)
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="Investigation complete",
            prevention_recommendations=["Monitor partitions"],
            related_event_ids=[],
            created_at=created,
            resolution_at=resolved,
        )
        assert report.is_publish_eligible()

    def test_is_publish_eligible_requires_resolution(self) -> None:
        """Incident should NOT be eligible for publication if not resolved."""
        created = datetime.now(timezone.utc) - timedelta(days=10)
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",  # Not resolved
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=created,
            resolution_at=None,  # Not resolved
        )
        assert not report.is_publish_eligible()

    def test_with_status_returns_new_instance(self) -> None:
        """with_status should return a new IncidentReport instance."""
        original = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        updated = original.with_status(IncidentStatus.PUBLISHED)

        assert updated.status == IncidentStatus.PUBLISHED
        assert original.status == IncidentStatus.DRAFT  # Original unchanged
        assert updated.incident_id == original.incident_id

    def test_with_resolution_returns_new_instance(self) -> None:
        """with_resolution should return a new IncidentReport instance."""
        original = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        resolved_at = datetime.now(timezone.utc)
        updated = original.with_resolution(
            response="Root cause identified",
            recommendations=["Implement monitoring"],
            resolved_at=resolved_at,
        )

        assert updated.resolution_at == resolved_at
        assert updated.response == "Root cause identified"
        assert updated.prevention_recommendations == ["Implement monitoring"]
        assert updated.status == IncidentStatus.PENDING_PUBLICATION
        assert original.resolution_at is None  # Original unchanged

    def test_with_redactions_returns_new_instance(self) -> None:
        """with_redactions should return a new IncidentReport instance."""
        original = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="Sensitive internal details",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        redacted = original.with_redactions(["cause"])

        assert redacted.redacted_fields == ["cause"]
        assert original.redacted_fields == []

    def test_add_timeline_entry_returns_new_instance(self) -> None:
        """add_timeline_entry should return a new IncidentReport instance."""
        original = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        entry = TimelineEntry(
            timestamp=datetime.now(timezone.utc),
            description="New event",
        )
        updated = original.add_timeline_entry(entry)

        assert len(updated.timeline) == 1
        assert len(original.timeline) == 0  # Original unchanged

    def test_content_hash_is_consistent(self) -> None:
        """content_hash should return consistent hash for same content."""
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="Test cause",
            impact="Test impact",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        hash1 = report.content_hash()
        hash2 = report.content_hash()

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex

    def test_incident_report_is_frozen(self) -> None:
        """IncidentReport should be immutable."""
        report = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            timeline=[],
            cause="",
            impact="",
            response="",
            prevention_recommendations=[],
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            report.title = "Modified"  # type: ignore


class TestConstants:
    """Test module constants (FR145, FR147)."""

    def test_publication_delay_days_is_7(self) -> None:
        """Publication delay should be 7 days per FR147."""
        assert PUBLICATION_DELAY_DAYS == 7

    def test_daily_override_threshold_is_3(self) -> None:
        """Daily override threshold should be 3 per FR145."""
        assert DAILY_OVERRIDE_THRESHOLD == 3
