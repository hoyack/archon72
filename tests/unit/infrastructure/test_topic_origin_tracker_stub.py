"""Unit tests for TopicOriginTrackerStub (FR15, FR73).

Tests the in-memory stub implementation of TopicOriginTrackerPort.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.topic_origin_tracker import TopicOriginTrackerPort
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)
from src.infrastructure.stubs.topic_origin_tracker_stub import TopicOriginTrackerStub


class TestTopicOriginTrackerStubImplementsProtocol:
    """Tests that stub implements protocol."""

    def test_stub_implements_protocol(self) -> None:
        """Stub is a valid TopicOriginTrackerPort implementation."""
        stub = TopicOriginTrackerStub()
        assert isinstance(stub, TopicOriginTrackerPort)


class TestTopicOriginTrackerStubRecording:
    """Tests for recording and retrieving topics."""

    @pytest.mark.asyncio
    async def test_record_and_get_topic(self) -> None:
        """Record a topic and retrieve it by ID."""
        stub = TopicOriginTrackerStub()
        topic_id = uuid4()
        topic = TopicOrigin(
            topic_id=topic_id,
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(
                autonomous_trigger="test",
                source_agent_id="archon-1",
            ),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        await stub.record_topic_origin(topic)
        result = await stub.get_topic_origin(topic_id)

        assert result is not None
        assert result.topic_id == topic_id
        assert result.origin_type == TopicOriginType.AUTONOMOUS

    @pytest.mark.asyncio
    async def test_get_nonexistent_topic_returns_none(self) -> None:
        """Getting nonexistent topic returns None."""
        stub = TopicOriginTrackerStub()
        result = await stub.get_topic_origin(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_topics_by_origin_type(self) -> None:
        """Get topics filtered by origin type."""
        stub = TopicOriginTrackerStub()
        now = datetime.now(timezone.utc)

        # Add topics of different types
        for i in range(3):
            await stub.record_topic_origin(
                TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=TopicOriginType.AUTONOMOUS,
                    origin_metadata=TopicOriginMetadata(source_agent_id=f"archon-{i}"),
                    created_at=now,
                    created_by=f"archon-{i}",
                )
            )
        for i in range(2):
            await stub.record_topic_origin(
                TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=TopicOriginType.PETITION,
                    origin_metadata=TopicOriginMetadata(
                        petition_id=uuid4(),
                        source_agent_id="petition-system",
                    ),
                    created_at=now,
                    created_by="petition-system",
                )
            )

        autonomous = await stub.get_topics_by_origin_type(
            TopicOriginType.AUTONOMOUS, since=now - timedelta(hours=1)
        )
        petition = await stub.get_topics_by_origin_type(
            TopicOriginType.PETITION, since=now - timedelta(hours=1)
        )

        assert len(autonomous) == 3
        assert len(petition) == 2


class TestTopicOriginTrackerStubDiversity:
    """Tests for diversity statistics calculation."""

    @pytest.mark.asyncio
    async def test_diversity_stats_empty_returns_zeros(self) -> None:
        """Empty tracker returns zero counts."""
        stub = TopicOriginTrackerStub()
        stats = await stub.get_diversity_stats(window_days=30)

        assert stats.total_topics == 0
        assert stats.autonomous_count == 0
        assert stats.petition_count == 0
        assert stats.scheduled_count == 0

    @pytest.mark.asyncio
    async def test_diversity_stats_counts_correctly(self) -> None:
        """Diversity stats count topics by type correctly."""
        stub = TopicOriginTrackerStub()
        now = datetime.now(timezone.utc)

        # Add 10 autonomous, 5 petition, 5 scheduled
        for i in range(10):
            await stub.record_topic_origin(
                TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=TopicOriginType.AUTONOMOUS,
                    origin_metadata=TopicOriginMetadata(source_agent_id=f"archon-{i}"),
                    created_at=now,
                    created_by=f"archon-{i}",
                )
            )
        for i in range(5):
            await stub.record_topic_origin(
                TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=TopicOriginType.PETITION,
                    origin_metadata=TopicOriginMetadata(
                        petition_id=uuid4(),
                        source_agent_id="petition-system",
                    ),
                    created_at=now,
                    created_by="petition-system",
                )
            )
        for i in range(5):
            await stub.record_topic_origin(
                TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=TopicOriginType.SCHEDULED,
                    origin_metadata=TopicOriginMetadata(
                        schedule_ref=f"weekly-{i}",
                        source_agent_id="scheduler",
                    ),
                    created_at=now,
                    created_by="scheduler",
                )
            )

        stats = await stub.get_diversity_stats(window_days=30)

        assert stats.total_topics == 20
        assert stats.autonomous_count == 10
        assert stats.petition_count == 5
        assert stats.scheduled_count == 5
        assert stats.autonomous_pct == 0.5  # 50%
        assert stats.petition_pct == 0.25  # 25%
        assert stats.scheduled_pct == 0.25  # 25%

    @pytest.mark.asyncio
    async def test_diversity_stats_respects_window(self) -> None:
        """Diversity stats only count topics within window."""
        stub = TopicOriginTrackerStub()
        now = datetime.now(timezone.utc)

        # Add topic within window
        await stub.record_topic_origin(
            TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
                created_at=now,
                created_by="archon-1",
            )
        )

        # Add topic outside window (35 days ago)
        await stub.record_topic_origin(
            TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.PETITION,
                origin_metadata=TopicOriginMetadata(
                    petition_id=uuid4(),
                    source_agent_id="petition-system",
                ),
                created_at=now - timedelta(days=35),
                created_by="petition-system",
            )
        )

        stats = await stub.get_diversity_stats(window_days=30)

        # Only the autonomous topic is in window
        assert stats.total_topics == 1
        assert stats.autonomous_count == 1
        assert stats.petition_count == 0


class TestTopicOriginTrackerStubSourceCounting:
    """Tests for counting topics by source."""

    @pytest.mark.asyncio
    async def test_count_topics_from_source(self) -> None:
        """Count topics from a specific source."""
        stub = TopicOriginTrackerStub()
        now = datetime.now(timezone.utc)

        # Add 5 topics from archon-42
        for _ in range(5):
            await stub.record_topic_origin(
                TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=TopicOriginType.AUTONOMOUS,
                    origin_metadata=TopicOriginMetadata(source_agent_id="archon-42"),
                    created_at=now,
                    created_by="archon-42",
                )
            )
        # Add 3 topics from different source
        for _ in range(3):
            await stub.record_topic_origin(
                TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=TopicOriginType.AUTONOMOUS,
                    origin_metadata=TopicOriginMetadata(source_agent_id="archon-7"),
                    created_at=now,
                    created_by="archon-7",
                )
            )

        count = await stub.count_topics_from_source("archon-42", since=now - timedelta(hours=1))
        assert count == 5

    @pytest.mark.asyncio
    async def test_count_respects_time_window(self) -> None:
        """Source count respects time window."""
        stub = TopicOriginTrackerStub()
        now = datetime.now(timezone.utc)

        # Add topic now
        await stub.record_topic_origin(
            TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
                created_at=now,
                created_by="archon-1",
            )
        )
        # Add topic 2 hours ago
        await stub.record_topic_origin(
            TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
                created_at=now - timedelta(hours=2),
                created_by="archon-1",
            )
        )

        # Only count last hour
        count = await stub.count_topics_from_source("archon-1", since=now - timedelta(hours=1))
        assert count == 1


class TestTopicOriginTrackerStubDevMode:
    """Tests for DEV_MODE watermark pattern."""

    def test_stub_has_dev_mode_watermark(self) -> None:
        """Stub is marked with DEV_MODE."""
        stub = TopicOriginTrackerStub()
        assert hasattr(stub, "DEV_MODE")
        assert stub.DEV_MODE is True
