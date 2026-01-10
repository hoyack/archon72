"""Unit tests for TopicRateLimiterPort interface (FR71-72).

Tests the port protocol for topic rate limiting.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.topic_rate_limiter import (
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_WINDOW_SECONDS,
    TopicRateLimiterPort,
)
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)


class TestTopicRateLimiterPortConstants:
    """Tests for port constants."""

    def test_rate_limit_per_hour_is_10(self) -> None:
        """Rate limit is 10 per hour per FR71."""
        assert RATE_LIMIT_PER_HOUR == 10

    def test_rate_limit_window_is_3600_seconds(self) -> None:
        """Rate limit window is 1 hour (3600 seconds)."""
        assert RATE_LIMIT_WINDOW_SECONDS == 3600


class TestTopicRateLimiterPortProtocol:
    """Tests for TopicRateLimiterPort protocol definition."""

    def test_protocol_defines_check_rate_limit(self) -> None:
        """Protocol defines check_rate_limit method."""
        assert hasattr(TopicRateLimiterPort, "check_rate_limit")

    def test_protocol_defines_record_submission(self) -> None:
        """Protocol defines record_submission method."""
        assert hasattr(TopicRateLimiterPort, "record_submission")

    def test_protocol_defines_get_queue_position(self) -> None:
        """Protocol defines get_queue_position method."""
        assert hasattr(TopicRateLimiterPort, "get_queue_position")

    def test_protocol_defines_queue_topic(self) -> None:
        """Protocol defines queue_topic method."""
        assert hasattr(TopicRateLimiterPort, "queue_topic")

    def test_protocol_defines_dequeue_topic(self) -> None:
        """Protocol defines dequeue_topic method."""
        assert hasattr(TopicRateLimiterPort, "dequeue_topic")


class MockTopicRateLimiter:
    """Mock implementation for protocol testing."""

    async def check_rate_limit(self, source_id: str) -> bool:
        """Check if source is within rate limit."""
        return True

    async def record_submission(self, source_id: str) -> int:
        """Record a submission and return count."""
        return 1

    async def get_queue_position(self, topic_id: str) -> int | None:
        """Get queue position for a topic."""
        return None

    async def queue_topic(self, topic: TopicOrigin) -> int:
        """Queue a topic and return position."""
        return 1

    async def dequeue_topic(self) -> TopicOrigin | None:
        """Dequeue next topic."""
        return None


class TestMockImplementsProtocol:
    """Tests that mock implementation satisfies protocol."""

    def test_mock_is_valid_implementation(self) -> None:
        """Mock satisfies TopicRateLimiterPort protocol."""
        mock = MockTopicRateLimiter()
        limiter: TopicRateLimiterPort = mock
        assert isinstance(limiter, TopicRateLimiterPort)

    @pytest.mark.asyncio
    async def test_mock_check_rate_limit(self) -> None:
        """Mock can check rate limit."""
        mock = MockTopicRateLimiter()
        result = await mock.check_rate_limit("archon-42")
        assert result is True

    @pytest.mark.asyncio
    async def test_mock_queue_topic(self) -> None:
        """Mock can queue topic."""
        mock = MockTopicRateLimiter()
        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="test"),
            created_at=datetime.now(timezone.utc),
            created_by="test",
        )
        position = await mock.queue_topic(topic)
        assert position == 1
