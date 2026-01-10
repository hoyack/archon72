"""Unit tests for TopicOrigin domain model (FR15).

Tests the topic origin tracking model for manipulation defense.
All origin types (AUTONOMOUS, PETITION, SCHEDULED) must include
appropriate metadata.

Constitutional Constraints:
- FR15: Topic origins SHALL be tracked with origin metadata
- FR71-73: Topic flooding defense and diversity enforcement
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)


class TestTopicOriginType:
    """Tests for TopicOriginType enum."""

    def test_autonomous_type_value(self) -> None:
        """AUTONOMOUS type has correct string value."""
        assert TopicOriginType.AUTONOMOUS.value == "autonomous"

    def test_petition_type_value(self) -> None:
        """PETITION type has correct string value."""
        assert TopicOriginType.PETITION.value == "petition"

    def test_scheduled_type_value(self) -> None:
        """SCHEDULED type has correct string value."""
        assert TopicOriginType.SCHEDULED.value == "scheduled"


class TestTopicOriginMetadata:
    """Tests for TopicOriginMetadata frozen dataclass."""

    def test_create_petition_metadata(self) -> None:
        """Petition metadata includes petition_id."""
        petition_id = uuid4()
        metadata = TopicOriginMetadata(
            petition_id=petition_id,
            source_agent_id="petition-system",
        )
        assert metadata.petition_id == petition_id
        assert metadata.schedule_ref is None
        assert metadata.autonomous_trigger is None
        assert metadata.source_agent_id == "petition-system"

    def test_create_scheduled_metadata(self) -> None:
        """Scheduled metadata includes schedule_ref."""
        metadata = TopicOriginMetadata(
            schedule_ref="weekly-conclave-2026-01",
            source_agent_id="scheduler",
        )
        assert metadata.schedule_ref == "weekly-conclave-2026-01"
        assert metadata.petition_id is None
        assert metadata.autonomous_trigger is None

    def test_create_autonomous_metadata(self) -> None:
        """Autonomous metadata includes trigger description."""
        metadata = TopicOriginMetadata(
            autonomous_trigger="breach-detected-fr80",
            source_agent_id="archon-42",
        )
        assert metadata.autonomous_trigger == "breach-detected-fr80"
        assert metadata.petition_id is None
        assert metadata.schedule_ref is None

    def test_metadata_is_frozen(self) -> None:
        """Metadata is immutable."""
        metadata = TopicOriginMetadata(source_agent_id="test")
        with pytest.raises(AttributeError):
            metadata.source_agent_id = "modified"  # type: ignore[misc]


class TestTopicOrigin:
    """Tests for TopicOrigin frozen dataclass."""

    def test_create_autonomous_topic(self) -> None:
        """Create topic with AUTONOMOUS origin type."""
        topic_id = uuid4()
        now = datetime.now(timezone.utc)
        metadata = TopicOriginMetadata(
            autonomous_trigger="agent-initiated",
            source_agent_id="archon-7",
        )

        topic = TopicOrigin(
            topic_id=topic_id,
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=metadata,
            created_at=now,
            created_by="archon-7",
        )

        assert topic.topic_id == topic_id
        assert topic.origin_type == TopicOriginType.AUTONOMOUS
        assert topic.origin_metadata == metadata
        assert topic.created_at == now
        assert topic.created_by == "archon-7"

    def test_create_petition_topic(self) -> None:
        """Create topic with PETITION origin type."""
        topic_id = uuid4()
        petition_id = uuid4()
        now = datetime.now(timezone.utc)
        metadata = TopicOriginMetadata(
            petition_id=petition_id,
            source_agent_id="petition-system",
        )

        topic = TopicOrigin(
            topic_id=topic_id,
            origin_type=TopicOriginType.PETITION,
            origin_metadata=metadata,
            created_at=now,
            created_by="petition-system",
        )

        assert topic.origin_type == TopicOriginType.PETITION
        assert topic.origin_metadata.petition_id == petition_id

    def test_create_scheduled_topic(self) -> None:
        """Create topic with SCHEDULED origin type."""
        topic_id = uuid4()
        now = datetime.now(timezone.utc)
        metadata = TopicOriginMetadata(
            schedule_ref="monthly-audit-2026-01",
            source_agent_id="scheduler",
        )

        topic = TopicOrigin(
            topic_id=topic_id,
            origin_type=TopicOriginType.SCHEDULED,
            origin_metadata=metadata,
            created_at=now,
            created_by="scheduler",
        )

        assert topic.origin_type == TopicOriginType.SCHEDULED
        assert topic.origin_metadata.schedule_ref == "monthly-audit-2026-01"

    def test_topic_is_frozen(self) -> None:
        """TopicOrigin is immutable."""
        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="test"),
            created_at=datetime.now(timezone.utc),
            created_by="test",
        )
        with pytest.raises(AttributeError):
            topic.created_by = "modified"  # type: ignore[misc]

    def test_petition_requires_petition_id(self) -> None:
        """PETITION type without petition_id raises ValueError."""
        metadata = TopicOriginMetadata(source_agent_id="petition-system")

        with pytest.raises(ValueError, match="FR15: PETITION.*petition_id"):
            TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.PETITION,
                origin_metadata=metadata,
                created_at=datetime.now(timezone.utc),
                created_by="petition-system",
            )

    def test_scheduled_requires_schedule_ref(self) -> None:
        """SCHEDULED type without schedule_ref raises ValueError."""
        metadata = TopicOriginMetadata(source_agent_id="scheduler")

        with pytest.raises(ValueError, match="FR15: SCHEDULED.*schedule_ref"):
            TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.SCHEDULED,
                origin_metadata=metadata,
                created_at=datetime.now(timezone.utc),
                created_by="scheduler",
            )

    def test_created_by_cannot_be_empty(self) -> None:
        """created_by must be non-empty string."""
        with pytest.raises(ValueError, match="FR15.*created_by"):
            TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id="test"),
                created_at=datetime.now(timezone.utc),
                created_by="",
            )
