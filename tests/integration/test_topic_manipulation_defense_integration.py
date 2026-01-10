"""Integration tests for topic manipulation defense (Story 6.9, FR118-FR119).

Tests TopicManipulationDefenseService with infrastructure stubs.

Constitutional Constraints:
- FR118: External topic rate limiting (10/day per source)
- FR119: Autonomous topics have priority over external submissions
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

import pytest

from src.application.ports.topic_manipulation_detector import (
    ManipulationAnalysisResult,
)
from src.application.ports.topic_priority import TopicPriorityLevel
from src.application.ports.topic_daily_limiter import DAILY_TOPIC_LIMIT
from src.application.services.topic_manipulation_defense_service import (
    COORDINATION_THRESHOLD,
    TopicManipulationDefenseService,
)
from src.domain.errors.topic_manipulation import DailyRateLimitExceededError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.topic_manipulation import ManipulationPatternType
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.topic_daily_limiter_stub import TopicDailyLimiterStub
from src.infrastructure.stubs.topic_manipulation_detector_stub import (
    TopicManipulationDetectorStub,
)
from src.infrastructure.stubs.topic_priority_stub import TopicPriorityStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def detector() -> TopicManipulationDetectorStub:
    """Create manipulation detector stub."""
    return TopicManipulationDetectorStub()


@pytest.fixture
def limiter() -> TopicDailyLimiterStub:
    """Create daily limiter stub."""
    return TopicDailyLimiterStub()


@pytest.fixture
def priority() -> TopicPriorityStub:
    """Create priority stub."""
    return TopicPriorityStub()


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub,
    detector: TopicManipulationDetectorStub,
    limiter: TopicDailyLimiterStub,
    priority: TopicPriorityStub,
) -> TopicManipulationDefenseService:
    """Create topic manipulation defense service with stubs."""
    return TopicManipulationDefenseService(
        halt_checker=halt_checker,
        detector=detector,
        limiter=limiter,
        priority=priority,
    )


class TestHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_check_for_manipulation_halted(
        self,
        service: TopicManipulationDefenseService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that check_for_manipulation raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.check_for_manipulation(("topic-1", "topic-2"))

    @pytest.mark.asyncio
    async def test_submit_external_topic_halted(
        self,
        service: TopicManipulationDefenseService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that submit_external_topic raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.submit_external_topic("topic-1", "source-1")

    @pytest.mark.asyncio
    async def test_get_next_topic_with_priority_halted(
        self,
        service: TopicManipulationDefenseService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that get_next_topic_with_priority raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.get_next_topic_with_priority()

    @pytest.mark.asyncio
    async def test_check_coordination_halted(
        self,
        service: TopicManipulationDefenseService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that check_coordination raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.check_coordination(("sub-1", "sub-2"))


class TestManipulationDetection:
    """Tests for manipulation detection (AC1, AC5)."""

    @pytest.mark.asyncio
    async def test_no_manipulation_detected(
        self,
        service: TopicManipulationDefenseService,
    ) -> None:
        """Test clean analysis with no manipulation."""
        result = await service.check_for_manipulation(("topic-1", "topic-2"))

        assert not result.manipulation_suspected
        assert result.event is None
        assert result.analysis_result.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_manipulation_detected_flags_topics(
        self,
        service: TopicManipulationDefenseService,
        detector: TopicManipulationDetectorStub,
    ) -> None:
        """Test manipulation detection flags topics for review."""
        # Configure detector to return high coordination score
        detector.set_coordination_score(("topic-1", "topic-2"), 0.85)

        result = await service.check_for_manipulation(("topic-1", "topic-2"))

        assert result.manipulation_suspected
        assert result.event is not None
        assert result.event.pattern_type == ManipulationPatternType.COORDINATED_TIMING
        assert result.analysis_result.confidence_score == 0.85

        # Topics should be flagged for review
        flagged = await detector.get_flagged_topics()
        assert len(flagged) == 2
        flagged_ids = [t.topic_id for t in flagged]
        assert "topic-1" in flagged_ids
        assert "topic-2" in flagged_ids

    @pytest.mark.asyncio
    async def test_burst_pattern_detected(
        self,
        service: TopicManipulationDefenseService,
        detector: TopicManipulationDetectorStub,
    ) -> None:
        """Test burst submission pattern detection."""
        # Configure detector for burst pattern (0.7-0.79)
        detector.set_coordination_score(("topic-1",), 0.72)

        result = await service.check_for_manipulation(("topic-1",))

        assert result.manipulation_suspected
        assert result.event is not None
        assert result.event.pattern_type == ManipulationPatternType.BURST_SUBMISSION


class TestDailyRateLimiting:
    """Tests for external topic rate limiting (FR118, AC2)."""

    @pytest.mark.asyncio
    async def test_non_external_source_not_rate_limited(
        self,
        service: TopicManipulationDefenseService,
    ) -> None:
        """Test internal sources are not rate limited."""
        # Default sources are internal
        result = await service.submit_external_topic("topic-1", "internal-source")

        assert result.accepted
        assert result.daily_limit == DAILY_TOPIC_LIMIT

    @pytest.mark.asyncio
    async def test_external_source_accepts_within_limit(
        self,
        service: TopicManipulationDefenseService,
        limiter: TopicDailyLimiterStub,
    ) -> None:
        """Test external source accepts topics within daily limit."""
        # Mark source as external
        limiter.add_external_source("external-source")

        result = await service.submit_external_topic("topic-1", "external-source")

        assert result.accepted
        assert result.topics_today == 1
        assert result.daily_limit == DAILY_TOPIC_LIMIT

    @pytest.mark.asyncio
    async def test_external_source_rejects_over_limit(
        self,
        service: TopicManipulationDefenseService,
        limiter: TopicDailyLimiterStub,
    ) -> None:
        """Test external source rejects topics over daily limit (FR118)."""
        # Mark source as external
        limiter.add_external_source("external-source")

        # Submit up to the limit
        for i in range(DAILY_TOPIC_LIMIT):
            result = await service.submit_external_topic(f"topic-{i}", "external-source")
            assert result.accepted

        # 11th topic should be rejected
        with pytest.raises(DailyRateLimitExceededError) as exc_info:
            await service.submit_external_topic("topic-11", "external-source")

        assert exc_info.value.source_id == "external-source"
        assert exc_info.value.topics_today == DAILY_TOPIC_LIMIT + 1
        assert exc_info.value.daily_limit == DAILY_TOPIC_LIMIT

    @pytest.mark.asyncio
    async def test_rate_limit_per_source(
        self,
        service: TopicManipulationDefenseService,
        limiter: TopicDailyLimiterStub,
    ) -> None:
        """Test rate limit applies per source independently."""
        # Mark both sources as external
        limiter.add_external_source("source-a")
        limiter.add_external_source("source-b")

        # Submit topics from source A
        for i in range(5):
            result = await service.submit_external_topic(f"a-topic-{i}", "source-a")
            assert result.accepted

        # Source B should still have full quota
        for i in range(5):
            result = await service.submit_external_topic(f"b-topic-{i}", "source-b")
            assert result.accepted
            assert result.topics_today == i + 1


class TestTopicPriority:
    """Tests for topic priority (FR119, AC3)."""

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(
        self,
        service: TopicManipulationDefenseService,
    ) -> None:
        """Test returns None when queue is empty."""
        topic = await service.get_next_topic_with_priority()
        assert topic is None

    @pytest.mark.asyncio
    async def test_autonomous_before_petition(
        self,
        service: TopicManipulationDefenseService,
        priority: TopicPriorityStub,
    ) -> None:
        """Test autonomous topics before petition topics (FR119)."""
        # Add topics with different priorities
        priority.add_to_queue("petition-topic", TopicPriorityLevel.PETITION)
        priority.add_to_queue("autonomous-topic", TopicPriorityLevel.AUTONOMOUS)

        topic = await service.get_next_topic_with_priority()
        assert topic == "autonomous-topic"

    @pytest.mark.asyncio
    async def test_constitutional_before_autonomous(
        self,
        service: TopicManipulationDefenseService,
        priority: TopicPriorityStub,
    ) -> None:
        """Test constitutional examination before autonomous topics."""
        priority.add_to_queue("autonomous-topic", TopicPriorityLevel.AUTONOMOUS)
        priority.add_to_queue("constitutional-topic", TopicPriorityLevel.CONSTITUTIONAL_EXAMINATION)

        topic = await service.get_next_topic_with_priority()
        assert topic == "constitutional-topic"

    @pytest.mark.asyncio
    async def test_multiple_autonomous_before_any_petition(
        self,
        service: TopicManipulationDefenseService,
        priority: TopicPriorityStub,
    ) -> None:
        """Test all autonomous topics processed before any petition topics."""
        priority.add_to_queue("petition-1", TopicPriorityLevel.PETITION)
        priority.add_to_queue("autonomous-1", TopicPriorityLevel.AUTONOMOUS)
        priority.add_to_queue("petition-2", TopicPriorityLevel.PETITION)
        priority.add_to_queue("autonomous-2", TopicPriorityLevel.AUTONOMOUS)

        # First two should be autonomous
        topic1 = await service.get_next_topic_with_priority()
        topic2 = await service.get_next_topic_with_priority()

        # Both should be autonomous (order depends on queue time)
        assert topic1 in ["autonomous-1", "autonomous-2"]
        assert topic2 in ["autonomous-1", "autonomous-2"]

        # Next should be petition
        topic3 = await service.get_next_topic_with_priority()
        assert topic3 in ["petition-1", "petition-2"]


class TestCoordinationDetection:
    """Tests for coordination detection (AC5)."""

    @pytest.mark.asyncio
    async def test_no_coordination_below_threshold(
        self,
        service: TopicManipulationDefenseService,
        detector: TopicManipulationDetectorStub,
    ) -> None:
        """Test no coordination flagged below threshold."""
        detector.set_coordination_score(("sub-1", "sub-2"), 0.5)

        result = await service.check_coordination(("sub-1", "sub-2"))

        assert not result.coordination_suspected
        assert result.coordination_score == 0.5
        assert result.event is None

    @pytest.mark.asyncio
    async def test_coordination_detected_above_threshold(
        self,
        service: TopicManipulationDefenseService,
        detector: TopicManipulationDetectorStub,
    ) -> None:
        """Test coordination flagged above threshold."""
        detector.set_coordination_score(("sub-1", "sub-2", "sub-3"), 0.82)

        result = await service.check_coordination(("sub-1", "sub-2", "sub-3"))

        assert result.coordination_suspected
        assert result.coordination_score == 0.82
        assert result.event is not None
        assert result.event.submission_ids == ("sub-1", "sub-2", "sub-3")

    @pytest.mark.asyncio
    async def test_coordination_flags_submissions(
        self,
        service: TopicManipulationDefenseService,
        detector: TopicManipulationDetectorStub,
    ) -> None:
        """Test coordination detection flags submissions for review."""
        detector.set_coordination_score(("sub-a", "sub-b"), 0.95)

        await service.check_coordination(("sub-a", "sub-b"))

        flagged = await detector.get_flagged_topics()
        assert len(flagged) == 2
        flagged_ids = [t.topic_id for t in flagged]
        assert "sub-a" in flagged_ids
        assert "sub-b" in flagged_ids


class TestServiceDependencyValidation:
    """Tests for service initialization validation."""

    def test_requires_halt_checker(
        self,
        detector: TopicManipulationDetectorStub,
        limiter: TopicDailyLimiterStub,
        priority: TopicPriorityStub,
    ) -> None:
        """Test service requires halt_checker dependency."""
        with pytest.raises(TypeError) as exc_info:
            TopicManipulationDefenseService(
                halt_checker=None,  # type: ignore
                detector=detector,
                limiter=limiter,
                priority=priority,
            )
        assert "halt_checker is required" in str(exc_info.value)

    def test_requires_detector(
        self,
        halt_checker: HaltCheckerStub,
        limiter: TopicDailyLimiterStub,
        priority: TopicPriorityStub,
    ) -> None:
        """Test service requires detector dependency."""
        with pytest.raises(TypeError) as exc_info:
            TopicManipulationDefenseService(
                halt_checker=halt_checker,
                detector=None,  # type: ignore
                limiter=limiter,
                priority=priority,
            )
        assert "detector is required" in str(exc_info.value)

    def test_requires_limiter(
        self,
        halt_checker: HaltCheckerStub,
        detector: TopicManipulationDetectorStub,
        priority: TopicPriorityStub,
    ) -> None:
        """Test service requires limiter dependency."""
        with pytest.raises(TypeError) as exc_info:
            TopicManipulationDefenseService(
                halt_checker=halt_checker,
                detector=detector,
                limiter=None,  # type: ignore
                priority=priority,
            )
        assert "limiter is required" in str(exc_info.value)

    def test_requires_priority(
        self,
        halt_checker: HaltCheckerStub,
        detector: TopicManipulationDetectorStub,
        limiter: TopicDailyLimiterStub,
    ) -> None:
        """Test service requires priority dependency."""
        with pytest.raises(TypeError) as exc_info:
            TopicManipulationDefenseService(
                halt_checker=halt_checker,
                detector=detector,
                limiter=limiter,
                priority=None,  # type: ignore
            )
        assert "priority is required" in str(exc_info.value)


class TestEndToEndScenarios:
    """End-to-end integration scenarios."""

    @pytest.mark.asyncio
    async def test_external_attack_scenario(
        self,
        service: TopicManipulationDefenseService,
        detector: TopicManipulationDetectorStub,
        limiter: TopicDailyLimiterStub,
        priority: TopicPriorityStub,
    ) -> None:
        """Test defense against coordinated external attack.

        Scenario: Attacker submits coordinated topics from multiple sources
        trying to flood the queue and suppress autonomous topics.

        Expected defense:
        1. Rate limiting stops excess topics (FR118)
        2. Coordination detection flags suspicious pattern (AC5)
        3. Autonomous topics still processed first (FR119)
        """
        # Setup: attacker has 3 external sources
        limiter.add_external_source("attacker-1")
        limiter.add_external_source("attacker-2")
        limiter.add_external_source("attacker-3")

        # Configure coordination detection
        detector.set_coordination_score(
            ("attacker-topic-1", "attacker-topic-2", "attacker-topic-3"),
            0.92,
        )

        # Step 1: Attacker submits topics from each source
        submitted_topics = []
        for source_id in ["attacker-1", "attacker-2", "attacker-3"]:
            for i in range(DAILY_TOPIC_LIMIT):
                topic_id = f"{source_id}-topic-{i}"
                result = await service.submit_external_topic(topic_id, source_id)
                if result.accepted:
                    submitted_topics.append(topic_id)
                    priority.add_to_queue(topic_id, TopicPriorityLevel.PETITION)

        # Each source hit rate limit
        assert len(submitted_topics) == 3 * DAILY_TOPIC_LIMIT

        # Step 2: Coordination detection catches the attack
        result = await service.check_for_manipulation(
            ("attacker-topic-1", "attacker-topic-2", "attacker-topic-3")
        )
        assert result.manipulation_suspected

        # Step 3: Legitimate autonomous topic still gets priority
        priority.add_to_queue("legitimate-autonomous", TopicPriorityLevel.AUTONOMOUS)

        next_topic = await service.get_next_topic_with_priority()
        assert next_topic == "legitimate-autonomous"

    @pytest.mark.asyncio
    async def test_normal_operation_flow(
        self,
        service: TopicManipulationDefenseService,
        limiter: TopicDailyLimiterStub,
        priority: TopicPriorityStub,
    ) -> None:
        """Test normal operation with legitimate topics.

        Scenario: Mix of internal autonomous and external petition topics.

        Expected behavior:
        1. Internal topics not rate limited
        2. External topics rate limited but accepted within quota
        3. Autonomous topics processed before petitions
        """
        # Internal autonomous topics
        priority.add_to_queue("autonomous-1", TopicPriorityLevel.AUTONOMOUS)
        priority.add_to_queue("autonomous-2", TopicPriorityLevel.AUTONOMOUS)

        # External petition topics
        limiter.add_external_source("community-member")
        for i in range(3):
            result = await service.submit_external_topic(f"petition-{i}", "community-member")
            assert result.accepted
            priority.add_to_queue(f"petition-{i}", TopicPriorityLevel.PETITION)

        # Process in priority order
        topics_processed = []
        while True:
            topic = await service.get_next_topic_with_priority()
            if topic is None:
                break
            topics_processed.append(topic)

        # Verify order: autonomous first, then petitions
        assert topics_processed[0] in ["autonomous-1", "autonomous-2"]
        assert topics_processed[1] in ["autonomous-1", "autonomous-2"]
        assert all(t.startswith("petition") for t in topics_processed[2:])
