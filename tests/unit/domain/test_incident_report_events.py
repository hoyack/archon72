"""Unit tests for Incident Report event payloads (Story 8.4, FR54, FR145, FR147).

Tests the IncidentReportCreatedPayload and IncidentReportPublishedPayload.

Constitutional Constraints:
- CT-12: Witnessing creates accountability -> All payloads must have signable_content()
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.incident_report import (
    INCIDENT_REPORT_CREATED_EVENT_TYPE,
    INCIDENT_REPORT_PUBLISHED_EVENT_TYPE,
    INCIDENT_SYSTEM_AGENT_ID,
    IncidentReportCreatedPayload,
    IncidentReportPublishedPayload,
)
from src.domain.models.incident_report import IncidentType


class TestEventConstants:
    """Test event type constants."""

    def test_created_event_type(self) -> None:
        """Created event type should be properly namespaced."""
        assert INCIDENT_REPORT_CREATED_EVENT_TYPE == "incident.report.created"

    def test_published_event_type(self) -> None:
        """Published event type should be properly namespaced."""
        assert INCIDENT_REPORT_PUBLISHED_EVENT_TYPE == "incident.report.published"

    def test_system_agent_id(self) -> None:
        """System agent ID should be properly namespaced."""
        assert INCIDENT_SYSTEM_AGENT_ID == "system.incident_reporting"


class TestIncidentReportCreatedPayload:
    """Test IncidentReportCreatedPayload (AC: 1,2,3)."""

    def test_create_halt_incident_payload(self) -> None:
        """Create payload for halt incident."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)
        related_ids = [uuid4()]

        payload = IncidentReportCreatedPayload(
            incident_id=incident_id,
            incident_type=IncidentType.HALT,
            title="System Halt - Fork Detected",
            cause="Conflicting hash chains detected",
            impact="System writes halted",
            related_event_ids=related_ids,
            created_at=now,
        )

        assert payload.incident_id == incident_id
        assert payload.incident_type == IncidentType.HALT
        assert payload.title == "System Halt - Fork Detected"
        assert payload.cause == "Conflicting hash chains detected"
        assert payload.impact == "System writes halted"
        assert payload.related_event_ids == related_ids
        assert payload.created_at == now

    def test_create_fork_incident_payload(self) -> None:
        """Create payload for fork incident."""
        payload = IncidentReportCreatedPayload(
            incident_id=uuid4(),
            incident_type=IncidentType.FORK,
            title="Fork Detection",
            cause="Hash chain conflict",
            impact="Constitutional crisis",
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )

        assert payload.incident_type == IncidentType.FORK

    def test_create_override_threshold_payload(self) -> None:
        """Create payload for override threshold incident."""
        override_ids = [uuid4() for _ in range(4)]

        payload = IncidentReportCreatedPayload(
            incident_id=uuid4(),
            incident_type=IncidentType.OVERRIDE_THRESHOLD,
            title="Override Threshold Exceeded",
            cause=">3 overrides today",
            impact="Potential abuse pattern",
            related_event_ids=override_ids,
            created_at=datetime.now(timezone.utc),
        )

        assert payload.incident_type == IncidentType.OVERRIDE_THRESHOLD
        assert len(payload.related_event_ids) == 4

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content should return bytes (CT-12)."""
        payload = IncidentReportCreatedPayload(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            cause="Test cause",
            impact="Test impact",
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content should return same bytes for same input (CT-12)."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)
        related_ids = [uuid4()]

        payload = IncidentReportCreatedPayload(
            incident_id=incident_id,
            incident_type=IncidentType.HALT,
            title="Test",
            cause="Test cause",
            impact="Test impact",
            related_event_ids=related_ids,
            created_at=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()
        assert content1 == content2

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict should contain all payload fields."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)
        related_id = uuid4()

        payload = IncidentReportCreatedPayload(
            incident_id=incident_id,
            incident_type=IncidentType.HALT,
            title="Test",
            cause="Test cause",
            impact="Test impact",
            related_event_ids=[related_id],
            created_at=now,
        )

        d = payload.to_dict()
        assert d["incident_id"] == str(incident_id)
        assert d["incident_type"] == "halt"
        assert d["title"] == "Test"
        assert d["cause"] == "Test cause"
        assert d["impact"] == "Test impact"
        assert d["related_event_ids"] == [str(related_id)]
        assert d["created_at"] == now.isoformat()

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable."""
        payload = IncidentReportCreatedPayload(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Test",
            cause="Test",
            impact="Test",
            related_event_ids=[],
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.title = "Modified"  # type: ignore


class TestIncidentReportPublishedPayload:
    """Test IncidentReportPublishedPayload (AC: 4)."""

    def test_create_published_payload(self) -> None:
        """Create payload for published incident."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)
        resolved = now

        payload = IncidentReportPublishedPayload(
            incident_id=incident_id,
            incident_type=IncidentType.HALT,
            content_hash="a" * 64,
            redacted_fields=[],
            published_at=now,
            resolution_at=resolved,
        )

        assert payload.incident_id == incident_id
        assert payload.incident_type == IncidentType.HALT
        assert payload.content_hash == "a" * 64
        assert payload.redacted_fields == []
        assert payload.published_at == now
        assert payload.resolution_at == resolved

    def test_create_published_payload_with_redactions(self) -> None:
        """Create payload for published incident with redacted fields."""
        payload = IncidentReportPublishedPayload(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            content_hash="b" * 64,
            redacted_fields=["cause", "internal_details"],
            published_at=datetime.now(timezone.utc),
            resolution_at=datetime.now(timezone.utc),
        )

        assert payload.redacted_fields == ["cause", "internal_details"]

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content should return bytes (CT-12)."""
        payload = IncidentReportPublishedPayload(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            content_hash="c" * 64,
            redacted_fields=[],
            published_at=datetime.now(timezone.utc),
            resolution_at=datetime.now(timezone.utc),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content should return same bytes for same input (CT-12)."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)

        payload = IncidentReportPublishedPayload(
            incident_id=incident_id,
            incident_type=IncidentType.FORK,
            content_hash="d" * 64,
            redacted_fields=["cause"],
            published_at=now,
            resolution_at=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()
        assert content1 == content2

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict should contain all payload fields."""
        incident_id = uuid4()
        now = datetime.now(timezone.utc)
        content_hash = "e" * 64

        payload = IncidentReportPublishedPayload(
            incident_id=incident_id,
            incident_type=IncidentType.OVERRIDE_THRESHOLD,
            content_hash=content_hash,
            redacted_fields=["internal"],
            published_at=now,
            resolution_at=now,
        )

        d = payload.to_dict()
        assert d["incident_id"] == str(incident_id)
        assert d["incident_type"] == "override_threshold"
        assert d["content_hash"] == content_hash
        assert d["redacted_fields"] == ["internal"]
        assert d["published_at"] == now.isoformat()
        assert d["resolution_at"] == now.isoformat()

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable."""
        payload = IncidentReportPublishedPayload(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            content_hash="f" * 64,
            redacted_fields=[],
            published_at=datetime.now(timezone.utc),
            resolution_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.content_hash = "modified"  # type: ignore
