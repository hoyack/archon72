"""Topic origin domain model for manipulation defense (FR15, FR71-73).

This module defines models for tracking topic origins to enable
diversity analysis and flooding defense.

Constitutional Constraints:
- FR15: Topic origins SHALL be tracked (autonomous, petition, scheduled)
- FR71: Topic flooding defense SHALL rate limit rapid submissions
- FR72: Excess topics SHALL be queued, not rejected
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Origin tracking is explicit
- CT-12: Witnessing creates accountability -> All topic origins attributed
- CT-13: Integrity outranks availability -> Topics queued, not dropped
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class TopicOriginType(str, Enum):
    """Types of topic origins (FR15).

    Topics can originate from three sources:
    - AUTONOMOUS: Agent-initiated topics (e.g., breach detection)
    - PETITION: Seeker petition topics (external submissions)
    - SCHEDULED: Pre-scheduled recurring topics (e.g., weekly conclave)
    """

    AUTONOMOUS = "autonomous"
    PETITION = "petition"
    SCHEDULED = "scheduled"


@dataclass(frozen=True)
class TopicOriginMetadata:
    """Metadata for topic origin tracking.

    Different origin types require different metadata fields:
    - PETITION requires petition_id
    - SCHEDULED requires schedule_ref
    - AUTONOMOUS may include autonomous_trigger

    Attributes:
        petition_id: UUID of petition (required for PETITION type).
        schedule_ref: Reference to schedule entry (required for SCHEDULED type).
        autonomous_trigger: Description of autonomous trigger (for AUTONOMOUS type).
        source_agent_id: ID of agent or system that created topic.
    """

    petition_id: UUID | None = None
    schedule_ref: str | None = None
    autonomous_trigger: str | None = None
    source_agent_id: str | None = None


@dataclass(frozen=True, eq=True)
class TopicOrigin:
    """Topic with tracked origin for manipulation defense (FR15, FR71-73).

    TopicOrigin is immutable and captures the full context of how a topic
    was introduced to the system. This enables diversity analysis and
    flooding defense.

    Attributes:
        topic_id: Unique identifier for the topic.
        origin_type: Classification of topic origin.
        origin_metadata: Details about the origin.
        created_at: Timestamp of topic creation.
        created_by: ID of creator (agent_id or system identifier).

    Raises:
        ValueError: If validation fails (missing required metadata, empty creator).
    """

    topic_id: UUID
    origin_type: TopicOriginType
    origin_metadata: TopicOriginMetadata
    created_at: datetime
    created_by: str

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        self._validate_created_by()
        self._validate_origin_metadata()

    def _validate_created_by(self) -> None:
        """Validate created_by is non-empty string."""
        if not isinstance(self.created_by, str) or not self.created_by.strip():
            raise ValueError(
                "FR15: TopicOrigin validation failed - created_by must be non-empty string"
            )

    def _validate_origin_metadata(self) -> None:
        """Validate origin_type matches required metadata fields."""
        if (
            self.origin_type == TopicOriginType.PETITION
            and self.origin_metadata.petition_id is None
        ):
            raise ValueError(
                "FR15: PETITION origin type requires petition_id in metadata"
            )

        if (
            self.origin_type == TopicOriginType.SCHEDULED
            and self.origin_metadata.schedule_ref is None
        ):
            raise ValueError(
                "FR15: SCHEDULED origin type requires schedule_ref in metadata"
            )
