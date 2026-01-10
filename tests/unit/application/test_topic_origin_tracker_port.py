"""Unit tests for TopicOriginTrackerPort interface (FR15, FR73).

Tests the port protocol for topic origin tracking.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.topic_origin_tracker import (
    DIVERSITY_THRESHOLD,
    DIVERSITY_WINDOW_DAYS,
    TopicOriginTrackerPort,
)
from src.domain.models.topic_diversity import TopicDiversityStats
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)


class TestTopicOriginTrackerPortConstants:
    """Tests for port constants."""

    def test_diversity_window_days_is_30(self) -> None:
        """Diversity window is 30 days per FR73."""
        assert DIVERSITY_WINDOW_DAYS == 30

    def test_diversity_threshold_is_30_percent(self) -> None:
        """Diversity threshold is 30% per FR73."""
        assert DIVERSITY_THRESHOLD == 0.30


class TestTopicOriginTrackerPortProtocol:
    """Tests for TopicOriginTrackerPort protocol definition."""

    def test_protocol_defines_record_topic_origin(self) -> None:
        """Protocol defines record_topic_origin method."""
        assert hasattr(TopicOriginTrackerPort, "record_topic_origin")

    def test_protocol_defines_get_topic_origin(self) -> None:
        """Protocol defines get_topic_origin method."""
        assert hasattr(TopicOriginTrackerPort, "get_topic_origin")

    def test_protocol_defines_get_topics_by_origin_type(self) -> None:
        """Protocol defines get_topics_by_origin_type method."""
        assert hasattr(TopicOriginTrackerPort, "get_topics_by_origin_type")

    def test_protocol_defines_get_diversity_stats(self) -> None:
        """Protocol defines get_diversity_stats method."""
        assert hasattr(TopicOriginTrackerPort, "get_diversity_stats")

    def test_protocol_defines_count_topics_from_source(self) -> None:
        """Protocol defines count_topics_from_source method."""
        assert hasattr(TopicOriginTrackerPort, "count_topics_from_source")


class MockTopicOriginTracker:
    """Mock implementation for protocol testing."""

    async def record_topic_origin(self, topic: TopicOrigin) -> None:
        """Record a topic origin."""
        pass

    async def get_topic_origin(self, topic_id: UUID) -> TopicOrigin | None:
        """Get a topic by ID."""
        return None

    async def get_topics_by_origin_type(
        self, origin_type: TopicOriginType, since: datetime
    ) -> list[TopicOrigin]:
        """Get topics by origin type."""
        return []

    async def get_diversity_stats(self, window_days: int = 30) -> TopicDiversityStats:
        """Get diversity statistics."""
        now = datetime.now(timezone.utc)
        return TopicDiversityStats(
            window_start=now - timedelta(days=window_days),
            window_end=now,
            total_topics=0,
            autonomous_count=0,
            petition_count=0,
            scheduled_count=0,
        )

    async def count_topics_from_source(self, source_id: str, since: datetime) -> int:
        """Count topics from a source."""
        return 0


class TestMockImplementsProtocol:
    """Tests that mock implementation satisfies protocol."""

    def test_mock_is_valid_implementation(self) -> None:
        """Mock satisfies TopicOriginTrackerPort protocol."""
        mock = MockTopicOriginTracker()
        # Protocol check - if this doesn't raise, it's valid
        tracker: TopicOriginTrackerPort = mock
        assert isinstance(tracker, TopicOriginTrackerPort)

    @pytest.mark.asyncio
    async def test_mock_record_topic_origin(self) -> None:
        """Mock can record topic origin."""
        mock = MockTopicOriginTracker()
        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="test"),
            created_at=datetime.now(timezone.utc),
            created_by="test",
        )
        await mock.record_topic_origin(topic)

    @pytest.mark.asyncio
    async def test_mock_get_diversity_stats(self) -> None:
        """Mock can return diversity stats."""
        mock = MockTopicOriginTracker()
        stats = await mock.get_diversity_stats(window_days=30)
        assert isinstance(stats, TopicDiversityStats)
        assert stats.total_topics == 0
