"""Topic priority port definition (Story 6.9, FR119).

Defines the abstract interface for topic priority operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR119: Autonomous constitutional self-examination topics SHALL have
         priority over external submissions (Topic Drowning defense)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class TopicPriorityLevel(str, Enum):
    """Priority levels for topic deliberation.

    FR119: Autonomous constitutional self-examination topics
    SHALL have priority over external submissions.

    Priority order (highest to lowest):
    1. CONSTITUTIONAL_EXAMINATION - system self-examination
    2. AUTONOMOUS - agent-initiated topics
    3. SCHEDULED - pre-scheduled topics
    4. PETITION - external submissions (lowest)

    This ordering prevents topic drowning attacks where external
    submissions could flood the queue and prevent autonomous
    constitutional self-examination.
    """

    CONSTITUTIONAL_EXAMINATION = "constitutional_examination"
    AUTONOMOUS = "autonomous"
    SCHEDULED = "scheduled"
    PETITION = "petition"


class TopicPriorityProtocol(ABC):
    """Abstract protocol for topic priority operations.

    All priority implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific priority implementations.

    Constitutional Constraints:
    - FR119: Autonomous topics have priority over external submissions
    - External topics can NEVER starve autonomous topics

    Priority enforcement happens at queue processing time, not submission.
    External topics are accepted and queued, but processed after
    autonomous/constitutional topics.

    Production implementations may include:
    - PriorityQueueManager: Priority queue implementation
    - DatabasePriorityManager: PostgreSQL-backed priority

    Development/Testing:
    - TopicPriorityStub: In-memory test double
    """

    @abstractmethod
    async def get_topic_priority(self, topic_id: str) -> TopicPriorityLevel:
        """Get priority level for a topic.

        Args:
            topic_id: The topic to check.

        Returns:
            Priority level for the topic.
        """
        ...

    @abstractmethod
    async def set_topic_priority(
        self,
        topic_id: str,
        priority: TopicPriorityLevel,
    ) -> None:
        """Set priority level for a topic.

        Args:
            topic_id: The topic to update.
            priority: New priority level.
        """
        ...

    @abstractmethod
    async def get_next_topic_for_deliberation(self) -> str | None:
        """Get highest priority topic not yet deliberated.

        FR119: Always returns autonomous/constitutional topics before
        external submissions to prevent topic drowning attack.

        Returns:
            Topic ID of highest priority topic, or None if queue empty.
        """
        ...

    @abstractmethod
    async def get_queued_topics_by_priority(
        self,
    ) -> dict[TopicPriorityLevel, list[str]]:
        """Get all queued topics grouped by priority level.

        Returns:
            Dictionary mapping priority levels to lists of topic IDs.
        """
        ...

    @abstractmethod
    async def ensure_autonomous_priority(self) -> None:
        """Enforce autonomous topics always have higher priority.

        This is a maintenance operation that ensures the priority
        queue is correctly ordered. Should be called periodically
        or after queue modifications.

        FR119: External topics can NEVER starve autonomous topics.
        """
        ...
