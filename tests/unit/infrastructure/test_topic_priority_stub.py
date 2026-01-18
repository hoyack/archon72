"""Unit tests for TopicPriorityStub (Story 6.9, FR119).

Tests the in-memory implementation of topic priority management.

Constitutional Constraints:
- FR119: Autonomous topic priority SHALL be respected
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.topic_priority import (
    TopicPriorityLevel,
    TopicPriorityProtocol,
)
from src.infrastructure.stubs.topic_priority_stub import (
    TopicPriorityStub,
)


class TestTopicPriorityStubImplementsProtocol:
    """Test stub implements protocol correctly."""

    def test_implements_protocol(self) -> None:
        """Test stub inherits from protocol."""
        stub = TopicPriorityStub()
        assert isinstance(stub, TopicPriorityProtocol)


class TestGetTopicPriority:
    """Tests for get_topic_priority method."""

    @pytest.mark.asyncio
    async def test_default_priority_is_petition(self) -> None:
        """Test default priority is PETITION (lowest)."""
        stub = TopicPriorityStub()
        priority = await stub.get_topic_priority("unknown-topic")
        assert priority == TopicPriorityLevel.PETITION

    @pytest.mark.asyncio
    async def test_returns_configured_priority(self) -> None:
        """Test returns configured priority."""
        stub = TopicPriorityStub()
        await stub.set_topic_priority(
            "topic-1",
            TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION,
        )

        priority = await stub.get_topic_priority("topic-1")
        assert priority == TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION


class TestSetTopicPriority:
    """Tests for set_topic_priority method."""

    @pytest.mark.asyncio
    async def test_sets_priority(self) -> None:
        """Test priority is set."""
        stub = TopicPriorityStub()
        await stub.set_topic_priority(
            "topic-1",
            TopicPriorityLevel.AUTONOMOUS,
        )

        priority = await stub.get_topic_priority("topic-1")
        assert priority == TopicPriorityLevel.AUTONOMOUS

    @pytest.mark.asyncio
    async def test_updates_priority_in_queue(self) -> None:
        """Test priority update affects queued topic."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.PETITION)

        await stub.set_topic_priority(
            "topic-1",
            TopicPriorityLevel.AUTONOMOUS,
        )

        queue = stub.get_queue()
        topic_in_queue = next(t for t in queue if t.topic_id == "topic-1")
        assert topic_in_queue.priority == TopicPriorityLevel.AUTONOMOUS


class TestGetNextTopicForDeliberation:
    """Tests for get_next_topic_for_deliberation method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(self) -> None:
        """Test returns None when queue is empty."""
        stub = TopicPriorityStub()
        topic = await stub.get_next_topic_for_deliberation()
        assert topic is None

    @pytest.mark.asyncio
    async def test_returns_highest_priority(self) -> None:
        """Test returns highest priority topic (FR119)."""
        stub = TopicPriorityStub()
        stub.add_to_queue("petition-topic", TopicPriorityLevel.PETITION)
        stub.add_to_queue("autonomous-topic", TopicPriorityLevel.AUTONOMOUS)
        stub.add_to_queue("scheduled-topic", TopicPriorityLevel.SCHEDULED)

        topic = await stub.get_next_topic_for_deliberation()
        assert topic == "autonomous-topic"  # AUTONOMOUS > SCHEDULED > PETITION

    @pytest.mark.asyncio
    async def test_constitutional_examination_highest(self) -> None:
        """Test CONSTITUTIONAL_EXAMINATION is highest priority."""
        stub = TopicPriorityStub()
        stub.add_to_queue("autonomous-topic", TopicPriorityLevel.AUTONOMOUS)
        stub.add_to_queue(
            "constitutional-topic", TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION
        )

        topic = await stub.get_next_topic_for_deliberation()
        assert topic == "constitutional-topic"

    @pytest.mark.asyncio
    async def test_fifo_within_priority(self) -> None:
        """Test FIFO ordering within same priority level."""
        stub = TopicPriorityStub()
        now = datetime.now(timezone.utc)

        stub.add_to_queue(
            "first", TopicPriorityLevel.AUTONOMOUS, queued_at=now - timedelta(hours=2)
        )
        stub.add_to_queue(
            "second", TopicPriorityLevel.AUTONOMOUS, queued_at=now - timedelta(hours=1)
        )
        stub.add_to_queue("third", TopicPriorityLevel.AUTONOMOUS, queued_at=now)

        topic = await stub.get_next_topic_for_deliberation()
        assert topic == "first"  # Oldest first

    @pytest.mark.asyncio
    async def test_removes_topic_from_queue(self) -> None:
        """Test topic is removed from queue after selection."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.AUTONOMOUS)

        await stub.get_next_topic_for_deliberation()

        assert stub.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_marks_topic_as_deliberated(self) -> None:
        """Test topic is marked as deliberated."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.AUTONOMOUS)

        await stub.get_next_topic_for_deliberation()

        assert stub.is_deliberated("topic-1") is True


class TestGetQueuedTopicsByPriority:
    """Tests for get_queued_topics_by_priority method."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_all_priorities(self) -> None:
        """Test returns dict with all priority levels."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.AUTONOMOUS)
        stub.add_to_queue("topic-2", TopicPriorityLevel.PETITION)

        topics = await stub.get_queued_topics_by_priority()

        assert isinstance(topics, dict)
        assert TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION in topics
        assert TopicPriorityLevel.AUTONOMOUS in topics
        assert TopicPriorityLevel.SCHEDULED in topics
        assert TopicPriorityLevel.PETITION in topics

    @pytest.mark.asyncio
    async def test_groups_topics_by_priority(self) -> None:
        """Test groups topics correctly by priority."""
        stub = TopicPriorityStub()
        stub.add_to_queue("autonomous-1", TopicPriorityLevel.AUTONOMOUS)
        stub.add_to_queue("autonomous-2", TopicPriorityLevel.AUTONOMOUS)
        stub.add_to_queue("petition-1", TopicPriorityLevel.PETITION)

        topics = await stub.get_queued_topics_by_priority()

        assert len(topics[TopicPriorityLevel.AUTONOMOUS]) == 2
        assert "autonomous-1" in topics[TopicPriorityLevel.AUTONOMOUS]
        assert "autonomous-2" in topics[TopicPriorityLevel.AUTONOMOUS]
        assert len(topics[TopicPriorityLevel.PETITION]) == 1
        assert "petition-1" in topics[TopicPriorityLevel.PETITION]

    @pytest.mark.asyncio
    async def test_empty_priorities_included(self) -> None:
        """Test empty priority levels are included."""
        stub = TopicPriorityStub()
        stub.add_to_queue("petition", TopicPriorityLevel.PETITION)

        topics = await stub.get_queued_topics_by_priority()

        # All priority levels should be present, even if empty
        assert topics[TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION] == []
        assert topics[TopicPriorityLevel.AUTONOMOUS] == []
        assert topics[TopicPriorityLevel.SCHEDULED] == []
        assert topics[TopicPriorityLevel.PETITION] == ["petition"]


class TestEnsureAutonomousPriority:
    """Tests for ensure_autonomous_priority method (FR119)."""

    @pytest.mark.asyncio
    async def test_is_callable(self) -> None:
        """Test ensure_autonomous_priority is callable without args."""
        stub = TopicPriorityStub()
        # Should not raise - maintenance operation
        await stub.ensure_autonomous_priority()

    @pytest.mark.asyncio
    async def test_maintains_queue_integrity(self) -> None:
        """Test queue is maintained after call."""
        stub = TopicPriorityStub()
        stub.add_to_queue("autonomous-1", TopicPriorityLevel.AUTONOMOUS)
        stub.add_to_queue("petition-1", TopicPriorityLevel.PETITION)

        await stub.ensure_autonomous_priority()

        # Queue should still work correctly
        topic = await stub.get_next_topic_for_deliberation()
        assert topic == "autonomous-1"


class TestTestHelpers:
    """Tests for test helper methods."""

    def test_add_to_queue_adds_topic(self) -> None:
        """Test add_to_queue adds topic."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.AUTONOMOUS, "source-1")

        queue = stub.get_queue()
        assert len(queue) == 1
        assert queue[0].topic_id == "topic-1"
        assert queue[0].priority == TopicPriorityLevel.AUTONOMOUS
        assert queue[0].source_id == "source-1"

    def test_get_queue_size_returns_count(self) -> None:
        """Test get_queue_size returns correct count."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.PETITION)
        stub.add_to_queue("topic-2", TopicPriorityLevel.PETITION)

        assert stub.get_queue_size() == 2

    @pytest.mark.asyncio
    async def test_is_deliberated_tracks_status(self) -> None:
        """Test is_deliberated tracks deliberation status."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.PETITION)

        assert stub.is_deliberated("topic-1") is False

        await stub.get_next_topic_for_deliberation()

        assert stub.is_deliberated("topic-1") is True

    def test_clear_removes_all_data(self) -> None:
        """Test clear removes all stored data."""
        stub = TopicPriorityStub()
        stub.add_to_queue("topic-1", TopicPriorityLevel.AUTONOMOUS)
        stub._deliberated.add("topic-old")

        stub.clear()

        assert len(stub._priorities) == 0
        assert len(stub._queue) == 0
        assert len(stub._deliberated) == 0
