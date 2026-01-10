"""Topic diversity statistics for rolling window analysis (FR73).

This module defines the TopicDiversityStats model for analyzing topic
origin distribution over a rolling time window.

Constitutional Constraints:
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Violations are explicitly detected
- CT-12: Witnessing creates accountability -> Stats enable auditing
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.topic_origin import TopicOriginType


@dataclass(frozen=True)
class TopicDiversityStats:
    """Statistics for topic diversity over a rolling window (FR73).

    Used to analyze the distribution of topic origins and detect
    when any single origin type exceeds the diversity threshold.

    Attributes:
        window_start: Start of analysis window.
        window_end: End of analysis window.
        total_topics: Total topics in window.
        autonomous_count: Count of AUTONOMOUS topics.
        petition_count: Count of PETITION topics.
        scheduled_count: Count of SCHEDULED topics.

    Raises:
        ValueError: If any count is negative or total_topics is negative.
    """

    window_start: datetime
    window_end: datetime
    total_topics: int
    autonomous_count: int
    petition_count: int
    scheduled_count: int

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if self.total_topics < 0:
            raise ValueError(
                "FR73: TopicDiversityStats validation failed - "
                "total_topics cannot be negative"
            )
        if self.autonomous_count < 0:
            raise ValueError(
                "FR73: TopicDiversityStats validation failed - "
                "autonomous_count cannot be negative"
            )
        if self.petition_count < 0:
            raise ValueError(
                "FR73: TopicDiversityStats validation failed - "
                "petition_count cannot be negative"
            )
        if self.scheduled_count < 0:
            raise ValueError(
                "FR73: TopicDiversityStats validation failed - "
                "scheduled_count cannot be negative"
            )

    @property
    def autonomous_pct(self) -> float:
        """Calculate percentage of AUTONOMOUS topics.

        Returns:
            Percentage as decimal (0.0-1.0), or 0.0 if no topics.
        """
        if self.total_topics == 0:
            return 0.0
        return self.autonomous_count / self.total_topics

    @property
    def petition_pct(self) -> float:
        """Calculate percentage of PETITION topics.

        Returns:
            Percentage as decimal (0.0-1.0), or 0.0 if no topics.
        """
        if self.total_topics == 0:
            return 0.0
        return self.petition_count / self.total_topics

    @property
    def scheduled_pct(self) -> float:
        """Calculate percentage of SCHEDULED topics.

        Returns:
            Percentage as decimal (0.0-1.0), or 0.0 if no topics.
        """
        if self.total_topics == 0:
            return 0.0
        return self.scheduled_count / self.total_topics

    def exceeds_threshold(self, threshold: float = 0.30) -> TopicOriginType | None:
        """Check if any origin type exceeds diversity threshold.

        Per FR73, no single origin type should exceed 30% of total topics
        over a rolling 30-day window. Only values STRICTLY GREATER THAN
        the threshold are violations (exactly at threshold is acceptable).

        Args:
            threshold: Maximum allowed percentage (default 0.30 = 30%).

        Returns:
            The first TopicOriginType exceeding threshold, or None if compliant.
        """
        # Import here to avoid circular import
        from src.domain.models.topic_origin import TopicOriginType

        if self.autonomous_pct > threshold:
            return TopicOriginType.AUTONOMOUS
        if self.petition_pct > threshold:
            return TopicOriginType.PETITION
        if self.scheduled_pct > threshold:
            return TopicOriginType.SCHEDULED
        return None
