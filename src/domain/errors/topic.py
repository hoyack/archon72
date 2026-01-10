"""Topic-related error classes for manipulation defense (FR15, FR71-73).

This module defines error classes for topic diversity violations
and rate limiting.

Constitutional Constraints:
- FR71: Topic flooding defense rate limits
- FR73: Topic diversity enforcement (30% threshold)
"""

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.exceptions import ConclaveError
from src.domain.models.topic_origin import TopicOriginType


class TopicDiversityViolationError(ConstitutionalViolationError):
    """Raised when topic diversity threshold is violated (FR73).

    This is a constitutional violation because diversity enforcement
    is a fundamental protection against topic manipulation.

    Attributes:
        origin_type: The origin type that exceeded threshold.
        current_percentage: Current percentage of this origin type.
        threshold: Maximum allowed percentage (default 0.30).
    """

    def __init__(
        self,
        origin_type: TopicOriginType,
        current_percentage: float,
        threshold: float = 0.30,
    ) -> None:
        """Initialize the error.

        Args:
            origin_type: The origin type that exceeded threshold.
            current_percentage: Current percentage of this origin type.
            threshold: Maximum allowed percentage (default 0.30).
        """
        self.origin_type = origin_type
        self.current_percentage = current_percentage
        self.threshold = threshold

        pct_display = int(current_percentage * 100)
        threshold_display = int(threshold * 100)
        message = (
            f"FR73: Topic diversity violation - {origin_type.value.upper()} "
            f"at {pct_display}% exceeds {threshold_display}% threshold"
        )
        super().__init__(message)


class TopicRateLimitError(ConclaveError):
    """Raised when topic submission rate limit is exceeded (FR71).

    This is NOT a constitutional violation - it's an operational limit.
    Excess topics are queued, not rejected (per FR72).

    Attributes:
        source_id: The source that exceeded rate limit.
        topics_per_hour: Number of topics submitted this hour.
        limit: Maximum allowed topics per hour (default 10).
    """

    def __init__(
        self,
        source_id: str,
        topics_per_hour: int,
        limit: int = 10,
    ) -> None:
        """Initialize the error.

        Args:
            source_id: The source that exceeded rate limit.
            topics_per_hour: Number of topics submitted this hour.
            limit: Maximum allowed topics per hour (default 10).
        """
        self.source_id = source_id
        self.topics_per_hour = topics_per_hour
        self.limit = limit

        message = (
            f"FR71: Topic rate limit exceeded - {source_id} "
            f"submitted {topics_per_hour} topics/hour (limit: {limit})"
        )
        super().__init__(message)
