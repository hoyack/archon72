"""Unit tests for TopicDiversityStats domain model (FR73).

Tests the topic diversity statistics model for rolling window analysis.
Ensures no single origin type exceeds 30% threshold.

Constitutional Constraints:
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.models.topic_diversity import TopicDiversityStats
from src.domain.models.topic_origin import TopicOriginType


class TestTopicDiversityStats:
    """Tests for TopicDiversityStats frozen dataclass."""

    def test_create_diversity_stats(self) -> None:
        """Create diversity stats with counts."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        stats = TopicDiversityStats(
            window_start=window_start,
            window_end=now,
            total_topics=100,
            autonomous_count=30,
            petition_count=40,
            scheduled_count=30,
        )

        assert stats.total_topics == 100
        assert stats.autonomous_count == 30
        assert stats.petition_count == 40
        assert stats.scheduled_count == 30

    def test_percentage_calculations(self) -> None:
        """Percentages are calculated correctly."""
        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=25,
            petition_count=50,
            scheduled_count=25,
        )

        assert stats.autonomous_pct == 0.25
        assert stats.petition_pct == 0.50
        assert stats.scheduled_pct == 0.25

    def test_percentage_zero_when_no_topics(self) -> None:
        """Percentages return 0.0 when total_topics is 0."""
        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=0,
            autonomous_count=0,
            petition_count=0,
            scheduled_count=0,
        )

        assert stats.autonomous_pct == 0.0
        assert stats.petition_pct == 0.0
        assert stats.scheduled_pct == 0.0

    def test_exceeds_threshold_returns_violating_type(self) -> None:
        """exceeds_threshold returns first type exceeding threshold."""
        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=35,  # 35% > 30%
            petition_count=35,  # 35% > 30%
            scheduled_count=30,
        )

        # Should return AUTONOMOUS (first checked)
        result = stats.exceeds_threshold(threshold=0.30)
        assert result == TopicOriginType.AUTONOMOUS

    def test_exceeds_threshold_returns_none_when_compliant(self) -> None:
        """exceeds_threshold returns None when all types are within threshold."""
        now = datetime.now(timezone.utc)
        TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=30,
            petition_count=30,
            scheduled_count=40,  # Exactly 40% but testing 30% threshold
        )

        # All types <= 30%, except scheduled which we're checking separately
        stats_compliant = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=30,
            petition_count=30,
            scheduled_count=30,
        )

        # Note: 30% at threshold is acceptable per PRD (only > 30% triggers)
        assert stats_compliant.exceeds_threshold(0.30) is None

    def test_exactly_at_threshold_is_acceptable(self) -> None:
        """Exactly 30% (at threshold) does not trigger violation."""
        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=30,  # Exactly 30%
            petition_count=35,
            scheduled_count=35,
        )

        # Only > 30% triggers, not ==30%
        result = stats.exceeds_threshold(0.30)
        # petition and scheduled are > 30%
        assert result in [TopicOriginType.PETITION, TopicOriginType.SCHEDULED]

    def test_diversity_stats_is_frozen(self) -> None:
        """TopicDiversityStats is immutable."""
        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=30,
            petition_count=40,
            scheduled_count=30,
        )
        with pytest.raises(AttributeError):
            stats.total_topics = 200  # type: ignore[misc]

    def test_single_topic_exceeds_threshold(self) -> None:
        """Single topic = 100% for its type, exceeds threshold."""
        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=1,
            autonomous_count=1,  # 100%
            petition_count=0,
            scheduled_count=0,
        )

        result = stats.exceeds_threshold(0.30)
        assert result == TopicOriginType.AUTONOMOUS

    def test_negative_total_topics_rejected(self) -> None:
        """Negative total_topics raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="total_topics cannot be negative"):
            TopicDiversityStats(
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=-1,
                autonomous_count=0,
                petition_count=0,
                scheduled_count=0,
            )

    def test_negative_autonomous_count_rejected(self) -> None:
        """Negative autonomous_count raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="autonomous_count cannot be negative"):
            TopicDiversityStats(
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=100,
                autonomous_count=-1,
                petition_count=0,
                scheduled_count=0,
            )

    def test_negative_petition_count_rejected(self) -> None:
        """Negative petition_count raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="petition_count cannot be negative"):
            TopicDiversityStats(
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=100,
                autonomous_count=0,
                petition_count=-1,
                scheduled_count=0,
            )

    def test_negative_scheduled_count_rejected(self) -> None:
        """Negative scheduled_count raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="scheduled_count cannot be negative"):
            TopicDiversityStats(
                window_start=now - timedelta(days=30),
                window_end=now,
                total_topics=100,
                autonomous_count=0,
                petition_count=0,
                scheduled_count=-1,
            )
