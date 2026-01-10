"""TopicOriginTrackerStub - In-memory stub for topic origin tracking (FR15, FR73).

[DEV_MODE] This is a development stub per RT-1/ADR-4.
DO NOT use in production. Use a persistent implementation instead.

Constitutional Constraints:
- FR15: Topic origins SHALL be tracked with metadata
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID

import structlog

from src.application.ports.topic_origin_tracker import (
    DIVERSITY_WINDOW_DAYS,
)
from src.domain.models.topic_diversity import TopicDiversityStats
from src.domain.models.topic_origin import TopicOrigin, TopicOriginType

logger = structlog.get_logger()


class TopicOriginTrackerStub:
    """In-memory stub implementation of TopicOriginTrackerPort.

    [DEV_MODE] This stub stores topics in memory and is not
    suitable for production use. Use for development and testing only.

    Attributes:
        DEV_MODE: Indicates this is a development stub (RT-1/ADR-4).
    """

    DEV_MODE: bool = True

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._topics: dict[UUID, TopicOrigin] = {}
        logger.info(
            "topic_origin_tracker_stub_initialized",
            dev_mode=self.DEV_MODE,
            message="[DEV_MODE] In-memory topic origin tracker initialized",
        )

    async def record_topic_origin(self, topic: TopicOrigin) -> None:
        """Record a topic origin in memory.

        Args:
            topic: The topic origin to record.
        """
        self._topics[topic.topic_id] = topic
        logger.info(
            "topic_origin_recorded",
            topic_id=str(topic.topic_id),
            origin_type=topic.origin_type.value,
            created_by=topic.created_by,
            dev_mode=self.DEV_MODE,
        )

    async def get_topic_origin(self, topic_id: UUID) -> TopicOrigin | None:
        """Retrieve a topic origin by ID.

        Args:
            topic_id: The topic's unique identifier.

        Returns:
            The TopicOrigin if found, None otherwise.
        """
        return self._topics.get(topic_id)

    async def get_topics_by_origin_type(
        self, origin_type: TopicOriginType, since: datetime
    ) -> list[TopicOrigin]:
        """Get all topics of a specific origin type since a given time.

        Args:
            origin_type: The type of origin to filter by.
            since: Only include topics created after this time.

        Returns:
            List of matching TopicOrigin objects.
        """
        return [
            topic
            for topic in self._topics.values()
            if topic.origin_type == origin_type and topic.created_at >= since
        ]

    async def get_diversity_stats(
        self, window_days: int = DIVERSITY_WINDOW_DAYS
    ) -> TopicDiversityStats:
        """Calculate topic diversity statistics over a rolling window.

        Args:
            window_days: Number of days for rolling window (default 30).

        Returns:
            TopicDiversityStats with counts and percentages.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=window_days)

        # Filter topics within window
        topics_in_window = [
            t for t in self._topics.values() if t.created_at >= window_start
        ]

        # Count by type
        autonomous_count = sum(
            1 for t in topics_in_window if t.origin_type == TopicOriginType.AUTONOMOUS
        )
        petition_count = sum(
            1 for t in topics_in_window if t.origin_type == TopicOriginType.PETITION
        )
        scheduled_count = sum(
            1 for t in topics_in_window if t.origin_type == TopicOriginType.SCHEDULED
        )

        stats = TopicDiversityStats(
            window_start=window_start,
            window_end=now,
            total_topics=len(topics_in_window),
            autonomous_count=autonomous_count,
            petition_count=petition_count,
            scheduled_count=scheduled_count,
        )

        logger.debug(
            "diversity_stats_calculated",
            window_days=window_days,
            total_topics=stats.total_topics,
            autonomous_pct=stats.autonomous_pct,
            petition_pct=stats.petition_pct,
            scheduled_pct=stats.scheduled_pct,
            dev_mode=self.DEV_MODE,
        )

        return stats

    async def count_topics_from_source(self, source_id: str, since: datetime) -> int:
        """Count topics submitted by a specific source.

        Args:
            source_id: The source identifier.
            since: Only count topics created after this time.

        Returns:
            Number of topics from this source in the time window.
        """
        return sum(
            1
            for t in self._topics.values()
            if t.created_by == source_id and t.created_at >= since
        )
