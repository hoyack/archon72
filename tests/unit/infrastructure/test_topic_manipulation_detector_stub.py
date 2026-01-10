"""Unit tests for TopicManipulationDetectorStub (Story 6.9, FR118).

Tests the in-memory implementation of manipulation detection.

Constitutional Constraints:
- FR118: External topic rate limiting (10/day)
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone

import pytest

from src.application.ports.topic_manipulation_detector import (
    FlaggedTopic,
    ManipulationAnalysisResult,
    TimingPatternResult,
    TopicManipulationDetectorProtocol,
)
from src.domain.events.topic_manipulation import ManipulationPatternType
from src.infrastructure.stubs.topic_manipulation_detector_stub import (
    TopicManipulationDetectorStub,
)


class TestTopicManipulationDetectorStubImplementsProtocol:
    """Test stub implements protocol correctly."""

    def test_implements_protocol(self) -> None:
        """Test stub inherits from protocol."""
        stub = TopicManipulationDetectorStub()
        assert isinstance(stub, TopicManipulationDetectorProtocol)


class TestAnalyzeSubmissions:
    """Tests for analyze_submissions method."""

    @pytest.mark.asyncio
    async def test_returns_analysis_result(self) -> None:
        """Test analyze_submissions returns ManipulationAnalysisResult."""
        stub = TopicManipulationDetectorStub()
        result = await stub.analyze_submissions(
            topic_ids=("topic-1", "topic-2"),
            window_hours=24,
        )
        assert isinstance(result, ManipulationAnalysisResult)

    @pytest.mark.asyncio
    async def test_default_coordination_score_zero(self) -> None:
        """Test default coordination score is zero."""
        stub = TopicManipulationDetectorStub()
        result = await stub.analyze_submissions(
            topic_ids=("topic-1",),
            window_hours=24,
        )
        assert result.confidence_score == 0.0
        assert result.manipulation_suspected is False

    @pytest.mark.asyncio
    async def test_configurable_coordination_score(self) -> None:
        """Test coordination score can be configured."""
        stub = TopicManipulationDetectorStub()
        stub.set_coordination_score(("topic-1", "topic-2"), 0.85)

        result = await stub.analyze_submissions(
            topic_ids=("topic-1", "topic-2"),
            window_hours=24,
        )
        assert result.confidence_score == 0.85
        assert result.manipulation_suspected is True
        assert result.pattern_type == ManipulationPatternType.COORDINATED_TIMING

    @pytest.mark.asyncio
    async def test_high_score_detects_burst_pattern(self) -> None:
        """Test high score includes burst pattern."""
        stub = TopicManipulationDetectorStub()
        stub.set_coordination_score(("topic-1",), 0.72)

        result = await stub.analyze_submissions(
            topic_ids=("topic-1",),
            window_hours=24,
        )
        assert result.manipulation_suspected is True
        assert result.pattern_type == ManipulationPatternType.BURST_SUBMISSION

    @pytest.mark.asyncio
    async def test_analysis_history_recorded(self) -> None:
        """Test analysis is recorded in history."""
        stub = TopicManipulationDetectorStub()
        await stub.analyze_submissions(("topic-1",), 24)
        await stub.analyze_submissions(("topic-2",), 12)

        history = stub.get_analysis_history()
        assert len(history) == 2


class TestCalculateCoordinationScore:
    """Tests for calculate_coordination_score method."""

    @pytest.mark.asyncio
    async def test_default_returns_zero(self) -> None:
        """Test default score is zero."""
        stub = TopicManipulationDetectorStub()
        score = await stub.calculate_coordination_score(("sub-1", "sub-2"))
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_configured_score_returned(self) -> None:
        """Test configured score is returned."""
        stub = TopicManipulationDetectorStub()
        stub.set_coordination_score(("sub-1", "sub-2"), 0.92)

        score = await stub.calculate_coordination_score(("sub-1", "sub-2"))
        assert score == 0.92


class TestGetContentSimilarity:
    """Tests for get_content_similarity method."""

    @pytest.mark.asyncio
    async def test_default_returns_zero(self) -> None:
        """Test default similarity is zero."""
        stub = TopicManipulationDetectorStub()
        similarity = await stub.get_content_similarity("topic-1", "topic-2")
        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_configured_similarity_returned(self) -> None:
        """Test configured similarity is returned."""
        stub = TopicManipulationDetectorStub()
        stub.set_content_similarity("topic-1", "topic-2", 0.75)

        similarity = await stub.get_content_similarity("topic-1", "topic-2")
        assert similarity == 0.75

    @pytest.mark.asyncio
    async def test_similarity_symmetric(self) -> None:
        """Test similarity works in either direction."""
        stub = TopicManipulationDetectorStub()
        stub.set_content_similarity("topic-1", "topic-2", 0.8)

        # Should work in both directions
        assert await stub.get_content_similarity("topic-1", "topic-2") == 0.8
        assert await stub.get_content_similarity("topic-2", "topic-1") == 0.8


class TestGetTimingPattern:
    """Tests for get_timing_pattern method."""

    @pytest.mark.asyncio
    async def test_default_returns_empty_pattern(self) -> None:
        """Test default pattern has no burst."""
        stub = TopicManipulationDetectorStub()
        pattern = await stub.get_timing_pattern("source-1", 24)

        assert isinstance(pattern, TimingPatternResult)
        assert pattern.is_burst is False
        assert pattern.submissions_in_window == 0

    @pytest.mark.asyncio
    async def test_configured_pattern_returned(self) -> None:
        """Test configured pattern is returned."""
        stub = TopicManipulationDetectorStub()
        configured_pattern = TimingPatternResult(
            is_burst=True,
            submissions_in_window=15,
            burst_threshold=10,
            window_hours=24,
        )
        stub.set_timing_pattern("source-1", configured_pattern)

        pattern = await stub.get_timing_pattern("source-1", 24)
        assert pattern.is_burst is True
        assert pattern.submissions_in_window == 15


class TestFlagForReview:
    """Tests for flag_for_review method."""

    @pytest.mark.asyncio
    async def test_creates_flagged_topic(self) -> None:
        """Test flagging creates a FlaggedTopic."""
        stub = TopicManipulationDetectorStub()
        await stub.flag_for_review(
            topic_id="topic-123",
            reason="Suspicious pattern",
        )

        flagged = await stub.get_flagged_topics()
        assert len(flagged) == 1
        assert flagged[0].topic_id == "topic-123"
        assert flagged[0].flag_reason == "Suspicious pattern"
        assert flagged[0].reviewed is False

    @pytest.mark.asyncio
    async def test_flagged_topic_retrievable(self) -> None:
        """Test flagged topics can be retrieved."""
        stub = TopicManipulationDetectorStub()
        await stub.flag_for_review("topic-1", "reason 1")
        await stub.flag_for_review("topic-2", "reason 2")

        flagged = await stub.get_flagged_topics()
        assert len(flagged) == 2
        assert any(t.topic_id == "topic-1" for t in flagged)
        assert any(t.topic_id == "topic-2" for t in flagged)


class TestGetFlaggedTopics:
    """Tests for get_flagged_topics method."""

    @pytest.mark.asyncio
    async def test_empty_when_none_flagged(self) -> None:
        """Test returns empty when no topics flagged."""
        stub = TopicManipulationDetectorStub()
        flagged = await stub.get_flagged_topics()
        assert len(flagged) == 0

    @pytest.mark.asyncio
    async def test_respects_limit(self) -> None:
        """Test respects limit parameter."""
        stub = TopicManipulationDetectorStub()
        for i in range(10):
            await stub.flag_for_review(f"topic-{i}", "reason")

        flagged = await stub.get_flagged_topics(limit=5)
        assert len(flagged) == 5

    @pytest.mark.asyncio
    async def test_includes_reviewed_topics(self) -> None:
        """Test includes reviewed topics."""
        stub = TopicManipulationDetectorStub()
        await stub.flag_for_review("topic-1", "reason")
        stub.mark_reviewed("topic-1")

        flagged = await stub.get_flagged_topics()
        assert len(flagged) == 1
        assert flagged[0].reviewed is True


class TestTestHelpers:
    """Tests for test helper methods."""

    @pytest.mark.asyncio
    async def test_mark_reviewed(self) -> None:
        """Test mark_reviewed updates reviewed status."""
        stub = TopicManipulationDetectorStub()
        await stub.flag_for_review("topic-1", "reason")
        stub.mark_reviewed("topic-1")

        topics = await stub.get_flagged_topics()
        assert topics[0].reviewed is True

    def test_get_unreviewed_topics(self) -> None:
        """Test get_unreviewed_topics filters correctly."""
        stub = TopicManipulationDetectorStub()
        stub._flagged_topics["topic-1"] = FlaggedTopic(
            topic_id="topic-1",
            flag_reason="test",
            flagged_at=datetime.now(timezone.utc),
            reviewed=False,
        )
        stub._flagged_topics["topic-2"] = FlaggedTopic(
            topic_id="topic-2",
            flag_reason="test",
            flagged_at=datetime.now(timezone.utc),
            reviewed=True,
        )

        unreviewed = stub.get_unreviewed_topics()
        assert len(unreviewed) == 1
        assert unreviewed[0].topic_id == "topic-1"

    def test_clear_removes_all_data(self) -> None:
        """Test clear removes all stored data."""
        stub = TopicManipulationDetectorStub()
        stub.set_coordination_score(("sub-1",), 0.8)
        stub.set_content_similarity("t1", "t2", 0.9)
        stub._flagged_topics["topic-1"] = FlaggedTopic(
            topic_id="topic-1",
            flag_reason="test",
            flagged_at=datetime.now(timezone.utc),
            reviewed=False,
        )
        stub._analysis_history.append(
            ManipulationAnalysisResult(
                manipulation_suspected=False,
                pattern_type=None,
                confidence_score=0.5,
                evidence_summary="test",
                topic_ids_affected=(),
            )
        )

        stub.clear()

        assert len(stub._coordination_scores) == 0
        assert len(stub._content_similarity) == 0
        assert len(stub._flagged_topics) == 0
        assert len(stub._analysis_history) == 0
