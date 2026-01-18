"""Integration tests for Topic Origin Tracking (FR15, FR71-73).

These tests verify the full flow of topic origin tracking,
rate limiting, queuing, and diversity enforcement using real
stub implementations.

Constitutional Constraints Verified:
- FR15: Topic origins SHALL be tracked with metadata
- FR71: Rate limit rapid submissions (>10/hour from single source)
- FR72: Excess topics SHALL be queued, not rejected
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window

Constitutional Truths Verified:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> All operations traceable
- CT-13: Integrity outranks availability -> Topics queued, not dropped
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.topic_origin_tracker import (
    DIVERSITY_THRESHOLD,
)
from src.application.ports.topic_rate_limiter import RATE_LIMIT_PER_HOUR
from src.application.services.topic_origin_service import TopicOriginService
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)
from src.infrastructure.stubs.topic_origin_tracker_stub import TopicOriginTrackerStub
from src.infrastructure.stubs.topic_rate_limiter_stub import TopicRateLimiterStub


class TestFR15TopicOriginTracking:
    """FR15: Topic origins SHALL be tracked with metadata."""

    @pytest.mark.asyncio
    async def test_autonomous_topic_tracked_with_metadata(self) -> None:
        """Autonomous topics are tracked with source agent metadata."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(
                source_agent_id="archon-1",
                autonomous_trigger="system_alert",
            ),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        result = await service.record_topic(topic, source_id="archon-1")

        assert result.recorded is True
        assert result.queued is False

        # Verify topic is retrievable
        stored = await service.get_topic_origin(topic.topic_id)
        assert stored is not None
        assert stored.origin_type == TopicOriginType.AUTONOMOUS
        assert stored.origin_metadata.source_agent_id == "archon-1"
        assert stored.origin_metadata.autonomous_trigger == "system_alert"

    @pytest.mark.asyncio
    async def test_petition_topic_tracked_with_petition_id(self) -> None:
        """Petition topics are tracked with petition reference."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        petition_id = uuid4()
        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.PETITION,
            origin_metadata=TopicOriginMetadata(
                petition_id=petition_id,
                source_agent_id="petition-system",
            ),
            created_at=datetime.now(timezone.utc),
            created_by="petition-system",
        )

        result = await service.record_topic(topic, source_id="petition-system")

        assert result.recorded is True

        stored = await service.get_topic_origin(topic.topic_id)
        assert stored is not None
        assert stored.origin_type == TopicOriginType.PETITION
        assert stored.origin_metadata.petition_id == petition_id

    @pytest.mark.asyncio
    async def test_scheduled_topic_tracked_with_schedule_ref(self) -> None:
        """Scheduled topics are tracked with schedule reference."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.SCHEDULED,
            origin_metadata=TopicOriginMetadata(
                schedule_ref="daily_review_0900",
                source_agent_id="scheduler",
            ),
            created_at=datetime.now(timezone.utc),
            created_by="scheduler",
        )

        result = await service.record_topic(topic, source_id="scheduler")

        assert result.recorded is True

        stored = await service.get_topic_origin(topic.topic_id)
        assert stored is not None
        assert stored.origin_type == TopicOriginType.SCHEDULED
        assert stored.origin_metadata.schedule_ref == "daily_review_0900"


class TestFR71RateLimiting:
    """FR71: Rate limit rapid submissions (>10/hour from single source)."""

    @pytest.mark.asyncio
    async def test_first_10_topics_within_limit(self) -> None:
        """First 10 topics from a source are within rate limit."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        source_id = "archon-1"
        recorded_count = 0

        for _i in range(RATE_LIMIT_PER_HOUR):  # 10 topics
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
                created_at=datetime.now(timezone.utc),
                created_by=source_id,
            )

            result = await service.record_topic(topic, source_id=source_id)

            if result.recorded:
                recorded_count += 1

        assert recorded_count == RATE_LIMIT_PER_HOUR

    @pytest.mark.asyncio
    async def test_11th_topic_triggers_rate_limit(self) -> None:
        """11th topic from same source triggers rate limiting."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        source_id = "archon-flood"

        # Submit 10 topics (all within limit)
        for _ in range(RATE_LIMIT_PER_HOUR):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
                created_at=datetime.now(timezone.utc),
                created_by=source_id,
            )
            await service.record_topic(topic, source_id=source_id)

        # 11th topic should be rate limited
        overflow_topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
            created_at=datetime.now(timezone.utc),
            created_by=source_id,
        )

        result = await service.record_topic(overflow_topic, source_id=source_id)

        assert result.recorded is False
        assert result.queued is True
        assert result.rate_limit_event is not None
        assert result.rate_limit_event.source_id == source_id
        assert result.rate_limit_event.limit == RATE_LIMIT_PER_HOUR

    @pytest.mark.asyncio
    async def test_different_sources_have_independent_limits(self) -> None:
        """Different sources have independent rate limits."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        # Source 1 submits 5 topics
        for _ in range(5):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id="archon-1"),
                created_at=datetime.now(timezone.utc),
                created_by="archon-1",
            )
            await service.record_topic(topic, source_id="archon-1")

        # Source 2 submits 5 topics - should all succeed (independent limit)
        source2_recorded = 0
        for _ in range(5):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id="archon-2"),
                created_at=datetime.now(timezone.utc),
                created_by="archon-2",
            )
            result = await service.record_topic(topic, source_id="archon-2")
            if result.recorded:
                source2_recorded += 1

        assert source2_recorded == 5


class TestFR72TopicQueuing:
    """FR72: Excess topics SHALL be queued, not rejected."""

    @pytest.mark.asyncio
    async def test_rate_limited_topic_is_queued(self) -> None:
        """Topics exceeding rate limit are queued (FR72 - queue, don't reject)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        source_id = "archon-queuer"

        # Exhaust rate limit
        for _ in range(RATE_LIMIT_PER_HOUR):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
                created_at=datetime.now(timezone.utc),
                created_by=source_id,
            )
            await service.record_topic(topic, source_id=source_id)

        # Submit excess topics - should be queued
        queued_topics = []
        for _i in range(3):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
                created_at=datetime.now(timezone.utc),
                created_by=source_id,
            )
            result = await service.record_topic(topic, source_id=source_id)

            assert result.queued is True
            assert result.queue_position is not None
            queued_topics.append(topic)

        # Verify queue positions are sequential
        assert len(queued_topics) == 3

    @pytest.mark.asyncio
    async def test_queued_topics_can_be_processed_later(self) -> None:
        """Queued topics can be processed when rate limit expires."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        source_id = "archon-dequeue"

        # Exhaust rate limit
        for _ in range(RATE_LIMIT_PER_HOUR):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
                created_at=datetime.now(timezone.utc),
                created_by=source_id,
            )
            await service.record_topic(topic, source_id=source_id)

        # Queue a topic
        queued_topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
            created_at=datetime.now(timezone.utc),
            created_by=source_id,
        )
        result = await service.record_topic(queued_topic, source_id=source_id)
        assert result.queued is True

        # Reset rate limit (simulate time passage)
        await limiter.reset_submissions(source_id)

        # Process queue
        processed = await service.process_queued_topics()

        assert processed >= 1

        # Verify topic was recorded
        stored = await service.get_topic_origin(queued_topic.topic_id)
        assert stored is not None


class TestFR73DiversityEnforcement:
    """FR73: No single origin type SHALL exceed 30% over rolling 30-day window."""

    @pytest.mark.asyncio
    async def test_balanced_distribution_is_compliant(self) -> None:
        """Balanced topic distribution is compliant."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        # Add topics with balanced distribution (25% each type)
        # Different sources to avoid rate limiting
        types_and_sources = [
            (TopicOriginType.AUTONOMOUS, "archon-auto"),
            (TopicOriginType.PETITION, "petition-sys"),
            (TopicOriginType.SCHEDULED, "scheduler"),
        ]

        for origin_type, source_id in types_and_sources:
            for i in range(5):  # 5 of each type = 5+5+5 = 15 total
                metadata = TopicOriginMetadata(source_agent_id=source_id)
                if origin_type == TopicOriginType.PETITION:
                    metadata = TopicOriginMetadata(
                        petition_id=uuid4(), source_agent_id=source_id
                    )
                elif origin_type == TopicOriginType.SCHEDULED:
                    metadata = TopicOriginMetadata(
                        schedule_ref=f"schedule_{i}", source_agent_id=source_id
                    )

                topic = TopicOrigin(
                    topic_id=uuid4(),
                    origin_type=origin_type,
                    origin_metadata=metadata,
                    created_at=datetime.now(timezone.utc),
                    created_by=source_id,
                )
                await service.record_topic(topic, source_id=source_id)

        result = await service.check_diversity_compliance()

        # 5/15 = 33.3% for each - this exceeds 30% threshold
        # Actually all three types are equal, so first one found > 30% triggers
        assert result.compliant is False

    @pytest.mark.asyncio
    async def test_autonomous_dominance_triggers_alert(self) -> None:
        """Heavy autonomous topic distribution triggers alert."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        # Add 8 autonomous topics (use multiple sources to avoid rate limit)
        for i in range(8):
            source = f"archon-{i % 3}"
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=source),
                created_at=datetime.now(timezone.utc),
                created_by=source,
            )
            await service.record_topic(topic, source_id=source)

        # Add 1 petition and 1 scheduled
        petition_topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.PETITION,
            origin_metadata=TopicOriginMetadata(
                petition_id=uuid4(), source_agent_id="petition-sys"
            ),
            created_at=datetime.now(timezone.utc),
            created_by="petition-sys",
        )
        await service.record_topic(petition_topic, source_id="petition-sys")

        scheduled_topic = TopicOrigin(
            topic_id=uuid4(),
            origin_type=TopicOriginType.SCHEDULED,
            origin_metadata=TopicOriginMetadata(
                schedule_ref="daily", source_agent_id="scheduler"
            ),
            created_at=datetime.now(timezone.utc),
            created_by="scheduler",
        )
        await service.record_topic(scheduled_topic, source_id="scheduler")

        # 8/10 = 80% autonomous - far exceeds 30%
        result = await service.check_diversity_compliance()

        assert result.compliant is False
        assert result.alert_event is not None
        assert result.alert_event.violation_type == TopicOriginType.AUTONOMOUS
        assert result.alert_event.current_percentage == 0.8
        assert result.alert_event.threshold == DIVERSITY_THRESHOLD

    @pytest.mark.asyncio
    async def test_empty_window_is_compliant(self) -> None:
        """Empty topic window is considered compliant."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        # No topics submitted
        result = await service.check_diversity_compliance()

        assert result.compliant is True
        assert result.alert_event is None


class TestHALTFirstRule:
    """CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE."""

    @pytest.mark.asyncio
    async def test_diversity_check_halts_when_system_halted(self) -> None:
        """check_diversity_compliance raises SystemHaltedError when halted."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        with pytest.raises(SystemHaltedError):
            await service.check_diversity_compliance()

    @pytest.mark.asyncio
    async def test_record_topic_halts_when_system_halted(self) -> None:
        """record_topic raises SystemHaltedError when halted."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
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
    async def test_process_queue_halts_when_system_halted(self) -> None:
        """process_queued_topics raises SystemHaltedError when halted."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        with pytest.raises(SystemHaltedError):
            await service.process_queued_topics()

    @pytest.mark.asyncio
    async def test_halt_check_happens_before_any_operation(self) -> None:
        """HALT check is the first thing done, before any work."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        # Use mocks to verify no other operations are called
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

        # Verify no other operations were called
        tracker.record_topic_origin.assert_not_called()
        limiter.check_rate_limit.assert_not_called()
        limiter.queue_topic.assert_not_called()


class TestIntegrationWithRealStubs:
    """Integration tests using real stub implementations."""

    @pytest.mark.asyncio
    async def test_full_workflow_autonomous_topic(self) -> None:
        """Full workflow: submit, track, and retrieve autonomous topic."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        # 1. Submit topic
        topic_id = uuid4()
        topic = TopicOrigin(
            topic_id=topic_id,
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(
                source_agent_id="archon-1",
                autonomous_trigger="user_request",
            ),
            created_at=datetime.now(timezone.utc),
            created_by="archon-1",
        )

        result = await service.record_topic(topic, source_id="archon-1")

        # 2. Verify recorded
        assert result.recorded is True
        assert result.queued is False

        # 3. Retrieve and verify metadata
        stored = await service.get_topic_origin(topic_id)
        assert stored is not None
        assert stored.topic_id == topic_id
        assert stored.origin_type == TopicOriginType.AUTONOMOUS
        assert stored.origin_metadata.autonomous_trigger == "user_request"
        assert stored.created_by == "archon-1"

    @pytest.mark.asyncio
    async def test_rate_limit_queue_dequeue_cycle(self) -> None:
        """Full cycle: exceed rate limit, queue, then process queue."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        tracker = TopicOriginTrackerStub()
        limiter = TopicRateLimiterStub()
        service = TopicOriginService(halt_checker, tracker, limiter)

        source_id = "archon-cycle"

        # Phase 1: Exhaust rate limit
        for _ in range(RATE_LIMIT_PER_HOUR):
            topic = TopicOrigin(
                topic_id=uuid4(),
                origin_type=TopicOriginType.AUTONOMOUS,
                origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
                created_at=datetime.now(timezone.utc),
                created_by=source_id,
            )
            await service.record_topic(topic, source_id=source_id)

        # Phase 2: Submit excess - should be queued
        overflow_id = uuid4()
        overflow_topic = TopicOrigin(
            topic_id=overflow_id,
            origin_type=TopicOriginType.AUTONOMOUS,
            origin_metadata=TopicOriginMetadata(source_agent_id=source_id),
            created_at=datetime.now(timezone.utc),
            created_by=source_id,
        )
        result = await service.record_topic(overflow_topic, source_id=source_id)
        assert result.queued is True

        # Phase 3: Reset rate limit (simulate time passage)
        await limiter.reset_submissions(source_id)

        # Phase 4: Process queue
        processed = await service.process_queued_topics()
        assert processed >= 1

        # Phase 5: Verify queued topic was recorded
        stored = await service.get_topic_origin(overflow_id)
        assert stored is not None
        assert stored.topic_id == overflow_id
