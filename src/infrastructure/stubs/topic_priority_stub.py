"""Topic priority stub (Story 6.9, FR119).

In-memory implementation for testing and development.

Constitutional Constraints:
- FR119: Autonomous topic priority SHALL be respected
- CT-12: Witnessing creates accountability -> signable audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.application.ports.topic_priority import (
    TopicPriorityLevel,
    TopicPriorityProtocol,
)


@dataclass
class QueuedTopic:
    """A topic in the deliberation queue."""

    topic_id: str
    priority: TopicPriorityLevel
    queued_at: datetime
    source_id: str


@dataclass
class TopicPriorityStub(TopicPriorityProtocol):
    """In-memory stub for topic priority management.

    Manages topic queue with priority ordering.
    Supports configurable priority assignments for testing.

    FR119: Autonomous topic priority SHALL be respected.
    """

    # Topic priorities
    _priorities: dict[str, TopicPriorityLevel] = field(default_factory=dict)

    # Topic queue
    _queue: list[QueuedTopic] = field(default_factory=list)

    # Topics already deliberated (removed from queue)
    _deliberated: set[str] = field(default_factory=set)

    async def get_topic_priority(
        self,
        topic_id: str,
    ) -> TopicPriorityLevel:
        """Get priority level for a topic.

        Args:
            topic_id: Topic to query.

        Returns:
            Priority level (defaults to PETITION if not set).
        """
        return self._priorities.get(topic_id, TopicPriorityLevel.PETITION)

    async def set_topic_priority(
        self,
        topic_id: str,
        priority: TopicPriorityLevel,
    ) -> None:
        """Set priority level for a topic.

        Args:
            topic_id: Topic to set.
            priority: Priority level.
        """
        self._priorities[topic_id] = priority

        # Update queue if topic is in queue
        for queued in self._queue:
            if queued.topic_id == topic_id:
                # Remove and re-add with new priority
                self._queue.remove(queued)
                self._queue.append(
                    QueuedTopic(
                        topic_id=topic_id,
                        priority=priority,
                        queued_at=queued.queued_at,
                        source_id=queued.source_id,
                    )
                )
                break

    async def get_next_topic_for_deliberation(self) -> str | None:
        """Get next topic to deliberate based on priority.

        Returns:
            Topic ID or None if queue is empty.
        """
        if not self._queue:
            return None

        # Sort by priority (highest first), then by queue time (oldest first)
        # Priority ordering: CONSTITUTIONAL_EXAMINATION > AUTONOMOUS > SCHEDULED > PETITION
        priority_order = {
            TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION: 4,
            TopicPriorityLevel.AUTONOMOUS: 3,
            TopicPriorityLevel.SCHEDULED: 2,
            TopicPriorityLevel.PETITION: 1,
        }

        sorted_queue = sorted(
            self._queue,
            key=lambda t: (-priority_order[t.priority], t.queued_at),
        )

        # Return highest priority topic
        next_topic = sorted_queue[0]

        # Remove from queue and mark deliberated
        self._queue.remove(next_topic)
        self._deliberated.add(next_topic.topic_id)

        return next_topic.topic_id

    async def get_queued_topics_by_priority(
        self,
    ) -> dict[TopicPriorityLevel, list[str]]:
        """Get all queued topics grouped by priority level.

        Returns:
            Dictionary mapping priority levels to lists of topic IDs.
        """
        result: dict[TopicPriorityLevel, list[str]] = {
            TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION: [],
            TopicPriorityLevel.AUTONOMOUS: [],
            TopicPriorityLevel.SCHEDULED: [],
            TopicPriorityLevel.PETITION: [],
        }

        for queued in self._queue:
            result[queued.priority].append(queued.topic_id)

        return result

    async def ensure_autonomous_priority(self) -> None:
        """Ensure autonomous topics are always prioritized (FR119).

        This is a maintenance operation that ensures the priority
        queue is correctly ordered. No-op in stub since the queue
        is always sorted at retrieval time.

        FR119: External topics can NEVER starve autonomous topics.
        """
        # No-op - the stub already sorts by priority in get_next_topic_for_deliberation
        # This exists to match the protocol interface for queue maintenance
        pass

    # Test helper methods

    def add_to_queue(
        self,
        topic_id: str,
        priority: TopicPriorityLevel = TopicPriorityLevel.PETITION,
        source_id: str = "test-source",
        queued_at: datetime | None = None,
    ) -> None:
        """Add a topic to the queue.

        Args:
            topic_id: Topic to add.
            priority: Priority level.
            source_id: Source that submitted.
            queued_at: When queued (defaults to now).
        """
        self._priorities[topic_id] = priority
        self._queue.append(
            QueuedTopic(
                topic_id=topic_id,
                priority=priority,
                queued_at=queued_at or datetime.now(timezone.utc),
                source_id=source_id,
            )
        )

    def get_queue(self) -> list[QueuedTopic]:
        """Get current queue for verification.

        Returns:
            List of queued topics.
        """
        return list(self._queue)

    def get_queue_size(self) -> int:
        """Get number of topics in queue.

        Returns:
            Queue size.
        """
        return len(self._queue)

    def is_deliberated(self, topic_id: str) -> bool:
        """Check if topic has been deliberated.

        Args:
            topic_id: Topic to check.

        Returns:
            True if deliberated.
        """
        return topic_id in self._deliberated

    def clear(self) -> None:
        """Clear all stored data for test isolation."""
        self._priorities.clear()
        self._queue.clear()
        self._deliberated.clear()
