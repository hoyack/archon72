"""Topic manipulation detector port definition (Story 6.9, FR118).

Defines the abstract interface for topic manipulation detection operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR118: Detect coordinated manipulation patterns
- CT-12: Witnessing creates accountability -> All detections logged
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.domain.events.topic_manipulation import ManipulationPatternType


@dataclass(frozen=True)
class ManipulationAnalysisResult:
    """Result of analyzing topic submissions for manipulation patterns.

    Attributes:
        manipulation_suspected: Whether manipulation was detected.
        pattern_type: Type of pattern detected (if any).
        confidence_score: Confidence level (0.0 to 1.0).
        evidence_summary: Human-readable description of evidence.
        topic_ids_affected: Topic IDs involved in the pattern.
    """

    manipulation_suspected: bool
    pattern_type: Optional[ManipulationPatternType]
    confidence_score: float
    evidence_summary: str
    topic_ids_affected: tuple[str, ...]


@dataclass(frozen=True)
class TimingPatternResult:
    """Result of analyzing submission timing for burst detection.

    Attributes:
        is_burst: Whether a burst pattern was detected.
        submissions_in_window: Number of submissions in window.
        burst_threshold: Threshold for burst detection.
        window_hours: Analysis window in hours.
    """

    is_burst: bool
    submissions_in_window: int
    burst_threshold: int
    window_hours: int


@dataclass(frozen=True)
class FlaggedTopic:
    """A topic flagged for human review.

    Attributes:
        topic_id: The flagged topic ID.
        flag_reason: Why the topic was flagged.
        flagged_at: When the topic was flagged.
        reviewed: Whether the topic has been reviewed.
    """

    topic_id: str
    flag_reason: str
    flagged_at: datetime
    reviewed: bool


class TopicManipulationDetectorProtocol(ABC):
    """Abstract protocol for topic manipulation detection operations.

    All detector implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific detection implementations.

    Constitutional Constraints:
    - FR118: Detect coordinated manipulation patterns
    - CT-12: All detections create audit trail

    Production implementations may include:
    - StatisticalDetector: Statistical pattern analysis
    - MLDetector: Machine learning-based detection

    Development/Testing:
    - TopicManipulationDetectorStub: Configurable test double
    """

    @abstractmethod
    async def analyze_submissions(
        self,
        topic_ids: tuple[str, ...],
        window_hours: int = 24,
    ) -> ManipulationAnalysisResult:
        """Analyze topic submissions for manipulation patterns.

        Examines the specified topics within a time window to detect
        coordinated manipulation patterns.

        Args:
            topic_ids: Topic IDs to analyze.
            window_hours: Analysis window in hours (default 24).

        Returns:
            ManipulationAnalysisResult with detection findings.
        """
        ...

    @abstractmethod
    async def calculate_coordination_score(
        self,
        submission_ids: tuple[str, ...],
    ) -> float:
        """Calculate coordination score for submissions.

        Analyzes submissions for coordination signals:
        - Timing correlations (submissions within 5-minute window)
        - Content similarity (>70% similarity threshold)
        - Source patterns (same IP range, session patterns)

        Score > 0.7 triggers coordination investigation.

        Args:
            submission_ids: Submission IDs to analyze.

        Returns:
            Coordination score from 0.0 to 1.0.
        """
        ...

    @abstractmethod
    async def get_content_similarity(
        self,
        topic_id_a: str,
        topic_id_b: str,
    ) -> float:
        """Calculate content similarity between two topics.

        Uses TF-IDF or hash comparison to determine similarity.

        Args:
            topic_id_a: First topic ID.
            topic_id_b: Second topic ID.

        Returns:
            Similarity score from 0.0 to 1.0.
        """
        ...

    @abstractmethod
    async def get_timing_pattern(
        self,
        source_id: str,
        window_hours: int,
    ) -> TimingPatternResult:
        """Analyze submission timing for burst detection.

        Args:
            source_id: Source to analyze.
            window_hours: Analysis window in hours.

        Returns:
            TimingPatternResult with burst analysis.
        """
        ...

    @abstractmethod
    async def flag_for_review(
        self,
        topic_id: str,
        reason: str,
    ) -> None:
        """Flag a topic for human review.

        Flags are advisory - topics are not automatically rejected.

        Args:
            topic_id: Topic to flag.
            reason: Reason for flagging.
        """
        ...

    @abstractmethod
    async def get_flagged_topics(
        self,
        limit: int = 100,
    ) -> list[FlaggedTopic]:
        """Get topics flagged for review.

        Args:
            limit: Maximum number of topics to return.

        Returns:
            List of flagged topics.
        """
        ...
