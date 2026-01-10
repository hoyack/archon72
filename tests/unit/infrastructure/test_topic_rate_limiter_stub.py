"""Unit tests for TopicRateLimiterStub (FR71-72).

Tests the in-memory stub implementation of TopicRateLimiterPort.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.topic_rate_limiter import (
    RATE_LIMIT_PER_HOUR,
    TopicRateLimiterPort,
)
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)
from src.infrastructure.stubs.topic_rate_limiter_stub import TopicRateLimiterStub


class TestTopicRateLimiterStubImplementsProtocol:
    """Tests that stub implements protocol."""

    def test_stub_implements_protocol(self) -> None:
        """Stub is a valid TopicRateLimiterPort implementation."""
        stub = TopicRateLimiterStub()
        assert isinstance(stub, TopicRateLimiterPort)


class TestTopicRateLimiterStubRateLimit:
    """Tests for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_within_limit_returns_true(self) -> None:
        """Source within rate limit can submit."""
        stub = TopicRateLimiterStub()
        result = await stub.check_rate_limit("archon-42")
        assert result is True

    @pytest.mark.asyncio
    async def test_at_limit_returns_true(self) -> None:
        """Source at limit (10 submissions) can still submit one more."""
        stub = TopicRateLimiterStub()
        # Submit up to limit
        for _ in range(RATE_LIMIT_PER_HOUR):
            await stub.record_submission("archon-42")

        # 10th submission is OK, 11th would exceed
        result = await stub.check_rate_limit("archon-42")
        assert result is False  # Already at 10, can't submit more

    @pytest.mark.asyncio
    async def test_exceeds_limit_returns_false(self) -> None:
        """Source exceeding rate limit cannot submit."""
        stub = TopicRateLimiterStub()
        # Submit more than limit
        for _ in range(RATE_LIMIT_PER_HOUR + 1):
            await stub.record_submission("archon-42")

        result = await stub.check_rate_limit("archon-42")
        assert result is False

    @pytest.mark.asyncio
    async def test_record_submission_returns_count(self) -> None:
        """record_submission returns current count."""
        stub = TopicRateLimiterStub()
        count1 = await stub.record_submission("archon-42")
        count2 = await stub.record_submission("archon-42")
        count3 = await stub.record_submission("archon-42")

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

    @pytest.mark.asyncio
    async def test_different_sources_tracked_separately(self) -> None:
        """Each source has its own rate limit."""
        stub = TopicRateLimiterStub()
        # Max out one source
        for _ in range(RATE_LIMIT_PER_HOUR):
            await stub.record_submission("archon-1")

        # Other source should be OK
        assert await stub.check_rate_limit("archon-2") is True
        assert await stub.check_rate_limit("archon-1") is False


class TestTopicRateLimiterStubQueue:
    """Tests for topic queue functionality."""

    @pytest.mark.asyncio
    async def test_queue_topic_returns_position(self) -> None:
        """queue_topic returns queue position."""
        stub = TopicRateLimiterStub()
        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        position = await stub.queue_topic(topic)
        assert position == 1

    @pytest.mark.asyncio
    async def test_queue_multiple_topics(self) -> None:
        """Multiple topics get sequential positions."""
        stub = TopicRateLimiterStub()

        positions = []
        for i in range(3):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=f"archon-{i}"),
                created_at=datetime.now(timezone.utc),
                created_by=f"archon-{i}",
            )
            pos = await stub.queue_topic(topic)
            positions.append(pos)

        assert positions == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_queue_position(self) -> None:
        """get_queue_position returns correct position."""
        stub = TopicRateLimiterStub()
        topic_id = uuid4()
        topic = TopicOrigin(
            topic_id=topic_id,
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        await stub.queue_topic(topic)
        position = await stub.get_queue_position(topic_id)

        assert position == 1

    @pytest.mark.asyncio
    async def test_get_queue_position_not_queued_returns_none(self) -> None:
        """get_queue_position returns None if not queued."""
        stub = TopicRateLimiterStub()
        position = await stub.get_queue_position(uuid4())
        assert position is None

    @pytest.mark.asyncio
    async def test_dequeue_topic_fifo(self) -> None:
        """dequeue_topic returns topics in FIFO order."""
        stub = TopicRateLimiterStub()
        topic_ids = []

        for i in range(3):
            topic_id = uuid4()
            topic_ids.append(topic_id)
            topic = TopicOrigin(
                topic_id=topic_id,
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=f"archon-{i}"),
                created_at=datetime.now(timezone.utc),
                created_by=f"archon-{i}",
            )
            await stub.queue_topic(topic)

        # Dequeue in order
        dequeued1 = await stub.dequeue_topic()
        dequeued2 = await stub.dequeue_topic()
        dequeued3 = await stub.dequeue_topic()

        assert dequeued1 is not None and dequeued1.topic_id == topic_ids[0]
        assert dequeued2 is not None and dequeued2.topic_id == topic_ids[1]
        assert dequeued3 is not None and dequeued3.topic_id == topic_ids[2]

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self) -> None:
        """dequeue_topic returns None when queue is empty."""
        stub = TopicRateLimiterStub()
        result = await stub.dequeue_topic()
        assert result is None


class TestTopicRateLimiterStubDevMode:
    """Tests for DEV_MODE watermark pattern."""

    def test_stub_has_dev_mode_watermark(self) -> None:
        """Stub is marked with DEV_MODE."""
        stub = TopicRateLimiterStub()
        assert hasattr(stub, "DEV_MODE")
        assert stub.DEV_MODE is True
