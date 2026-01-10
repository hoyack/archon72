"""TopicRateLimiterStub - In-memory stub for topic rate limiting (FR71-72).

[DEV_MODE] This is a development stub per RT-1/ADR-4.
DO NOT use in production. Use a persistent implementation instead.

Constitutional Constraints:
- FR71: Rate limit rapid submissions (>10/hour from single source)
- FR72: Excess topics SHALL be queued, not rejected
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone, timedelta
from uuid import UUID

import structlog

from src.application.ports.topic_rate_limiter import (
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_WINDOW_SECONDS,
)
from src.domain.models.topic_origin import TopicOrigin

logger = structlog.get_logger()


class TopicRateLimiterStub:
    """In-memory stub implementation of TopicRateLimiterPort.

    [DEV_MODE] This stub stores rate tracking and queued topics in memory.
    Not suitable for production use. Use for development and testing only.

    Attributes:
        DEV_MODE: Indicates this is a development stub (RT-1/ADR-4).
    """

    DEV_MODE: bool = True

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        # Track submissions: source_id -> list of submission timestamps
        self._submissions: dict[str, list[datetime]] = {}
        # Queue of deferred topics (FIFO)
        self._queue: deque[TopicOrigin] = deque()
        # Track topic_id -> queue position for lookups
        self._queue_positions: dict[UUID, int] = {}
        self._next_position: int = 1

        logger.info(
            "topic_rate_limiter_stub_initialized",
            dev_mode=self.DEV_MODE,
            message="[DEV_MODE] In-memory topic rate limiter initialized",
        )

    def _clean_old_submissions(self, source_id: str) -> None:
        """Remove submissions older than the rate limit window.

        Args:
            source_id: The source to clean.
        """
        if source_id not in self._submissions:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        self._submissions[source_id] = [
            ts for ts in self._submissions[source_id] if ts >= cutoff
        ]

    async def check_rate_limit(self, source_id: str) -> bool:
        """Check if a source is within rate limit.

        Args:
            source_id: The source identifier.

        Returns:
            True if within limit (can submit), False if rate limited.
        """
        self._clean_old_submissions(source_id)
        current_count = len(self._submissions.get(source_id, []))
        return current_count < RATE_LIMIT_PER_HOUR

    async def record_submission(self, source_id: str) -> int:
        """Record a topic submission from a source.

        Args:
            source_id: The source identifier.

        Returns:
            Current submission count for this hour.
        """
        self._clean_old_submissions(source_id)

        if source_id not in self._submissions:
            self._submissions[source_id] = []

        now = datetime.now(timezone.utc)
        self._submissions[source_id].append(now)

        count = len(self._submissions[source_id])
        logger.debug(
            "submission_recorded",
            source_id=source_id,
            current_count=count,
            limit=RATE_LIMIT_PER_HOUR,
            dev_mode=self.DEV_MODE,
        )

        return count

    async def get_queue_position(self, topic_id: UUID) -> int | None:
        """Get the queue position for a topic.

        Args:
            topic_id: The topic's unique identifier.

        Returns:
            Queue position (1-based), or None if not queued.
        """
        return self._queue_positions.get(topic_id)

    async def queue_topic(self, topic: TopicOrigin) -> int:
        """Queue a topic for later processing.

        Per FR72, excess topics are queued rather than rejected.

        Args:
            topic: The topic to queue.

        Returns:
            Queue position (1-based).
        """
        self._queue.append(topic)
        position = self._next_position
        self._queue_positions[topic.topic_id] = position
        self._next_position += 1

        logger.info(
            "topic_queued",
            topic_id=str(topic.topic_id),
            queue_position=position,
            created_by=topic.created_by,
            dev_mode=self.DEV_MODE,
        )

        return position

    async def dequeue_topic(self) -> TopicOrigin | None:
        """Dequeue the next topic for processing.

        Returns:
            The next TopicOrigin in queue, or None if empty.
        """
        if not self._queue:
            return None

        topic = self._queue.popleft()
        if topic.topic_id in self._queue_positions:
            del self._queue_positions[topic.topic_id]

        logger.info(
            "topic_dequeued",
            topic_id=str(topic.topic_id),
            remaining_queue_size=len(self._queue),
            dev_mode=self.DEV_MODE,
        )

        return topic

    # Test utility methods (not part of port interface)

    async def reset_submissions(self, source_id: str) -> None:
        """Reset submission count for a source (test utility).

        This method is NOT part of the TopicRateLimiterPort interface.
        It is provided for testing to simulate time passage/window reset.

        Args:
            source_id: The source to reset.
        """
        if source_id in self._submissions:
            del self._submissions[source_id]
            logger.debug(
                "submissions_reset",
                source_id=source_id,
                dev_mode=self.DEV_MODE,
            )
