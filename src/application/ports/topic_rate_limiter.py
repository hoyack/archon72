"""TopicRateLimiterPort interface for rate limiting (FR71-72).

This module defines the port protocol for topic rate limiting
and queue management.

Constitutional Constraints:
- FR71: Rate limit rapid submissions (>10/hour from single source)
- FR72: Excess topics SHALL be queued, not rejected

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Rate limiting is explicit
- CT-13: Integrity outranks availability -> Topics queued, not dropped
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.topic_origin import TopicOrigin

# Constants per FR71
RATE_LIMIT_PER_HOUR: int = 10
RATE_LIMIT_WINDOW_SECONDS: int = 3600  # 1 hour


@runtime_checkable
class TopicRateLimiterPort(Protocol):
    """Port for topic rate limiting operations (FR71-72).

    Implementations must provide rate tracking per source and
    a queue for deferred topics.

    All methods are async to support non-blocking I/O.
    """

    async def check_rate_limit(self, source_id: str) -> bool:
        """Check if a source is within rate limit.

        Args:
            source_id: The source identifier.

        Returns:
            True if within limit (can submit), False if rate limited.
        """
        ...

    async def record_submission(self, source_id: str) -> int:
        """Record a topic submission from a source.

        Increments the submission count for rate limit tracking.

        Args:
            source_id: The source identifier.

        Returns:
            Current submission count for this hour.
        """
        ...

    async def get_queue_position(self, topic_id: UUID) -> int | None:
        """Get the queue position for a topic.

        Args:
            topic_id: The topic's unique identifier.

        Returns:
            Queue position (1-based), or None if not queued.
        """
        ...

    async def queue_topic(self, topic: TopicOrigin) -> int:
        """Queue a topic for later processing.

        Called when rate limit is exceeded (FR72 - queue, don't reject).

        Args:
            topic: The topic to queue.

        Returns:
            Queue position (1-based).
        """
        ...

    async def dequeue_topic(self) -> TopicOrigin | None:
        """Dequeue the next topic for processing.

        Returns:
            The next TopicOrigin in queue, or None if empty.
        """
        ...
