"""TopicDiversityAlertPayload domain event for diversity violations (FR73).

This module defines the event payload created when topic diversity
threshold is violated.

Constitutional Constraints:
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Violations create alerts
- CT-12: Witnessing creates accountability -> Event provides audit trail
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.models.topic_origin import TopicOriginType

# Event type constant for use in Event.event_type
TOPIC_DIVERSITY_ALERT_EVENT_TYPE = "topic_diversity_alert"


@dataclass(frozen=True)
class TopicDiversityAlertPayload:
    """Payload for topic diversity alert events (FR73).

    Created when any single origin type exceeds the 30% threshold
    over a rolling 30-day window.

    Attributes:
        violation_type: The origin type that exceeded threshold.
        current_percentage: Current percentage of the violating type.
        threshold: Maximum allowed percentage (e.g., 0.30).
        window_start: Start of analysis window.
        window_end: End of analysis window.
        total_topics: Total topics in the window.

    Raises:
        ValueError: If validation fails (negative values, invalid percentages).
    """

    violation_type: TopicOriginType
    current_percentage: float
    threshold: float
    window_start: datetime
    window_end: datetime
    total_topics: int

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if self.total_topics < 1:
            raise ValueError(
                "FR73: TopicDiversityAlertPayload validation failed - "
                "total_topics must be at least 1 for a violation to occur"
            )
        if self.current_percentage < 0.0 or self.current_percentage > 1.0:
            raise ValueError(
                "FR73: TopicDiversityAlertPayload validation failed - "
                "current_percentage must be between 0.0 and 1.0"
            )
        if self.threshold < 0.0 or self.threshold > 1.0:
            raise ValueError(
                "FR73: TopicDiversityAlertPayload validation failed - "
                "threshold must be between 0.0 and 1.0"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "violation_type": self.violation_type.value,
            "current_percentage": self.current_percentage,
            "threshold": self.threshold,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "total_topics": self.total_topics,
        }
