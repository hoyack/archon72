"""Unit tests for TopicOriginService application service (FR15, FR71-73).

Tests the orchestration of topic origin tracking, rate limiting,
and diversity enforcement.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.topic_origin_service import (
    TopicOriginService,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.topic_diversity import TopicDiversityStats
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)


class TestTopicOriginServiceRecordTopic:
    """Tests for record_topic functionality."""

    @pytest.mark.asyncio
    async def test_halt_check_first(self) -> None:
        """HALT FIRST rule is enforced."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        tracker = AsyncMock()
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        with pytest.raises(SystemHaltedError):
            await service.record_topic(topic, source_id="archon-1")

    @pytest.mark.asyncio
    async def test_record_topic_within_rate_limit(self) -> None:
        """Topic within rate limit is recorded directly."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = AsyncMock()
        limiter = AsyncMock()
        limiter.check_rate_limit.return_value = True
        limiter.record_submission.return_value = 1

        service = TopicOriginService(halt_checker, tracker, limiter)

        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        result = await service.record_topic(topic, source_id="archon-1")

        assert result.recorded is True
        assert result.queued is False
        tracker.record_topic_origin.assert_called_once_with(topic)

    @pytest.mark.asyncio
    async def test_record_topic_rate_limited_queues(self) -> None:
        """Topic exceeding rate limit is queued (FR72)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = AsyncMock()
        limiter = AsyncMock()
        limiter.check_rate_limit.return_value = False  # Rate limited
        limiter.queue_topic.return_value = 3  # Queue position 3
        limiter.record_submission.return_value = 11

        service = TopicOriginService(halt_checker, tracker, limiter)

        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        result = await service.record_topic(topic, source_id="archon-1")

        assert result.recorded is False
        assert result.queued is True
        assert result.queue_position == 3
        tracker.record_topic_origin.assert_not_called()
        limiter.queue_topic.assert_called_once_with(topic)

    @pytest.mark.asyncio
    async def test_record_topic_creates_rate_limit_event(self) -> None:
        """Rate limited topic creates TopicRateLimitEvent."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = AsyncMock()
        limiter = AsyncMock()
        limiter.check_rate_limit.return_value = False
        limiter.queue_topic.return_value = 1
        limiter.record_submission.return_value = 11

        service = TopicOriginService(halt_checker, tracker, limiter)

        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        result = await service.record_topic(topic, source_id="archon-1")

        assert result.rate_limit_event is not None
        assert result.rate_limit_event.source_id == "archon-1"


class TestTopicOriginServiceDiversityCheck:
    """Tests for check_diversity_compliance functionality."""

    @pytest.mark.asyncio
    async def test_halt_check_first(self) -> None:
        """HALT FIRST rule is enforced for diversity check."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        tracker = AsyncMock()
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        with pytest.raises(SystemHaltedError):
            await service.check_diversity_compliance()

        # Verify no other operations were called
        tracker.get_diversity_stats.assert_not_called()

    @pytest.mark.asyncio
    async def test_diversity_compliant_returns_true(self) -> None:
        """Returns True when all origin types within threshold."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        now = datetime.now(timezone.utc)
        # Each type at 25% (25/100 = 0.25), all <= 30% threshold
        # Note: 25+25+25=75 out of 100 - the remaining 25 topics could be
        # distributed across types, but for this test we want clear compliance
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=25,  # 25% <= 30%
            petition_count=25,  # 25% <= 30%
            scheduled_count=25,  # 25% <= 30%
        )

        tracker = AsyncMock()
        tracker.get_diversity_stats.return_value = stats
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        result = await service.check_diversity_compliance()

        assert result.compliant is True

    @pytest.mark.asyncio
    async def test_diversity_violation_returns_false_with_alert(self) -> None:
        """Returns False with alert when threshold exceeded."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=100,
            autonomous_count=40,  # 40% > 30%
            petition_count=30,
            scheduled_count=30,
        )

        tracker = AsyncMock()
        tracker.get_diversity_stats.return_value = stats
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        result = await service.check_diversity_compliance()

        assert result.compliant is False
        assert result.alert_event is not None
        assert result.alert_event.violation_type == TopicOriginType.AUTONOMOUS
        assert result.alert_event.current_percentage == 0.4

    @pytest.mark.asyncio
    async def test_empty_window_is_compliant(self) -> None:
        """Empty window (no topics) is considered compliant."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        now = datetime.now(timezone.utc)
        stats = TopicDiversityStats(
            window_start=now - timedelta(days=30),
            window_end=now,
            total_topics=0,
            autonomous_count=0,
            petition_count=0,
            scheduled_count=0,
        )

        tracker = AsyncMock()
        tracker.get_diversity_stats.return_value = stats
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        result = await service.check_diversity_compliance()

        assert result.compliant is True


class TestTopicOriginServiceGetTopic:
    """Tests for get_topic_origin functionality."""

    @pytest.mark.asyncio
    async def test_get_topic_origin(self) -> None:
        """Get topic origin by ID."""
        halt_checker = AsyncMock()
        topic_id = uuid4()
        topic = TopicOrigin(
            topic_id=topic_id,
            origin_type=TopicOriginType.PETITION,
            origin_metadata=TopicOriginMetadata(
                petition_id=uuid4(),
                source_agent_id="petition-system",
            ),
            created_at=datetime.now(timezone.utc),
            created_by="petition-system",
        )

        tracker = AsyncMock()
        tracker.get_topic_origin.return_value = topic
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        result = await service.get_topic_origin(topic_id)

        assert result == topic
        tracker.get_topic_origin.assert_called_once_with(topic_id)

    @pytest.mark.asyncio
    async def test_get_nonexistent_topic_returns_none(self) -> None:
        """Get nonexistent topic returns None."""
        halt_checker = AsyncMock()
        tracker = AsyncMock()
        tracker.get_topic_origin.return_value = None
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        result = await service.get_topic_origin(uuid4())

        assert result is None


class TestTopicOriginServiceProcessQueue:
    """Tests for process_queued_topics functionality."""

    @pytest.mark.asyncio
    async def test_halt_check_before_processing(self) -> None:
        """HALT FIRST rule enforced when processing queue."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        tracker = AsyncMock()
        limiter = AsyncMock()

        service = TopicOriginService(halt_checker, tracker, limiter)

        with pytest.raises(SystemHaltedError):
            await service.process_queued_topics()

    @pytest.mark.asyncio
    async def test_process_queued_topics_empty_queue(self) -> None:
        """Processing empty queue returns 0."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = AsyncMock()
        limiter = AsyncMock()
        limiter.dequeue_topic.return_value = None
        limiter.check_rate_limit.return_value = True

        service = TopicOriginService(halt_checker, tracker, limiter)

        processed = await service.process_queued_topics()

        assert processed == 0

    @pytest.mark.asyncio
    async def test_process_queued_topics_records_when_no_longer_limited(self) -> None:
        """Queued topics are recorded when rate limit expires."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        tracker = AsyncMock()
        limiter = AsyncMock()
        limiter.dequeue_topic.side_effect = [topic, None]  # Return topic, then None
        limiter.check_rate_limit.return_value = True  # No longer rate limited

        service = TopicOriginService(halt_checker, tracker, limiter)

        processed = await service.process_queued_topics()

        assert processed == 1
        tracker.record_topic_origin.assert_called_once_with(topic)


class TestTopicOriginServiceDependencyInjection:
    """Tests for dependency injection."""

    def test_service_requires_halt_checker(self) -> None:
        """Service requires halt_checker."""
        with pytest.raises(TypeError):
            TopicOriginService(None, AsyncMock(), AsyncMock())  # type: ignore[arg-type]

    def test_service_requires_tracker(self) -> None:
        """Service requires tracker."""
        with pytest.raises(TypeError):
            TopicOriginService(AsyncMock(), None, AsyncMock())  # type: ignore[arg-type]

    def test_service_requires_limiter(self) -> None:
        """Service requires limiter."""
        with pytest.raises(TypeError):
            TopicOriginService(AsyncMock(), AsyncMock(), None)  # type: ignore[arg-type]
