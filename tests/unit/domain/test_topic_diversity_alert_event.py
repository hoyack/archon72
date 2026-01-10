"""Unit tests for TopicDiversityAlertPayload domain event (FR73).

Tests the event payload created when diversity threshold is violated.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.events.topic_diversity_alert import (
    TOPIC_DIVERSITY_ALERT_EVENT_TYPE,
    TopicDiversityAlertPayload,
)
from src.domain.models.topic_origin import TopicOriginType


class TestTopicDiversityAlertPayload:
    """Tests for TopicDiversityAlertPayload frozen dataclass."""

    def test_event_type_constant(self) -> None:
        """Event type constant is defined."""
        assert TOPIC_DIVERSITY_ALERT_EVENT_TYPE == "topic_diversity_alert"

    def test_create_payload(self) -> None:
        """Create diversity alert payload with all fields."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        payload = TopicDiversityAlertPayload(
            violation_type=TopicOriginType.AUTONOMOUS,
            current_percentage=0.35,
            threshold=0.30,
            window_start=window_start,
            window_end=now,
            total_topics=100,
        )

        assert payload.violation_type == TopicOriginType.AUTONOMOUS
        assert payload.current_percentage == 0.35
        assert payload.threshold == 0.30
        assert payload.window_start == window_start
        assert payload.window_end == now
        assert payload.total_topics == 100

    def test_payload_is_frozen(self) -> None:
        """Payload is immutable."""
        now = datetime.now(timezone.utc)
        payload = TopicDiversityAlertPayload(
            violation_type=TopicOriginType.PETITION,
            current_percentage=0.40,
            threshold=0.30,
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=50,
        )
        with pytest.raises(AttributeError):
            payload.current_percentage = 0.50  # type: ignore[misc]

    def test_to_dict_method(self) -> None:
        """to_dict returns serializable dictionary."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)
        payload = TopicDiversityAlertPayload(
            violation_type=TopicOriginType.SCHEDULED,
            current_percentage=0.45,
            threshold=0.30,
            window_start=window_start,
            window_end=now,
            total_topics=200,
        )

        result = payload.to_dict()

        assert isinstance(result, dict)
        assert result["violation_type"] == "scheduled"
        assert result["current_percentage"] == 0.45
        assert result["threshold"] == 0.30
        assert result["total_topics"] == 200
        # Timestamps should be ISO format strings
        assert isinstance(result["window_start"], str)
        assert isinstance(result["window_end"], str)

    def test_all_origin_types_supported(self) -> None:
        """All TopicOriginType values can be used as violation_type."""
        now = datetime.now(timezone.utc)

        for origin_type in TopicOriginType:
            payload = TopicDiversityAlertPayload(
                violation_type=origin_type,
                current_percentage=0.35,
                threshold=0.30,
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=100,
            )
            assert payload.violation_type == origin_type

    def test_percentage_display_in_dict(self) -> None:
        """Percentages are preserved as decimals in dict."""
        now = datetime.now(timezone.utc)
        payload = TopicDiversityAlertPayload(
            violation_type=TopicOriginType.AUTONOMOUS,
            current_percentage=0.333333,
            threshold=0.30,
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=75,
        )

        result = payload.to_dict()
        assert result["current_percentage"] == 0.333333

    def test_total_topics_must_be_positive(self) -> None:
        """total_topics must be at least 1 for a valid alert."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="total_topics must be at least 1"):
            TopicDiversityAlertPayload(
                violation_type=TopicOriginType.AUTONOMOUS,
                current_percentage=0.0,
                threshold=0.30,
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=0,  # Invalid - can't have violation with 0 topics
            )

    def test_negative_percentage_rejected(self) -> None:
        """Negative current_percentage raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="current_percentage must be between"):
            TopicDiversityAlertPayload(
                violation_type=TopicOriginType.AUTONOMOUS,
                current_percentage=-0.5,
                threshold=0.30,
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=100,
            )

    def test_percentage_over_one_rejected(self) -> None:
        """current_percentage > 1.0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="current_percentage must be between"):
            TopicDiversityAlertPayload(
                violation_type=TopicOriginType.AUTONOMOUS,
                current_percentage=1.5,
                threshold=0.30,
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=100,
            )

    def test_invalid_threshold_rejected(self) -> None:
        """Threshold outside 0.0-1.0 range raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="threshold must be between"):
            TopicDiversityAlertPayload(
                violation_type=TopicOriginType.AUTONOMOUS,
                current_percentage=0.5,
                threshold=1.5,  # Invalid
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=100,
            )
