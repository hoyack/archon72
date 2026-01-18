"""Topic manipulation defense service (Story 6.9, FR118-FR119).

This service orchestrates topic manipulation defense operations
including pattern detection, rate limiting, and priority enforcement.

Constitutional Constraints:
- FR118: External topics rate limited to 10/day per source
- FR119: Autonomous topics have priority over external submissions
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All actions logged

Architecture Pattern:
    TopicManipulationDefenseService orchestrates FR118/FR119 compliance:

    check_for_manipulation(topic_ids):
      ├─ halt_checker.is_halted()          # HALT FIRST rule
      ├─ detector.analyze_submissions()     # Pattern detection
      └─ If manipulation suspected:
           └─ Create TopicManipulationSuspectedEvent

    submit_external_topic(topic_id, source_id):
      ├─ halt_checker.is_halted()          # HALT FIRST rule
      ├─ limiter.check_daily_limit()       # FR118 check
      └─ If limit exceeded:
           ├─ Create TopicRateLimitDailyEvent
           └─ Raise DailyRateLimitExceededError

    get_next_topic_with_priority():
      ├─ halt_checker.is_halted()          # HALT FIRST rule
      └─ priority.get_next_topic()         # FR119 - autonomous first
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import structlog

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.topic_daily_limiter import (
    DAILY_TOPIC_LIMIT,
    TopicDailyLimiterProtocol,
)
from src.application.ports.topic_manipulation_detector import (
    ManipulationAnalysisResult,
    TopicManipulationDetectorProtocol,
)
from src.application.ports.topic_priority import (
    TopicPriorityProtocol,
)
from src.domain.errors.topic_manipulation import DailyRateLimitExceededError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.topic_manipulation import (
    CoordinatedSubmissionSuspectedEventPayload,
    ManipulationPatternType,
    TopicManipulationSuspectedEventPayload,
    TopicRateLimitDailyEventPayload,
)

logger = structlog.get_logger()

# Coordination score threshold per story requirements
COORDINATION_THRESHOLD = 0.7


@dataclass
class ManipulationCheckResult:
    """Result of checking for topic manipulation.

    Attributes:
        manipulation_suspected: Whether manipulation was detected.
        analysis_result: Detailed analysis result.
        event: Event created if manipulation suspected.
    """

    manipulation_suspected: bool
    analysis_result: ManipulationAnalysisResult
    event: TopicManipulationSuspectedEventPayload | None = None


@dataclass
class ExternalTopicResult:
    """Result of submitting an external topic.

    Attributes:
        accepted: Whether the topic was accepted.
        topics_today: Total topics submitted today by source.
        daily_limit: Maximum allowed per day.
    """

    accepted: bool
    topics_today: int
    daily_limit: int


@dataclass
class CoordinationCheckResult:
    """Result of checking for submission coordination.

    Attributes:
        coordination_suspected: Whether coordination was detected.
        coordination_score: Calculated score (0.0 to 1.0).
        event: Event created if coordination suspected.
    """

    coordination_suspected: bool
    coordination_score: float
    event: CoordinatedSubmissionSuspectedEventPayload | None = None


class TopicManipulationDefenseService:
    """Application service for topic manipulation defense (FR118-FR119).

    This service provides the primary interface for:
    - Detecting manipulation patterns (AC1, AC5)
    - Enforcing daily rate limits (FR118, AC2)
    - Ensuring autonomous topic priority (FR119, AC3)
    - Creating audit trail (AC6)

    HALT FIRST Rule:
        Every operation checks halt state before proceeding.
        Never retry after SystemHaltedError.

    Attributes:
        _halt_checker: Interface for checking halt state.
        _detector: Interface for manipulation detection.
        _limiter: Interface for daily rate limiting.
        _priority: Interface for topic priority.
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        detector: TopicManipulationDetectorProtocol,
        limiter: TopicDailyLimiterProtocol,
        priority: TopicPriorityProtocol,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            halt_checker: Interface for checking halt state.
            detector: Interface for manipulation detection.
            limiter: Interface for daily rate limiting.
            priority: Interface for topic priority.

        Raises:
            TypeError: If any required dependency is None.
        """
        if halt_checker is None:
            raise TypeError("halt_checker is required")
        if detector is None:
            raise TypeError("detector is required")
        if limiter is None:
            raise TypeError("limiter is required")
        if priority is None:
            raise TypeError("priority is required")

        self._halt_checker = halt_checker
        self._detector = detector
        self._limiter = limiter
        self._priority = priority

    async def check_for_manipulation(
        self,
        topic_ids: tuple[str, ...],
        window_hours: int = 24,
    ) -> ManipulationCheckResult:
        """Check topics for manipulation patterns (AC1, AC5).

        This is the primary method for detecting coordinated manipulation.
        Topics are flagged for review if manipulation is suspected.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Analyze submissions for patterns
            3. If manipulation suspected: create event, flag topics
            4. Return result (detection is advisory, not enforcement)

        Args:
            topic_ids: Topic IDs to analyze.
            window_hours: Analysis window in hours.

        Returns:
            ManipulationCheckResult with detection findings.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "manipulation_check_blocked_halted",
                topic_count=len(topic_ids),
            )
            raise SystemHaltedError("System halted - cannot check for manipulation")

        # Analyze submissions
        analysis = await self._detector.analyze_submissions(
            topic_ids,
            window_hours=window_hours,
        )

        if not analysis.manipulation_suspected:
            logger.debug(
                "no_manipulation_detected",
                topic_count=len(topic_ids),
                window_hours=window_hours,
            )
            return ManipulationCheckResult(
                manipulation_suspected=False,
                analysis_result=analysis,
            )

        # Manipulation suspected - create event and flag topics
        detection_id = str(uuid4())
        event = TopicManipulationSuspectedEventPayload(
            detection_id=detection_id,
            suspected_topics=analysis.topic_ids_affected,
            pattern_type=analysis.pattern_type or ManipulationPatternType.UNKNOWN,
            confidence_score=analysis.confidence_score,
            evidence_summary=analysis.evidence_summary,
            detected_at=datetime.now(timezone.utc),
            detection_window_hours=window_hours,
        )

        # Flag topics for review
        for topic_id in analysis.topic_ids_affected:
            await self._detector.flag_for_review(
                topic_id,
                reason=f"Manipulation pattern detected: {analysis.pattern_type}",
            )

        logger.warning(
            "manipulation_pattern_detected",
            detection_id=detection_id,
            pattern_type=analysis.pattern_type,
            confidence_score=analysis.confidence_score,
            topic_count=len(analysis.topic_ids_affected),
        )

        return ManipulationCheckResult(
            manipulation_suspected=True,
            analysis_result=analysis,
            event=event,
        )

    async def submit_external_topic(
        self,
        topic_id: str,
        source_id: str,
    ) -> ExternalTopicResult:
        """Submit an external topic with rate limit check (FR118, AC2).

        External (non-autonomous) topics are subject to daily rate limits.
        Excess topics are rejected (not queued).

        FR118: External topic sources (non-autonomous) SHALL be rate-limited
               to 10 topics/day per source.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Check if source is external
            3. Check daily rate limit (FR118)
            4. If exceeded: create event, raise error
            5. Record submission and return success

        Args:
            topic_id: Topic being submitted.
            source_id: Source making submission.

        Returns:
            ExternalTopicResult with submission status.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
            DailyRateLimitExceededError: If daily limit exceeded (FR118).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "topic_submission_blocked_halted",
                topic_id=topic_id,
                source_id=source_id,
            )
            raise SystemHaltedError("System halted - cannot submit topic")

        # Check if this is an external source
        is_external = await self._limiter.is_external_source(source_id)
        if not is_external:
            # Non-external sources (autonomous, scheduled) are not rate limited
            logger.debug(
                "non_external_source_submission",
                topic_id=topic_id,
                source_id=source_id,
            )
            return ExternalTopicResult(
                accepted=True,
                topics_today=0,
                daily_limit=DAILY_TOPIC_LIMIT,
            )

        # Check daily rate limit (FR118)
        within_limit = await self._limiter.check_daily_limit(source_id)
        topics_today = await self._limiter.get_daily_count(source_id)

        if not within_limit:
            # Create rate limit event
            reset_time = await self._limiter.get_limit_reset_time(source_id)
            TopicRateLimitDailyEventPayload(
                source_id=source_id,
                topics_today=topics_today + 1,
                daily_limit=DAILY_TOPIC_LIMIT,
                rejected_topic_ids=(topic_id,),
                limit_start=datetime.now(timezone.utc),
                limit_reset_at=reset_time,
            )

            logger.warning(
                "daily_rate_limit_exceeded",
                source_id=source_id,
                topics_today=topics_today,
                daily_limit=DAILY_TOPIC_LIMIT,
                rejected_topic_id=topic_id,
            )

            raise DailyRateLimitExceededError(
                source_id=source_id,
                topics_today=topics_today + 1,
                daily_limit=DAILY_TOPIC_LIMIT,
            )

        # Record submission
        new_count = await self._limiter.record_daily_submission(source_id)

        logger.info(
            "external_topic_submitted",
            topic_id=topic_id,
            source_id=source_id,
            topics_today=new_count,
            daily_limit=DAILY_TOPIC_LIMIT,
        )

        return ExternalTopicResult(
            accepted=True,
            topics_today=new_count,
            daily_limit=DAILY_TOPIC_LIMIT,
        )

    async def get_next_topic_with_priority(self) -> str | None:
        """Get highest priority topic for deliberation (FR119, AC3).

        FR119: Autonomous constitutional self-examination topics
        SHALL have priority over external submissions.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Ensure autonomous priority is enforced
            3. Return highest priority topic

        Returns:
            Topic ID of highest priority topic, or None if queue empty.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning("priority_check_blocked_halted")
            raise SystemHaltedError("System halted - cannot get next topic")

        # Ensure autonomous priority (FR119)
        await self._priority.ensure_autonomous_priority()

        # Get highest priority topic
        topic_id = await self._priority.get_next_topic_for_deliberation()

        if topic_id:
            priority = await self._priority.get_topic_priority(topic_id)
            logger.info(
                "topic_selected_for_deliberation",
                topic_id=topic_id,
                priority=priority.value,
            )
        else:
            logger.debug("no_topics_in_queue")

        return topic_id

    async def check_coordination(
        self,
        submission_ids: tuple[str, ...],
    ) -> CoordinationCheckResult:
        """Check submissions for coordination patterns (AC5).

        Calculates coordination score and flags submissions if
        score exceeds threshold (0.7).

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Calculate coordination score
            3. If score > 0.7: create event, flag submissions
            4. Return result

        Args:
            submission_ids: Submission IDs to analyze.

        Returns:
            CoordinationCheckResult with coordination findings.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "coordination_check_blocked_halted",
                submission_count=len(submission_ids),
            )
            raise SystemHaltedError("System halted - cannot check coordination")

        # Calculate coordination score
        score = await self._detector.calculate_coordination_score(submission_ids)

        if score <= COORDINATION_THRESHOLD:
            logger.debug(
                "no_coordination_detected",
                submission_count=len(submission_ids),
                coordination_score=score,
                threshold=COORDINATION_THRESHOLD,
            )
            return CoordinationCheckResult(
                coordination_suspected=False,
                coordination_score=score,
            )

        # Coordination suspected - create event and flag
        detection_id = str(uuid4())
        event = CoordinatedSubmissionSuspectedEventPayload(
            detection_id=detection_id,
            submission_ids=submission_ids,
            coordination_score=score,
            coordination_signals=("score_above_threshold",),
            source_ids=(),  # Would be populated by detector
            detected_at=datetime.now(timezone.utc),
        )

        # Flag submissions for review
        for submission_id in submission_ids:
            await self._detector.flag_for_review(
                submission_id,
                reason=f"Coordination score {score:.2f} exceeds threshold {COORDINATION_THRESHOLD}",
            )

        logger.warning(
            "coordination_pattern_detected",
            detection_id=detection_id,
            coordination_score=score,
            threshold=COORDINATION_THRESHOLD,
            submission_count=len(submission_ids),
        )

        return CoordinationCheckResult(
            coordination_suspected=True,
            coordination_score=score,
            event=event,
        )
