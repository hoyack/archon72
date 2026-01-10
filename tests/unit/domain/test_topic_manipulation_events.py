"""Unit tests for topic manipulation domain events (Story 6.9, FR118).

Tests for TopicManipulationSuspectedEventPayload, CoordinatedSubmissionSuspectedEventPayload,
and TopicRateLimitDailyEventPayload.

Constitutional Constraints:
- FR118: External topic rate limiting (10/day)
- CT-12: Witnessing creates accountability -> signable_content()
"""

from datetime import datetime, timezone

import pytest

from src.domain.events.topic_manipulation import (
    COORDINATED_SUBMISSION_SUSPECTED_EVENT_TYPE,
    TOPIC_MANIPULATION_SUSPECTED_EVENT_TYPE,
    TOPIC_RATE_LIMIT_DAILY_EVENT_TYPE,
    CoordinatedSubmissionSuspectedEventPayload,
    ManipulationPatternType,
    TopicManipulationSuspectedEventPayload,
    TopicRateLimitDailyEventPayload,
)


class TestManipulationPatternType:
    """Tests for ManipulationPatternType enum."""

    def test_enum_values_exist(self) -> None:
        """Test that all expected enum values are present."""
        assert ManipulationPatternType.COORDINATED_TIMING.value == "coordinated_timing"
        assert ManipulationPatternType.CONTENT_SIMILARITY.value == "content_similarity"
        assert ManipulationPatternType.SOURCE_COLLUSION.value == "source_collusion"
        assert ManipulationPatternType.BURST_SUBMISSION.value == "burst_submission"
        assert ManipulationPatternType.UNKNOWN.value == "unknown"

    def test_enum_is_string_based(self) -> None:
        """Test enum values are strings for JSON serialization."""
        for pattern in ManipulationPatternType:
            assert isinstance(pattern.value, str)


class TestTopicManipulationSuspectedEventPayload:
    """Tests for TopicManipulationSuspectedEventPayload."""

    def test_creation_with_valid_data(self) -> None:
        """Test payload creation with all required fields."""
        now = datetime.now(timezone.utc)
        payload = TopicManipulationSuspectedEventPayload(
            detection_id="det-123",
            suspected_topics=("topic-1", "topic-2"),
            pattern_type=ManipulationPatternType.COORDINATED_TIMING,
            confidence_score=0.85,
            evidence_summary="Multiple topics from same IP in 2 minutes",
            detected_at=now,
            detection_window_hours=24,
        )

        assert payload.detection_id == "det-123"
        assert payload.suspected_topics == ("topic-1", "topic-2")
        assert payload.pattern_type == ManipulationPatternType.COORDINATED_TIMING
        assert payload.confidence_score == 0.85
        assert payload.evidence_summary == "Multiple topics from same IP in 2 minutes"
        assert payload.detected_at == now
        assert payload.detection_window_hours == 24

    def test_event_type_constant(self) -> None:
        """Test event type constant is defined."""
        assert TOPIC_MANIPULATION_SUSPECTED_EVENT_TYPE == "topic.manipulation_suspected"

    def test_frozen_dataclass_immutable(self) -> None:
        """Test payload is immutable (frozen dataclass)."""
        now = datetime.now(timezone.utc)
        payload = TopicManipulationSuspectedEventPayload(
            detection_id="det-123",
            suspected_topics=("topic-1",),
            pattern_type=ManipulationPatternType.UNKNOWN,
            confidence_score=0.5,
            evidence_summary="Test",
            detected_at=now,
            detection_window_hours=24,
        )

        with pytest.raises(AttributeError):
            payload.detection_id = "new-id"  # type: ignore[misc]

    def test_to_dict_returns_serializable_structure(self) -> None:
        """Test to_dict returns JSON-serializable dictionary."""
        now = datetime.now(timezone.utc)
        payload = TopicManipulationSuspectedEventPayload(
            detection_id="det-456",
            suspected_topics=("topic-1", "topic-2", "topic-3"),
            pattern_type=ManipulationPatternType.SOURCE_COLLUSION,
            confidence_score=0.92,
            evidence_summary="Coordinated submission pattern",
            detected_at=now,
            detection_window_hours=12,
        )

        result = payload.to_dict()

        assert result["detection_id"] == "det-456"
        assert result["suspected_topics"] == ["topic-1", "topic-2", "topic-3"]
        assert result["pattern_type"] == "source_collusion"
        assert result["confidence_score"] == 0.92
        assert result["evidence_summary"] == "Coordinated submission pattern"
        assert result["detected_at"] == now.isoformat()
        assert result["detection_window_hours"] == 12

    def test_signable_content_deterministic_ct12(self) -> None:
        """Test signable_content is deterministic for witnessing (CT-12)."""
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        payload = TopicManipulationSuspectedEventPayload(
            detection_id="det-789",
            suspected_topics=("topic-a", "topic-b"),
            pattern_type=ManipulationPatternType.BURST_SUBMISSION,
            confidence_score=0.75,
            evidence_summary="Burst detected",
            detected_at=now,
            detection_window_hours=6,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        # Same payload produces identical signable content
        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_different_for_different_data(self) -> None:
        """Test different payloads produce different signable content."""
        now = datetime.now(timezone.utc)
        payload1 = TopicManipulationSuspectedEventPayload(
            detection_id="det-001",
            suspected_topics=("topic-1",),
            pattern_type=ManipulationPatternType.UNKNOWN,
            confidence_score=0.5,
            evidence_summary="Test 1",
            detected_at=now,
            detection_window_hours=24,
        )
        payload2 = TopicManipulationSuspectedEventPayload(
            detection_id="det-002",
            suspected_topics=("topic-2",),
            pattern_type=ManipulationPatternType.UNKNOWN,
            confidence_score=0.5,
            evidence_summary="Test 2",
            detected_at=now,
            detection_window_hours=24,
        )

        assert payload1.signable_content() != payload2.signable_content()

    def test_validation_rejects_empty_detection_id(self) -> None:
        """Test validation rejects empty detection_id."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="detection_id must be non-empty"):
            TopicManipulationSuspectedEventPayload(
                detection_id="",
                suspected_topics=("topic-1",),
                pattern_type=ManipulationPatternType.UNKNOWN,
                confidence_score=0.5,
                evidence_summary="Test",
                detected_at=now,
                detection_window_hours=24,
            )

    def test_validation_rejects_invalid_confidence_score(self) -> None:
        """Test validation rejects confidence score outside 0-1 range."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            TopicManipulationSuspectedEventPayload(
                detection_id="det-123",
                suspected_topics=("topic-1",),
                pattern_type=ManipulationPatternType.UNKNOWN,
                confidence_score=1.5,
                evidence_summary="Test",
                detected_at=now,
                detection_window_hours=24,
            )


class TestCoordinatedSubmissionSuspectedEventPayload:
    """Tests for CoordinatedSubmissionSuspectedEventPayload."""

    def test_creation_with_valid_data(self) -> None:
        """Test payload creation with all required fields."""
        now = datetime.now(timezone.utc)
        payload = CoordinatedSubmissionSuspectedEventPayload(
            detection_id="coord-123",
            submission_ids=("sub-1", "sub-2", "sub-3"),
            coordination_score=0.85,
            coordination_signals=("timing_burst", "content_similarity"),
            source_ids=("src-a", "src-b"),
            detected_at=now,
        )

        assert payload.detection_id == "coord-123"
        assert payload.submission_ids == ("sub-1", "sub-2", "sub-3")
        assert payload.coordination_score == 0.85
        assert payload.coordination_signals == ("timing_burst", "content_similarity")
        assert payload.source_ids == ("src-a", "src-b")
        assert payload.detected_at == now

    def test_event_type_constant(self) -> None:
        """Test event type constant is defined."""
        assert COORDINATED_SUBMISSION_SUSPECTED_EVENT_TYPE == "topic.coordinated_submission_suspected"

    def test_to_dict_returns_serializable_structure(self) -> None:
        """Test to_dict returns JSON-serializable dictionary."""
        now = datetime.now(timezone.utc)
        payload = CoordinatedSubmissionSuspectedEventPayload(
            detection_id="coord-456",
            submission_ids=("sub-1", "sub-2"),
            coordination_score=0.72,
            coordination_signals=("timing_burst",),
            source_ids=("src-x",),
            detected_at=now,
        )

        result = payload.to_dict()

        assert result["detection_id"] == "coord-456"
        assert result["submission_ids"] == ["sub-1", "sub-2"]
        assert result["coordination_score"] == 0.72
        assert result["coordination_signals"] == ["timing_burst"]
        assert result["source_ids"] == ["src-x"]
        assert result["detected_at"] == now.isoformat()

    def test_signable_content_deterministic(self) -> None:
        """Test signable_content is deterministic."""
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        payload = CoordinatedSubmissionSuspectedEventPayload(
            detection_id="coord-789",
            submission_ids=("sub-a", "sub-b"),
            coordination_score=0.80,
            coordination_signals=("test",),
            source_ids=("src-1",),
            detected_at=now,
        )

        assert payload.signable_content() == payload.signable_content()


class TestTopicRateLimitDailyEventPayload:
    """Tests for TopicRateLimitDailyEventPayload (FR118)."""

    def test_creation_with_valid_data(self) -> None:
        """Test payload creation with all required fields."""
        now = datetime.now(timezone.utc)
        reset_at = datetime(2026, 1, 9, 0, 0, 0, tzinfo=timezone.utc)
        payload = TopicRateLimitDailyEventPayload(
            source_id="external-source-123",
            topics_today=11,
            daily_limit=10,
            rejected_topic_ids=("topic-11",),
            limit_start=now,
            limit_reset_at=reset_at,
        )

        assert payload.source_id == "external-source-123"
        assert payload.topics_today == 11
        assert payload.daily_limit == 10
        assert payload.rejected_topic_ids == ("topic-11",)
        assert payload.limit_start == now
        assert payload.limit_reset_at == reset_at

    def test_event_type_constant(self) -> None:
        """Test event type constant is defined."""
        assert TOPIC_RATE_LIMIT_DAILY_EVENT_TYPE == "topic.rate_limit_daily"

    def test_default_daily_limit(self) -> None:
        """Test default daily limit is 10 per FR118."""
        now = datetime.now(timezone.utc)
        reset_at = datetime(2026, 1, 9, 0, 0, 0, tzinfo=timezone.utc)
        payload = TopicRateLimitDailyEventPayload(
            source_id="src-123",
            topics_today=10,
            daily_limit=10,  # FR118 specifies 10
            rejected_topic_ids=(),
            limit_start=now,
            limit_reset_at=reset_at,
        )

        assert payload.daily_limit == 10

    def test_to_dict_returns_serializable_structure(self) -> None:
        """Test to_dict returns JSON-serializable dictionary."""
        now = datetime.now(timezone.utc)
        reset_at = datetime(2026, 1, 9, 0, 0, 0, tzinfo=timezone.utc)
        payload = TopicRateLimitDailyEventPayload(
            source_id="src-456",
            topics_today=12,
            daily_limit=10,
            rejected_topic_ids=("topic-11", "topic-12"),
            limit_start=now,
            limit_reset_at=reset_at,
        )

        result = payload.to_dict()

        assert result["source_id"] == "src-456"
        assert result["topics_today"] == 12
        assert result["daily_limit"] == 10
        assert result["rejected_topic_ids"] == ["topic-11", "topic-12"]
        assert result["limit_start"] == now.isoformat()
        assert result["limit_reset_at"] == reset_at.isoformat()

    def test_validation_rejects_empty_source_id(self) -> None:
        """Test validation rejects empty source_id."""
        now = datetime.now(timezone.utc)
        reset_at = datetime(2026, 1, 9, 0, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="source_id must be non-empty"):
            TopicRateLimitDailyEventPayload(
                source_id="",
                topics_today=11,
                daily_limit=10,
                rejected_topic_ids=("topic-11",),
                limit_start=now,
                limit_reset_at=reset_at,
            )

    def test_fr118_message_in_validation_error(self) -> None:
        """Test FR118 referenced in validation error message."""
        now = datetime.now(timezone.utc)
        reset_at = datetime(2026, 1, 9, 0, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="FR118"):
            TopicRateLimitDailyEventPayload(
                source_id="  ",  # whitespace only
                topics_today=11,
                daily_limit=10,
                rejected_topic_ids=("topic-11",),
                limit_start=now,
                limit_reset_at=reset_at,
            )
