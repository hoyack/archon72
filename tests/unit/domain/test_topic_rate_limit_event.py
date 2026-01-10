"""Unit tests for TopicRateLimitPayload domain event (FR71-72).

Tests the event payload created when rate limiting is applied.
"""

from datetime import datetime, timezone

import pytest

from src.domain.events.topic_rate_limit import (
    TOPIC_RATE_LIMIT_EVENT_TYPE,
    TopicRateLimitPayload,
)


class TestTopicRateLimitPayload:
    """Tests for TopicRateLimitPayload frozen dataclass."""

    def test_event_type_constant(self) -> None:
        """Event type constant is defined."""
        assert TOPIC_RATE_LIMIT_EVENT_TYPE == "topic_rate_limit"

    def test_create_payload(self) -> None:
        """Create rate limit payload with all fields."""
        now = datetime.now(timezone.utc)

        payload = TopicRateLimitPayload(
            source_id="archon-42",
            topics_submitted=15,
            limit=10,
            queued_count=5,
            rate_limit_start=now,
            rate_limit_duration_seconds=3600,
        )

        assert payload.source_id == "archon-42"
        assert payload.topics_submitted == 15
        assert payload.limit == 10
        assert payload.queued_count == 5
        assert payload.rate_limit_start == now
        assert payload.rate_limit_duration_seconds == 3600

    def test_payload_is_frozen(self) -> None:
        """Payload is immutable."""
        now = datetime.now(timezone.utc)
        payload = TopicRateLimitPayload(
            source_id="test",
            topics_submitted=11,
            limit=10,
            queued_count=1,
            rate_limit_start=now,
            rate_limit_duration_seconds=3600,
        )
        with pytest.raises(AttributeError):
            payload.source_id = "modified"  # type: ignore[misc]

    def test_to_dict_method(self) -> None:
        """to_dict returns serializable dictionary."""
        now = datetime.now(timezone.utc)
        payload = TopicRateLimitPayload(
            source_id="petition-system",
            topics_submitted=20,
            limit=10,
            queued_count=10,
            rate_limit_start=now,
            rate_limit_duration_seconds=3600,
        )

        result = payload.to_dict()

        assert isinstance(result, dict)
        assert result["source_id"] == "petition-system"
        assert result["topics_submitted"] == 20
        assert result["limit"] == 10
        assert result["queued_count"] == 10
        assert result["rate_limit_duration_seconds"] == 3600
        # Timestamp should be ISO format string
        assert isinstance(result["rate_limit_start"], str)

    def test_queued_count_represents_excess(self) -> None:
        """queued_count represents topics that were queued (excess over limit)."""
        now = datetime.now(timezone.utc)
        payload = TopicRateLimitPayload(
            source_id="scheduler",
            topics_submitted=12,
            limit=10,
            queued_count=2,  # 12 - 10 = 2 queued
            rate_limit_start=now,
            rate_limit_duration_seconds=3600,
        )

        assert payload.queued_count == payload.topics_submitted - payload.limit

    def test_source_id_cannot_be_empty(self) -> None:
        """source_id must be non-empty string."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR71.*source_id"):
            TopicRateLimitPayload(
                source_id="",
                topics_submitted=11,
                limit=10,
                queued_count=1,
                rate_limit_start=now,
                rate_limit_duration_seconds=3600,
            )
