"""TopicOriginTrackerPort interface for topic origin tracking (FR15, FR73).

This module defines the port protocol for tracking topic origins
and calculating diversity statistics.

Constitutional Constraints:
- FR15: Topic origins SHALL be tracked with metadata
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All topic origins tracked
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.topic_diversity import TopicDiversityStats
    from src.domain.models.topic_origin import TopicOrigin, TopicOriginType

# Constants per FR73
DIVERSITY_WINDOW_DAYS: int = 30
DIVERSITY_THRESHOLD: float = 0.30


@runtime_checkable
class TopicOriginTrackerPort(Protocol):
    """Port for topic origin tracking operations (FR15, FR73).

    Implementations must provide persistent storage for topic origins
    and support diversity statistics calculation.

    All methods are async to support non-blocking I/O.
    """

    async def record_topic_origin(self, topic: TopicOrigin) -> None:
        """Record a new topic origin.

        Args:
            topic: The topic origin to record.

        Raises:
            EventStoreError: If storage fails.
        """
        ...

    async def get_topic_origin(self, topic_id: UUID) -> TopicOrigin | None:
        """Retrieve a topic origin by ID.

        Args:
            topic_id: The topic's unique identifier.

        Returns:
            The TopicOrigin if found, None otherwise.
        """
        ...

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
        ...

    async def get_diversity_stats(
        self, window_days: int = DIVERSITY_WINDOW_DAYS
    ) -> TopicDiversityStats:
        """Calculate topic diversity statistics over a rolling window.

        Args:
            window_days: Number of days for rolling window (default 30).

        Returns:
            TopicDiversityStats with counts and percentages.
        """
        ...

    async def count_topics_from_source(self, source_id: str, since: datetime) -> int:
        """Count topics submitted by a specific source.

        Used for rate limiting (FR71).

        Args:
            source_id: The source identifier (e.g., agent_id, petition-system).
            since: Only count topics created after this time.

        Returns:
            Number of topics from this source in the time window.
        """
        ...
