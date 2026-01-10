"""Topic daily rate limiter port definition (Story 6.9, FR118).

Defines the abstract interface for daily topic rate limiting operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR118: External topic sources (non-autonomous) SHALL be rate-limited
         to 10 topics/day per source

Note: This is separate from the hourly rate limiter in TopicRateLimiterPort.
Daily limits reject excess topics; hourly limits queue them (FR72).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

# FR118 specifies 10 topics/day per external source
DAILY_TOPIC_LIMIT = 10


class TopicDailyLimiterProtocol(ABC):
    """Abstract protocol for daily topic rate limiting operations.

    All daily limiter implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific rate limiting implementations.

    Constitutional Constraints:
    - FR118: 10 topics/day per external (non-autonomous) source
    - Excess topics are REJECTED (not queued like hourly limits)

    Key differences from hourly rate limiter (TopicRateLimiterPort):
    - Daily limits apply only to external sources (FR118)
    - Excess topics are rejected, not queued (unlike FR72)
    - Reset at midnight UTC

    Production implementations may include:
    - RedisDailyLimiter: Redis-backed rate limiting
    - DatabaseDailyLimiter: PostgreSQL-backed rate limiting

    Development/Testing:
    - TopicDailyLimiterStub: In-memory test double
    """

    @abstractmethod
    async def check_daily_limit(self, source_id: str) -> bool:
        """Check if source is within daily limit.

        Args:
            source_id: The source to check.

        Returns:
            True if within daily limit, False if exceeded.
        """
        ...

    @abstractmethod
    async def get_daily_count(self, source_id: str) -> int:
        """Get topics submitted today by source.

        Args:
            source_id: The source to check.

        Returns:
            Number of topics submitted today.
        """
        ...

    @abstractmethod
    async def record_daily_submission(self, source_id: str) -> int:
        """Record a topic submission and return new count.

        Args:
            source_id: The source making submission.

        Returns:
            New total count for today.
        """
        ...

    @abstractmethod
    async def get_daily_limit(self) -> int:
        """Get the current daily limit.

        Returns:
            Maximum topics per day per source (default 10 per FR118).
        """
        ...

    @abstractmethod
    async def get_limit_reset_time(self, source_id: str) -> datetime:
        """Get when the limit will reset for a source.

        Args:
            source_id: The source to check.

        Returns:
            Datetime when limit resets (midnight UTC).
        """
        ...

    @abstractmethod
    async def is_external_source(self, source_id: str) -> bool:
        """Check if source is external (non-autonomous).

        FR118 only applies to external sources.
        Autonomous and scheduled sources are not rate limited.

        Args:
            source_id: The source to check.

        Returns:
            True if external (rate limit applies), False otherwise.
        """
        ...
