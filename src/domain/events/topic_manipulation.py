"""Topic manipulation domain events (Story 6.9, FR118-FR119).

This module defines event payloads for topic manipulation detection,
coordinated submission detection, and daily rate limiting.

Constitutional Constraints:
- FR118: External topic sources (non-autonomous) SHALL be rate-limited
         to 10 topics/day per source
- FR119: Autonomous topics have priority over external submissions

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Events surface manipulation
- CT-12: Witnessing creates accountability -> signable_content() for audit
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# Event type constants for use in Event.event_type
TOPIC_MANIPULATION_SUSPECTED_EVENT_TYPE = "topic.manipulation_suspected"
COORDINATED_SUBMISSION_SUSPECTED_EVENT_TYPE = "topic.coordinated_submission_suspected"
TOPIC_RATE_LIMIT_DAILY_EVENT_TYPE = "topic.rate_limit_daily"


class ManipulationPatternType(str, Enum):
    """Types of manipulation patterns that can be detected.

    Used to categorize suspected manipulation for review and logging.
    """

    COORDINATED_TIMING = "coordinated_timing"
    CONTENT_SIMILARITY = "content_similarity"
    SOURCE_COLLUSION = "source_collusion"
    BURST_SUBMISSION = "burst_submission"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TopicManipulationSuspectedEventPayload:
    """Payload for suspected topic manipulation events (FR118).

    Created when the system detects patterns that suggest coordinated
    manipulation of the topic submission process. This is advisory -
    topics are flagged for review, not automatically rejected.

    Attributes:
        detection_id: Unique identifier for this detection.
        suspected_topics: Tuple of topic IDs flagged for review.
        pattern_type: Type of manipulation pattern detected.
        confidence_score: Confidence level (0.0 to 1.0).
        evidence_summary: Human-readable description of evidence.
        detected_at: When the detection occurred.
        detection_window_hours: Analysis window used.

    Raises:
        ValueError: If detection_id is empty or confidence_score invalid.
    """

    detection_id: str
    suspected_topics: tuple[str, ...]
    pattern_type: ManipulationPatternType
    confidence_score: float
    evidence_summary: str
    detected_at: datetime
    detection_window_hours: int

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(self.detection_id, str) or not self.detection_id.strip():
            raise ValueError(
                "FR118: TopicManipulationSuspectedEventPayload validation failed - "
                "detection_id must be non-empty string"
            )
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(
                "FR118: TopicManipulationSuspectedEventPayload validation failed - "
                "confidence_score must be between 0.0 and 1.0"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "detection_id": self.detection_id,
            "suspected_topics": list(self.suspected_topics),
            "pattern_type": self.pattern_type.value,
            "confidence_score": self.confidence_score,
            "evidence_summary": self.evidence_summary,
            "detected_at": self.detected_at.isoformat(),
            "detection_window_hours": self.detection_window_hours,
        }

    def signable_content(self) -> bytes:
        """Get deterministic bytes for signing (CT-12).

        Returns canonical JSON encoding for cryptographic signing,
        ensuring witnessing creates accountability.

        Returns:
            Deterministic bytes representation for signing.
        """
        canonical = {
            "detection_id": self.detection_id,
            "suspected_topics": list(self.suspected_topics),
            "pattern_type": self.pattern_type.value,
            "confidence_score": self.confidence_score,
            "evidence_summary": self.evidence_summary,
            "detected_at": self.detected_at.isoformat(),
            "detection_window_hours": self.detection_window_hours,
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )


@dataclass(frozen=True)
class CoordinatedSubmissionSuspectedEventPayload:
    """Payload for coordinated submission suspicion events.

    Created when multiple submissions exhibit coordination signals
    that exceed the threshold (score > 0.7).

    Attributes:
        detection_id: Unique identifier for this detection.
        submission_ids: Tuple of related submission IDs.
        coordination_score: Calculated coordination score (0.0 to 1.0).
        coordination_signals: Detected coordination signals.
        source_ids: Sources involved in coordination.
        detected_at: When the detection occurred.

    Raises:
        ValueError: If detection_id is empty.
    """

    detection_id: str
    submission_ids: tuple[str, ...]
    coordination_score: float
    coordination_signals: tuple[str, ...]
    source_ids: tuple[str, ...]
    detected_at: datetime

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(self.detection_id, str) or not self.detection_id.strip():
            raise ValueError(
                "CoordinatedSubmissionSuspectedEventPayload validation failed - "
                "detection_id must be non-empty string"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "detection_id": self.detection_id,
            "submission_ids": list(self.submission_ids),
            "coordination_score": self.coordination_score,
            "coordination_signals": list(self.coordination_signals),
            "source_ids": list(self.source_ids),
            "detected_at": self.detected_at.isoformat(),
        }

    def signable_content(self) -> bytes:
        """Get deterministic bytes for signing (CT-12).

        Returns:
            Deterministic bytes representation for signing.
        """
        canonical = {
            "detection_id": self.detection_id,
            "submission_ids": list(self.submission_ids),
            "coordination_score": self.coordination_score,
            "coordination_signals": list(self.coordination_signals),
            "source_ids": list(self.source_ids),
            "detected_at": self.detected_at.isoformat(),
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )


@dataclass(frozen=True)
class TopicRateLimitDailyEventPayload:
    """Payload for daily topic rate limit events (FR118).

    Created when an external source exceeds the daily topic limit
    of 10 topics per source. Unlike hourly rate limiting, excess
    topics are rejected (not queued).

    FR118: External topic sources (non-autonomous) SHALL be rate-limited
           to 10 topics/day per source.

    Attributes:
        source_id: The source that hit the limit.
        topics_today: Total topics submitted today.
        daily_limit: Maximum allowed per day (default 10).
        rejected_topic_ids: IDs of topics that were rejected.
        limit_start: When the limit period started.
        limit_reset_at: When the limit will reset.

    Raises:
        ValueError: If source_id is empty.
    """

    source_id: str
    topics_today: int
    daily_limit: int
    rejected_topic_ids: tuple[str, ...]
    limit_start: datetime
    limit_reset_at: datetime

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError(
                "FR118: TopicRateLimitDailyEventPayload validation failed - "
                "source_id must be non-empty string"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "source_id": self.source_id,
            "topics_today": self.topics_today,
            "daily_limit": self.daily_limit,
            "rejected_topic_ids": list(self.rejected_topic_ids),
            "limit_start": self.limit_start.isoformat(),
            "limit_reset_at": self.limit_reset_at.isoformat(),
        }

    def signable_content(self) -> bytes:
        """Get deterministic bytes for signing (CT-12).

        Returns:
            Deterministic bytes representation for signing.
        """
        canonical = {
            "source_id": self.source_id,
            "topics_today": self.topics_today,
            "daily_limit": self.daily_limit,
            "rejected_topic_ids": list(self.rejected_topic_ids),
            "limit_start": self.limit_start.isoformat(),
            "limit_reset_at": self.limit_reset_at.isoformat(),
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
