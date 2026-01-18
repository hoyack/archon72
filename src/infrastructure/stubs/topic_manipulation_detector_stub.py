"""Topic manipulation detector stub (Story 6.9, FR118).

In-memory implementation for testing and development.

Constitutional Constraints:
- FR118: External topic rate limiting (10/day)
- CT-12: Witnessing creates accountability -> signable audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.application.ports.topic_manipulation_detector import (
    FlaggedTopic,
    ManipulationAnalysisResult,
    TimingPatternResult,
    TopicManipulationDetectorProtocol,
)
from src.domain.events.topic_manipulation import ManipulationPatternType


@dataclass
class TopicManipulationDetectorStub(TopicManipulationDetectorProtocol):
    """In-memory stub for topic manipulation detection.

    Stores analysis results and flagged topics for testing.
    Supports configurable responses for different test scenarios.

    FR118: External topic rate limiting to prevent manipulation.
    """

    # Storage for flagged topics
    _flagged_topics: dict[str, FlaggedTopic] = field(default_factory=dict)

    # Storage for analysis history
    _analysis_history: list[ManipulationAnalysisResult] = field(default_factory=list)

    # Configurable coordination scores for testing
    _coordination_scores: dict[tuple[str, ...], float] = field(default_factory=dict)

    # Configurable content similarity scores
    _content_similarity: dict[tuple[str, str], float] = field(default_factory=dict)

    # Configurable timing patterns
    _timing_patterns: dict[str, TimingPatternResult] = field(default_factory=dict)

    async def analyze_submissions(
        self,
        topic_ids: tuple[str, ...],
        window_hours: int = 24,
    ) -> ManipulationAnalysisResult:
        """Analyze submissions for manipulation patterns.

        Args:
            topic_ids: IDs of topics to analyze.
            window_hours: Time window for analysis.

        Returns:
            Analysis result with detected patterns and confidence.
        """
        # Check for pre-configured coordination score
        coordination_score = self._coordination_scores.get(topic_ids, 0.0)

        # Determine pattern type based on score
        pattern_type = None
        if coordination_score >= 0.8:
            pattern_type = ManipulationPatternType.COORDINATED_TIMING
        elif coordination_score >= 0.7:
            pattern_type = ManipulationPatternType.BURST_SUBMISSION

        manipulation_suspected = coordination_score >= 0.7

        result = ManipulationAnalysisResult(
            manipulation_suspected=manipulation_suspected,
            pattern_type=pattern_type,
            confidence_score=coordination_score,
            evidence_summary=f"Stub analysis with score {coordination_score}",
            topic_ids_affected=topic_ids if manipulation_suspected else (),
        )

        self._analysis_history.append(result)
        return result

    async def calculate_coordination_score(
        self,
        submission_ids: tuple[str, ...],
    ) -> float:
        """Calculate coordination score for submissions.

        Args:
            submission_ids: IDs of submissions to score.

        Returns:
            Coordination score between 0.0 and 1.0.
        """
        return self._coordination_scores.get(submission_ids, 0.0)

    async def get_content_similarity(
        self,
        topic_id_a: str,
        topic_id_b: str,
    ) -> float:
        """Get content similarity between two topics.

        Args:
            topic_id_a: First topic ID.
            topic_id_b: Second topic ID.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        # Check both orderings
        key1 = (topic_id_a, topic_id_b)
        key2 = (topic_id_b, topic_id_a)
        return self._content_similarity.get(
            key1, self._content_similarity.get(key2, 0.0)
        )

    async def get_timing_pattern(
        self,
        source_id: str,
        window_hours: int,
    ) -> TimingPatternResult:
        """Get timing pattern for a source.

        Args:
            source_id: Source to analyze.
            window_hours: Time window for analysis.

        Returns:
            Timing pattern analysis result.
        """
        if source_id in self._timing_patterns:
            return self._timing_patterns[source_id]

        return TimingPatternResult(
            is_burst=False,
            submissions_in_window=0,
            burst_threshold=10,
            window_hours=window_hours,
        )

    async def flag_for_review(
        self,
        topic_id: str,
        reason: str,
    ) -> None:
        """Flag a topic for human review.

        Args:
            topic_id: Topic to flag.
            reason: Reason for flagging.
        """
        flagged = FlaggedTopic(
            topic_id=topic_id,
            flag_reason=reason,
            flagged_at=datetime.now(timezone.utc),
            reviewed=False,
        )
        self._flagged_topics[topic_id] = flagged

    async def get_flagged_topics(
        self,
        limit: int = 100,
    ) -> list[FlaggedTopic]:
        """Get flagged topics.

        Args:
            limit: Maximum number of topics to return.

        Returns:
            List of flagged topics.
        """
        topics = list(self._flagged_topics.values())
        return topics[:limit]

    # Test helper methods

    def set_coordination_score(
        self,
        topic_ids: tuple[str, ...],
        score: float,
    ) -> None:
        """Set coordination score for testing.

        Args:
            topic_ids: Topic IDs to configure.
            score: Score to return.
        """
        self._coordination_scores[topic_ids] = score

    def set_content_similarity(
        self,
        topic_id_1: str,
        topic_id_2: str,
        similarity: float,
    ) -> None:
        """Set content similarity for testing.

        Args:
            topic_id_1: First topic ID.
            topic_id_2: Second topic ID.
            similarity: Similarity score.
        """
        self._content_similarity[(topic_id_1, topic_id_2)] = similarity

    def set_timing_pattern(
        self,
        source_id: str,
        pattern: TimingPatternResult,
    ) -> None:
        """Set timing pattern for testing.

        Args:
            source_id: Source ID.
            pattern: Pattern to return.
        """
        self._timing_patterns[source_id] = pattern

    def get_analysis_history(self) -> list[ManipulationAnalysisResult]:
        """Get analysis history for verification.

        Returns:
            List of all analyses performed.
        """
        return list(self._analysis_history)

    def mark_reviewed(
        self,
        topic_id: str,
    ) -> None:
        """Mark a flagged topic as reviewed.

        Args:
            topic_id: Topic to mark.
        """
        if topic_id in self._flagged_topics:
            old = self._flagged_topics[topic_id]
            self._flagged_topics[topic_id] = FlaggedTopic(
                topic_id=old.topic_id,
                flag_reason=old.flag_reason,
                flagged_at=old.flagged_at,
                reviewed=True,
            )

    def get_unreviewed_topics(self) -> list[FlaggedTopic]:
        """Get only unreviewed topics.

        Returns:
            List of unreviewed flagged topics.
        """
        return [t for t in self._flagged_topics.values() if not t.reviewed]

    def clear(self) -> None:
        """Clear all stored data for test isolation."""
        self._flagged_topics.clear()
        self._analysis_history.clear()
        self._coordination_scores.clear()
        self._content_similarity.clear()
        self._timing_patterns.clear()
