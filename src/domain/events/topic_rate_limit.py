"""TopicRateLimitPayload domain event for rate limiting (FR71-72).

This module defines the event payload created when topic rate
limiting is applied.

Constitutional Constraints:
- FR71: Rate limit rapid submissions (>10/hour from single source)
- FR72: Excess topics SHALL be queued, not rejected

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Rate limiting is logged
- CT-12: Witnessing creates accountability -> Event provides audit trail
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Event type constant for use in Event.event_type
TOPIC_RATE_LIMIT_EVENT_TYPE = "topic_rate_limit"


@dataclass(frozen=True)
class TopicRateLimitPayload:
    """Payload for topic rate limit events (FR71-72).

    Created when a source exceeds the topic submission rate limit.
    Per FR72, excess topics are queued rather than rejected.

    Attributes:
        source_id: The source that triggered rate limiting.
        topics_submitted: Total topics submitted this hour.
        limit: Maximum allowed topics per hour.
        queued_count: Number of topics that were queued.
        rate_limit_start: When rate limiting began.
        rate_limit_duration_seconds: Duration of rate limit window.

    Raises:
        ValueError: If source_id is empty.
    """

    source_id: str
    topics_submitted: int
    limit: int
    queued_count: int
    rate_limit_start: datetime
    rate_limit_duration_seconds: int

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError(
                "FR71: TopicRateLimitPayload validation failed - "
                "source_id must be non-empty string"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "source_id": self.source_id,
            "topics_submitted": self.topics_submitted,
            "limit": self.limit,
            "queued_count": self.queued_count,
            "rate_limit_start": self.rate_limit_start.isoformat(),
            "rate_limit_duration_seconds": self.rate_limit_duration_seconds,
        }
